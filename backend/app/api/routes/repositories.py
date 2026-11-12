"""Repository listing and indexing actions."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.github import get_sync_db
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
def list_repositories(db: Session = Depends(get_sync_db)) -> RepositoryListResponse:
    repos = db.execute(select(Repository).order_by(Repository.full_name)).scalars().all()
    return RepositoryListResponse(
        items=[RepositoryOut.model_validate(r) for r in repos],
        total=len(repos),
    )


@router.get("/{repository_id}", response_model=RepositoryOut)
def get_repository(repository_id: uuid.UUID, db: Session = Depends(get_sync_db)) -> RepositoryOut:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return RepositoryOut.model_validate(repo)


@router.post("/{repository_id}/reindex")
def reindex_repository(repository_id: uuid.UUID, full: bool = True, db: Session = Depends(get_sync_db)) -> dict:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.indexing_status = "pending"
    db.flush()
    from app.workers.tasks import index_repository

    task = index_repository.delay(str(repository_id), full)
    return {"status": "queued", "task_id": task.id, "repository_id": str(repository_id)}


@router.post("/{repository_id}/auto-review")
def set_auto_review(repository_id: uuid.UUID, enabled: bool = True, db: Session = Depends(get_sync_db)) -> dict:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.auto_review_enabled = enabled
    return {"id": str(repo.id), "auto_review_enabled": repo.auto_review_enabled}