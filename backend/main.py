"""
Reckoner — FastAPI Backend

Split deployment: this service provides the API only.
The React frontend is a separate Railway service.
CORS origins are configured via the FRONTEND_URL environment variable.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from auth import auth_enabled, require_auth, require_auth_if_protected
from routers import auth, credits, settings, health
from models.database import init_db
from scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info("Starting Reckoner API...")
    await init_db()
    start_scheduler()
    yield
    logger.info("Shutting down Reckoner API...")
    stop_scheduler()


# Disable interactive API docs when auth is enabled (production).
_is_production = auth_enabled or os.getenv("ENVIRONMENT", "").lower() == "production"

app = FastAPI(
    title="Reckoner API",
    description="Backend API for monitoring cloud AI service balances and usage",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,  # Prevent 301 redirects that break fetch() calls
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# CORS — restrict origins in production, allow wildcard only for local dev.
# Set FRONTEND_URL or ALLOWED_ORIGINS in Railway Variables
# (comma-separated list of origins, e.g. "https://reckoner.captainasic.dev").
_allowed_origins_env = (
    os.getenv("ALLOWED_ORIGINS", "")
    or os.getenv("FRONTEND_URL", "")
).strip()

if _allowed_origins_env:
    # Parse comma-separated list and add localhost dev origins
    _cors_origins = [
        o.strip().rstrip("/")
        for o in _allowed_origins_env.split(",")
        if o.strip()
    ]
    _cors_origins += [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:4173",
    ]
    _use_wildcard = False
elif auth_enabled:
    # Auth is on but no origins configured — log a warning and restrict to localhost only.
    logger.warning("Auth is enabled but ALLOWED_ORIGINS is not set — restricting CORS to localhost")
    _cors_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:4173",
    ]
    _use_wildcard = False
else:
    # No auth, no origins — local dev mode, allow all origins.
    _cors_origins = ["*"]
    _use_wildcard = True

logger.info(f"CORS mode: {'wildcard' if _use_wildcard else 'restricted'}, origins: {_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not _use_wildcard,  # credentials=True incompatible with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers on every response.
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        """Process request and add security headers to response."""
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# API routes
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(
    credits.router,
    prefix="/api/credits",
    tags=["credits"],
    dependencies=[Depends(require_auth_if_protected)],
)
app.include_router(
    settings.router,
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_auth)],
)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "Reckoner API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
