"""
Manus provider — fetches credits via the Manus Connect RPC API.

Endpoints (Connect RPC, POST, content-type: application/json):

  POST https://api.manus.im/user.v1.UserService/GetAvailableCredits
    body: {}
    → {
        totalCredits: int,        # total balance (free + monthly + add-on)
        freeCredits: int,         # free/bonus credits
        addonCredits: int,        # purchased add-on credits
        proMonthlyCredits: int,   # monthly plan allotment (e.g. 40000)
        maxRefreshCredits: int,   # daily refresh allotment (e.g. 300)
        nextRefreshTime: str,     # ISO timestamp of next daily refresh
        refreshInterval: str,     # "daily"
      }

  POST https://api.manus.im/user.v1.UserService/WebdevUsageInfo
    body: {}
    → {
        cloudRefreshUsage: float,       # daily refresh units consumed (e.g. 0.38 of 10)
        cloudRefreshUsageBudget: int,   # daily refresh budget in cloud units (10 = 300 credits)
      }

Authentication: Bearer JWT token (set MANUS_API_KEY in env).

No env vars required — all credit data is fetched live from the API.
"""

import logging
import httpx

from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MANUS_API_BASE          = "https://api.manus.im"
AVAILABLE_CREDITS_EP    = f"{MANUS_API_BASE}/user.v1.UserService/GetAvailableCredits"
USAGE_INFO_ENDPOINT     = f"{MANUS_API_BASE}/user.v1.UserService/WebdevUsageInfo"


class ManusProvider(BaseProvider):
    """Manus credits provider using Connect RPC API."""

    provider_id   = "manus"
    provider_name = "Manus"
    auth_type     = "bearer_token"

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key or self.credentials.session_cookie)

    def _get_token(self) -> str:
        return self.credentials.api_key or self.credentials.session_cookie or ""

    def _build_headers(self) -> dict:
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "authorization": f"Bearer {self._get_token()}",
            "connect-protocol-version": "1",
            "content-type": "application/json",
            "x-client-type": "web",
            "x-client-locale": "en",
            "origin": "https://manus.im",
            "referer": "https://manus.im/",
        }

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client  = await self.get_client()
        headers = self._build_headers()

        credits_data: dict | None = None
        usage_data:   dict | None = None

        # ── 1. GetAvailableCredits (primary — live balance breakdown) ─────────
        try:
            resp = await client.post(
                AVAILABLE_CREDITS_EP,
                headers=headers,
                content="{}",
                timeout=15.0,
            )
            logger.debug("[Manus] GetAvailableCredits → %d", resp.status_code)
            if resp.status_code == 401:
                return self._error_snapshot(
                    "Manus JWT token is invalid or expired. "
                    "Refresh it from manus.im DevTools → Network → Authorization header."
                )
            if resp.status_code == 200:
                credits_data = resp.json()
                logger.info("[Manus] GetAvailableCredits: %s", credits_data)
        except httpx.TimeoutException:
            logger.warning("[Manus] GetAvailableCredits timed out")
        except Exception as e:
            logger.warning("[Manus] GetAvailableCredits error: %s", e)

        # ── 2. WebdevUsageInfo (daily refresh ratio) ──────────────────────────
        try:
            resp = await client.post(
                USAGE_INFO_ENDPOINT,
                headers=headers,
                content="{}",
                timeout=15.0,
            )
            logger.debug("[Manus] WebdevUsageInfo → %d", resp.status_code)
            if resp.status_code == 200:
                usage_data = resp.json()
                logger.info("[Manus] WebdevUsageInfo: %s", usage_data)
        except httpx.TimeoutException:
            logger.warning("[Manus] WebdevUsageInfo timed out")
        except Exception as e:
            logger.warning("[Manus] WebdevUsageInfo error: %s", e)

        return self._build_snapshot(credits_data, usage_data)

    def _build_snapshot(
        self,
        credits_data: dict | None,
        usage_data:   dict | None,
    ) -> BalanceSnapshot:
        """
        Build a BalanceSnapshot with three credit buckets in raw_data:

          manus_monthly_total     - monthly plan allotment (from API: proMonthlyCredits)
          manus_monthly_remaining - monthly credits still available
                                    = min(totalCredits, proMonthlyCredits)
          manus_daily_total       - daily refresh allotment (from API: maxRefreshCredits)
          manus_daily_used        - daily refresh credits used (from WebdevUsageInfo ratio)
          manus_addon_balance     - purchased add-on credits (from API: addonCredits)
          manus_free_credits      - free/bonus credits (from API: freeCredits)
          manus_total_balance     - total credits remaining (from API: totalCredits)
          manus_next_refresh      - ISO timestamp of next daily refresh
        """
        if not credits_data:
            return self._error_snapshot(
                "Could not fetch Manus credits from GetAvailableCredits. "
                "Check that your JWT token is valid."
            )

        total_balance   = credits_data.get("totalCredits")
        free_credits    = credits_data.get("freeCredits", 0)
        addon_credits   = credits_data.get("addonCredits", 0)
        monthly_total   = credits_data.get("proMonthlyCredits", 40_000)
        daily_total     = credits_data.get("maxRefreshCredits", 300)
        next_refresh    = credits_data.get("nextRefreshTime")

        if total_balance is None:
            return self._error_snapshot(
                "GetAvailableCredits response missing 'totalCredits' field."
            )

        # Monthly remaining: total credits up to the monthly allotment
        # (when total > monthly_total, monthly is fully available; excess = add-on)
        monthly_remaining = min(int(total_balance), int(monthly_total))

        # ── Daily refresh used (from WebdevUsageInfo ratio) ───────────────────
        daily_used: float | None = None
        if usage_data:
            cloud_used   = usage_data.get("cloudRefreshUsage")
            cloud_budget = usage_data.get("cloudRefreshUsageBudget")
            if cloud_used is not None and cloud_budget and cloud_budget > 0:
                daily_used = round((cloud_used / cloud_budget) * daily_total, 1)

        raw: dict = {
            # Monthly quota bucket
            "manus_monthly_total":     int(monthly_total),
            "manus_monthly_remaining": monthly_remaining,
            # Daily refresh bucket
            "manus_daily_total":       int(daily_total),
            "manus_daily_used":        daily_used,
            # Add-on and free buckets
            "manus_addon_balance":     int(addon_credits),
            "manus_free_credits":      int(free_credits),
            # Total
            "manus_total_balance":     int(total_balance),
            "manus_next_refresh":      next_refresh,
        }

        return self._make_snapshot(
            balance_usd=None,
            remaining_credits=float(total_balance),
            used_credits=None,
            total_credits=float(total_balance),
            currency="credits",
            status="ok",
            raw_data=raw,
        )
