"""
RunPod provider — fetches credit balance via the RunPod GraphQL API.

Endpoint: POST https://api.runpod.io/graphql?api_key=<key>
Query: { myself { clientBalance spendLimit currentSpendPerHr } }

Auth: API key passed as query parameter (not Bearer header)
Get your API key at: runpod.io/console/user/settings → API Keys
"""
import logging
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

RUNPOD_GRAPHQL = "https://api.runpod.io/graphql"

BALANCE_QUERY = "{ myself { clientBalance spendLimit currentSpendPerHr } }"


class RunPodProvider(BaseProvider):
    """RunPod GPU cloud provider — credit balance via GraphQL API."""

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

        try:
            resp = await client.post(
                RUNPOD_GRAPHQL,
                params={"api_key": self.credentials.api_key},
                json={"query": BALANCE_QUERY},
                headers={"Content-Type": "application/json"},
                timeout=15.0,
            )

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Invalid RunPod API key. Generate one at runpod.io/console/user/settings."
                )
            if resp.status_code == 403:
                return self._error_snapshot("Forbidden — API key lacks required permissions.")

            resp.raise_for_status()
            payload = resp.json()

            # GraphQL errors come back as 200 with an "errors" key
            if "errors" in payload:
                errs = payload["errors"]
                msg = errs[0].get("message", str(errs)) if errs else "Unknown GraphQL error"
                return self._error_snapshot(f"GraphQL error: {msg}")

            me = (payload.get("data") or {}).get("myself") or {}
            balance      = me.get("clientBalance")
            spend_limit  = me.get("spendLimit")
            spend_per_hr = me.get("currentSpendPerHr")

            if balance is None:
                return self._error_snapshot(
                    "Could not read clientBalance from RunPod API response."
                )

            raw: dict = {"client_balance_usd": balance}
            if spend_limit is not None:
                raw["spend_limit_usd"] = spend_limit
            if spend_per_hr is not None:
                raw["current_spend_per_hr"] = spend_per_hr

            return self._make_snapshot(
                balance_usd       = float(balance),
                remaining_credits = float(balance),
                status            = "ok",
                raw_data          = raw,
            )

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching RunPod API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(
                f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            )
        except Exception as exc:
            return self._error_snapshot(f"Unexpected error: {exc}")
