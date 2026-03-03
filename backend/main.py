"""
AI Credits Tracker — FastAPI Backend

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
    logger.info("Starting AI Credits Tracker API...")
    await init_db()
    start_scheduler()
    yield
    logger.info("Shutting down AI Credits Tracker API...")
    stop_scheduler()


app = FastAPI(
    title="AI Credits Tracker API",
    description="Backend API for monitoring cloud AI service balances and usage",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow the frontend service URL plus local dev origins.
# Set FRONTEND_URL in Railway Variables to your frontend service domain.
_frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
_cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:4173",
]
if _frontend_url:
    _cors_origins.append(_frontend_url)
    # Also allow with and without trailing slash
    if _frontend_url.startswith("https://"):
        _cors_origins.append(_frontend_url.replace("https://", "http://"))

logger.info(f"CORS origins: {_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
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
        "service": "AI Credits Tracker API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
