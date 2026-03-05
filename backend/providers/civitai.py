"""
CivitAI provider - fetches Buzz credits via TRPC endpoints.

CivitAI has no public billing API. Internally it uses TRPC (tRPC) for all
data fetching. We attempt to read the user's Buzz balance from the
``buzz.getBuzzAccount`` TRPC endpoint using a session cookie.

To get credentials:
1. Log in to civitai.com
2. Open DevTools → Application → Cookies
3. Copy the full Cookie header string (or at minimum the ``__Secure-civitai-token`` cookie)
"""

import logging

import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

CIVITAI_BASE = "https://civitai.com"


class CivitAIProvider(BaseProvider):
    """CivitAI Buzz credits provider (session-based)."""

    provider_id = "civitai"
    provider_name = "CivitAI"
    auth_type = "session_cookie"

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Attempt to fetch CivitAI Buzz balance via TRPC endpoints."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        headers = {
            "Cookie": self.credentials.session_cookie,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Referer": "https://civitai.com/user/buzz-dashboard",
        }

        # TRPC endpoints that may expose the Buzz balance.
        # CivitAI uses tRPC; the response shape is:
        #   {"result": {"data": {"json": { ... }}}}
        candidate_endpoints = [
            f"{CIVITAI_BASE}/api/trpc/buzz.getBuzzAccount?input=%7B%7D",
            f"{CIVITAI_BASE}/api/trpc/buzz.getUserAccount?input=%7B%7D",
            f"{CIVITAI_BASE}/api/trpc/buzz.getAccountSummary?input=%7B%7D",
        ]

        for endpoint in candidate_endpoints:
            try:
                response = await client.get(endpoint, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    balance = self._extract_buzz(data)
                    if balance is not None:
                        return self._make_snapshot(
                            balance_usd=None,
                            remaining_credits=balance,
                            currency="buzz",
                            raw_data={"endpoint": endpoint, **data},
                        )
            except Exception:
                continue

        return self._error_snapshot(
            "CivitAI has no public billing API. "
            "Provide session cookies from civitai.com DevTools to attempt scraping."
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_buzz(data: dict) -> float | None:
        """Walk common TRPC response shapes to find a buzz balance.

        Tries the standard tRPC envelope first, then falls back to
        scanning top-level keys.
        """
        # Standard tRPC envelope: result.data.json.<key>
        try:
            inner = data["result"]["data"]["json"]
            for key in ("balance", "lifetimeBalance", "buzz", "total", "amount"):
                if key in inner:
                    return float(inner[key])
        except (KeyError, TypeError):
            pass

        # Flat response fallback
        for key in ("balance", "buzz", "credits", "amount", "total"):
            if key in data:
                try:
                    return float(data[key])
                except (ValueError, TypeError):
                    pass

        return None
