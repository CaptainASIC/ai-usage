"""
mem0 provider — API usage tracking via the mem0 REST API.

mem0 does not expose a public billing/credits API. However, the core
memory API can be used to validate the key and report usage metadata.

Endpoint: https://api.mem0.ai/v1/memories/
Auth: Bearer API key (from app.mem0.ai/dashboard/api-keys)

We call the memories list endpoint with a minimal page size to validate
the key and extract any usage metadata from response headers.
"""

import logging
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MEM0_API_BASE = "https://api.mem0.ai/v1"


class Mem0Provider(BaseProvider):
    """mem0 memory API provider — key validation and usage metadata."""

    provider_id   = "mem0"
    provider_name = "mem0"
    auth_type     = "api_key"
    category      = "cloud"

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        headers = {
            "Authorization": f"Token {self.credentials.api_key}",
            "Accept": "application/json",
        }

        try:
            # Validate key via memories list (minimal request)
            resp = await client.get(
                f"{MEM0_API_BASE}/memories/",
                headers=headers,
                params={"page": 1, "page_size": 1},
                timeout=15.0,
            )

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Invalid mem0 API key. Get yours at app.mem0.ai/dashboard/api-keys."
                )
            if resp.status_code == 403:
                return self._error_snapshot("Forbidden — key may be expired or revoked.")

            resp.raise_for_status()
            data = resp.json()

            # Extract usage metadata if present
            total_memories = None
            if isinstance(data, dict):
                total_memories = data.get("total") or data.get("count")
            elif isinstance(data, list):
                total_memories = len(data)

            # Check for usage headers (mem0 may include X-RateLimit-* headers)
            rate_limit = resp.headers.get("X-RateLimit-Limit")
            rate_remaining = resp.headers.get("X-RateLimit-Remaining")

            raw: dict = {
                "note": (
                    "mem0 does not expose a billing/credits API. "
                    "Key is valid — usage limits shown in app.mem0.ai dashboard."
                ),
                "key_valid": True,
            }
            if total_memories is not None:
                raw["total_memories"] = total_memories
            if rate_limit:
                raw["rate_limit"] = rate_limit
            if rate_remaining:
                raw["rate_remaining"] = rate_remaining

            return self._make_snapshot(status="ok", raw_data=raw)

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching mem0 API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return self._error_snapshot(f"Unexpected error: {exc}")
