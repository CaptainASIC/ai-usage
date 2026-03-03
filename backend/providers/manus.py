"""
Manus provider - fetches credits via session cookie scraping.

Manus has a task management API but no public credits/billing API.
Credits are visible at manus.im/app#settings/usage.

We attempt to fetch from internal API endpoints using session cookies.

To get credentials:
1. Log in to manus.im
2. Open DevTools → Network tab
3. Find requests to /api/... endpoints
4. Copy the Authorization header (Bearer token) or Cookie header value
"""

import logging
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MANUS_BASE = "https://api.manus.im"
MANUS_APP_BASE = "https://manus.im"


class ManusProvider(BaseProvider):
    """Manus credits provider (session-based)."""

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

        # Build headers - try both cookie and bearer token approaches
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        }

        if self.credentials.api_key:
            headers["Authorization"] = f"Bearer {self.credentials.api_key}"
        if self.credentials.session_cookie:
            headers["Cookie"] = self.credentials.session_cookie

        # Try known internal API endpoints
        candidate_endpoints = [
            f"{MANUS_BASE}/v1/user/credits",
            f"{MANUS_BASE}/v1/billing/balance",
            f"{MANUS_APP_BASE}/api/user/credits",
            f"{MANUS_APP_BASE}/api/billing/credits",
            f"{MANUS_APP_BASE}/api/settings/usage",
        ]

        for endpoint in candidate_endpoints:
            try:
                response = await client.get(endpoint, headers=headers)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        for key in ("credits", "balance", "remaining", "amount", "total_credits"):
                            if key in data:
                                val = float(data[key])
                                return self._make_snapshot(
                                    balance_usd=val,
                                    remaining_credits=val,
                                    raw_data={"endpoint": endpoint, **data},
                                )
                    except Exception:
                        pass
            except Exception:
                continue

        return self._error_snapshot(
            "Could not fetch Manus credits. "
            "Provide your session cookie from manus.im DevTools. "
            "Credits visible at manus.im/app#settings/usage"
        )
