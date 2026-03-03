"""
Vercel provider — fetches billing spend via the official Billing Charges API.

Endpoint: GET https://api.vercel.com/v1/billing/charges
Auth: Bearer token (generate at vercel.com/account/tokens)
Optional: VERCEL_TEAM_ID for team accounts

The API returns FOCUS v1.3 JSONL (newline-delimited JSON).
We sum BilledCost for the current billing period to get total spend.
"""

import logging
from datetime import datetime, timezone, timedelta
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

CHARGES_ENDPOINT = "https://api.vercel.com/v1/billing/charges"


class VercelProvider(BaseProvider):
    """Vercel cloud platform billing spend provider."""

    provider_id   = "vercel"
    provider_name = "Vercel"
    auth_type     = "api_key"
    category      = "cloud"

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        headers = {
            "Authorization": f"Bearer {self.credentials.api_key}",
            "Accept": "application/jsonl",
        }

        # Query current month
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        params: dict = {
            "start": start.strftime("%Y-%m-%d"),
            "end": now.strftime("%Y-%m-%d"),
            "granularity": "total",
        }
        if self.credentials.team_id:
            params["teamId"] = self.credentials.team_id

        try:
            resp = await client.get(
                CHARGES_ENDPOINT,
                headers=headers,
                params=params,
                timeout=20.0,
            )

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Invalid Vercel token. Generate one at vercel.com/account/tokens."
                )
            if resp.status_code == 403:
                return self._error_snapshot(
                    "Forbidden — token lacks billing read permission or wrong team ID."
                )

            resp.raise_for_status()

            # Parse JSONL response
            total_billed = 0.0
            currency = "USD"
            line_count = 0

            for line in resp.text.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    import json
                    record = json.loads(line)
                    cost = record.get("BilledCost") or record.get("EffectiveCost") or 0
                    total_billed += float(cost)
                    if "BillingCurrency" in record:
                        currency = record["BillingCurrency"]
                    line_count += 1
                except Exception:
                    continue

            return self._make_snapshot(
                used_credits=total_billed,
                currency=currency,
                status="ok",
                raw_data={
                    "note": f"Month-to-date spend ({start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})",
                    "thirty_day_spend_usd": total_billed,
                    "line_items": line_count,
                    "billing_period_start": start.isoformat(),
                },
            )

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching Vercel API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return self._error_snapshot(f"Unexpected error: {exc}")
