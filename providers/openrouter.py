"""
OpenRouter provider - fetches credits via the official /api/v1/key endpoint.

Endpoint: GET https://openrouter.ai/api/v1/key
Auth: Standard API key as Bearer token
Response includes: limit, limit_remaining, usage, usage_daily, usage_monthly
"""

import logging
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

KEY_ENDPOINT = "https://openrouter.ai/api/v1/key"
CREDITS_ENDPOINT = "https://openrouter.ai/api/v1/credits"


class OpenRouterProvider(BaseProvider):
    """OpenRouter credit balance provider."""

    provider_id = "openrouter"
    provider_name = "OpenRouter"
    auth_type = "api_key"

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Fetch balance from OpenRouter /api/v1/key endpoint."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        headers = {"Authorization": f"Bearer {self.credentials.api_key}"}

        try:
            response = await client.get(KEY_ENDPOINT, headers=headers)
            response.raise_for_status()
            data = response.json()
            key_data = data.get("data", {})

            limit = key_data.get("limit")  # None = unlimited
            limit_remaining = key_data.get("limit_remaining")  # None = unlimited
            usage = key_data.get("usage", 0.0)
            usage_monthly = key_data.get("usage_monthly", 0.0)

            # If limit_remaining is None, the key has no credit cap (unlimited/BYOK)
            # In that case surface monthly usage as the primary metric
            remaining = limit_remaining if limit_remaining is not None else None
            note = "Unlimited key — showing usage" if limit is None else None

            raw: dict = {
                "label": key_data.get("label"),
                "limit": limit,
                "limit_remaining": limit_remaining,
                "usage": usage,
                "usage_daily": key_data.get("usage_daily"),
                "usage_weekly": key_data.get("usage_weekly"),
                "usage_monthly": usage_monthly,
                "is_free_tier": key_data.get("is_free_tier"),
            }
            if note:
                raw["note"] = note

            return self._make_snapshot(
                balance_usd=remaining,
                total_credits=limit,
                used_credits=usage,
                remaining_credits=remaining,
                raw_data=raw,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return self._error_snapshot("Invalid API key")
            return self._error_snapshot(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            return self._error_snapshot(f"Network error: {str(e)}")
        except Exception as e:
            return self._error_snapshot(f"Unexpected error: {str(e)}")
