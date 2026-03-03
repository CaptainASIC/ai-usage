"""
Gemini (Google AI Studio) provider.

Google AI Studio does not expose a credits/balance API for free-tier or
pay-as-you-go API keys. What IS available:
  - Quota status via the GCP Service Usage API (shows RPM/TPD limits)
  - Spend tracking via the GCP Cost Explorer (see the GCP cloud provider)

This provider validates the API key by making a lightweight models list
request and reports quota information where available.

Auth: GEMINI_API_KEY (from aistudio.google.com/app/apikey)
"""

import logging
import httpx
from models.schemas import BalanceSnapshot
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(BaseProvider):
    """Google Gemini (AI Studio) provider — quota and key validation."""

    provider_id   = "gemini"
    provider_name = "Gemini"
    auth_type     = "api_key"

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key)

    async def fetch_balance(self) -> BalanceSnapshot:
        if not self.is_configured():
            return self._unconfigured_snapshot()

        client = await self.get_client()
        api_key = self.credentials.api_key

        try:
            # Validate the key and get available models
            resp = await client.get(
                MODELS_ENDPOINT,
                params={"key": api_key, "pageSize": 5},
                timeout=10.0,
            )

            if resp.status_code == 401 or resp.status_code == 403:
                return self._error_snapshot(
                    f"Invalid or unauthorised API key (HTTP {resp.status_code}). "
                    "Generate a key at aistudio.google.com/app/apikey."
                )

            if resp.status_code == 429:
                return self._make_snapshot(
                    status="ok",
                    raw_data={
                        "note": "Rate limited — key is valid but quota exceeded",
                        "quota_status": "exceeded",
                    },
                )

            resp.raise_for_status()
            data = resp.json()
            model_count = len(data.get("models", []))

            return self._make_snapshot(
                status="ok",
                raw_data={
                    "note": (
                        "No balance endpoint — Gemini AI Studio does not expose "
                        "credit balance via API. Spend tracking requires GCP billing access."
                    ),
                    "key_valid": True,
                    "available_models": model_count,
                    "quota_status": "active",
                },
            )

        except httpx.TimeoutException:
            return self._error_snapshot("Request timed out reaching Gemini API.")
        except httpx.HTTPStatusError as exc:
            return self._error_snapshot(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return self._error_snapshot(f"Unexpected error: {exc}")
