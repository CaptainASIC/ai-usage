"""
Base provider class for AI service credit fetchers.
All providers inherit from this and implement fetch_balance().
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import httpx

from models.schemas import BalanceSnapshot, ProviderCredentials

logger = logging.getLogger(__name__)

# Default HTTP timeout for all provider requests
DEFAULT_TIMEOUT = 15.0


class BaseProvider(ABC):
    """Abstract base class for all AI credit providers."""

    provider_id: str = ""
    provider_name: str = ""
    auth_type: str = "api_key"

    def __init__(self, credentials: ProviderCredentials):
        self.credentials = credentials
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create an async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @abstractmethod
    async def fetch_balance(self) -> BalanceSnapshot:
        """Fetch the current balance from the provider API."""
        ...

    def is_configured(self) -> bool:
        """Check if the provider has the required credentials."""
        return True

    def _make_snapshot(
        self,
        balance_usd: Optional[float] = None,
        total_credits: Optional[float] = None,
        used_credits: Optional[float] = None,
        remaining_credits: Optional[float] = None,
        currency: str = "USD",
        status: str = "ok",
        error_message: Optional[str] = None,
        raw_data: Optional[dict] = None,
    ) -> BalanceSnapshot:
        """Helper to create a BalanceSnapshot."""
        return BalanceSnapshot(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            balance_usd=balance_usd,
            total_credits=total_credits,
            used_credits=used_credits,
            remaining_credits=remaining_credits,
            currency=currency,
            status=status,
            error_message=error_message,
            fetched_at=datetime.now(timezone.utc),
            raw_data=raw_data,
        )

    def _error_snapshot(self, message: str) -> BalanceSnapshot:
        """Create an error snapshot."""
        logger.error(f"[{self.provider_name}] Error: {message}")
        return self._make_snapshot(status="error", error_message=message)

    def _unconfigured_snapshot(self) -> BalanceSnapshot:
        """Create an unconfigured snapshot when credentials are missing."""
        return self._make_snapshot(
            status="unconfigured",
            error_message="API key or credentials not configured",
        )
