"""Centralized Gemini client — model names come from config, never hardcoded in agents."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_value
from app.core.logging import get_logger
from app.models.settings import ModelConfiguration
from app.models.usage import ApiUsageRecord

logger = get_logger(__name__)

# Approximate Gemini pricing (USD per 1M tokens) — used for budget estimates
PRICE_TABLE = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "text-embedding-004": {"input": 0.025, "output": 0.0},
}


@dataclass
class GeminiRuntimeConfig:
    api_key: str
    primary_model: str
    embedding_model: str
    temperature: float
    max_output_tokens: int
    organization_id: Any | None = None


def resolve_gemini_config(db: Session | None = None, organization_id=None) -> GeminiRuntimeConfig:
    if db is not None:
        q = db.query(ModelConfiguration)
        if organization_id:
            q = q.filter(ModelConfiguration.organization_id == organization_id)
        config = q.first()
        if config and config.encrypted_api_key:
            return GeminiRuntimeConfig(
                api_key=decrypt_value(config.encrypted_api_key),
                primary_model=config.primary_model,
                embedding_model=config.embedding_model,
                temperature=config.temperature,
                max_output_tokens=config.max_output_tokens,
                organization_id=config.organization_id,
            )
    if not settings.gemini_api_key:
        raise ValueError(
            "Gemini API key not configured. Set GEMINI_API_KEY or save a key in Settings."
        )
    return GeminiRuntimeConfig(
        api_key=settings.gemini_api_key,
        primary_model=settings.gemini_model,
        embedding_model=settings.gemini_embedding_model,
        temperature=settings.gemini_temperature,
        max_output_tokens=settings.gemini_max_output_tokens,
        organization_id=organization_id,
    )


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICE_TABLE.get(model, {"input": 0.10, "output": 0.40})
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def _client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def generate_json(
    prompt: str,
    *,
    system: str | None = None,
    db: Session | None = None,
    organization_id=None,
    review_job_id=None,
    repository_id=None,
    operation: str = "review",
    config: GeminiRuntimeConfig | None = None,
) -> tuple[dict[str, Any] | list[Any], dict[str, Any]]:
    """Generate structured JSON from Gemini. Returns (parsed, usage_meta)."""
    import json
    import re

    cfg = config or resolve_gemini_config(db, organization_id)
    client = _client(cfg.api_key)
    full_prompt = prompt
    if system:
        full_prompt = f"{system}\n\n{prompt}"
    full_prompt += "\n\nRespond with valid JSON only. No markdown fences."

    started = time.time()
    response = client.models.generate_content(
        model=cfg.primary_model,
        contents=full_prompt,
        config={
            "temperature": cfg.temperature,
            "max_output_tokens": cfg.max_output_tokens,
            "response_mime_type": "application/json",
        },
    )
    latency_ms = int((time.time() - started) * 1000)
    text = getattr(response, "text", None) or ""
    usage = getattr(response, "usage_metadata", None)
    input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    cost = estimate_cost(cfg.primary_model, input_tokens, output_tokens)

    meta = {
        "model": cfg.primary_model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": cost,
        "latency_ms": latency_ms,
        "operation": operation,
    }

    if db is not None and cfg.organization_id:
        db.add(
            ApiUsageRecord(
                organization_id=cfg.organization_id,
                review_job_id=review_job_id,
                repository_id=repository_id,
                model_name=cfg.primary_model,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                estimated_cost_usd=cost,
                latency_ms=latency_ms,
                success=True,
            )
        )

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("gemini_json_parse_failed", preview=cleaned[:200])
        parsed = {}
    return parsed, meta


def embed_texts(
    texts: list[str],
    *,
    db: Session | None = None,
    organization_id=None,
    repository_id=None,
    config: GeminiRuntimeConfig | None = None,
) -> list[list[float]]:
    if not texts:
        return []
    cfg = config or resolve_gemini_config(db, organization_id)
    client = _client(cfg.api_key)
    vectors: list[list[float]] = []
    # Batch in small groups
    batch_size = 16
    total_tokens = 0
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        started = time.time()
        result = client.models.embed_content(
            model=cfg.embedding_model,
            contents=batch,
        )
        latency_ms = int((time.time() - started) * 1000)
        embeddings = getattr(result, "embeddings", None) or []
        for emb in embeddings:
            values = list(getattr(emb, "values", []) or [])
            # Pad/truncate to configured dimensions
            dim = settings.gemini_embedding_dimensions
            if len(values) < dim:
                values = values + [0.0] * (dim - len(values))
            elif len(values) > dim:
                values = values[:dim]
            vectors.append(values)
            total_tokens += max(1, len(batch[0]) // 4) if batch else 0

        cost = estimate_cost(cfg.embedding_model, total_tokens, 0)
        if db is not None and cfg.organization_id:
            db.add(
                ApiUsageRecord(
                    organization_id=cfg.organization_id,
                    repository_id=repository_id,
                    model_name=cfg.embedding_model,
                    operation="embed",
                    input_tokens=total_tokens,
                    output_tokens=0,
                    total_tokens=total_tokens,
                    estimated_cost_usd=cost,
                    latency_ms=latency_ms,
                    success=True,
                )
            )
    return vectors


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return str(text)
    # Fallback for models that put output in candidate parts
    for cand in getattr(response, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                return str(part_text)
    return ""


def validate_api_key(api_key: str, model: str | None = None) -> tuple[bool, str]:
    """
    Validate a Gemini API key with a tiny live request.
    Returns (ok, detail). Uses a higher token budget because some Gemini
    models spend tokens on internal reasoning before visible output.
    """
    client = _client(api_key)
    model_name = model or settings.gemini_model
    try:
        response = client.models.generate_content(
            model=model_name,
            contents='Reply with JSON only: {"ok": true}',
            config={
                "temperature": 0,
                "max_output_tokens": 256,
                "response_mime_type": "application/json",
            },
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    text = _response_text(response)
    if "ok" in text.lower():
        return True, "connected"
    return False, f"Unexpected model response for {model_name}: {text[:200]!r}"