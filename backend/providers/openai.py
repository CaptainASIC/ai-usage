"""
OpenAI provider - fetches costs via the official Admin API.

OpenAI does NOT expose a direct balance/credits endpoint via standard API keys.
Instead, we use the Admin API (requires sk-admin-... key) to fetch:
  - /v1/organization/costs - daily cost breakdown in USD
  - /v1/organization/usage/completions - token usage data

The balance_usd shown is the rolling 30-day spend (not remaining balance).
Users must check the OpenAI dashboard for exact remaining credits.
"""

import logging
import time
from datetime import datetime, timezone, timedelta

import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

COSTS_ENDPOINT = "https://api.openai.com/v1/organization/costs"
USAGE_ENDPOINT = "https://api.openai.com/v1/organization/usage/completions"


class OpenAIProvider(BaseProvider):
    """OpenAI cost and usage provider."""

    provider_id = "openai"
    provider_name = "OpenAI"
    auth_type = "admin_key"

    def is_configured(self) -> bool:
        return bool(self.credentials.admin_key or self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Fetch 30-day cost data from OpenAI Admin API."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        # Prefer admin key; fall back to regular API key (limited access)
        key = self.credentials.admin_key or self.credentials.api_key
        client = await self.get_client()
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        # Fetch last 30 days of costs
        start_time = int(time.time()) - (30 * 24 * 60 * 60)

        try:
            response = await client.get(
                COSTS_ENDPOINT,
                headers=headers,
                params={"start_time": start_time, "limit": 30},
            )
            response.raise_for_status()
            data = response.json()

            # Sum up all costs from the buckets
            total_cost_usd = 0.0
            buckets = data.get("data", [])
            for bucket in buckets:
                for result in bucket.get("results", []):
                    amount = result.get("amount", {})
                    value = float(amount.get("value", 0))
                    total_cost_usd += value

            return self._make_snapshot(
                used_credits=round(total_cost_usd, 4),
                raw_data={
                    "note": "30-day spend shown. No direct balance API available.",
                    "thirty_day_spend_usd": round(total_cost_usd, 4),
                    "bucket_count": len(buckets),
                },
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return self._error_snapshot(
                    "Invalid key. Use an Admin key (sk-admin-...) from platform.openai.com/settings/organization/admin-keys"
                )
            if e.response.status_code == 403:
                return self._error_snapshot(
                    "Access denied. Admin key required for organization cost data."
                )
            return self._error_snapshot(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            return self._error_snapshot(f"Network error: {str(e)}")
        except Exception as e:
            return self._error_snapshot(f"Unexpected error: {str(e)}")
