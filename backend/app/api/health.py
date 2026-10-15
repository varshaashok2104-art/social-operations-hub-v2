import logging
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from app.core.database import check_database_connection
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    api: str
    database: str
    database_latency_ms: float | None = None
    environment: str
    error: str | None = None


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Distinguishes between API being alive and database connectivity.",
)
async def get_health(response: Response):
    is_db_connected, latency_ms, error_msg = await check_database_connection()

    if not is_db_connected:
        logger.warning("Database unreachable during health check: %s", error_msg)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            api="ok",
            database="unreachable",
            database_latency_ms=latency_ms,
            environment=settings.ENVIRONMENT,
            error="Database connection unavailable",
        )

    return HealthResponse(
        status="healthy",
        api="ok",
        database="connected",
        database_latency_ms=latency_ms,
        environment=settings.ENVIRONMENT,
        error=None,
    )
