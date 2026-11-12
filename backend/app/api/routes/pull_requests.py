"""Pull request listing endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.pull_request import PullRequest
from app.models.repository import Repository

router = APIRouter(prefix="/pull-requests", tags=["pull-requests"])


class PullRequestOut(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    state: str
    author_login: str
    review_status: str
    findings_count: int
    critical_count: int
    high_count: int
    head_sha: str
    html_url: str | None
    last_reviewed_at: datetime | None
    repository_id: uuid.UUID
    repository_full_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PullRequestListResponse(BaseModel):
    items: list[PullRequestOut]
    total: int


@router.get("", response_model=PullRequestListResponse)
async def list_pull_requests(
    repository_id: uuid.UUID | None = None,
    review_status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> PullRequestListResponse:
    query = select(PullRequest).order_by(PullRequest.created_at.desc())
    if repository_id:
        query = query.where(PullRequest.repository_id == repository_id)
    if review_status:
        query = query.where(PullRequest.review_status == review_status)

    result = await db.execute(query.offset(offset).limit(limit))
    prs = result.scalars().all()

    items: list[PullRequestOut] = []
    for pr in prs:
        out = PullRequestOut.model_validate(pr)
        repo = await db.get(Repository, pr.repository_id)
        out.repository_full_name = repo.full_name if repo else None
        items.append(out)

    return PullRequestListResponse(items=items, total=len(items))


@router.get("/{pr_id}", response_model=PullRequestOut)
async def get_pull_request(
    pr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> PullRequestOut:
    pr = await db.get(PullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull request not found")
    out = PullRequestOut.model_validate(pr)
    repo = await db.get(Repository, pr.repository_id)
    out.repository_full_name = repo.full_name if repo else None
    return out