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

from models.schemas import BalanceSnapshot, ProviderCredentials
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

        # CivitAI tRPC endpoints require {"json":{"authed":true}} input
        candidate_endpoints = [
            f"{CIVITAI_BASE}/api/trpc/buzz.getBuzzAccount?input={_AUTHED_INPUT}",
            f"{CIVITAI_BASE}/api/trpc/buzz.getUserAccount?input={_AUTHED_INPUT}",
        ]

        for endpoint in candidate_endpoints:
            try:
                response = await client.get(endpoint, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"[CivitAI] {endpoint.split('?')[0].split('/')[-1]} response: {data}")
                    balance = self._extract_buzz(data)
                    if balance is not None:
                        raw = data if isinstance(data, dict) else {"batch": data}
                        return self._make_snapshot(
                            balance_usd=None,
                            remaining_credits=balance,
                            currency="buzz",
                            raw_data={"endpoint": endpoint, **raw},
                        )
            except Exception:
                continue

        return self._error_snapshot(
            "CivitAI has no public billing API. "
            "Provide session cookies from civitai.com DevTools to attempt scraping."
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_buzz(data) -> float | None:
        """Walk common TRPC response shapes to find a buzz balance.

        Handles both batch responses (list) and single responses (dict).
        Batch shape:  [{"result":{"data":{"json":{...}}}}]
        Single shape: {"result":{"data":{"json":{...}}}}
        """
        candidates = []

        # Batch response: unwrap the first element
        if isinstance(data, list) and data:
            candidates.append(data[0])
        if isinstance(data, dict):
            candidates.append(data)

        for item in candidates:
            # Standard tRPC envelope: result.data.json.<key>
            try:
                inner = item["result"]["data"]["json"]
                for key in ("balance", "lifetimeBalance", "buzz", "total", "amount"):
                    if key in inner:
                        return float(inner[key])
            except (KeyError, TypeError):
                pass

            # Flat response fallback
            if isinstance(item, dict):
                for key in ("balance", "buzz", "credits", "amount", "total"):
                    if key in item:
                        try:
                            return float(item[key])
                        except (ValueError, TypeError):
                            pass

        return None
