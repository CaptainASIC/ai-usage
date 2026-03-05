"""
Firecrawl provider — fetches credit usage via the Firecrawl v2 API.

Endpoint: GET https://api.firecrawl.dev/v2/team/credit-usage
Auth: Bearer <api_key>

Response:
{
  "success": true,
  "data": {
    "remainingCredits": 1000,
    "planCredits": 500000,
    "billingPeriodStart": "2025-01-01T00:00:00Z",
    "billingPeriodEnd": "2025-01-31T23:59:59Z"
  }
}

Get your API key at: firecrawl.dev/app/api-keys
"""

import logging
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

FIRECRAWL_CREDIT_URL = "https://api.firecrawl.dev/v2/team/credit-usage"


class FirecrawlProvider(BaseProvider):
    """Firecrawl web-scraping API provider — credit usage via REST API."""

    provider_id   = "firecrawl"
    provider_name = "Firecrawl"
    auth_type     = "api_key"
    category      = "cloud"

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()

        try:
            resp = await client.get(
                FIRECRAWL_CREDIT_URL,
                headers={
                    "Authorization": f"Bearer {self.credentials.api_key}",
                    "Accept": "application/json",
                },
                timeout=15.0,
            )

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Invalid Firecrawl API key. Get yours at firecrawl.dev/app/api-keys."
                )
            if resp.status_code == 403:
                return self._error_snapshot("Forbidden — API key lacks required permissions.")

            resp.raise_for_status()
            payload = resp.json()

            if not payload.get("success"):
                return self._error_snapshot(
                    f"API returned success=false: {payload}"
                )

            data = payload.get("data") or {}
            remaining = data.get("remainingCredits")
            plan      = data.get("planCredits")

            if remaining is None:
                return self._error_snapshot(
                    "Could not read remainingCredits from Firecrawl API response."
                )

            used = (plan - remaining) if plan is not None else None

            raw: dict = {
                "remaining_credits": remaining,
            }
            if plan is not None:
                raw["plan_credits"] = plan
            if used is not None:
                raw["used_credits"] = used
            if data.get("billingPeriodStart"):
                raw["billing_period_start"] = data["billingPeriodStart"]
            if data.get("billingPeriodEnd"):
                raw["billing_period_end"] = data["billingPeriodEnd"]

            return self._make_snapshot(
                total_credits     = float(plan) if plan is not None else None,
                used_credits      = float(used) if used is not None else None,
                remaining_credits = float(remaining),
                currency          = "credits",
                status            = "ok",
                raw_data          = raw,
            )

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching Firecrawl API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(
                f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            )
        except Exception as exc:
            logger.exception("[Firecrawl] Unexpected error")
            return self._error_snapshot(f"Unexpected error: {exc}")
