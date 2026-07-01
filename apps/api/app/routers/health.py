from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Zero I/O — must not touch Postgres/ClickHouse/Redis."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": "0.1.0",
    }
