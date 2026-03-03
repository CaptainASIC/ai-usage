"""
Mistral AI provider - fetches credits via session cookie scraping.

Mistral has no public billing API. We fetch the billing page and parse the balance.

Endpoint: GET https://console.mistral.ai/billing/
Auth: Session cookie from browser (log in to console.mistral.ai, copy cookies)

To get credentials:
1. Log in to console.mistral.ai
2. Open DevTools → Application → Cookies
3. Copy the session cookie value (typically named 'session' or similar)
"""

import logging
import re
import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Mistral API endpoint for workspace billing (may exist as internal API)
BILLING_API = "https://api.mistral.ai/v1/billing/subscription"
CONSOLE_URL = "https://console.mistral.ai/billing/"


class MistralProvider(BaseProvider):
    """Mistral AI credits provider (session-based)."""

    provider_id = "mistral"
    provider_name = "Mistral AI"
    auth_type = "session_cookie"

    def is_configured(self) -> bool:
        return bool(self.credentials.session_cookie)

    async def fetch_balance(self) -> BalanceSnapshot:
        """Attempt to fetch Mistral balance via session cookie."""
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        headers = {
            "Cookie": self.credentials.session_cookie,
            "Accept": "application/json, text/html",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        }

        # Try internal API endpoint first
        try:
            response = await client.get(
                "https://console.mistral.ai/api/billing/balance",
                headers=headers,
            )
            if response.status_code == 200:
                data = response.json()
                balance = data.get("balance") or data.get("credits") or data.get("amount")
                if balance is not None:
                    balance_usd = float(balance) / 100.0 if float(balance) > 100 else float(balance)
                    return self._make_snapshot(
                        balance_usd=balance_usd,
                        remaining_credits=balance_usd,
                        raw_data=data,
                    )
        except Exception:
            pass

        # Fallback: scrape the billing page for balance text
        try:
            response = await client.get(CONSOLE_URL, headers=headers)
            if response.status_code in (401, 403):
                return self._error_snapshot(
                    "Session expired. Please update your session cookie from console.mistral.ai"
                )
            response.raise_for_status()

            # Try to find balance in page HTML
            html = response.text
            patterns = [
                r'\$\s*([\d,]+\.?\d*)',
                r'"balance":\s*([\d.]+)',
                r'"credits":\s*([\d.]+)',
                r'([\d,]+\.?\d*)\s*USD',
            ]
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    value_str = match.group(1).replace(',', '')
                    try:
                        balance_usd = float(value_str)
                        return self._make_snapshot(
                            balance_usd=balance_usd,
                            remaining_credits=balance_usd,
                            raw_data={"source": "page_scrape", "pattern": pattern},
                        )
                    except ValueError:
                        continue

            return self._error_snapshot(
                "Could not parse balance from Mistral console. "
                "The page structure may have changed."
            )

        except httpx.HTTPStatusError as e:
            return self._error_snapshot(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            return self._error_snapshot(f"Network error: {str(e)}")
        except Exception as e:
            return self._error_snapshot(f"Unexpected error: {str(e)}")
