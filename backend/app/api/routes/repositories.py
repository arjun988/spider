"""Repository listing endpoints (Phase 1 shell — discovery in Phase 2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.repository import Repository

router = APIRouter(prefix="/repositories", tags=["repositories"])


class RepositoryOut(BaseModel):
    id: uuid.UUID
    name: str
    full_name: str
    owner_login: str
    primary_language: str | None
    indexing_status: str
    last_indexed_commit_sha: str | None
    last_indexed_at: datetime | None
    auto_review_enabled: bool
    prs_reviewed_count: int
    last_review_at: datetime | None
    html_url: str | None

    model_config = {"from_attributes": True}


class RepositoryListResponse(BaseModel):
    items: list[RepositoryOut]
    total: int


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(db: AsyncSession = Depends(get_db_session)) -> RepositoryListResponse:
    result = await db.execute(select(Repository).order_by(Repository.full_name))
    repos = result.scalars().all()
    return RepositoryListResponse(
        items=[RepositoryOut.model_validate(r) for r in repos],
        total=len(repos),
    )


@router.get("/{repository_id}", response_model=RepositoryOut)
async def get_repository(
    repository_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RepositoryOut:
    repo = await db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return RepositoryOut.model_validate(repo)