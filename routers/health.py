"""
Health check router.
"""

from fastapi import APIRouter
from models.schemas import HealthResponse
from models.database import get_db

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Railway and monitoring."""
    db_ok = True
    try:
        async with get_db() as db:
            await db.execute("SELECT 1")
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version="1.0.0",
        db_connected=db_ok,
    )
