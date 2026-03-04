"""
Manus provider - fetches credits via the Manus Connect RPC API.

The Manus web app uses a Connect RPC (gRPC-Web compatible) API at api.manus.im.
Two relevant endpoints discovered via network inspection:

  POST https://api.manus.im/user.v1.UserService/WebdevUsageInfo
    body: {}
    → returns webdev usage quota / remaining info

  POST https://api.manus.im/user.v1.UserService/ListUserCreditsLog
    body: {"page": 1, "pageSize": 10}
    → returns paginated credits transaction log

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

        # ── 1. Try WebdevUsageInfo ──────────────────────────────────────────
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
                data = resp.json()
                logger.debug("[Manus] WebdevUsageInfo data keys: %s", list(data.keys()))
                snapshot = self._parse_usage_info(data)
                if snapshot:
                    return snapshot

        except httpx.TimeoutException:
            logger.warning("[Manus] WebdevUsageInfo timed out")
        except Exception as e:
            logger.warning("[Manus] WebdevUsageInfo error: %s", e)

        # ── 2. Fall back to ListUserCreditsLog ──────────────────────────────
        try:
            resp = await client.post(
                CREDITS_LOG_ENDPOINT,
                headers=headers,
                content='{"page":1,"pageSize":10}',
                timeout=15.0,
            )
            logger.debug("[Manus] ListUserCreditsLog → %d", resp.status_code)

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Manus JWT token is invalid or expired. "
                    "Refresh it from manus.im DevTools → Network → Authorization header."
                )

            if resp.status_code == 200:
                data = resp.json()
                logger.debug("[Manus] ListUserCreditsLog data keys: %s", list(data.keys()))
                snapshot = self._parse_credits_log(data)
                if snapshot:
                    return snapshot

        except httpx.TimeoutException:
            logger.warning("[Manus] ListUserCreditsLog timed out")
        except Exception as e:
            logger.warning("[Manus] ListUserCreditsLog error: %s", e)

        return self._error_snapshot(
            "Could not parse Manus credits data. "
            "Check backend logs for the raw response fields."
        )

    # ── Parsers ────────────────────────────────────────────────────────────

    def _parse_usage_info(self, data: dict) -> BalanceSnapshot | None:
        """
        Parse WebdevUsageInfo response.
        Expected fields (based on Connect RPC convention):
          totalCredits, usedCredits, remainingCredits, quota, used, remaining, ...
        """
        # Try common field name patterns
        remaining = None
        total = None
        used = None

        for key in ("remainingCredits", "remaining_credits", "remaining", "available"):
            if key in data:
                try:
                    remaining = float(data[key])
                    break
                except (TypeError, ValueError):
                    pass

        for key in ("totalCredits", "total_credits", "total", "quota"):
            if key in data:
                try:
                    total = float(data[key])
                    break
                except (TypeError, ValueError):
                    pass

        for key in ("usedCredits", "used_credits", "used", "consumed"):
            if key in data:
                try:
                    used = float(data[key])
                    break
                except (TypeError, ValueError):
                    pass

        # If we have remaining, that's enough
        if remaining is not None:
            usage_pct = None
            if total and total > 0:
                usage_pct = ((total - remaining) / total) * 100
            elif used is not None and total:
                usage_pct = (used / total) * 100

            return self._make_snapshot(
                balance_usd=None,
                remaining_credits=remaining,
                total_credits=total,
                used_credits=used,
                usage_percentage=usage_pct,
                raw_data=data,
            )

        # If we only have total + used, compute remaining
        if total is not None and used is not None:
            remaining = total - used
            usage_pct = (used / total * 100) if total > 0 else None
            return self._make_snapshot(
                balance_usd=None,
                remaining_credits=remaining,
                total_credits=total,
                used_credits=used,
                usage_percentage=usage_pct,
                raw_data=data,
            )

        return None

    def _parse_credits_log(self, data: dict) -> BalanceSnapshot | None:
        """
        Parse ListUserCreditsLog response.
        Expected to have a list of transactions with balance/amount fields.
        """
        # Try to find a current balance from the log
        for key in ("currentBalance", "current_balance", "balance", "totalCredits",
                    "total_credits", "remainingCredits", "remaining_credits"):
            if key in data:
                try:
                    val = float(data[key])
                    return self._make_snapshot(
                        balance_usd=None,
                        remaining_credits=val,
                        raw_data=data,
                    )
                except (TypeError, ValueError):
                    pass

        # Try to get balance from the first log entry
        for list_key in ("list", "logs", "items", "data", "records"):
            if list_key in data and isinstance(data[list_key], list) and data[list_key]:
                entry = data[list_key][0]
                for key in ("balance", "remainingBalance", "remaining_balance",
                            "afterBalance", "after_balance"):
                    if key in entry:
                        try:
                            val = float(entry[key])
                            return self._make_snapshot(
                                balance_usd=None,
                                remaining_credits=val,
                                raw_data=data,
                            )
                        except (TypeError, ValueError):
                            pass

        return None
