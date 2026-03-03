"""
Anthropic provider - fetches credits via an undocumented console endpoint.

Endpoint: GET https://platform.claude.com/api/organizations/{org_id}/prepaid/credits
Auth: sessionKey cookie (obtained from browser DevTools on platform.claude.com)

The response returns { "amount": <cents> } where amount is in USD cents.
This endpoint requires a browser session cookie, not an API key.

To get credentials:
1. Log in to platform.claude.com
2. Open DevTools → Network tab
3. Find a request to /api/organizations/<org-id>/prepaid/credits
4. Copy the org_id from the URL
5. Copy the sessionKey value from the Cookie header
"""

import logging
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

CREDITS_ENDPOINT = "https://platform.claude.com/api/organizations/{org_id}/prepaid/credits"


class AnthropicProvider(BaseProvider):
    """Anthropic prepaid credits provider (session-based)."""

    provider_id = "anthropic"
    provider_name = "Anthropic"
    auth_type = "session_cookie"

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie and self.credentials.org_id)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Fetch prepaid credits from Anthropic console endpoint."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        url = CREDITS_ENDPOINT.format(org_id=self.credentials.org_id)
        client = await self.get_client()
        headers = {
            "Cookie": f"sessionKey={self.credentials.session_cookie}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; AI-Credits-Tracker/1.0)",
        }

        try:
            response = await client.get(url, headers=headers)

            if response.status_code == 401:
                return self._error_snapshot(
                    "Session expired. Please update your sessionKey cookie from platform.claude.com"
                )
            if response.status_code == 403:
                return self._error_snapshot(
                    "Access denied. Check your org_id and sessionKey."
                )

            response.raise_for_status()
            data = response.json()

            # Amount is in cents
            amount_cents = data.get("amount", 0)
            balance_usd = amount_cents / 100.0

            return self._make_snapshot(
                balance_usd=balance_usd,
                remaining_credits=balance_usd,
                raw_data={"amount_cents": amount_cents, "amount_usd": balance_usd},
            )

        except httpx.HTTPStatusError as e:
            return self._error_snapshot(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            return self._error_snapshot(f"Network error: {str(e)}")
        except Exception as e:
            return self._error_snapshot(f"Unexpected error: {str(e)}")
