"""
xAI (Grok) provider - fetches prepaid credits via the official Management API.

Endpoint: GET https://api.x.ai/v1/billing/teams/{team_id}/prepaid/balance
Auth: Management key (separate from API key, obtained from xAI Console → Settings)

Response: { "changes": [...], "total": { "val": "<cents>" } }
The total.val is in USD cents (negative = credit balance available).

To get credentials:
1. Log in to console.x.ai
2. Go to Settings → API Keys → Management Keys
3. Create a Management Key
4. Find your team_id in the console URL or account settings
"""

import logging
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

BALANCE_ENDPOINT = "https://api.x.ai/v1/billing/teams/{team_id}/prepaid/balance"
USAGE_ENDPOINT = "https://api.x.ai/v1/billing/teams/{team_id}/usage"


class XAIProvider(BaseProvider):
    """xAI (Grok) prepaid credits provider."""

    provider_id = "xai"
    provider_name = "xAI (Grok)"
    auth_type = "management_key"

    def is_configured(self) -> bool:
        return bool(self.credentials.management_key and self.credentials.team_id)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Fetch prepaid balance from xAI Management API."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        url = BALANCE_ENDPOINT.format(team_id=self.credentials.team_id)
        client = await self.get_client()
        headers = {
            "Authorization": f"Bearer {self.credentials.management_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await client.get(url, headers=headers)

            if response.status_code == 401:
                return self._error_snapshot("Invalid management key")
            if response.status_code == 403:
                return self._error_snapshot(
                    "Access denied. Ensure your management key has billing read permissions."
                )

            response.raise_for_status()
            data = response.json()

            # total.val is in USD cents; negative value means available credit
            total_obj = data.get("total", {})
            total_cents_str = total_obj.get("val", "0")
            total_cents = int(total_cents_str)

            # Negative = credits available (convention in xAI API)
            balance_usd = abs(total_cents) / 100.0 if total_cents < 0 else 0.0

            changes = data.get("changes", [])
            total_purchased = sum(
                abs(int(c.get("amount", {}).get("val", "0"))) / 100.0
                for c in changes
                if c.get("changeOrigin") == "PURCHASE"
            )

            return self._make_snapshot(
                balance_usd=balance_usd,
                remaining_credits=balance_usd,
                total_credits=total_purchased if total_purchased > 0 else None,
                raw_data={
                    "total_cents": total_cents,
                    "balance_usd": balance_usd,
                    "change_count": len(changes),
                },
            )

        except httpx.HTTPStatusError as e:
            return self._error_snapshot(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            return self._error_snapshot(f"Network error: {str(e)}")
        except Exception as e:
            return self._error_snapshot(f"Unexpected error: {str(e)}")
