"""
OpenRouter provider - fetches credits via official endpoints.

Endpoints:
  GET https://openrouter.ai/api/v1/credits
    → data.total_credits  (USD purchased)
    → data.total_usage    (USD spent)
    → remaining = total_credits - total_usage
    Requires: Management key (same key used for API calls works)

  GET https://openrouter.ai/api/v1/key
    → data.limit, data.limit_remaining, data.usage, data.usage_monthly
    Used as fallback / supplemental usage stats

For unlimited/BYOK keys with no prepaid balance: total_credits will be 0
or null; we fall back to showing monthly usage from the key endpoint.
"""

import logging
import httpx

from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

CREDITS_ENDPOINT = "https://openrouter.ai/api/v1/credits"
KEY_ENDPOINT     = "https://openrouter.ai/api/v1/key"


class OpenRouterProvider(BaseProvider):
    """OpenRouter credit balance provider."""

    provider_id   = "openrouter"
    provider_name = "OpenRouter"
    auth_type     = "api_key"

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Fetch balance from OpenRouter credits + key endpoints."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client  = await self.get_client()
        headers = {"Authorization": f"Bearer {self.credentials.api_key}"}

        # ── 1. Fetch account credit balance ───────────────────────────────
        total_purchased: float | None = None
        total_usage_credits: float | None = None
        remaining_credits: float | None = None

        try:
            cr = await client.get(CREDITS_ENDPOINT, headers=headers)
            cr.raise_for_status()
            cd = cr.json().get("data", {})
            total_purchased     = cd.get("total_credits")   # USD bought
            total_usage_credits = cd.get("total_usage")     # USD spent
            if total_purchased is not None and total_usage_credits is not None:
                remaining_credits = round(total_purchased - total_usage_credits, 6)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return self._error_snapshot("Invalid API key")
            return self._error_snapshot(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            return self._error_snapshot(f"Network error: {str(e)}")
        except Exception as e:
            return self._error_snapshot(f"Unexpected error: {str(e)}")

        # ── 2. Fetch key-level usage stats (best-effort) ──────────────────
        usage_monthly: float = 0.0
        usage_total:   float = 0.0
        key_label:     str | None = None
        key_limit:     float | None = None

        try:
            kr = await client.get(KEY_ENDPOINT, headers=headers)
            kr.raise_for_status()
            kd = kr.json().get("data", {})
            usage_monthly = kd.get("usage_monthly", 0.0)
            usage_total   = kd.get("usage", 0.0)
            key_label     = kd.get("label")
            key_limit     = kd.get("limit")
        except Exception:
            pass  # key endpoint is supplemental; don't fail on it

        # ── 3. Decide what to surface ─────────────────────────────────────
        # If the account has a prepaid balance, show remaining.
        # If total_purchased is 0 / null (BYOK / unlimited), fall back to
        # monthly usage from the key endpoint.
        has_prepaid = total_purchased is not None and total_purchased > 0

        raw: dict = {
            "label":         key_label,
            "total_credits": total_purchased,
            "total_usage":   total_usage_credits,
            "usage_monthly": usage_monthly,
            "usage":         usage_total,
            "key_limit":     key_limit,
        }

        if not has_prepaid:
            raw["note"] = "Unlimited/BYOK key — showing monthly usage"

        return self._make_snapshot(
            balance_usd       = remaining_credits if has_prepaid else None,
            total_credits     = total_purchased   if has_prepaid else None,
            used_credits      = total_usage_credits if has_prepaid else usage_total,
            remaining_credits = remaining_credits if has_prepaid else None,
            raw_data          = raw,
        )
