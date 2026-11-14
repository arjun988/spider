"""Settings and LLM BYOK configuration endpoints (Gemini default, LiteLLM optional)."""

from __future__ import annotations

from typing import Literal

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
    """Kept name for API compatibility; covers Gemini + LiteLLM."""

    configured: bool
    api_key_masked: str | None
    api_key_validated: bool
    connection_status: str
    llm_provider: Literal["gemini", "litellm"] = "gemini"
    litellm_base_url: str | None = None
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
    llm_provider: Literal["gemini", "litellm"] | None = None
    litellm_base_url: str | None = None
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
    litellm_env_configured: bool = False
    llm_provider: str = "gemini"
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
    provider = app_settings.llm_provider
    config = ModelConfiguration(
        organization_id=org.id,
        llm_provider=provider,
        litellm_base_url=app_settings.litellm_base_url or None,
        primary_model=(
            app_settings.litellm_model if provider == "litellm" else app_settings.gemini_model
        ),
        embedding_model=(
            app_settings.litellm_embedding_model
            if provider == "litellm"
            else app_settings.gemini_embedding_model
        ),
        temperature=app_settings.gemini_temperature,
        max_output_tokens=app_settings.gemini_max_output_tokens,
        monthly_budget_usd=app_settings.monthly_budget_usd,
    )
    bootstrap_key = (
        app_settings.litellm_api_key if provider == "litellm" else app_settings.gemini_api_key
    )
    if bootstrap_key:
        config.encrypted_api_key = encrypt_value(bootstrap_key)
        config.api_key_last_four = bootstrap_key[-4:]
        config.connection_status = "connected"
        config.api_key_validated = False
    db.add(config)
    db.flush()
    return config


def _config_to_out(db: Session, config: ModelConfiguration) -> GeminiConfigOut:
    provider = (config.llm_provider or "gemini").lower()
    if provider not in {"gemini", "litellm"}:
        provider = "gemini"
    configured = bool(config.encrypted_api_key) or (
        provider == "litellm" and bool(config.litellm_base_url)
    )
    return GeminiConfigOut(
        configured=configured,
        api_key_masked=mask_secret(f"****{config.api_key_last_four}") if config.api_key_last_four else None,
        api_key_validated=config.api_key_validated,
        connection_status=config.connection_status,
        llm_provider=provider,  # type: ignore[arg-type]
        litellm_base_url=config.litellm_base_url,
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
        litellm_env_configured=app_settings.litellm_configured,
        llm_provider=app_settings.llm_provider,
        app_env=app_settings.app_env,
        app_name=app_settings.app_name,
    )


def _get_config(db: Session) -> GeminiConfigOut:
    org = _ensure_default_org(db)
    config = _get_or_create_config(db, org)
    return _config_to_out(db, config)


@router.get("/gemini", response_model=GeminiConfigOut)
@router.get("/llm", response_model=GeminiConfigOut)
def get_llm_config(db: Session = Depends(get_sync_db)) -> GeminiConfigOut:
    return _get_config(db)


@router.put("/gemini", response_model=GeminiConfigOut)
@router.put("/llm", response_model=GeminiConfigOut)
def update_llm_config(
    body: GeminiConfigUpdate,
    db: Session = Depends(get_sync_db),
    _: None = Depends(require_admin_token),
) -> GeminiConfigOut:
    org = _ensure_default_org(db)
    config = _get_or_create_config(db, org)

    if body.llm_provider is not None:
        config.llm_provider = body.llm_provider
    if body.litellm_base_url is not None:
        url = body.litellm_base_url.strip()
        config.litellm_base_url = url or None

    provider = (body.llm_provider or config.llm_provider or "gemini").lower()

    if body.api_key is not None:
        key = body.api_key.strip()
        if key:
            if provider == "gemini" and len(key) < 20:
                raise HTTPException(status_code=400, detail="API key appears invalid")
            if body.validate_key:
                try:
                    from app.services.llm_client import validate_connection

                    model = body.primary_model or config.primary_model
                    base = body.litellm_base_url if body.litellm_base_url is not None else config.litellm_base_url
                    ok, detail = validate_connection(
                        provider=provider,  # type: ignore[arg-type]
                        api_key=key,
                        model=model,
                        litellm_base_url=base,
                    )
                    if not ok:
                        config.connection_status = "invalid"
                        label = "LiteLLM" if provider == "litellm" else "Gemini"
                        raise HTTPException(
                            status_code=400,
                            detail=f"{label} validation failed ({model}): {detail}",
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
            # Empty string clears key (LiteLLM may still work with local proxy + no key)
            config.encrypted_api_key = None
            config.api_key_last_four = None
            if provider == "litellm" and (config.litellm_base_url or body.litellm_base_url):
                config.connection_status = "connected"
            else:
                config.connection_status = "not_configured"
            config.api_key_validated = False

    # Switching to LiteLLM with base URL but no key change — validate connectivity optionally
    if (
        provider == "litellm"
        and body.validate_key
        and body.api_key is None
        and (body.litellm_base_url is not None or body.llm_provider == "litellm")
        and config.litellm_base_url
    ):
        from app.core.encryption import decrypt_value
        from app.services.llm_client import validate_connection

        existing_key = decrypt_value(config.encrypted_api_key) if config.encrypted_api_key else ""
        model = body.primary_model or config.primary_model
        ok, detail = validate_connection(
            provider="litellm",
            api_key=existing_key,
            model=model,
            litellm_base_url=config.litellm_base_url,
        )
        config.api_key_validated = ok
        config.connection_status = "connected" if ok else "invalid"
        if not ok:
            raise HTTPException(status_code=400, detail=f"LiteLLM validation failed ({model}): {detail}")

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
@router.post("/llm/validate")
def validate_llm(db: Session = Depends(get_sync_db)) -> dict:
    org = _ensure_default_org(db)
    config = _get_or_create_config(db, org)
    provider = (config.llm_provider or "gemini").lower()
    if provider == "gemini" and not config.encrypted_api_key:
        raise HTTPException(status_code=400, detail="No API key configured")
    if provider == "litellm" and not config.litellm_base_url:
        raise HTTPException(status_code=400, detail="LiteLLM base URL not configured")

    from app.core.encryption import decrypt_value
    from app.services.llm_client import validate_connection

    key = decrypt_value(config.encrypted_api_key) if config.encrypted_api_key else ""
    try:
        ok, detail = validate_connection(
            provider=provider,  # type: ignore[arg-type]
            api_key=key,
            model=config.primary_model,
            litellm_base_url=config.litellm_base_url,
        )
        config.api_key_validated = ok
        config.connection_status = "connected" if ok else "invalid"
        db.flush()
        return {
            "valid": ok,
            "provider": provider,
            "connection_status": config.connection_status,
            "detail": detail,
        }
    except Exception as exc:
        config.connection_status = "error"
        db.flush()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
