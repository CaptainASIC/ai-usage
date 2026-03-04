"""
Manus provider — fetches credits via the Manus Connect RPC API.

Endpoints (Connect RPC, POST, content-type: application/json):

  POST https://api.manus.im/user.v1.UserService/WebdevUsageInfo
    body: {}
    → {
        cloudRefreshUsage: float,       # daily refresh units consumed (e.g. 0.38 of 10)
        cloudRefreshUsageBudget: int,   # daily refresh budget in cloud units (10 = 300 credits)
        aiRefreshUsageBudget: int,
        integrationsRefreshUsageBudget: int,
        bindCard: bool,
      }

  POST https://api.manus.im/user.v1.UserService/ListUserCreditsLog
    body: {"page": 1, "pageSize": 100}
    → {
        logs: [{sessionId, title, createAt, credits (int), type}, ...],
        total: int   ← number of log entries, NOT a credit balance
      }
      credits: negative = spent, positive = refund/earned

Authentication: Bearer JWT token (set MANUS_API_KEY in env).

Optional env vars:
  MANUS_TOTAL_CREDITS   - current total credit balance (from manus.im/billing)
                          e.g. 142363  (free + monthly + add-on combined)
  MANUS_ADDON_CREDITS   - add-on credit bucket balance (from manus.im/billing)
                          e.g. 141231
  MANUS_MONTHLY_CREDITS - monthly plan allotment (default 40000 for Pro plan)
  MANUS_DAILY_CREDITS   - daily refresh allotment (default 300 for Pro plan)

The Manus API does not expose the monthly used/remaining or add-on balance
directly — these must be configured via env vars from the billing page.
The daily refresh ratio IS available from WebdevUsageInfo.
"""

import logging
import os
import httpx

from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MANUS_API_BASE       = "https://api.manus.im"
USAGE_INFO_ENDPOINT  = f"{MANUS_API_BASE}/user.v1.UserService/WebdevUsageInfo"
CREDITS_LOG_ENDPOINT = f"{MANUS_API_BASE}/user.v1.UserService/ListUserCreditsLog"

