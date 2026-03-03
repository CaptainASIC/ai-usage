"""
Railway provider — fetches account credit balance via GraphQL API.

Endpoint: https://backboard.railway.app/graphql/v2
Auth: Bearer token (generate at railway.app/account/tokens)

The `me` query returns the current user's credit balance in cents.
"""

import logging
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

GRAPHQL_ENDPOINT = "https://backboard.railway.app/graphql/v2"

# Query for account credit balance
BALANCE_QUERY = """
query GetBalance {
  me {
    creditBalance
    name
    email
  }
}
"""


class RailwayProvider(BaseProvider):
    """Railway cloud platform credit balance provider."""

    provider_id   = "railway"
    provider_name = "Railway"
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
            "Content-Type": "application/json",
        }

        try:
            resp = await client.post(
                GRAPHQL_ENDPOINT,
                json={"query": BALANCE_QUERY},
                headers=headers,
                timeout=15.0,
            )

            if resp.status_code == 401:
                return self._error_snapshot(
                    "Invalid Railway token. Generate one at railway.app/account/tokens."
                )

            resp.raise_for_status()
            data = resp.json()

            if "errors" in data:
                errors = data["errors"]
                msg = errors[0].get("message", str(errors)) if errors else "GraphQL error"
                return self._error_snapshot(f"GraphQL error: {msg}")

            me = data.get("data", {}).get("me", {})
            if not me:
                return self._error_snapshot("No user data returned from Railway API.")

            # creditBalance is in cents (USD)
            credit_cents = me.get("creditBalance")
            if credit_cents is None:
                return self._make_snapshot(
                    status="ok",
                    raw_data={
                        "note": "creditBalance not returned — may require a paid plan",
                        "user": me.get("name") or me.get("email"),
                    },
                )

            balance_usd = float(credit_cents) / 100.0

            return self._make_snapshot(
                remaining_credits=balance_usd,
                status="ok",
                raw_data={
                    "credit_balance_cents": credit_cents,
                    "user": me.get("name") or me.get("email"),
                },
            )

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching Railway API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return self._error_snapshot(f"Unexpected error: {exc}")
