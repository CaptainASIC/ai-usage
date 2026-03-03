"""
Credits router - endpoints for fetching and refreshing provider balances.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config_manager import (
    get_all_provider_configs,
    get_provider_config,
    get_latest_snapshots,
    save_balance_snapshot,
)
from models.schemas import BalanceSnapshot, DashboardResponse, RefreshResponse
from providers import PROVIDER_REGISTRY
from scheduler import refresh_provider, refresh_all_providers, get_last_refresh_times

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=DashboardResponse)
async def get_dashboard():
    """
    Get the current balance dashboard for all providers.
    Returns cached snapshots; use /refresh to force a live fetch.
    """
    configs = await get_all_provider_configs()
    config_map = {c.id: c for c in configs}

    # Get cached snapshots from DB
    cached = await get_latest_snapshots()
    cached_map = {row["provider_id"]: row for row in cached}

    snapshots = []
    total_usd = 0.0
    has_balance = False

    for provider_id, meta in PROVIDER_REGISTRY.items():
        config = config_map.get(provider_id)
        name = meta["name"]
        category = meta.get("category", "ai")

        if provider_id in cached_map:
            row = cached_map[provider_id]
            raw_data = None
            if row.get("raw_data"):
                try:
                    raw_data = json.loads(row["raw_data"])
                except Exception:
                    pass

            snapshot = BalanceSnapshot(
                provider_id=provider_id,
                provider_name=name,
                category=category,
                balance_usd=row.get("balance_usd"),
                total_credits=row.get("total_credits"),
                used_credits=row.get("used_credits"),
                remaining_credits=row.get("remaining_credits"),
                currency=row.get("currency", "USD"),
                status=row.get("status", "ok"),
                error_message=row.get("error_message"),
                fetched_at=datetime.fromisoformat(row["fetched_at"]) if row.get("fetched_at") else None,
                raw_data=raw_data,
            )
        elif config and not config.enabled:
            snapshot = BalanceSnapshot(
                provider_id=provider_id,
                provider_name=name,
                category=category,
                status="disabled",
                error_message="Provider is disabled",
            )
        else:
            snapshot = BalanceSnapshot(
                provider_id=provider_id,
                provider_name=name,
                category=category,
                status="unconfigured",
                error_message="No credentials configured",
            )

        snapshots.append(snapshot)

        if snapshot.balance_usd is not None and snapshot.status == "ok":
            total_usd += snapshot.balance_usd
            has_balance = True

    return DashboardResponse(
        providers=snapshots,
        last_updated=datetime.now(timezone.utc),
        total_usd_balance=round(total_usd, 2) if has_balance else None,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_all():
    """Trigger a live refresh of all enabled providers."""
    configs = await get_all_provider_configs()
    enabled = [c.id for c in configs if c.enabled]

    await refresh_all_providers()

    return RefreshResponse(
        message=f"Refreshed {len(enabled)} providers",
        providers_refreshed=enabled,
    )


@router.post("/refresh/{provider_id}", response_model=BalanceSnapshot)
async def refresh_single(provider_id: str):
    """Trigger a live refresh for a single provider and return the result."""
    if provider_id not in PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

    config = await get_provider_config(provider_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Provider not configured: {provider_id}")

    meta = PROVIDER_REGISTRY[provider_id]
    provider_class = meta["class"]
    provider = provider_class(config.credentials)

    snapshot = await provider.fetch_balance()
    await save_balance_snapshot(snapshot)

    return snapshot


@router.get("/providers")
async def list_providers():
    """List all available providers with their metadata and configuration status."""
    configs = await get_all_provider_configs()
    config_map = {c.id: c for c in configs}
    last_refresh = get_last_refresh_times()

    result = []
    for provider_id, meta in PROVIDER_REGISTRY.items():
        config = config_map.get(provider_id)
        provider_class = meta["class"]

        is_configured = False
        if config:
            provider = provider_class(config.credentials)
            is_configured = provider.is_configured()

        result.append({
            "id": provider_id,
            "name": meta["name"],
            "category": meta.get("category", "ai"),
            "auth_type": meta["auth_type"],
            "auth_fields": meta["auth_fields"],
            "auth_help": meta["auth_help"],
            "tier": meta["tier"],
            "note": meta.get("note"),
            "enabled": config.enabled if config else True,
            "is_configured": is_configured,
            "refresh_interval": meta["refresh_interval"],
            "last_refresh": last_refresh.get(provider_id),
        })

    return result
