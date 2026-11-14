"""Unified LLM facade — Gemini (default) or LiteLLM provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_value
from app.core.logging import get_logger
from app.models.settings import ModelConfiguration

logger = get_logger(__name__)

Provider = Literal["gemini", "litellm"]


@dataclass
class LlmRuntimeConfig:
    provider: Provider
    api_key: str
    primary_model: str
    embedding_model: str
    temperature: float
    max_output_tokens: int
    organization_id: Any | None = None
    litellm_base_url: str | None = None


def resolve_llm_config(db: Session | None = None, organization_id=None) -> LlmRuntimeConfig:
    if db is not None:
        q = db.query(ModelConfiguration)
        if organization_id:
            q = q.filter(ModelConfiguration.organization_id == organization_id)
        config = q.first()
        if config:
            provider: Provider = (config.llm_provider or "gemini").lower()  # type: ignore[assignment]
            if provider not in {"gemini", "litellm"}:
                provider = "gemini"

            if provider == "litellm":
                key = (
                    decrypt_value(config.encrypted_api_key)
                    if config.encrypted_api_key
                    else (settings.litellm_api_key or "")
                )
                base = config.litellm_base_url or settings.litellm_base_url
                if not base:
                    raise ValueError(
                        "LiteLLM base URL not configured. Set LITELLM_BASE_URL or save it in Settings."
                    )
                if not key and not settings.litellm_api_key:
                    # Some LiteLLM proxies allow empty key for local use
                    key = ""
                return LlmRuntimeConfig(
                    provider="litellm",
                    api_key=key,
                    primary_model=config.primary_model or settings.litellm_model,
                    embedding_model=config.embedding_model or settings.litellm_embedding_model,
                    temperature=config.temperature,
                    max_output_tokens=config.max_output_tokens,
                    organization_id=config.organization_id,
                    litellm_base_url=base,
                )

            if config.encrypted_api_key:
                return LlmRuntimeConfig(
                    provider="gemini",
                    api_key=decrypt_value(config.encrypted_api_key),
                    primary_model=config.primary_model,
                    embedding_model=config.embedding_model,
                    temperature=config.temperature,
                    max_output_tokens=config.max_output_tokens,
                    organization_id=config.organization_id,
                )

    # Env defaults — Gemini unless LLM_PROVIDER=litellm
    provider_env: Provider = "litellm" if settings.llm_provider == "litellm" else "gemini"
    if provider_env == "litellm":
        if not settings.litellm_base_url:
            raise ValueError("LITELLM_BASE_URL is required when LLM_PROVIDER=litellm")
        return LlmRuntimeConfig(
            provider="litellm",
            api_key=settings.litellm_api_key or "",
            primary_model=settings.litellm_model,
            embedding_model=settings.litellm_embedding_model,
            temperature=settings.gemini_temperature,
            max_output_tokens=settings.gemini_max_output_tokens,
            organization_id=organization_id,
            litellm_base_url=settings.litellm_base_url,
        )

    if not settings.gemini_api_key:
        raise ValueError(
            "Gemini API key not configured. Set GEMINI_API_KEY or save a key in Settings."
        )
    return LlmRuntimeConfig(
        provider="gemini",
        api_key=settings.gemini_api_key,
        primary_model=settings.gemini_model,
        embedding_model=settings.gemini_embedding_model,
        temperature=settings.gemini_temperature,
        max_output_tokens=settings.gemini_max_output_tokens,
        organization_id=organization_id,
    )


def generate_json(
    prompt: str,
    *,
    system: str | None = None,
    db: Session | None = None,
    organization_id=None,
    review_job_id=None,
    repository_id=None,
    operation: str = "review",
    config: LlmRuntimeConfig | None = None,
) -> tuple[dict[str, Any] | list[Any], dict[str, Any]]:
    cfg = config or resolve_llm_config(db, organization_id)
    if cfg.provider == "litellm":
        from app.services.litellm_client import generate_json_litellm

        return generate_json_litellm(
            prompt,
            system=system,
            api_key=cfg.api_key,
            base_url=cfg.litellm_base_url or "",
            model=cfg.primary_model,
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_output_tokens,
            db=db,
            organization_id=cfg.organization_id,
            review_job_id=review_job_id,
            repository_id=repository_id,
            operation=operation,
        )

    from app.services import gemini_client

    gemini_cfg = gemini_client.GeminiRuntimeConfig(
        api_key=cfg.api_key,
        primary_model=cfg.primary_model,
        embedding_model=cfg.embedding_model,
        temperature=cfg.temperature,
        max_output_tokens=cfg.max_output_tokens,
        organization_id=cfg.organization_id,
    )
    return gemini_client.generate_json(
        prompt,
        system=system,
        db=db,
        organization_id=organization_id,
        review_job_id=review_job_id,
        repository_id=repository_id,
        operation=operation,
        config=gemini_cfg,
    )


def embed_texts(
    texts: list[str],
    *,
    db: Session | None = None,
    organization_id=None,
    repository_id=None,
    config: LlmRuntimeConfig | None = None,
) -> list[list[float]]:
    cfg = config or resolve_llm_config(db, organization_id)
    if cfg.provider == "litellm":
        from app.services.litellm_client import embed_texts_litellm

        return embed_texts_litellm(
            texts,
            api_key=cfg.api_key,
            base_url=cfg.litellm_base_url or "",
            model=cfg.embedding_model,
            db=db,
            organization_id=cfg.organization_id,
            repository_id=repository_id,
        )

    from app.services import gemini_client

    gemini_cfg = gemini_client.GeminiRuntimeConfig(
        api_key=cfg.api_key,
        primary_model=cfg.primary_model,
        embedding_model=cfg.embedding_model,
        temperature=cfg.temperature,
        max_output_tokens=cfg.max_output_tokens,
        organization_id=cfg.organization_id,
    )
    return gemini_client.embed_texts(
        texts,
        db=db,
        organization_id=organization_id,
        repository_id=repository_id,
        config=gemini_cfg,
    )


def validate_connection(
    *,
    provider: Provider,
    api_key: str,
    model: str | None = None,
    litellm_base_url: str | None = None,
) -> tuple[bool, str]:
    if provider == "litellm":
        from app.services.litellm_client import validate_litellm

        if not litellm_base_url:
            return False, "LiteLLM base URL is required"
        return validate_litellm(
            base_url=litellm_base_url,
            api_key=api_key or "",
            model=model,
        )
    from app.services.gemini_client import validate_api_key

    if not api_key:
        return False, "API key is required for Gemini"
    return validate_api_key(api_key, model)
