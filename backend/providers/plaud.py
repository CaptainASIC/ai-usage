"""
Plaud provider — reverse-engineered API via JWT session token.

Auth: JWT token from localStorage.getItem("tokenstr") in the Plaud web app.
      Token is long-lived (~10 months).
      Store in PLAUD_JWT_TOKEN env var, or enter via the Settings panel.
      The token should be passed in the `session_cookie` credential field
      (it's a Bearer JWT, not a cookie, but we reuse the field for simplicity).

API base: https://api.plaud.ai
Endpoints probed:
  - GET /user/quota  → transcription minutes used/remaining
  - GET /member/info → subscription plan details
  - GET /file/simple/web → file count (fallback connectivity check)
"""

import logging
from typing import Optional

import httpx

from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

PLAUD_API_BASE = "https://api.plaud.ai"


class PlaudProvider(BaseProvider):
    """Plaud AI recorder usage provider (JWT token auth)."""

    provider_id   = "plaud"
    provider_name = "Plaud"
    auth_type     = "session_cookie"  # reusing session_cookie field for JWT

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie)

    def _get_token(self) -> Optional[str]:
        token = self.credentials.session_cookie
        if not token:
            return None
        token = token.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; AI-Credits-Tracker/1.0)",
        }

        client = await self.get_client()

        # Try /user/quota and /member/info in parallel
        quota_data = await self._try_endpoint(client, headers, "/user/quota")
        member_data = await self._try_endpoint(client, headers, "/member/info")

        if quota_data is None and member_data is None:
            # Connectivity check via file list
            files_data = await self._try_endpoint(client, headers, "/file/simple/web")
            if files_data is None:
                return self._error_snapshot(
                    "All Plaud API endpoints returned errors. Token may be expired."
                )
            file_count = len(files_data) if isinstance(files_data, list) else 0
            return self._make_snapshot(
                status="ok",
                raw_data={
                    "note": "Quota endpoint unavailable — showing file count",
                    "file_count": file_count,
                },
            )

        # Parse quota data
        minutes_used: Optional[float] = None
        minutes_total: Optional[float] = None
        minutes_remaining: Optional[float] = None
        plan_name: Optional[str] = None

        if quota_data and isinstance(quota_data, dict):
            data = quota_data.get("data") or quota_data.get("payload") or quota_data
            if isinstance(data, dict):
                minutes_used = (
                    data.get("used_minutes")
                    or data.get("transcription_used")
                    or data.get("minutes_used")
                    or data.get("used")
                )
                minutes_total = (
                    data.get("total_minutes")
                    or data.get("transcription_total")
                    or data.get("minutes_total")
                    or data.get("total")
                    or data.get("quota")
                )
                minutes_remaining = (
                    data.get("remaining_minutes")
                    or data.get("transcription_remaining")
                    or data.get("minutes_remaining")
                    or data.get("remaining")
                )
                if minutes_remaining is None and minutes_total is not None and minutes_used is not None:
                    try:
                        minutes_remaining = float(minutes_total) - float(minutes_used)
                    except (TypeError, ValueError):
                        pass

        if member_data and isinstance(member_data, dict):
            data = member_data.get("data") or member_data.get("payload") or member_data
            if isinstance(data, dict):
                plan_name = (
                    data.get("plan_name")
                    or data.get("membership_type")
                    or data.get("plan")
                    or data.get("subscription_type")
                    or data.get("level_name")
                )

        # Build result — Plaud uses minutes not USD, so we store in used_credits/remaining_credits
        # with a note that the unit is minutes
        try:
            rem   = float(minutes_remaining) if minutes_remaining is not None else None
            tot   = float(minutes_total)     if minutes_total     is not None else None
            used  = float(minutes_used)      if minutes_used      is not None else None
        except (TypeError, ValueError):
            rem = tot = used = None

        note = f"Unit: minutes · Plan: {plan_name}" if plan_name else "Unit: transcription minutes"

        return self._make_snapshot(
            remaining_credits=rem,
            total_credits=tot,
            used_credits=used,
            status="ok",
            raw_data={
                "note": note,
                "plan": plan_name,
                "quota_raw": quota_data,
                "member_raw": member_data,
            },
        )

    async def _try_endpoint(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        path: str,
    ) -> Optional[dict]:
        """Try an endpoint, return parsed JSON or None on failure."""
        try:
            resp = await client.get(f"{PLAUD_API_BASE}{path}", headers=headers)
            if resp.status_code == 200:
                return resp.json()
            logger.debug("Plaud %s returned HTTP %d", path, resp.status_code)
            return None
        except Exception as exc:
            logger.debug("Plaud %s error: %s", path, exc)
            return None
