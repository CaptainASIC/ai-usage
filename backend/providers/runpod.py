"""
RunPod provider — fetches credit balance via the RunPod REST API.

Endpoints:
  GET https://rest.runpod.io/v1/user  → account info including credits
  GET https://rest.runpod.io/v1/billing/pods → recent pod billing

Auth: Bearer API key (from runpod.io/console/user/settings → API Keys)
"""

import logging
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

RUNPOD_API_BASE = "https://rest.runpod.io/v1"


class RunPodProvider(BaseProvider):
    """RunPod GPU cloud provider — credit balance and usage."""

    provider_id   = "runpod"
    provider_name = "RunPod"
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
            "Accept": "application/json",
        }

        try:
            # Try user endpoint for account balance
            resp = await client.get(
                f"{RUNPOD_API_BASE}/user",
                headers=headers,
                timeout=15.0,
            )

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Invalid RunPod API key. Generate one at runpod.io/console/user/settings."
                )
            if resp.status_code == 403:
                return self._error_snapshot("Forbidden — API key lacks required permissions.")

            if resp.status_code == 200:
                data = resp.json()
                # RunPod user object may contain creditBalance or balance fields
                balance = (
                    data.get("creditBalance")
                    or data.get("balance")
                    or data.get("credits")
                    or data.get("currentBalance")
                )

                if balance is not None:
                    return self._make_snapshot(
                        remaining_credits=float(balance),
                        status="ok",
                        raw_data={
                            "user_id": data.get("id"),
                            "email": data.get("email"),
                        },
                    )

            # Fall back to billing history to derive spend
            return await self._billing_fallback(client, headers)

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching RunPod API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return self._error_snapshot(f"Unexpected error: {exc}")

    async def _billing_fallback(
        self, client: httpx.AsyncClient, headers: dict
    ) -> BalanceSnapshot:
        """Fallback: sum recent pod billing to estimate spend."""
        try:
            resp = await client.get(
                f"{RUNPOD_API_BASE}/billing/pods",
                headers=headers,
                params={"limit": 100},
                timeout=15.0,
            )
            if resp.status_code != 200:
                return self._error_snapshot(
                    f"Could not fetch RunPod billing (HTTP {resp.status_code})."
                )

            records = resp.json()
            if not isinstance(records, list):
                records = records.get("data", records.get("items", []))

            total_spend = sum(float(r.get("amount", 0)) for r in records if isinstance(r, dict))

            return self._make_snapshot(
                used_credits=total_spend,
                status="ok",
                raw_data={
                    "note": "Balance endpoint unavailable — showing recent pod billing spend",
                    "thirty_day_spend_usd": total_spend,
                    "billing_records": len(records),
                },
            )
        except Exception as exc:
            return self._error_snapshot(f"Billing fallback error: {exc}")
