"""Settings and Gemini BYOK configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.github import get_sync_db
from app.core.config import settings as app_settings
from app.core.encryption import encrypt_value, mask_secret
from app.core.security import require_admin_token
from app.models.organization import Organization
from app.models.settings import ModelConfiguration
from app.services.cost_service import budget_remaining

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
    budget: dict | None = None


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
    validate_key: bool = True


class SystemStatusOut(BaseModel):
    github_app_configured: bool
    github_app_id: str | None
    gemini_env_configured: bool
    app_env: str
    app_name: str


def _ensure_default_org(db: Session) -> Organization:
    """Prefer a GitHub-linked org so BYOK settings apply to real reviews."""
    org = db.execute(
        select(Organization)
        .where(Organization.github_org_id.is_not(None))
        .order_by(Organization.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    if org:
        return org
    org = db.execute(
        select(Organization).where(Organization.slug != "default").limit(1)
    ).scalar_one_or_none()
    if org:
        return org
    org = db.execute(select(Organization).limit(1)).scalar_one_or_none()
    if org:
        return org
    org = Organization(name="Default", slug="default")
    db.add(org)
    db.flush()
    return org


def _get_or_create_config(db: Session, org: Organization) -> ModelConfiguration:
    config = db.execute(
        select(ModelConfiguration).where(ModelConfiguration.organization_id == org.id)
    ).scalar_one_or_none()
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
        config.api_key_validated = False
    db.add(config)
    db.flush()
    return config


def _config_to_out(db: Session, config: ModelConfiguration) -> GeminiConfigOut:
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
        budget=budget_remaining(db, config.organization_id),
    )


@router.get("/system", response_model=SystemStatusOut)
def system_status() -> SystemStatusOut:
    return SystemStatusOut(
        github_app_configured=app_settings.github_app_configured,
        github_app_id=app_settings.github_app_id or None,
        gemini_env_configured=app_settings.gemini_configured,
        app_env=app_settings.app_env,
        app_name=app_settings.app_name,
    )


@router.get("/gemini", response_model=GeminiConfigOut)
def get_gemini_config(db: Session = Depends(get_sync_db)) -> GeminiConfigOut:
    org = _ensure_default_org(db)
    config = _get_or_create_config(db, org)
    return _config_to_out(db, config)


@router.put("/gemini", response_model=GeminiConfigOut)
def update_gemini_config(
    body: GeminiConfigUpdate,
    db: Session = Depends(get_sync_db),
    _: None = Depends(require_admin_token),
) -> GeminiConfigOut:
    org = _ensure_default_org(db)
    config = _get_or_create_config(db, org)

    if body.api_key is not None:
        key = body.api_key.strip()
        if key:
            if len(key) < 20:
                raise HTTPException(status_code=400, detail="API key appears invalid")
            if body.validate_key:
                try:
                    from app.services.gemini_client import validate_api_key

                    model = body.primary_model or config.primary_model or app_settings.gemini_model
                    ok, detail = validate_api_key(key, model)
                    if not ok:
                        config.connection_status = "invalid"
                        raise HTTPException(
                            status_code=400,
                            detail=f"Gemini API key validation failed ({model}): {detail}",
                        )
                    config.api_key_validated = True
                    config.connection_status = "connected"
                except HTTPException:
                    raise
                except Exception as exc:
                    config.connection_status = "error"
                    raise HTTPException(status_code=400, detail=f"Key validation error: {exc}") from exc
            config.encrypted_api_key = encrypt_value(key)
            config.api_key_last_four = key[-4:]
            if not body.validate_key:
                config.connection_status = "connected"
                config.api_key_validated = False
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

    db.flush()
    return _config_to_out(db, config)


@router.post("/gemini/validate")
def validate_gemini(db: Session = Depends(get_sync_db)) -> dict:
    org = _ensure_default_org(db)
    config = _get_or_create_config(db, org)
    if not config.encrypted_api_key:
        raise HTTPException(status_code=400, detail="No API key configured")
    from app.core.encryption import decrypt_value
    from app.services.gemini_client import validate_api_key

    try:
        ok, detail = validate_api_key(
            decrypt_value(config.encrypted_api_key),
            config.primary_model or app_settings.gemini_model,
        )
        config.api_key_validated = ok
        config.connection_status = "connected" if ok else "invalid"
        db.flush()
        return {"valid": ok, "connection_status": config.connection_status, "detail": detail}
    except Exception as exc:
        config.connection_status = "error"
        db.flush()
        raise HTTPException(status_code=400, detail=str(exc)) from exc