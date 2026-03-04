"""
Plaud provider — uses the /user/stat/file and /user/membership REST endpoints.

Auth: Long-lived JWT from the Plaud web app (expires ~10 months after login).
      Store in PLAUD_API_KEY env var, or enter via the Settings panel.
      The token is a Bearer JWT — pass without the 'Bearer ' prefix.

API base: https://api.plaud.ai
Endpoints used:
  - GET /user/stat/file?diff_time=0&start_time=<epoch_ms>&end_time=<epoch_ms>
    Returns: total_files, total_duration, total_transcribed_duration,
             recent_30_days_daily_avg, group_result (daily breakdown)
  - GET /user/membership  (optional — returns plan name and expiry if available)

Dashboard mirrors: Days active / Recordings / Hours + plan tier + daily avg.
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

# Epoch start for "all-time" queries
_ALLTIME_START_MS = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)


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

        now = datetime.now(timezone.utc)
        now_ms = int(now.timestamp() * 1000)

        client = await self.get_client()

        try:
            # ── All-time stats ──────────────────────────────────────────────
            stat_resp = await client.get(
                f"{PLAUD_API_BASE}/user/stat/file",
                params={
                    "diff_time": 0,
                    "start_time": _ALLTIME_START_MS,
                    "end_time": now_ms,
                },
                headers=headers,
            )
            if stat_resp.status_code == 401:
                return self._error_snapshot("Invalid or expired Plaud JWT token.")
            if stat_resp.status_code != 200:
                return self._error_snapshot(
                    f"Plaud API returned HTTP {stat_resp.status_code}"
                )

            stat_data = stat_resp.json()
            stat = stat_data.get("data_stat") or stat_data.get("data") or {}

            # ── Membership / plan info (best-effort) ────────────────────────
            plan_name: Optional[str] = None
            plan_expires: Optional[str] = None
            membership_resp = await client.get(
                f"{PLAUD_API_BASE}/user/membership",
                headers=headers,
            )
            if membership_resp.status_code == 200:
                mem_data = membership_resp.json()
                mem = mem_data.get("data") or mem_data or {}
                # Try common field names
                plan_name = (
                    mem.get("plan_name")
                    or mem.get("plan")
                    or mem.get("membership_type")
                    or mem.get("type")
                    or mem.get("name")
                )
                expire_ts = (
                    mem.get("expire_time")
                    or mem.get("expires_at")
                    or mem.get("expiry")
                    or mem.get("end_time")
                )
                if expire_ts:
                    # Could be epoch ms or ISO string
                    if isinstance(expire_ts, (int, float)):
                        expire_dt = datetime.fromtimestamp(
                            expire_ts / 1000 if expire_ts > 1e10 else expire_ts,
                            tz=timezone.utc,
                        )
                        plan_expires = expire_dt.strftime("%Y-%m-%d")
                    elif isinstance(expire_ts, str):
                        plan_expires = expire_ts[:10]  # take YYYY-MM-DD prefix
                logger.info("[Plaud] Membership: plan=%s expires=%s raw=%s",
                            plan_name, plan_expires, mem)

        except Exception as exc:
            logger.error("[plaud] Request error: %s", exc)
            return self._error_snapshot(f"Request failed: {exc}")

        # ── Parse stat fields ───────────────────────────────────────────────
        total_files = stat.get("total_files", 0)
        total_duration_ms = stat.get("total_duration", 0)
        total_transcribed_ms = stat.get("total_transcribed_duration", 0)
        total_hours = round(total_duration_ms / 3_600_000, 1)
        total_transcribed_hours = round(total_transcribed_ms / 3_600_000, 1)

        # Count active days from group_result (list of daily entries)
        group_result = stat.get("group_result") or []
        active_days = sum(
            1 for day in group_result
            if isinstance(day, dict) and (day.get("total_files") or day.get("count") or 0) > 0
        )
        # Fallback: if group_result is empty, use a field directly
        if active_days == 0:
            active_days = stat.get("active_days") or stat.get("total_days") or 0

        # 30-day daily average (in hours) — field is in seconds
        recent_avg_sec = stat.get("recent_30_days_daily_avg", 0)
        recent_avg_hours = round(recent_avg_sec / 3600, 1) if recent_avg_sec else 0

        # Most active hour (0-23)
        most_active_hour = stat.get("most_active_hour")

        logger.info(
            "[Plaud] %d files | %.1f hrs recorded | %.1f hrs transcribed | "
            "%d active days | 30d avg: %.1f hrs/day | plan: %s",
            total_files, total_hours, total_transcribed_hours,
            active_days, recent_avg_hours, plan_name,
        )

        return self._make_snapshot(
            status="ok",
            raw_data={
                # Core stats (mirrors Plaud dashboard)
                "plaud_total_files": total_files,
                "plaud_total_hours": total_hours,
                "plaud_total_transcribed_hours": total_transcribed_hours,
                "plaud_active_days": active_days,
                "plaud_daily_avg_hours": recent_avg_hours,
                "plaud_most_active_hour": most_active_hour,
                # Plan / subscription
                "plaud_plan_name": plan_name,
                "plaud_plan_expires": plan_expires,
            },
        )
