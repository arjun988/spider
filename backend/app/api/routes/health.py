"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.api.deps import get_db_session
from app.core.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    app: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    redis: str
    github_app_configured: bool
    gemini_configured: bool


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        app=settings.app_name,
        environment=settings.app_env,
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(db: AsyncSession = Depends(get_db_session)) -> ReadinessResponse:
    db_status = "ok"
    redis_status = "unknown"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        await client.ping()
        await client.aclose()
        redis_status = "ok"
    except Exception:
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return ReadinessResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        github_app_configured=settings.github_app_configured,
        gemini_configured=settings.gemini_configured,
    )