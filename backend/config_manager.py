"""
Configuration manager for provider settings.
Reads/writes provider configs to SQLite and environment variables.
Credentials are stored encrypted in the database.
"""

import json
import logging
import os
from typing import Optional

import aiosqlite

from models.database import get_db
from models.schemas import ProviderConfig, ProviderCredentials
from providers import PROVIDER_REGISTRY

logger = logging.getLogger(__name__)


async def get_all_provider_configs() -> list[ProviderConfig]:
    """Get all provider configurations, merging DB settings with env var defaults."""
    configs = []

    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM provider_configs") as cursor:
            rows = {row["id"]: row async for row in cursor}

    for provider_id, meta in PROVIDER_REGISTRY.items():
        if provider_id in rows:
            row = rows[provider_id]
            try:
                creds_data = json.loads(row["credentials"])
                credentials = ProviderCredentials(**creds_data)
            except Exception:
                credentials = ProviderCredentials()

            configs.append(ProviderConfig(
                id=provider_id,
                name=meta["name"],
                enabled=bool(row["enabled"]),
                auth_type=meta["auth_type"],
                credentials=credentials,
                refresh_interval=row["refresh_interval"],
            ))
        else:
            # Load from environment variables as defaults
            credentials = _load_credentials_from_env(provider_id)
            configs.append(ProviderConfig(
                id=provider_id,
                name=meta["name"],
                enabled=True,
                auth_type=meta["auth_type"],
                credentials=credentials,
                refresh_interval=meta["refresh_interval"],
            ))

    return configs


async def get_provider_config(provider_id: str) -> Optional[ProviderConfig]:
    """Get configuration for a specific provider."""
    configs = await get_all_provider_configs()
    return next((c for c in configs if c.id == provider_id), None)


async def save_provider_config(config: ProviderConfig) -> None:
    """Save provider configuration to the database."""
    creds_json = config.credentials.model_dump_json()

    async with get_db() as db:
        await db.execute("""
            INSERT INTO provider_configs (id, name, enabled, auth_type, credentials, refresh_interval, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                enabled = excluded.enabled,
                credentials = excluded.credentials,
                refresh_interval = excluded.refresh_interval,
                updated_at = excluded.updated_at
        """, (
            config.id,
            config.name,
            int(config.enabled),
            config.auth_type,
            creds_json,
            config.refresh_interval,
        ))
        await db.commit()
    logger.info(f"Saved config for provider: {config.id}")


async def save_balance_snapshot(snapshot) -> None:
    """Persist a balance snapshot to the database."""
    raw_json = json.dumps(snapshot.raw_data) if snapshot.raw_data else None
    fetched_at = snapshot.fetched_at.isoformat() if snapshot.fetched_at else None

    async with get_db() as db:
        await db.execute("""
            INSERT INTO balance_snapshots
                (provider_id, balance_usd, total_credits, used_credits, remaining_credits,
                 currency, raw_data, status, error_message, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.provider_id,
            snapshot.balance_usd,
            snapshot.total_credits,
            snapshot.used_credits,
            snapshot.remaining_credits,
            snapshot.currency,
            raw_json,
            snapshot.status,
            snapshot.error_message,
            fetched_at,
        ))
        await db.commit()


async def get_latest_snapshots() -> list[dict]:
    """Get the most recent snapshot for each provider."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT bs.*
            FROM balance_snapshots bs
            INNER JOIN (
                SELECT provider_id, MAX(fetched_at) as max_time
                FROM balance_snapshots
                GROUP BY provider_id
            ) latest ON bs.provider_id = latest.provider_id
                      AND bs.fetched_at = latest.max_time
        """) as cursor:
            return [dict(row) async for row in cursor]


# Railway injects its own env vars (RAILWAY_API_KEY, RAILWAY_TOKEN, RAILWAY_SERVICE_ID, etc.)
# into every service. We use a custom prefix to avoid collisions.
_PROVIDER_ENV_OVERRIDES: dict[str, dict[str, str]] = {
    "railway": {
        # Use RAILWAY_CREDIT_TOKEN to avoid collision with Railway's own injected RAILWAY_API_KEY
        "api_key": "RAILWAY_CREDIT_TOKEN",
    },
}


def _load_credentials_from_env(provider_id: str) -> ProviderCredentials:
    """Load provider credentials from environment variables."""
    prefix = provider_id.upper().replace("-", "_")
    overrides = _PROVIDER_ENV_OVERRIDES.get(provider_id, {})

    def _get(field: str, default_var: str) -> Optional[str]:
        """Get env var, using override name if defined."""
        var_name = overrides.get(field, default_var)
        return os.getenv(var_name)

    return ProviderCredentials(
        api_key=_get("api_key", f"{prefix}_API_KEY"),
        admin_key=_get("admin_key", f"{prefix}_ADMIN_KEY"),
        management_key=_get("management_key", f"{prefix}_MANAGEMENT_KEY"),
        session_cookie=_get("session_cookie", f"{prefix}_SESSION_COOKIE"),
        org_id=_get("org_id", f"{prefix}_ORG_ID"),
        team_id=_get("team_id", f"{prefix}_TEAM_ID"),
        api_secret=(
            _get("api_secret", f"{prefix}_SECRET_ACCESS_KEY")
            or os.getenv(f"{prefix}_API_SECRET")
        ),
    )