# Pro plan defaults
DEFAULT_MONTHLY_CREDITS = 40_000
DEFAULT_DAILY_CREDITS   = 300
# Cloud refresh units per day on Pro plan (10 units = 300 credits)
CLOUD_UNITS_PER_DAY     = 10


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

        usage_data: dict | None = None
        log_data:   dict | None = None

        # ── 1. WebdevUsageInfo ──────────────────────────────────────────────
        try:
            resp = await client.post(
                USAGE_INFO_ENDPOINT,
                headers=headers,
                content="{}",
                timeout=15.0,
            )
            logger.debug("[Manus] WebdevUsageInfo → %d", resp.status_code)
            if resp.status_code == 401:
                return self._error_snapshot(
                    "Manus JWT token is invalid or expired. "
                    "Refresh it from manus.im DevTools → Network → Authorization header."
                )
            if resp.status_code == 200:
                usage_data = resp.json()
                logger.info("[Manus] WebdevUsageInfo data: %s", usage_data)
        except httpx.TimeoutException:
            logger.warning("[Manus] WebdevUsageInfo timed out")
        except Exception as e:
            logger.warning("[Manus] WebdevUsageInfo error: %s", e)

        # ── 2. ListUserCreditsLog ───────────────────────────────────────────
        try:
            resp = await client.post(
                CREDITS_LOG_ENDPOINT,
                headers=headers,
                content='{"page":1,"pageSize":100}',
                timeout=15.0,
            )
            logger.debug("[Manus] ListUserCreditsLog → %d", resp.status_code)
            if resp.status_code == 401:
                return self._error_snapshot(
                    "Manus JWT token is invalid or expired. "
                    "Refresh it from manus.im DevTools → Network → Authorization header."
                )
            if resp.status_code == 200:
                log_data = resp.json()
        except httpx.TimeoutException:
            logger.warning("[Manus] ListUserCreditsLog timed out")
        except Exception as e:
            logger.warning("[Manus] ListUserCreditsLog error: %s", e)

        return self._build_snapshot(usage_data, log_data)

    def _get_env_int(self, key: str, default: int | None = None) -> int | None:
        val = os.environ.get(key, "").strip()
        if val:
            try:
                return int(val)
            except ValueError:
                logger.warning("[Manus] %s is not a valid integer: %s", key, val)
        return default

    def _build_snapshot(
        self,
        usage_data: dict | None,
        log_data:   dict | None,
    ) -> BalanceSnapshot:
        """
        Build a BalanceSnapshot with three credit buckets exposed in raw_data:

          manus_monthly_used      - credits spent this month (from log sum)
          manus_monthly_total     - monthly allotment (MANUS_MONTHLY_CREDITS or 40000)
          manus_daily_used        - daily refresh credits used (from cloudRefreshUsage ratio)
          manus_daily_total       - daily refresh allotment (MANUS_DAILY_CREDITS or 300)
          manus_addon_balance     - add-on credit balance (MANUS_ADDON_CREDITS env var)
          manus_total_balance     - total balance (MANUS_TOTAL_CREDITS env var)

        The primary remaining_credits / total_credits fields show the total balance
        for the progress bar on the card header.
        """
        # ── Read env-var overrides ──────────────────────────────────────────
        total_balance  = self._get_env_int("MANUS_TOTAL_CREDITS")
        addon_balance  = self._get_env_int("MANUS_ADDON_CREDITS")
        monthly_total  = self._get_env_int("MANUS_MONTHLY_CREDITS", DEFAULT_MONTHLY_CREDITS)
        daily_total    = self._get_env_int("MANUS_DAILY_CREDITS",   DEFAULT_DAILY_CREDITS)

        # ── Parse log entries for monthly spend ─────────────────────────────
        monthly_spent: int = 0
        log_entry_count: int = 0

        if log_data and isinstance(log_data.get("logs"), list):
            logs = log_data["logs"]
            log_entry_count = log_data.get("total", len(logs))
            for entry in logs:
                c = entry.get("credits")
                if isinstance(c, (int, float)) and c < 0:
                    monthly_spent += abs(int(c))

        # ── Parse daily refresh from WebdevUsageInfo ────────────────────────
        daily_used: float | None = None
        if usage_data:
            cloud_used   = usage_data.get("cloudRefreshUsage")   # e.g. 0.38
            cloud_budget = usage_data.get("cloudRefreshUsageBudget")  # e.g. 10
            if cloud_used is not None and cloud_budget and cloud_budget > 0:
                # Convert cloud units to credits:
                # budget units map to daily_total credits proportionally
                daily_used = round((cloud_used / cloud_budget) * (daily_total or DEFAULT_DAILY_CREDITS), 1)

        # ── Derive remaining ────────────────────────────────────────────────
        # Primary display: total balance from env var (authoritative)
        remaining = float(total_balance) if total_balance is not None else None
        total     = float(total_balance) if total_balance is not None else None

        if remaining is None and daily_used is None and monthly_spent == 0:
            return self._error_snapshot(
                "Could not parse Manus credits. "
                "Set MANUS_TOTAL_CREDITS in backend env to your balance from manus.im/billing."
            )

        raw: dict = {
            # Monthly quota bucket
            "manus_monthly_used":   monthly_spent,
            "manus_monthly_total":  monthly_total,
            # Daily refresh bucket
            "manus_daily_used":     daily_used,
            "manus_daily_total":    daily_total,
            # Add-on bucket
            "manus_addon_balance":  addon_balance,
            # Total balance
            "manus_total_balance":  total_balance,
            # Metadata
            "log_entry_count":      log_entry_count,
        }

        return self._make_snapshot(
            balance_usd=None,
            remaining_credits=remaining,
            used_credits=float(monthly_spent) if monthly_spent else None,
            total_credits=total,
            currency="credits",
            status="ok",
            raw_data=raw,
        )
