"""
Background scheduler for auto-refreshing provider balances.
Uses APScheduler to periodically fetch balances from all configured providers.
"""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config_manager import get_all_provider_configs, save_balance_snapshot
from providers import PROVIDER_REGISTRY

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()
_last_refresh: dict[str, datetime] = {}


async def refresh_provider(provider_id: str) -> None:
    """Fetch and cache balance for a single provider."""
    try:
        from config_manager import get_provider_config
        config = await get_provider_config(provider_id)
        if not config or not config.enabled:
            return

        meta = PROVIDER_REGISTRY.get(provider_id)
        if not meta:
            return

        provider_class = meta["class"]
        provider = provider_class(config.credentials)

        logger.info(f"Refreshing balance for: {config.name}")
        snapshot = await provider.fetch_balance()
        await save_balance_snapshot(snapshot)

        _last_refresh[provider_id] = datetime.now(timezone.utc)
        logger.info(f"Balance refreshed for {config.name}: status={snapshot.status}")

    except Exception as e:
        logger.error(f"Error refreshing provider {provider_id}: {e}")


async def refresh_all_providers() -> None:
    """Refresh balances for all enabled providers."""
    configs = await get_all_provider_configs()
    tasks = [
        refresh_provider(config.id)
        for config in configs
        if config.enabled
    ]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def start_scheduler() -> None:
    """Start the background refresh scheduler."""
    # Run an initial refresh shortly after startup
    _scheduler.add_job(
        refresh_all_providers,
        trigger=IntervalTrigger(seconds=30),
        id="initial_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Background scheduler started")


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")


def get_last_refresh_times() -> dict[str, str]:
    """Get the last refresh time for each provider."""
    return {
        pid: ts.isoformat()
        for pid, ts in _last_refresh.items()
    }
