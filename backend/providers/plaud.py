"""
Plaud provider — uses the /user/stat/file REST endpoint.

Auth: Long-lived JWT from the Plaud web app (expires ~10 months after login).
      Store in PLAUD_API_TOKEN env var, or enter via the Settings panel.
      The token is a Bearer JWT — pass without the 'Bearer ' prefix.

API base: https://api.plaud.ai
Endpoints used:
  - GET /user/stat/file?diff_time=0&start_time=<epoch_ms>&end_time=<epoch_ms>
    Returns: total_files, total_duration, total_transcribed_duration, group_result (daily)

Note: Plaud has no subscription/quota API endpoint — plan info is not available via API.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

PLAUD_API_BASE = "https://api.plaud.ai"

# Required headers for all Plaud API calls
PLAUD_HEADERS_STATIC = {
    "app-platform": "web",
    "app-language": "en",
    "Accept": "application/json",
}


class PlaudProvider(BaseProvider):
    """Plaud AI recorder usage provider (JWT token auth)."""

    provider_id   = "plaud"
    provider_name = "Plaud"
    auth_type     = "session_cookie"  # reusing session_cookie field for JWT

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie or self.credentials.api_key)

    def _get_token(self) -> Optional[str]:
        token = self.credentials.api_key or self.credentials.session_cookie
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
        if not token:
            return self._unconfigured_snapshot()

        headers = {
            **PLAUD_HEADERS_STATIC,
            "authorization": f"bearer {token}",
        }

        # Build time range: start of current month → now
        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        now_ms = int(now.timestamp() * 1000)
        start_ms = int(month_start.timestamp() * 1000)

        # Also build a 30-day window for the all-time stat call
        thirty_days_ago = now - timedelta(days=365)  # use 1 year for all-time
        alltime_start_ms = int(thirty_days_ago.timestamp() * 1000)

        client = await self.get_client()

        try:
            # Monthly stats
            monthly_resp = await client.get(
                f"{PLAUD_API_BASE}/user/stat/file",
                params={
                    "diff_time": 0,
                    "start_time": start_ms,
                    "end_time": now_ms,
                },
                headers=headers,
            )
            if monthly_resp.status_code == 401:
                return self._error_snapshot("Invalid or expired Plaud JWT token.")
            if monthly_resp.status_code != 200:
                return self._error_snapshot(
                    f"Plaud API returned HTTP {monthly_resp.status_code}"
                )

            monthly_data = monthly_resp.json()
            stat = monthly_data.get("data_stat") or monthly_data.get("data") or {}

            # All-time stats (use a wide window)
            alltime_resp = await client.get(
                f"{PLAUD_API_BASE}/user/stat/file",
                params={
                    "diff_time": 0,
                    "start_time": alltime_start_ms,
                    "end_time": now_ms,
                },
                headers=headers,
            )
            alltime_stat = {}
            if alltime_resp.status_code == 200:
                alltime_data = alltime_resp.json()
                alltime_stat = alltime_data.get("data_stat") or alltime_data.get("data") or {}

        except Exception as exc:
            logger.error("[plaud] Request error: %s", exc)
            return self._error_snapshot(f"Request failed: {exc}")

        # Parse monthly stats
        monthly_files = stat.get("total_files", 0)
        monthly_duration_ms = stat.get("total_duration", 0)
        monthly_transcribed_ms = stat.get("total_transcribed_duration", 0)
        monthly_hours = round(monthly_duration_ms / 3_600_000, 1)
        monthly_transcribed_hours = round(monthly_transcribed_ms / 3_600_000, 1)

        # Parse all-time stats
        alltime_files = alltime_stat.get("total_files", 0)
        alltime_duration_ms = alltime_stat.get("total_duration", 0)
        alltime_transcribed_ms = alltime_stat.get("total_transcribed_duration", 0)
        alltime_hours = round(alltime_duration_ms / 3_600_000, 1)
        alltime_transcribed_hours = round(alltime_transcribed_ms / 3_600_000, 1)

        # 30-day daily average (in hours)
        recent_avg_sec = stat.get("recent_30_days_daily_avg", 0)
        recent_avg_hours = round(recent_avg_sec / 3600, 2) if recent_avg_sec else 0

        logger.info(
            "[Plaud] Monthly: %d files, %.1f hrs recorded, %.1f hrs transcribed | "
            "All-time: %d files, %.1f hrs | 30d avg: %.2f hrs/day",
            monthly_files, monthly_hours, monthly_transcribed_hours,
            alltime_files, alltime_hours, recent_avg_hours,
        )

        return self._make_snapshot(
            status="ok",
            raw_data={
                "plaud_monthly_files": monthly_files,
                "plaud_monthly_hours": monthly_hours,
                "plaud_monthly_transcribed_hours": monthly_transcribed_hours,
                "plaud_alltime_files": alltime_files,
                "plaud_alltime_hours": alltime_hours,
                "plaud_alltime_transcribed_hours": alltime_transcribed_hours,
                "plaud_daily_avg_hours": recent_avg_hours,
                "plaud_most_active_hour": stat.get("most_active_hour"),
            },
        )
