"""
Settings router - endpoints for managing provider configurations and credentials.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config_manager import get_all_provider_configs, get_provider_config, save_provider_config
from models.schemas import ProviderConfig, ProviderConfigUpdate, ProviderCredentials
from providers import PROVIDER_REGISTRY

logger = logging.getLogger(__name__)
router = APIRouter()


class UpdateCredentialsRequest(BaseModel):
    """Request body for updating provider credentials."""
    credentials: dict[str, Any]
    enabled: bool = True
    refresh_interval: int | None = None


@router.get("/providers")
async def get_provider_settings():
    """Get all provider settings (credentials are masked)."""
    configs = await get_all_provider_configs()
    result = []

    for config in configs:
        meta = PROVIDER_REGISTRY.get(config.id, {})
        masked_creds = _mask_credentials(config.credentials)

        result.append({
            "id": config.id,
            "name": config.name,
            "category": meta.get("category", "ai"),
            "enabled": config.enabled,
            "auth_type": config.auth_type,
            "auth_fields": meta.get("auth_fields", []),
            "auth_help": meta.get("auth_help", ""),
            "credentials": masked_creds,
            "refresh_interval": config.refresh_interval,
            "tier": meta.get("tier", 2),
            "note": meta.get("note"),
        })

    return result


@router.put("/providers/{provider_id}")
async def update_provider_settings(provider_id: str, body: UpdateCredentialsRequest):
    """Update credentials and settings for a provider."""
    if provider_id not in PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

    meta = PROVIDER_REGISTRY[provider_id]
    existing = await get_provider_config(provider_id)

    # Merge new credentials with existing (don't overwrite with empty values)
    if existing:
        existing_creds = existing.credentials.model_dump()
    else:
        existing_creds = {}

    new_creds = {k: v for k, v in body.credentials.items() if v}  # filter empty strings
    merged_creds = {**existing_creds, **new_creds}

    config = ProviderConfig(
        id=provider_id,
        name=meta["name"],
        enabled=body.enabled,
        auth_type=meta["auth_type"],
        credentials=ProviderCredentials(**merged_creds),
        refresh_interval=body.refresh_interval or meta["refresh_interval"],
    )

    await save_provider_config(config)

    return {
        "message": f"Settings updated for {meta['name']}",
        "provider_id": provider_id,
        "enabled": config.enabled,
    }


@router.delete("/providers/{provider_id}/credentials")
async def clear_provider_credentials(provider_id: str):
    """Clear all credentials for a provider."""
    if provider_id not in PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

    meta = PROVIDER_REGISTRY[provider_id]
    config = ProviderConfig(
        id=provider_id,
        name=meta["name"],
        enabled=False,
        auth_type=meta["auth_type"],
        credentials=ProviderCredentials(),
        refresh_interval=meta["refresh_interval"],
    )
    await save_provider_config(config)

    return {"message": f"Credentials cleared for {meta['name']}"}


def _mask_credentials(creds: ProviderCredentials) -> dict:
    """Mask sensitive credential values for API responses.

    Reveals minimal characters to help users identify which key is configured:
    - <= 8 chars: fully masked
    - <= 16 chars: first 2 + last 2
    - > 16 chars: first 4 + last 4
    """
    result = {}
    for field, value in creds.model_dump().items():
        if value and isinstance(value, str):
            n = len(value)
            if n <= 8:
                result[field] = "***"
            elif n <= 16:
                result[field] = value[:2] + "..." + value[-2:]
            else:
                result[field] = value[:4] + "..." + value[-4:]
        else:
            result[field] = None
    return result
