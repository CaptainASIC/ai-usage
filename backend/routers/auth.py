"""
Auth router — login and auth status endpoints.
"""

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from auth import auth_enabled, protect_dashboard, create_token, verify_token

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Login rate limiting ───────────────────────────────────────────────────────
# 5 attempts per IP per 5-minute window.
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300
_login_attempts: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if the IP has exceeded the login attempt limit.

    Args:
        ip: Client IP address.

    Raises:
        HTTPException: If rate limit exceeded.
    """
    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS
    # Prune old attempts
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]
    if len(_login_attempts[ip]) >= _MAX_ATTEMPTS:
        logger.warning("Login rate limit exceeded for IP: %s", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )
    _login_attempts[ip].append(now)


class LoginRequest(BaseModel):
    """Login request body."""
    password: str


class LoginResponse(BaseModel):
    """Successful login response."""
    token: str


class AuthStatusResponse(BaseModel):
    """Auth status for the frontend to decide what to show."""
    auth_enabled: bool
    dashboard_protected: bool
    authenticated: bool


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request):
    """Authenticate with the dashboard password and receive a JWT."""
    if not auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is not enabled",
        )

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    token = create_token(body.password)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    return LoginResponse(token=token)


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request):
    """Check whether auth is enabled and whether the caller is authenticated."""
    authenticated = False

    if auth_enabled:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            authenticated = verify_token(token)

    return AuthStatusResponse(
        auth_enabled=auth_enabled,
        dashboard_protected=protect_dashboard,
        authenticated=authenticated,
    )
