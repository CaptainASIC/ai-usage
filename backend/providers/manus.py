"""
Manus provider - fetches credits via the Manus web app internal API.

The Manus Open API (api.manus.im) only exposes task management endpoints.
Credits/billing data is only available via the web app's internal session API.

To get your session token:
1. Log in to manus.im in your browser
2. Open DevTools (F12) → Application tab → Local Storage → https://manus.im
3. Find the key 'token' or 'auth_token' and copy its value
   OR
4. DevTools → Network tab → find any request to manus.im → copy the
   'Authorization: Bearer <token>' header value
"""

import logging
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

# The Manus web app internal API base
MANUS_WEB_BASE = "https://manus.im"

# Known internal endpoints (discovered via web app network inspection)
# These require a valid session token from the web app
CANDIDATE_ENDPOINTS = [
    # Web app internal API patterns
    "/api/user/credits",
    "/api/user/quota",
    "/api/user/balance",
    "/api/billing/credits",
    "/api/billing/balance",
    "/api/account/credits",
    "/api/me/credits",
    "/api/me",
    # App-specific patterns
    "/app/api/user/credits",
    "/app/api/billing",
]


class ManusProvider(BaseProvider):
    """Manus credits provider (web session-based)."""

    provider_id = "manus"
    provider_name = "Manus"
    auth_type = "session_cookie"

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie or self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Attempt to fetch Manus credits via session token."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()

        # Build headers with session token
        headers = {
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://manus.im/",
            "Origin": "https://manus.im",
        }

        # Support both Bearer token and session cookie
        if self.credentials.api_key:
            headers["Authorization"] = f"Bearer {self.credentials.api_key}"
        if self.credentials.session_cookie:
            headers["Cookie"] = self.credentials.session_cookie

        for endpoint in CANDIDATE_ENDPOINTS:
            url = f"{MANUS_WEB_BASE}{endpoint}"
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
                logger.debug("[Manus] %s → %d", endpoint, response.status_code)

                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Try to extract a credits/balance value from common field names
                        for key in (
                            "credits", "balance", "remaining", "amount",
                            "total_credits", "credit_balance", "remaining_credits",
                            "quota", "available",
                        ):
                            if key in data:
                                val = float(data[key])
                                return self._make_snapshot(
                                    balance_usd=val,
                                    remaining_credits=val,
                                    raw_data={"endpoint": endpoint, **data},
                                )
                        # If we got a 200 but no known field, log the keys for debugging
                        logger.warning(
                            "[Manus] 200 from %s but unknown fields: %s",
                            endpoint, list(data.keys())[:10]
                        )
                    except Exception as e:
                        logger.debug("[Manus] JSON parse error at %s: %s", endpoint, e)

                elif response.status_code == 401:
                    # Token is invalid or expired
                    return self._error_snapshot(
                        "Manus session token is invalid or expired. "
                        "Please refresh your token from manus.im DevTools."
                    )

            except httpx.TimeoutException:
                logger.debug("[Manus] Timeout at %s", endpoint)
                continue
            except Exception as e:
                logger.debug("[Manus] Error at %s: %s", endpoint, e)
                continue

        # All endpoints failed — note that Manus doesn't have a public credits API
        return self._error_snapshot(
            "Manus credits endpoint not found. "
            "The Manus Open API does not expose billing data. "
            "If you have a session token, it may be expired. "
            "Credits are visible at manus.im → Settings → Usage."
        )
