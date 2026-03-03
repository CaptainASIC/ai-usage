"""
GCP provider — fetches billing spend via the Cloud Billing Budget API.

Approach: Uses the Cloud Billing API to list billing accounts and
then fetches budget information to show spend vs budget.

Auth: GCP_SERVICE_ACCOUNT_JSON (service account key JSON as a string)
      or GCP_PROJECT_ID + GCP_BILLING_ACCOUNT_ID with Application Default Credentials

The service account needs roles/billing.viewer on the billing account.

Note: GCP does not have a simple "current balance" API. We report
month-to-date spend from the most recent billing budget if configured,
or validate credentials and report account info otherwise.
"""

import logging
import json
import os
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
BILLING_API_BASE = "https://cloudbilling.googleapis.com/v1"


class GCPProvider(BaseProvider):
    """GCP cloud provider — billing account spend via Cloud Billing API."""

    provider_id   = "gcp"
    provider_name = "GCP"
    auth_type     = "service_account"
    category      = "cloud"

    def is_configured(self) -> bool:
        creds = self.credentials
        return bool(
            creds.session_cookie  # we store the service account JSON here
            or os.getenv("GCP_SERVICE_ACCOUNT_JSON")
        )

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        sa_json_str = (
            self.credentials.session_cookie
            or os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")
        )

        try:
            sa_info = json.loads(sa_json_str)
        except (json.JSONDecodeError, TypeError):
            return self._error_snapshot(
                "GCP_SERVICE_ACCOUNT_JSON is not valid JSON. "
                "Paste the full contents of your service account key file."
            )

        try:
            access_token = await self._get_access_token(sa_info)
        except Exception as exc:
            return self._error_snapshot(f"Failed to get GCP access token: {exc}")

        client = await self.get_client()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        billing_account = os.getenv("GCP_BILLING_ACCOUNT_ID", "").strip()

        try:
            # List billing accounts accessible to this service account
            resp = await client.get(
                f"{BILLING_API_BASE}/billingAccounts",
                headers=headers,
                timeout=15.0,
            )

            if resp.status_code == 401:
                return self._error_snapshot("GCP credentials invalid or expired.")
            if resp.status_code == 403:
                return self._error_snapshot(
                    "Forbidden — service account needs roles/billing.viewer "
                    "on the billing account."
                )

            resp.raise_for_status()
            data = resp.json()
            accounts = data.get("billingAccounts", [])

            if not accounts:
                return self._make_snapshot(
                    status="ok",
                    raw_data={
                        "note": (
                            "No billing accounts accessible to this service account. "
                            "Grant roles/billing.viewer on your billing account."
                        ),
                        "key_valid": True,
                    },
                )

            # Use first account or the specified one
            account = accounts[0]
            for a in accounts:
                if billing_account and billing_account in a.get("name", ""):
                    account = a
                    break

            account_name = account.get("displayName", account.get("name", "unknown"))

            # Try to get budget info for spend data
            budgets_resp = await client.get(
                f"{BILLING_API_BASE}/{account['name']}/budgets",
                headers=headers,
                timeout=15.0,
            )

            if budgets_resp.status_code == 200:
                budgets = budgets_resp.json().get("budgets", [])
                if budgets:
                    b = budgets[0]
                    budget_amount = (
                        b.get("amount", {})
                        .get("specifiedAmount", {})
                        .get("units", "unknown")
                    )
                    return self._make_snapshot(
                        status="ok",
                        raw_data={
                            "billing_account": account_name,
                            "budget_count": len(budgets),
                            "first_budget_amount_usd": budget_amount,
                            "note": (
                                "GCP does not expose real-time spend via API. "
                                "Budget amounts shown — check GCP console for actual spend."
                            ),
                        },
                    )

            return self._make_snapshot(
                status="ok",
                raw_data={
                    "billing_account": account_name,
                    "note": (
                        "GCP credentials valid. No budget configured — "
                        "set up a budget in GCP console to track spend."
                    ),
                    "key_valid": True,
                },
            )

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching GCP API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return self._error_snapshot(f"Unexpected error: {exc}")

    async def _get_access_token(self, sa_info: dict) -> str:
        """Exchange service account credentials for an access token via JWT."""
        import time
        import base64

        try:
            import jwt as pyjwt  # PyJWT
        except ImportError:
            raise ImportError("PyJWT is required for GCP auth. Add 'PyJWT' to dependencies.")

        now = int(time.time())
        payload = {
            "iss": sa_info["client_email"],
            "sub": sa_info["client_email"],
            "aud": TOKEN_ENDPOINT,
            "iat": now,
            "exp": now + 3600,
            "scope": "https://www.googleapis.com/auth/cloud-billing.readonly",
        }

        private_key = sa_info["private_key"]
        signed_jwt = pyjwt.encode(payload, private_key, algorithm="RS256")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": signed_jwt,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]
