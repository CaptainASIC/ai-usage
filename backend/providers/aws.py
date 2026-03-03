"""
AWS provider — fetches month-to-date spend via the Cost Explorer API.

Endpoint: POST https://ce.us-east-1.amazonaws.com/
Auth: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (IAM user with ce:GetCostAndUsage)

Uses boto3 (AWS SDK) for authenticated requests. The Cost Explorer API
is only available in us-east-1 and charges $0.01 per API call.
"""

import logging
import os
from datetime import datetime, timezone
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)


class AWSProvider(BaseProvider):
    """AWS cloud provider — Cost Explorer month-to-date spend."""

    provider_id   = "aws"
    provider_name = "AWS"
    auth_type     = "multi_key"
    category      = "cloud"

    def is_configured(self) -> bool:
        creds = self.credentials
        return bool(
            (creds.api_key and creds.api_secret)
            or (
                os.getenv("AWS_ACCESS_KEY_ID")
                and os.getenv("AWS_SECRET_ACCESS_KEY")
            )
        )

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
        except ImportError:
            return self._error_snapshot(
                "boto3 is not installed. Add it to pyproject.toml dependencies."
            )

        creds = self.credentials
        access_key = creds.api_key or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = creds.api_secret or os.getenv("AWS_SECRET_ACCESS_KEY")

        now = datetime.now(timezone.utc)
        start = now.replace(day=1).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

        try:
            ce = boto3.client(
                "ce",
                region_name="us-east-1",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )

            response = ce.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )

            results = response.get("ResultsByTime", [])
            if not results:
                return self._make_snapshot(
                    status="ok",
                    raw_data={"note": "No cost data for current period", "key_valid": True},
                )

            total_cost = sum(
                float(r["Total"]["UnblendedCost"]["Amount"])
                for r in results
                if "UnblendedCost" in r.get("Total", {})
            )
            currency = results[0]["Total"]["UnblendedCost"].get("Unit", "USD")

            return self._make_snapshot(
                used_credits=total_cost,
                currency=currency,
                status="ok",
                raw_data={
                    "note": f"Month-to-date spend ({start} to {end})",
                    "thirty_day_spend_usd": total_cost,
                    "billing_period_start": start,
                },
            )

        except Exception as exc:
            err = str(exc)
            if "AccessDenied" in err or "AuthFailure" in err:
                return self._error_snapshot(
                    "AWS credentials invalid or missing ce:GetCostAndUsage permission."
                )
            return self._error_snapshot(f"AWS Cost Explorer error: {err[:300]}")
