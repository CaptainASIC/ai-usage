"""
Groq provider - fetches credits via session cookie scraping.

Groq has no public billing API (community request open as of 2025).
We attempt to fetch balance from the Groq console API endpoints.

Endpoint: https://console.groq.com (internal API)
Auth: Session cookie from browser (log in to console.groq.com, copy cookies)

To get credentials:
1. Log in to console.groq.com
2. Open DevTools → Network tab
3. Find requests to /api/... endpoints
4. Copy the Cookie header value
"""

import logging
import re
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

CONSOLE_BASE = "https://console.groq.com"


class GroqProvider(BaseProvider):
    """Groq credits provider (session-based)."""

    provider_id = "groq"
    provider_name = "Groq"
    auth_type = "session_cookie"

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Attempt to fetch Groq balance via session cookie."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        headers = {
            "Cookie": self.credentials.session_cookie,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Referer": "https://console.groq.com/",
        }

        # Try known internal API endpoints
        candidate_endpoints = [
            f"{CONSOLE_BASE}/api/billing/balance",
            f"{CONSOLE_BASE}/api/credits",
            f"{CONSOLE_BASE}/api/billing/credits",
            f"{CONSOLE_BASE}/api/usage/balance",
        ]

        for endpoint in candidate_endpoints:
            try:
                response = await client.get(endpoint, headers=headers)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        for key in ("balance", "credits", "amount", "remaining"):
                            if key in data:
                                val = float(data[key])
                                balance_usd = val / 100.0 if val > 1000 else val
                                return self._make_snapshot(
                                    balance_usd=balance_usd,
                                    remaining_credits=balance_usd,
                                    raw_data={"endpoint": endpoint, **data},
                                )
                    except Exception:
                        pass
            except Exception:
                continue

        # Groq has no billing API - return informative status
        return self._error_snapshot(
            "Groq has no public billing API. "
            "Check console.groq.com manually. "
            "Provide session cookies to attempt scraping."
        )
