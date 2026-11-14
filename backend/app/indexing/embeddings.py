"""Embedding helpers wrapping the Gemini client."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.llm_client import embed_texts


def embed_chunks(
    texts: list[str],
    db: Session | None = None,
    organization_id=None,
    repository_id=None,
) -> list[list[float]]:
    return embed_texts(
        texts,
        db=db,
        organization_id=organization_id,
        repository_id=repository_id,
    )
