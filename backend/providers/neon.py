"""
Neon DB provider — fetches compute usage via the Neon Console API.

Endpoint: GET https://console.neon.tech/api/v2/consumption_history/account
Auth: Bearer API key (from console.neon.tech/app/settings/api-keys)

Required params: from (ISO 8601), to (ISO 8601), granularity (hourly|daily|monthly)

Returns compute unit seconds and storage bytes used in the current period.
Available for Launch, Scale, Agent, and Enterprise plans.
"""

import logging
from datetime import datetime, timezone
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

NEON_API_BASE = "https://console.neon.tech/api/v2"


class NeonProvider(BaseProvider):
    """Neon DB cloud database provider — usage and compute consumption."""

    provider_id   = "neon"
    provider_name = "Neon DB"
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
            from datetime import timedelta
            # Neon requires explicit from/to params (ISO 8601) and from < to
            now = datetime.now(timezone.utc)
            # Start of current calendar month
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Ensure at least 1 minute gap so from < to even on the 1st of the month
            to_dt   = now if now > period_start else period_start + timedelta(minutes=1)
            from_ts = period_start.strftime("%Y-%m-%dT%H:%M:%SZ")
            to_ts   = to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            resp = await client.get(
                f"{NEON_API_BASE}/consumption_history/account",
                headers=headers,
                params={"from": from_ts, "to": to_ts, "granularity": "daily"},
                timeout=15.0,
            )

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Invalid Neon API key. Generate one at console.neon.tech/app/settings/api-keys."
                )
            if resp.status_code == 403:
                return self._error_snapshot(
                    "Forbidden — consumption history requires a paid Neon plan (Launch or above)."
                )
            if resp.status_code == 404:
                return await self._fallback_projects(client, headers)

            resp.raise_for_status()
            data = resp.json()

            # Parse consumption data — sum all daily buckets for the current month
            periods = data.get("periods", [])
            if not periods:
                return self._make_snapshot(
                    status="ok",
                    raw_data={
                        "note": "No consumption data for current period",
                        "key_valid": True,
                    },
                )

            # Sum across all daily periods in the response
            total_compute_seconds = 0
            total_storage_bytes   = 0
            total_transfer_bytes  = 0
            for period in periods:
                c = period.get("consumption", {})
                total_compute_seconds += c.get("compute_time_seconds", 0) or c.get("compute_unit_seconds", 0)
                total_storage_bytes   += c.get("root_branch_bytes_month", 0)
                total_transfer_bytes  += c.get("public_network_transfer_bytes", 0)

            compute_hours = round(total_compute_seconds / 3600, 2) if total_compute_seconds else 0
            storage_gb    = round(total_storage_bytes / (1024 ** 3), 3) if total_storage_bytes else 0
            transfer_gb   = round(total_transfer_bytes / (1024 ** 3), 3) if total_transfer_bytes else 0

            return self._make_snapshot(
                used_credits=compute_hours,
                status="ok",
                raw_data={
                    "note": "Unit: compute hours (CU·h) this billing period (daily granularity, summed)",
                    "compute_hours": compute_hours,
                    "compute_seconds": total_compute_seconds,
                    "storage_gb": storage_gb,
                    "data_transfer_gb": transfer_gb,
                },
            )

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching Neon API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(f"HTTP {exc.response.status_code}: {exc.response.text[:500]}")
        except Exception as exc:
            return self._error_snapshot(f"Unexpected error: {exc}")

    async def _fallback_projects(
        self, client: httpx.AsyncClient, headers: dict
    ) -> BalanceSnapshot:
        """Fallback: validate key via projects list if consumption endpoint unavailable."""
        try:
            resp = await client.get(
                f"{NEON_API_BASE}/projects",
                headers=headers,
                params={"limit": 1},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                project_count = len(data.get("projects", []))
                return self._make_snapshot(
                    status="ok",
                    raw_data={
                        "note": (
                            "Consumption API unavailable for your plan. "
                            "Key is valid — upgrade to Launch or above for usage metrics."
                        ),
                        "key_valid": True,
                        "project_count": project_count,
                    },
                )
            return self._error_snapshot(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            return self._error_snapshot(f"Fallback error: {exc}")
