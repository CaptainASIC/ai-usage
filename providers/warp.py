"""
Warp provider - fetches credits via session cookie scraping.

Warp has no API or CLI for credit usage (GitHub issue #8405 open since Jan 2026).
Credits are visible in the Warp app under Settings → Billing and usage.

We attempt to fetch from internal API endpoints using session cookies.

To get credentials:
1. Log in to app.warp.dev or warp.dev
2. Open DevTools → Network tab
3. Find requests to /api/... endpoints
4. Copy the Cookie header or Authorization Bearer token
"""

import logging
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

WARP_BASE = "https://app.warp.dev"
WARP_API = "https://api.warp.dev"


class WarpProvider(BaseProvider):
    """Warp credits provider (session-based)."""

    provider_id = "warp"
    provider_name = "Warp"
    auth_type = "session_cookie"

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie or self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Attempt to fetch Warp credits via session cookie."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
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
            f"{WARP_API}/v1/billing/credits",
            f"{WARP_API}/v1/user/credits",
            f"{WARP_BASE}/api/billing/balance",
            f"{WARP_BASE}/api/credits",
            f"{WARP_BASE}/api/user/usage",
        ]

        for endpoint in candidate_endpoints:
            try:
                response = await client.get(endpoint, headers=headers)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        for key in ("credits", "balance", "remaining", "ai_credits", "amount"):
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
            "Warp has no public billing API (GitHub issue #8405). "
            "Provide session cookies from app.warp.dev DevTools to attempt scraping."
        )
