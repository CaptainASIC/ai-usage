"""
mem0 provider — API key validation via the mem0 REST API.

mem0 does not expose a public billing/credits endpoint. We validate the key
and report memory count metadata using the v2 memories endpoint.

Endpoint: POST https://api.mem0.ai/v2/memories/  (trailing slash required — Django APPEND_SLASH)
Auth: Token <api_key>  (note: "Token", not "Bearer")

Get your API key at: app.mem0.ai/dashboard/api-keys
"""

import logging
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MEM0_API_BASE = "https://api.mem0.ai"


class Mem0Provider(BaseProvider):
    """mem0 memory API provider — key validation and memory count metadata."""

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
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            # v2 POST endpoint — minimal request to validate key
            resp = await client.post(
                f"{MEM0_API_BASE}/v2/memories/",
                headers=headers,
                # filters cannot be empty — use wildcard to match all memories
                json={"filters": {"user_id": {"*": "*"}}, "page": 1, "page_size": 1},
                timeout=15.0,
            )

            logger.debug("[mem0] POST /v2/memories → %d", resp.status_code)

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Invalid mem0 API key. Get yours at app.mem0.ai/dashboard/api-keys."
                )
            if resp.status_code == 403:
                return self._error_snapshot("Forbidden — key may be expired or revoked.")

            resp.raise_for_status()
            data = resp.json()

            # Extract memory count
            total_memories: int | None = None
            if isinstance(data, list):
                total_memories = len(data)
            elif isinstance(data, dict):
                total_memories = (
                    data.get("total")
                    or data.get("count")
                    or (len(data.get("results", [])) if "results" in data else None)
                )

            # Check for rate limit headers
            rate_limit     = resp.headers.get("X-RateLimit-Limit")
            rate_remaining = resp.headers.get("X-RateLimit-Remaining")

            raw: dict = {
                "note": (
                    "mem0 does not expose a billing/credits API. "
                    "Key is valid — usage limits shown at app.mem0.ai/dashboard."
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
            return self._error_snapshot(
                f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            )
        except Exception as exc:
            logger.exception("[mem0] Unexpected error")
            return self._error_snapshot(f"Unexpected error: {exc}")
