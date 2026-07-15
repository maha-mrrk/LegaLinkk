"""Health-check endpoint."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app import __version__
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service status and database connectivity.",
)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Verify that the API and its database dependency are reachable."""
    db_status = "connected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        db_status = "unavailable"

    overall = "ok" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
        database=db_status,
    )
