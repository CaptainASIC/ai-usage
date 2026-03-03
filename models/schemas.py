"""
Pydantic v2 schemas for the AI Credits Tracker API.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ProviderCredentials(BaseModel):
    """Credentials for a provider. Fields vary by provider type."""
    api_key: Optional[str] = None
    admin_key: Optional[str] = None
    management_key: Optional[str] = None
    session_cookie: Optional[str] = None
    org_id: Optional[str] = None
    team_id: Optional[str] = None

    model_config = {"extra": "allow"}


class ProviderConfig(BaseModel):
    """Configuration for a single provider."""
    id: str
    name: str
    enabled: bool = True
    auth_type: str  # "api_key", "admin_key", "management_key", "session_cookie"
    credentials: ProviderCredentials = Field(default_factory=ProviderCredentials)
    refresh_interval: int = 300  # seconds


class ProviderConfigUpdate(BaseModel):
    """Update payload for provider configuration."""
    enabled: Optional[bool] = None
    credentials: Optional[ProviderCredentials] = None
    refresh_interval: Optional[int] = None


class BalanceSnapshot(BaseModel):
    """A point-in-time snapshot of a provider's balance."""
    provider_id: str
    provider_name: str
    balance_usd: Optional[float] = None
    total_credits: Optional[float] = None
    used_credits: Optional[float] = None
    remaining_credits: Optional[float] = None
    currency: str = "USD"
    status: str = "ok"  # "ok", "error", "unconfigured", "stale"
    error_message: Optional[str] = None
    fetched_at: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class DashboardResponse(BaseModel):
    """Full dashboard response with all provider balances."""
    providers: list[BalanceSnapshot]
    last_updated: datetime
    total_usd_balance: Optional[float] = None


class RefreshResponse(BaseModel):
    """Response after triggering a manual refresh."""
    message: str
    providers_refreshed: list[str]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "1.0.0"
    db_connected: bool = True
