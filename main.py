"""
AI Credits Tracker — Main FastAPI Application

Single-service deployment: FastAPI serves the API and the built React frontend
as static files. All Python source lives at repo root; the Railpack build step
compiles the frontend into ./frontend/dist before uvicorn starts.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from routers import credits, settings, health
from models.database import init_db
from scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info("Starting AI Credits Tracker...")
    await init_db()
    start_scheduler()
    yield
    logger.info("Shutting down AI Credits Tracker...")
    stop_scheduler()


app = FastAPI(
    title="AI Credits Tracker",
    description="Dashboard for monitoring cloud AI service balances and usage",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow localhost in development; in production the frontend is served
# by this same process so no cross-origin requests occur.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(credits.router, prefix="/api/credits", tags=["credits"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

# Serve React frontend static files (production build)
# main.py lives at repo root; frontend/dist is a sibling directory.
_HERE = Path(__file__).parent          # repo root
FRONTEND_DIST = _HERE / "frontend" / "dist"

if FRONTEND_DIST.exists():
    logger.info(f"Serving frontend from {FRONTEND_DIST}")
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve the React SPA for all non-API routes."""
        return FileResponse(str(FRONTEND_DIST / "index.html"))
else:
    logger.warning(
        f"Frontend dist not found at {FRONTEND_DIST}. "
        "API-only mode — run 'pnpm build' in /frontend to enable the dashboard."
    )
