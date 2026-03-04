"""
Reckoner — FastAPI Backend

Split deployment: this service provides the API only.
The React frontend is a separate Railway service.
CORS origins are configured via the FRONTEND_URL environment variable.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import credits, settings, health
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


app = FastAPI(
    title="Reckoner API",
    description="Backend API for monitoring cloud AI service balances and usage",
    version="2.0.0",
    lifespan=lifespan,
    redirect_slashes=False,  # Prevent 301 redirects that break fetch() calls
)

# CORS — personal dashboard, allow all origins by default.
# Optionally restrict by setting FRONTEND_URL or ALLOWED_ORIGINS in Railway Variables
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
else:
    # No restriction set — allow all origins (safe for personal dashboards)
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

# API routes
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(credits.router, prefix="/api/credits", tags=["credits"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "Reckoner API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
