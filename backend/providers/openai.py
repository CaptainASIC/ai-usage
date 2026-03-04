"""
OpenAI provider - fetches balance and costs via the OpenAI API.

Balance endpoint (standard sk- key):
  GET https://api.openai.com/v1/dashboard/billing/credit_grants
  → data.total_granted, data.total_used, data.total_available

Cost endpoint (Admin key sk-admin-...):
  GET https://api.openai.com/v1/organization/costs
  → rolling 30-day spend breakdown

If a credit_grants balance is available, it is shown as the primary metric.
If not (PAYG account), the 30-day spend from the Admin API is shown instead.
"""

import logging
import time

import httpx

from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

CREDIT_GRANTS_ENDPOINT = "https://api.openai.com/v1/dashboard/billing/credit_grants"
COSTS_ENDPOINT         = "https://api.openai.com/v1/organization/costs"


class OpenAIProvider(BaseProvider):
    """OpenAI balance and cost provider."""

    provider_id = "openai"
    provider_name = "OpenAI"
    auth_type = "admin_key"

    def is_configured(self) -> bool:
        return bool(self.credentials.admin_key or self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        # Prefer admin key for cost data; standard key works for credit_grants
        admin_key  = self.credentials.admin_key
        std_key    = self.credentials.api_key
        active_key = admin_key or std_key

        client  = await self.get_client()
        headers = {"Authorization": f"Bearer {active_key}"}

        # ── 1. Try credit_grants (works with standard sk- key) ────────────
        total_granted:   float | None = None
        total_used_cg:   float | None = None
        total_available: float | None = None
        is_payg          = False  # True when credit_grants returns 404 (PAYG account)
        key_invalid      = False

        try:
            cg = await client.get(CREDIT_GRANTS_ENDPOINT, headers=headers, timeout=15.0)
            if cg.status_code == 200:
                cg_data = cg.json()
                total_granted   = cg_data.get("total_granted")
                total_used_cg   = cg_data.get("total_used")
                total_available = cg_data.get("total_available")
                logger.info(
                    "[OpenAI] credit_grants → granted=%.4f used=%.4f available=%.4f",
                    total_granted or 0, total_used_cg or 0, total_available or 0,
                )
            elif cg.status_code == 404:
                # PAYG account — no prepaid credits, endpoint doesn't exist
                is_payg = True
                logger.info("[OpenAI] credit_grants 404 → PAYG account")
            elif cg.status_code in (401, 403):
                key_invalid = True
        except Exception as exc:
            logger.debug("[OpenAI] credit_grants fetch failed: %s", exc)

        # ── 2. Try 30-day costs (requires Admin key) ──────────────────────
        thirty_day_spend: float | None = None

        if admin_key:
            try:
                start_time = int(time.time()) - (30 * 24 * 60 * 60)
                admin_headers = {"Authorization": f"Bearer {admin_key}"}
                cr = await client.get(
                    COSTS_ENDPOINT,
                    headers=admin_headers,
                    params={"start_time": start_time, "limit": 30},
                    timeout=15.0,
                )
                if cr.status_code == 200:
                    buckets = cr.json().get("data", [])
                    thirty_day_spend = sum(
                        float(r.get("amount", {}).get("value", 0))
                        for b in buckets
                        for r in b.get("results", [])
                    )
            except Exception as exc:
                logger.debug("[OpenAI] costs fetch failed: %s", exc)

        # ── 3. Decide what to surface ─────────────────────────────────────
        has_credits = total_available is not None and (total_granted or 0) > 0

        raw: dict = {}
        if total_granted is not None:
            raw["total_granted_usd"]   = total_granted
            raw["total_used_usd"]      = total_used_cg
            raw["total_available_usd"] = total_available
        if thirty_day_spend is not None:
            raw["thirty_day_spend_usd"] = round(thirty_day_spend, 4)
        if not raw:
            raw["note"] = "No data returned — check API key permissions."

        if has_credits:
            return self._make_snapshot(
                balance_usd       = float(total_available),
                total_credits     = float(total_granted),
                used_credits      = float(total_used_cg or 0),
                remaining_credits = float(total_available),
                status            = "ok",
                raw_data          = raw,
            )

        if thirty_day_spend is not None:
            raw.setdefault("note", "PAYG account — showing 30-day spend. No prepaid balance.")
            return self._make_snapshot(
                used_credits = round(thirty_day_spend, 4),
                status       = "ok",
                raw_data     = raw,
            )

        # Invalid key
        if key_invalid:
            return self._error_snapshot(
                "Invalid OpenAI API key. Check your key at platform.openai.com/api-keys."
            )

        # PAYG account with no admin key — key is valid but no spend data available
        if is_payg:
            return self._make_snapshot(
                status   = "ok",
                raw_data = {
                    "note": (
                        "Pay-as-you-go account — no prepaid credits. "
                        "Add an Admin key (sk-admin-...) as OPENAI_ADMIN_KEY to see 30-day spend."
                    ),
                    "key_valid": True,
                },
            )

        # Both endpoints failed for unknown reason
        return self._error_snapshot(
            "Could not fetch OpenAI data. "
            "Use a standard API key (sk-...) for credit balance, "
            "or an Admin key (sk-admin-...) for cost data."
        )
