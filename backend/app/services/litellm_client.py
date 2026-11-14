"""LiteLLM OpenAI-compatible client (proxy or LiteLLM gateway)."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.usage import ApiUsageRecord
from app.services.gemini_client import estimate_cost

logger = get_logger(__name__)


def _normalize_base_url(base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise ValueError("LiteLLM base URL is required")
    # Accept both http://host:4000 and http://host:4000/v1
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def validate_litellm(
    *,
    base_url: str,
    api_key: str,
    model: str | None = None,
) -> tuple[bool, str]:
    """Ping LiteLLM with a tiny chat completion."""
    root = _normalize_base_url(base_url)
    model_name = model or settings.litellm_model
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": 'Reply with JSON only: {"ok": true}'},
        ],
        "temperature": 0,
        "max_tokens": 64,
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post(
                f"{root}/chat/completions",
                headers=_headers(api_key),
                json=payload,
            )
            if res.status_code >= 400:
                return False, f"HTTP {res.status_code}: {res.text[:300]}"
            data = res.json()
            content = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                or ""
            )
            if "ok" in str(content).lower():
                return True, "connected"
            return False, f"Unexpected response: {str(content)[:200]!r}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def generate_json_litellm(
    prompt: str,
    *,
    system: str | None = None,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    max_output_tokens: int,
    db=None,
    organization_id=None,
    review_job_id=None,
    repository_id=None,
    operation: str = "review",
) -> tuple[dict[str, Any] | list[Any], dict[str, Any]]:
    root = _normalize_base_url(base_url)
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append(
        {
            "role": "user",
            "content": f"{prompt}\n\nRespond with valid JSON only. No markdown fences.",
        }
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_output_tokens,
        "response_format": {"type": "json_object"},
    }

    started = time.time()
    with httpx.Client(timeout=120.0) as client:
        res = client.post(
            f"{root}/chat/completions",
            headers=_headers(api_key),
            json=payload,
        )
        if res.status_code >= 400:
            raise RuntimeError(f"LiteLLM chat failed ({res.status_code}): {res.text[:500]}")
        data = res.json()
    latency_ms = int((time.time() - started) * 1000)

    usage = data.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    cost = estimate_cost(model, input_tokens, output_tokens)
    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""

    meta = {
        "model": model,
        "provider": "litellm",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": cost,
        "latency_ms": latency_ms,
        "operation": operation,
    }

    if db is not None and organization_id:
        db.add(
            ApiUsageRecord(
                organization_id=organization_id,
                review_job_id=review_job_id,
                repository_id=repository_id,
                model_name=model,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                estimated_cost_usd=cost,
                latency_ms=latency_ms,
                success=True,
            )
        )

    cleaned = str(text).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("litellm_json_parse_failed", preview=cleaned[:200])
        parsed = {}
    return parsed, meta


def embed_texts_litellm(
    texts: list[str],
    *,
    api_key: str,
    base_url: str,
    model: str,
    db=None,
    organization_id=None,
    repository_id=None,
) -> list[list[float]]:
    if not texts:
        return []
    root = _normalize_base_url(base_url)
    dim = settings.gemini_embedding_dimensions
    vectors: list[list[float]] = []
    batch_size = 16
    total_tokens = 0

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        started = time.time()
        payload = {"model": model, "input": batch}
        last_exc: Exception | None = None
        data = None
        for attempt in range(4):
            try:
                with httpx.Client(timeout=60.0) as client:
                    res = client.post(
                        f"{root}/embeddings",
                        headers=_headers(api_key),
                        json=payload,
                    )
                    if res.status_code in {429, 503}:
                        delay = min(60, 5 * (2**attempt))
                        logger.warning("litellm_embed_rate_limited", attempt=attempt + 1, delay=delay)
                        time.sleep(delay)
                        continue
                    if res.status_code >= 400:
                        raise RuntimeError(
                            f"LiteLLM embeddings failed ({res.status_code}): {res.text[:500]}"
                        )
                    data = res.json()
                break
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                if "429" in msg or "rate" in msg:
                    delay = min(60, 5 * (2**attempt))
                    time.sleep(delay)
                    continue
                raise
        if data is None:
            assert last_exc is not None
            raise last_exc

        latency_ms = int((time.time() - started) * 1000)
        items = sorted(data.get("data") or [], key=lambda x: int(x.get("index") or 0))
        for item in items:
            values = list(item.get("embedding") or [])
            if len(values) < dim:
                values = values + [0.0] * (dim - len(values))
            elif len(values) > dim:
                values = values[:dim]
            vectors.append(values)

        usage = data.get("usage") or {}
        batch_tokens = int(usage.get("total_tokens") or usage.get("prompt_tokens") or 0)
        total_tokens += batch_tokens or sum(max(1, len(t) // 4) for t in batch)
        cost = estimate_cost(model, total_tokens, 0)
        if db is not None and organization_id:
            db.add(
                ApiUsageRecord(
                    organization_id=organization_id,
                    repository_id=repository_id,
                    model_name=model,
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
