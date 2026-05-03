"""Health and observability endpoints."""
import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.queue import get_signal_queue
from app.db.connections import AsyncSessionFactory, get_mongo_db, get_redis
from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="System health check")
async def health_check():
    queue = get_signal_queue(settings.queue_max_size)
    services: dict[str, str] = {}

    # PostgreSQL
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception as e:
        services["postgres"] = f"error: {e}"

    # MongoDB
    try:
        db = get_mongo_db()
        await db.command("ping")
        services["mongodb"] = "ok"
    except Exception as e:
        services["mongodb"] = f"error: {e}"

    # Redis
    try:
        redis = get_redis()
        await redis.ping()
        services["redis"] = "ok"
    except Exception as e:
        services["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in services.values())

    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        environment=settings.environment,
        queue_size=queue.qsize(),
        queue_capacity=queue.maxsize,
        services=services,
    )
