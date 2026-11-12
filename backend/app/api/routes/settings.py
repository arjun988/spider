"""Settings and Gemini BYOK configuration endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import settings as app_settings
from app.core.encryption import encrypt_value, mask_secret
from app.models.organization import Organization
from app.models.settings import ModelConfiguration

router = APIRouter(prefix="/settings", tags=["settings"])


class GeminiConfigOut(BaseModel):
    configured: bool
    api_key_masked: str | None
    api_key_validated: bool
    connection_status: str
    primary_model: str
    embedding_model: str
    temperature: float
    max_output_tokens: int
    auto_review_enabled: bool
    severity_threshold: str
    confidence_threshold: float
    max_files_per_review: int
    context_retrieval_limit: int
    monthly_budget_usd: float


class GeminiConfigUpdate(BaseModel):
    api_key: str | None = None
    primary_model: str | None = None
    embedding_model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=256, le=65536)
    auto_review_enabled: bool | None = None
    severity_threshold: str | None = None
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    max_files_per_review: int | None = Field(default=None, ge=1, le=500)
    context_retrieval_limit: int | None = Field(default=None, ge=1, le=100)
    monthly_budget_usd: float | None = Field(default=None, ge=0.0)


class SystemStatusOut(BaseModel):
    github_app_configured: bool
    github_app_id: str | None
    gemini_env_configured: bool
    app_env: str
    app_name: str


async def _ensure_default_org(db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if org:
        return org
    org = Organization(name="Default", slug="default")
    db.add(org)
    await db.flush()
    return org


async def _get_or_create_config(db: AsyncSession, org: Organization) -> ModelConfiguration:
    result = await db.execute(
        select(ModelConfiguration).where(ModelConfiguration.organization_id == org.id)
    )
    config = result.scalar_one_or_none()
    if config:
        return config
    config = ModelConfiguration(
        organization_id=org.id,
        primary_model=app_settings.gemini_model,
        embedding_model=app_settings.gemini_embedding_model,
        temperature=app_settings.gemini_temperature,
        max_output_tokens=app_settings.gemini_max_output_tokens,
        monthly_budget_usd=app_settings.monthly_budget_usd,
    )
    if app_settings.gemini_api_key:
        config.encrypted_api_key = encrypt_value(app_settings.gemini_api_key)
        config.api_key_last_four = app_settings.gemini_api_key[-4:]
        config.connection_status = "connected"
        config.api_key_validated = False  # validated on explicit save/validate
    db.add(config)
    await db.flush()
    return config


def _config_to_out(config: ModelConfiguration) -> GeminiConfigOut:
    return GeminiConfigOut(
        configured=bool(config.encrypted_api_key),
        api_key_masked=mask_secret(f"****{config.api_key_last_four}") if config.api_key_last_four else None,
        api_key_validated=config.api_key_validated,
        connection_status=config.connection_status,
        primary_model=config.primary_model,
        embedding_model=config.embedding_model,
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        auto_review_enabled=config.auto_review_enabled,
        severity_threshold=config.severity_threshold,
        confidence_threshold=config.confidence_threshold,
        max_files_per_review=config.max_files_per_review,
        context_retrieval_limit=config.context_retrieval_limit,
        monthly_budget_usd=config.monthly_budget_usd,
    )


@router.get("/system", response_model=SystemStatusOut)
async def system_status() -> SystemStatusOut:
    return SystemStatusOut(
        github_app_configured=app_settings.github_app_configured,
        github_app_id=app_settings.github_app_id or None,
        gemini_env_configured=app_settings.gemini_configured,
        app_env=app_settings.app_env,
        app_name=app_settings.app_name,
    )


@router.get("/gemini", response_model=GeminiConfigOut)
async def get_gemini_config(db: AsyncSession = Depends(get_db_session)) -> GeminiConfigOut:
    org = await _ensure_default_org(db)
    config = await _get_or_create_config(db, org)
    return _config_to_out(config)


@router.put("/gemini", response_model=GeminiConfigOut)
async def update_gemini_config(
    body: GeminiConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> GeminiConfigOut:
    org = await _ensure_default_org(db)
    config = await _get_or_create_config(db, org)

    if body.api_key is not None:
        key = body.api_key.strip()
        if key:
            # Validate key format; full live validation in Phase 6
            if len(key) < 20:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API key appears invalid",
                )
            config.encrypted_api_key = encrypt_value(key)
            config.api_key_last_four = key[-4:]
            config.connection_status = "connected"
            config.api_key_validated = True
        else:
            config.encrypted_api_key = None
            config.api_key_last_four = None
            config.connection_status = "not_configured"
            config.api_key_validated = False

    for field in (
        "primary_model",
        "embedding_model",
        "temperature",
        "max_output_tokens",
        "auto_review_enabled",
        "severity_threshold",
        "confidence_threshold",
        "max_files_per_review",
        "context_retrieval_limit",
        "monthly_budget_usd",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(config, field, value)

    await db.flush()
    return _config_to_out(config)