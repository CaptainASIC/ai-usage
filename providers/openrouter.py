"""
OpenRouter provider - fetches credits via official endpoints.

Endpoints:
  GET https://openrouter.ai/api/v1/key      → key metadata (limit, usage)
  GET https://openrouter.ai/api/v1/credits  → prepaid credit balance

For prepaid accounts: /api/v1/credits returns total_granted and total_used,
so remaining = total_granted - total_used.
For unlimited/BYOK keys: limit is null; we show monthly usage instead.
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
        """Fetch balance from OpenRouter key + credits endpoints."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        headers = {"Authorization": f"Bearer {self.credentials.api_key}"}

        try:
            # Fetch key metadata
            key_resp = await client.get(KEY_ENDPOINT, headers=headers)
            key_resp.raise_for_status()
            key_data = key_resp.json().get("data", {})

            limit = key_data.get("limit")          # None = unlimited
            limit_remaining = key_data.get("limit_remaining")
            usage = key_data.get("usage", 0.0)
            usage_monthly = key_data.get("usage_monthly", 0.0)
            is_free_tier = key_data.get("is_free_tier", False)

            # Fetch prepaid credit balance
            total_granted: float | None = None
            total_used_credits: float | None = None
            remaining_credits: float | None = None

            try:
                credits_resp = await client.get(CREDITS_ENDPOINT, headers=headers)
                credits_resp.raise_for_status()
                credits_data = credits_resp.json().get("data", {})
                total_granted = credits_data.get("total_granted")
                total_used_credits = credits_data.get("total_used")
                if total_granted is not None and total_used_credits is not None:
                    remaining_credits = round(total_granted - total_used_credits, 4)
            except Exception:
                # Credits endpoint may not be available for all key types
                pass

            # Determine best values to surface
            # Priority: prepaid remaining > key limit_remaining > None
            best_remaining = remaining_credits if remaining_credits is not None else limit_remaining
            best_total = total_granted if total_granted is not None else limit
            best_used = total_used_credits if total_used_credits is not None else usage

            raw: dict = {
                "label": key_data.get("label"),
                "limit": limit,
                "limit_remaining": limit_remaining,
                "usage": usage,
                "usage_daily": key_data.get("usage_daily"),
                "usage_weekly": key_data.get("usage_weekly"),
                "usage_monthly": usage_monthly,
                "is_free_tier": is_free_tier,
            }
            if total_granted is not None:
                raw["total_granted"] = total_granted
                raw["total_used_credits"] = total_used_credits
            if best_remaining is None:
                raw["note"] = "Unlimited key — showing monthly usage"

            return self._make_snapshot(
                balance_usd=best_remaining,
                total_credits=best_total,
                used_credits=best_used,
                remaining_credits=best_remaining,
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
