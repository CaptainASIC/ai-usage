"""
Authentication module for Reckoner.

Single-user password auth controlled by environment variables:
- RECKONER_PASSWORD: when set, auth is enabled; when empty/unset, auth is disabled.
- RECKONER_PROTECT_DASHBOARD: "true" (default) or "false". When true, viewing
  balances also requires login. When false, only settings mutations require login.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

_PASSWORD: str = os.getenv("RECKONER_PASSWORD", "").strip()
_PROTECT_DASHBOARD: bool = os.getenv("RECKONER_PROTECT_DASHBOARD", "true").strip().lower() in (
    "true", "1", "yes",
)

auth_enabled: bool = bool(_PASSWORD)
protect_dashboard: bool = _PROTECT_DASHBOARD

# Random signing key — tokens invalidate on redeploy (acceptable for single-user).
_JWT_SECRET: str = secrets.token_hex(32)
_JWT_ALGORITHM: str = "HS256"
_JWT_EXPIRY_DAYS: int = 30

if auth_enabled:
    logger.info("Auth enabled (dashboard protection: %s)", "on" if protect_dashboard else "off")
else:
    logger.info("Auth disabled — no RECKONER_PASSWORD set")


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_token(password: str) -> Optional[str]:
    """Validate password and return a signed JWT, or None on mismatch."""
    if not auth_enabled:
        return None

    # Constant-time comparison to prevent timing attacks.
    if not secrets.compare_digest(password, _PASSWORD):
        return None

    payload = {
        "sub": "reckoner",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=_JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_token(token: str) -> bool:
    """Return True if the token is valid and not expired."""
    try:
        jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return True
    except jwt.PyJWTError:
        return False


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def _extract_token(request: Request) -> Optional[str]:
    """Extract bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def require_auth(request: Request) -> None:
    """Dependency: require valid auth when auth is enabled.

    Used on settings routes — mutations are never anonymous.
    """
    if not auth_enabled:
        return

    token = _extract_token(request)
    if not token or not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_auth_if_protected(request: Request) -> None:
    """Dependency: require valid auth only when dashboard protection is on.

    Used on credits/dashboard routes.
    """
    if not auth_enabled or not protect_dashboard:
        return

    token = _extract_token(request)
    if not token or not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
