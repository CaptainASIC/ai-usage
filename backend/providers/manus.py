"""
Manus provider - fetches credits via the Manus Connect RPC API.

Endpoints (Connect RPC, POST, content-type: application/json):

  POST https://api.manus.im/user.v1.UserService/WebdevUsageInfo
    body: {}
    → { cloudRefreshUsage, cloudRefreshUsageBudget, aiRefreshUsageBudget, ... }

  POST https://api.manus.im/user.v1.UserService/ListUserCreditsLog
    body: {"page": 1, "pageSize": 100}
    → { logs: [{credits, title, createAt, type, ...}], total }
      credits: positive = earned/refund, negative = spent
      total: number of log entries (NOT credit balance)

Authentication: Bearer JWT token (set MANUS_API_KEY in env).

Optional env vars:
  MANUS_TOTAL_CREDITS   - your known total credit balance (integer)
                          Set this to the value shown on manus.im/billing.
                          Used as the denominator for the progress bar.
  MANUS_MONTHLY_CREDITS - monthly plan allotment (default 40000 for Pro plan)

To get your JWT token:
1. Log in to manus.im in your browser
2. Open DevTools (F12) → Network tab
3. Find any request to api.manus.im → Headers → Authorization
4. Copy the value after "Bearer " — that is your JWT token

Set MANUS_API_KEY=<your JWT token> in the backend environment.
The token typically expires after ~90 days (check the 'exp' claim).
"""

import logging
import os
import httpx

from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MANUS_API_BASE = "https://api.manus.im"
USAGE_INFO_ENDPOINT  = f"{MANUS_API_BASE}/user.v1.UserService/WebdevUsageInfo"
CREDITS_LOG_ENDPOINT = f"{MANUS_API_BASE}/user.v1.UserService/ListUserCreditsLog"

# Pro plan monthly allotment (override with MANUS_MONTHLY_CREDITS env var)
DEFAULT_MONTHLY_CREDITS = 40_000


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

    def _build_snapshot(
        self,
        usage_data: dict | None,
        log_data:   dict | None,
    ) -> BalanceSnapshot:
        """
        Build a BalanceSnapshot using raw credit integers.

        - remaining_credits = MANUS_TOTAL_CREDITS env var (known balance from billing page)
          If not set, falls back to net sum of log entries (approximate).
        - total_credits     = MANUS_TOTAL_CREDITS (for progress bar denominator)
        - used_credits      = sum of negative log entries (spent this period)
        - currency          = "credits"  ← tells the frontend to format as integers
        """
        # ── Read env-var overrides ──────────────────────────────────────────
        total_from_env: int | None = None
        env_val = os.environ.get("MANUS_TOTAL_CREDITS", "").strip()
        if env_val:
            try:
                total_from_env = int(env_val)
            except ValueError:
                logger.warning("[Manus] MANUS_TOTAL_CREDITS is not a valid integer: %s", env_val)

        monthly_credits = DEFAULT_MONTHLY_CREDITS
        monthly_val = os.environ.get("MANUS_MONTHLY_CREDITS", "").strip()
        if monthly_val:
            try:
                monthly_credits = int(monthly_val)
            except ValueError:
                pass

        # ── Parse log entries ───────────────────────────────────────────────
        net_from_log: int | None = None
        spent_credits: int = 0
        earned_credits: int = 0
        log_entry_count: int = 0

        if log_data and isinstance(log_data.get("logs"), list):
            logs = log_data["logs"]
            log_entry_count = log_data.get("total", len(logs))
            for entry in logs:
                c = entry.get("credits")
                if isinstance(c, (int, float)):
                    c = int(c)
                    if c < 0:
                        spent_credits += abs(c)
                    else:
                        earned_credits += c
            net_from_log = earned_credits - spent_credits

        # ── Parse usage quota ───────────────────────────────────────────────
        cloud_used:   float | None = None
        cloud_budget: int   | None = None
        if usage_data:
            cloud_used   = usage_data.get("cloudRefreshUsage")
            cloud_budget = usage_data.get("cloudRefreshUsageBudget")

        # ── Decide remaining / total ────────────────────────────────────────
        # Prefer the env-var total (authoritative from billing page).
        # Fall back to net log sum (approximate — only last 100 entries).
        remaining = float(total_from_env) if total_from_env is not None else (
            float(net_from_log) if net_from_log is not None else None
        )
        total = float(total_from_env) if total_from_env is not None else None

        if remaining is None and cloud_used is None:
            return self._error_snapshot(
                "Could not parse Manus credits data. "
                "Set MANUS_TOTAL_CREDITS in backend env to your balance from manus.im/billing."
            )

        raw: dict = {}
        if usage_data:
            raw.update({
                "cloud_refresh_used":   cloud_used,
                "cloud_refresh_budget": cloud_budget,
                "ai_refresh_budget":    usage_data.get("aiRefreshUsageBudget"),
            })
        raw.update({
            "monthly_allotment":  monthly_credits,
            "spent_this_period":  spent_credits,
            "earned_this_period": earned_credits,
            "log_entry_count":    log_entry_count,
            "total_from_env":     total_from_env,
        })

        return self._make_snapshot(
            balance_usd=None,
            remaining_credits=remaining,
            used_credits=float(spent_credits) if spent_credits else None,
            total_credits=total,
            currency="credits",
            status="ok",
            raw_data=raw,
        )
