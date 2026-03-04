"""
Manus provider — fetches credits via the Manus Connect RPC API.

Endpoint (Connect RPC, POST, content-type: application/json):

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

Credit logic:
  - Manus depletes monthly credits first, then add-on credits.
  - monthly_remaining = max(0, total - addon - free)
    → 0 when add-ons are being drawn (monthly fully consumed)
  - daily_remaining = maxRefreshCredits if nextRefreshTime is in the past
    (refresh already happened today but not yet used), else 0
    NOTE: daily refresh credits are separate from totalCredits and not
    directly returned by the API; we infer depletion from nextRefreshTime.

Authentication: Bearer JWT token (set MANUS_API_KEY in env).
No additional env vars required.
"""

import logging
from datetime import datetime, timezone

import httpx

from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MANUS_API_BASE       = "https://api.manus.im"
AVAILABLE_CREDITS_EP = f"{MANUS_API_BASE}/user.v1.UserService/GetAvailableCredits"


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

        # ── GetAvailableCredits ───────────────────────────────────────────────
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
                data = resp.json()
                logger.info("[Manus] GetAvailableCredits: %s", data)
                return self._build_snapshot(data)
        except httpx.TimeoutException:
            logger.warning("[Manus] GetAvailableCredits timed out")
        except Exception as e:
            logger.warning("[Manus] GetAvailableCredits error: %s", e)

        return self._error_snapshot(
            "Could not fetch Manus credits. Check that your JWT token is valid."
        )

    def _build_snapshot(self, data: dict) -> BalanceSnapshot:
        """
        Build a BalanceSnapshot with three credit buckets in raw_data:

          manus_monthly_total     - monthly plan allotment (proMonthlyCredits)
          manus_monthly_remaining - monthly credits left (0 when add-ons active)
          manus_daily_total       - daily refresh allotment (maxRefreshCredits)
          manus_daily_remaining   - daily credits left (0 if refresh not yet happened)
          manus_addon_balance     - purchased add-on credits (addonCredits)
          manus_free_credits      - free/bonus credits (freeCredits)
          manus_total_balance     - total credits remaining (totalCredits)
          manus_next_refresh      - ISO timestamp of next daily refresh
        """
        total_balance  = data.get("totalCredits")
        free_credits   = int(data.get("freeCredits",       0))
        addon_credits  = int(data.get("addonCredits",      0))
        monthly_total  = int(data.get("proMonthlyCredits", 40_000))
        daily_total    = int(data.get("maxRefreshCredits", 300))
        next_refresh   = data.get("nextRefreshTime")  # e.g. "2026-03-05T00:00:00Z"

        if total_balance is None:
            return self._error_snapshot(
                "GetAvailableCredits response missing 'totalCredits' field."
            )

        total_balance = int(total_balance)

        # ── Monthly remaining ─────────────────────────────────────────────────
        # Manus consumes monthly credits first; add-ons only activate after
        # monthly is exhausted. So monthly_remaining = total minus add-on and free.
        monthly_remaining = max(0, total_balance - addon_credits - free_credits)
        # Cap at the monthly allotment (can't exceed what the plan provides)
        monthly_remaining = min(monthly_remaining, monthly_total)

        # ── Daily refresh remaining ───────────────────────────────────────────
        # The daily refresh pool is NOT included in totalCredits.
        # nextRefreshTime is the next time the pool refills.
        # If nextRefreshTime is in the future → the pool was refilled today
        #   and may have been used. We can't know how much remains without
        #   WebdevUsageInfo (which is unreliable), so we show 0 as a safe default
        #   indicating the daily has been consumed.
        # If nextRefreshTime is in the past → something is wrong; show 0.
        daily_remaining = 0  # conservative: assume depleted

        if next_refresh:
            try:
                refresh_dt = datetime.fromisoformat(
                    next_refresh.replace("Z", "+00:00")
                )
                now = datetime.now(timezone.utc)
                # If next refresh is more than 20 hours away, the daily pool
                # was just refilled and hasn't been touched yet → show full.
                hours_until_refresh = (refresh_dt - now).total_seconds() / 3600
                if hours_until_refresh > 20:
                    daily_remaining = daily_total
                # Otherwise: refresh is coming soon → daily was used today → 0
            except (ValueError, TypeError):
                pass

        raw: dict = {
            "manus_monthly_total":     monthly_total,
            "manus_monthly_remaining": monthly_remaining,
            "manus_daily_total":       daily_total,
            "manus_daily_remaining":   daily_remaining,
            "manus_addon_balance":     addon_credits,
            "manus_free_credits":      free_credits,
            "manus_total_balance":     total_balance,
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
