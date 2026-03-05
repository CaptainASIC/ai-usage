"""
Auth router — login and auth status endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from auth import auth_enabled, protect_dashboard, create_token, verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


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
async def login(body: LoginRequest):
    """Authenticate with the dashboard password and receive a JWT."""
    if not auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is not enabled",
        )

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
