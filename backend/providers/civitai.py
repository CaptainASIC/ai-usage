"""
CivitAI provider - fetches Buzz credits via TRPC endpoints.

CivitAI has no public billing API. Internally it uses TRPC (tRPC) for all
data fetching. We attempt to read the user's Buzz balance from the
``buzz.getBuzzAccount`` TRPC endpoint using a session cookie.

To get credentials:
1. Log in to civitai.com
2. Open DevTools → Application → Cookies
3. Copy the full Cookie header string (or at minimum the ``__Secure-civitai-token`` cookie)
"""

import logging
import time
import urllib.parse

import httpx

from models.schemas import ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

CIVITAI_BASE = "https://civitai.com"
COOKIE_NAME = "__Secure-civitai-token"

# CivitAI tRPC requires {"json":{"authed":true}} as input
_AUTHED_INPUT = urllib.parse.quote('{"json":{"authed":true}}')


class CivitAIProvider(BaseProvider):
    """CivitAI Buzz credits provider (session-based)."""

    provider_id = "civitai"
    provider_name = "CivitAI"
    auth_type = "session_cookie"

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie)

    @staticmethod
    def _normalize_cookie(raw: str) -> str:
        """Ensure the cookie string contains the expected cookie name.

        Users may paste just the token value or the full
        ``__Secure-civitai-token=<value>`` string.
        """
        raw = raw.strip()
        if COOKIE_NAME in raw:
            return raw
        return f"{COOKIE_NAME}={raw}"

    async def fetch_balance(self) -> BalanceSnapshot:
        """Attempt to fetch CivitAI Buzz balance via TRPC endpoints."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        cookie = self._normalize_cookie(self.credentials.session_cookie)
        client = await self.get_client()
        headers = {
            "Cookie": cookie,
            "Accept": "*/*",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Referer": "https://civitai.com/user/buzz-dashboard",
            "x-client": "web",
            "x-client-date": str(int(time.time() * 1000)),
        }

        # Try getBuzzAccount first (has per-type breakdown)
        try:
            url = f"{CIVITAI_BASE}/api/trpc/buzz.getBuzzAccount?input={_AUTHED_INPUT}"
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                inner = data["result"]["data"]["json"]
                # Shape: {"blue": N, "green": N, "yellow": N}
                yellow = inner.get("yellow", 0)
                blue = inner.get("blue", 0)
                green = inner.get("green", 0)
                total_buzz = yellow + blue + green
                return self._make_snapshot(
                    balance_usd=None,
                    remaining_credits=float(total_buzz),
                    currency="buzz",
                    raw_data={
                        "endpoint": "buzz.getBuzzAccount",
                        "yellow": yellow,
                        "blue": blue,
                        "green": green,
                    },
                )
        except Exception as exc:
            logger.debug(f"[CivitAI] getBuzzAccount failed: {exc}")

        # Fallback: getUserAccount (returns list of accounts)
        try:
            url = f"{CIVITAI_BASE}/api/trpc/buzz.getUserAccount?input={_AUTHED_INPUT}"
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                accounts = data["result"]["data"]["json"]
                # Shape: [{"id": N, "balance": N, "lifetimeBalance": N, "accountType": "yellow"}, ...]
                if isinstance(accounts, list) and accounts:
                    total_buzz = sum(a.get("balance", 0) for a in accounts)
                    lifetime = sum(a.get("lifetimeBalance", 0) for a in accounts)
                    return self._make_snapshot(
                        balance_usd=None,
                        remaining_credits=float(total_buzz),
                        currency="buzz",
                        raw_data={
                            "endpoint": "buzz.getUserAccount",
                            "accounts": accounts,
                            "lifetime_balance": lifetime,
                        },
                    )
        except Exception as exc:
            logger.debug(f"[CivitAI] getUserAccount failed: {exc}")

        return self._error_snapshot(
            "CivitAI has no public billing API. "
            "Provide session cookies from civitai.com DevTools to attempt scraping."
        )
