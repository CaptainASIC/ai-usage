"""
Railway provider — fetches account credit balance via GraphQL API.

Endpoint: https://backboard.railway.app/graphql/v2
Auth: Bearer token (generate at railway.app/account/tokens)

The `creditBalance` field lives on the `Customer` type, accessed via:
  me { workspaces { customer { creditBalance ... } } }

Note: set env var RAILWAY_CREDIT_TOKEN (not RAILWAY_API_KEY, which
Railway injects automatically into every service).
"""

import logging
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

GRAPHQL_ENDPOINT = "https://backboard.railway.app/graphql/v2"

# creditBalance is on Customer, accessed through workspaces
BALANCE_QUERY = """
query GetCreditBalance {
  me {
    name
    email
    workspaces {
      id
      name
      customer {
        creditBalance
        remainingUsageCreditBalance
        currentUsage
        appliedCredits
        isPrepaying
        usageLimit {
          hardLimit
          softLimit
          isOverLimit
        }
      }
    }
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
                    "Invalid Railway token. Generate an Account token (select 'No workspace') "
                    "at railway.app/account/tokens and set it as RAILWAY_CREDIT_TOKEN."
                )

            resp.raise_for_status()
            data = resp.json()

            if "errors" in data and data["errors"]:
                errors = data["errors"]
                msg = errors[0].get("message", str(errors))
                if "not authorized" in msg.lower() or "unauthorized" in msg.lower():
                    return self._error_snapshot(
                        "Railway token lacks billing access. "
                        "You need an Account token (select 'No workspace') at "
                        "railway.app/account/tokens — workspace/project tokens "
                        "cannot read credit balance."
                    )
                return self._error_snapshot(f"GraphQL error: {msg}")

            me = data.get("data", {}).get("me") or {}
            workspaces = me.get("workspaces") or []

            if not workspaces:
                return self._error_snapshot(
                    "No workspaces found on this Railway account."
                )

            # Aggregate credit balance across all workspaces
            total_credit_cents = 0
            total_usage_cents = 0
            usage_limit_cents = None
            workspace_data = []

            for ws in workspaces:
                customer = ws.get("customer") or {}
                credit_cents = customer.get("creditBalance") or 0
                usage_cents = customer.get("currentUsage") or 0
                remaining_cents = customer.get("remainingUsageCreditBalance") or 0
                usage_limit_obj = customer.get("usageLimit") or {}
                limit_cents = usage_limit_obj.get("hardLimit") or usage_limit_obj.get("softLimit")

                total_credit_cents += credit_cents
                total_usage_cents += usage_cents
                if limit_cents is not None:
                    usage_limit_cents = (usage_limit_cents or 0) + limit_cents

                workspace_data.append({
                    "workspace": ws.get("name"),
                    "credit_balance_usd": credit_cents,
                    "current_usage_usd": usage_cents,
                    "remaining_usage_credit_usd": remaining_cents,
                    "is_prepaying": customer.get("isPrepaying"),
                })

            # Railway GraphQL returns monetary values in dollars (float), not cents.
            balance_usd = float(total_credit_cents)
            usage_usd = float(total_usage_cents)
            limit_usd = float(usage_limit_cents) if usage_limit_cents else None

            return self._make_snapshot(
                remaining_credits=balance_usd if balance_usd > 0 else None,
                used_credits=usage_usd if usage_usd > 0 else None,
                total_credits=limit_usd,
                status="ok",
                raw_data={
                    "credit_balance_usd": balance_usd,
                    "current_usage_usd": usage_usd,
                    "usage_limit_usd": limit_usd,
                    "user": me.get("name") or me.get("email"),
                    "workspaces": workspace_data,
                },
            )

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching Railway API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(
                f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            )
        except Exception as exc:
            logger.exception("Unexpected error in RailwayProvider")
            return self._error_snapshot(f"Unexpected error: {exc}")
