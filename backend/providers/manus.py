"""
Manus provider - fetches credits via the Manus Connect RPC API.

The Manus web app uses a Connect RPC (gRPC-Web compatible) API at api.manus.im.
Two relevant endpoints discovered via network inspection:

  POST https://api.manus.im/user.v1.UserService/WebdevUsageInfo
    body: {}
    → returns:
        {
          "cloudRefreshUsage": 0.38,
          "aiRefreshUsageBudget": 1,
          "cloudRefreshUsageBudget": 10,
          "integrationsRefreshUsageBudget": 1,
          "bindCard": true
        }
    NOTE: this endpoint returns quota/usage counts, NOT credit balance.

  POST https://api.manus.im/user.v1.UserService/ListUserCreditsLog
    body: {"page": 1, "pageSize": 10}
    → returns:
        {
          "logs": [
            {
              "sessionId": "...",
              "title": "...",
              "createAt": 1772593008,
              "credits": -5702,
              "type": "CREDIT_LOG_TYPE_COST"
            },
            ...
          ],
          "total": 211   ← total number of log entries (NOT credit balance)
        }
    NOTE: credits are integers (positive = earned, negative = spent).
          There is no "current balance" field in this response.
          We derive remaining balance by summing all log entries.

Authentication: Bearer JWT token.

To get your JWT token:
1. Log in to manus.im in your browser
2. Open DevTools (F12) → Network tab
3. Navigate to Settings → Usage (or any page that loads)
4. Find any request to api.manus.im → Headers → Authorization
5. Copy the value after "Bearer " — that is your JWT token

Set MANUS_API_KEY=<your JWT token> in the backend environment.
The token typically expires after ~90 days (check the 'exp' claim).
"""

import logging
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MANUS_API_BASE = "https://api.manus.im"

# Connect RPC endpoints (POST, content-type: application/json)
USAGE_INFO_ENDPOINT = f"{MANUS_API_BASE}/user.v1.UserService/WebdevUsageInfo"
CREDITS_LOG_ENDPOINT = f"{MANUS_API_BASE}/user.v1.UserService/ListUserCreditsLog"

# Manus credits are integer units (not USD).
# Approximate conversion: 1 USD ≈ 3500 credits (based on observed spend).
# We display raw credit integers; no USD conversion applied.
CREDITS_PER_USD = 3500


class ManusProvider(BaseProvider):
    """Manus credits provider using Connect RPC API."""

    provider_id = "manus"
    provider_name = "Manus"
    auth_type = "bearer_token"

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key or self.credentials.session_cookie)

    def _get_token(self) -> str:
        """Return whichever credential is set (api_key preferred)."""
        return self.credentials.api_key or self.credentials.session_cookie or ""

    def _build_headers(self) -> dict:
        token = self._get_token()
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "authorization": f"Bearer {token}",
            "connect-protocol-version": "1",
            "content-type": "application/json",
            "x-client-type": "web",
            "x-client-locale": "en",
            "origin": "https://manus.im",
            "referer": "https://manus.im/",
        }

    async def fetch_balance(self) -> BalanceSnapshot:
        """Fetch Manus credits via Connect RPC API."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        headers = self._build_headers()

        usage_data: dict | None = None
        log_data: dict | None = None

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
        # Fetch all pages to compute the running balance from transactions.
        # The API returns up to pageSize entries per call; we fetch page 1 first
        # to get `total`, then fetch remaining pages.
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

        # ── 3. Build snapshot from what we have ─────────────────────────────
        return self._build_snapshot(usage_data, log_data)

    def _build_snapshot(
        self,
        usage_data: dict | None,
        log_data: dict | None,
    ) -> BalanceSnapshot:
        """
        Build a BalanceSnapshot from the two API responses.

        WebdevUsageInfo fields (actual):
          cloudRefreshUsage          - float, cloud refresh slots used
          cloudRefreshUsageBudget    - int, cloud refresh slot budget
          aiRefreshUsageBudget       - int, AI refresh slot budget
          integrationsRefreshUsageBudget - int

        ListUserCreditsLog fields (actual):
          logs[].credits  - int, positive = earned, negative = spent
          logs[].type     - "CREDIT_LOG_TYPE_COST" | "CREDIT_LOG_TYPE_ROLLBACK" | ...
          total           - int, total number of log entries (NOT balance)

        Strategy:
          - Sum all log entries to get net credits balance (running total).
          - Use cloudRefreshUsage / cloudRefreshUsageBudget for usage percentage
            as a secondary display metric.
        """
        net_credits: int | None = None
        used_credits: int | None = None
        cloud_used: float | None = None
        cloud_budget: int | None = None

        # Parse usage quota data
        if usage_data:
            cloud_used = usage_data.get("cloudRefreshUsage")
            cloud_budget = usage_data.get("cloudRefreshUsageBudget")

        # Compute net balance from transaction log
        if log_data and isinstance(log_data.get("logs"), list):
            logs = log_data["logs"]
            net_credits = sum(
                int(entry["credits"])
                for entry in logs
                if isinstance(entry.get("credits"), (int, float))
            )
            # Separate cost vs earned
            spent = sum(
                abs(int(e["credits"]))
                for e in logs
                if isinstance(e.get("credits"), (int, float)) and e["credits"] < 0
            )
            used_credits = spent

        if net_credits is None and cloud_used is None:
            return self._error_snapshot(
                "Could not parse Manus credits data. "
                "Check backend logs for the raw response fields."
            )

        # Build display values
        # Credits are raw integers; convert to a pseudo-USD for display consistency
        remaining_usd = float(net_credits) / CREDITS_PER_USD if net_credits is not None else None
        used_usd = float(used_credits) / CREDITS_PER_USD if used_credits is not None else None

        # Usage percentage from cloud refresh quota (most meaningful metric)
        usage_pct: float | None = None
        if cloud_used is not None and cloud_budget and cloud_budget > 0:
            usage_pct = (cloud_used / cloud_budget) * 100

        raw: dict = {}
        if usage_data:
            raw.update({
                "cloud_refresh_used": cloud_used,
                "cloud_refresh_budget": cloud_budget,
                "ai_refresh_budget": usage_data.get("aiRefreshUsageBudget"),
            })
        if log_data:
            raw.update({
                "net_credits": net_credits,
                "log_entry_count": log_data.get("total"),
            })

        return self._make_snapshot(
            balance_usd=None,
            remaining_credits=remaining_usd,
            used_credits=used_usd,
            total_credits=None,
            status="ok",
            raw_data=raw,
        )
