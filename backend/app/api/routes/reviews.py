"""Review job and finding endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.models.review import ReviewFinding, ReviewJob

router = APIRouter(prefix="/reviews", tags=["reviews"])


class FindingOut(BaseModel):
    id: uuid.UUID
    finding_key: str
    file_path: str
    start_line: int
    end_line: int
    category: str
    severity: str
    confidence: float
    title: str
    explanation: str
    failure_scenario: str
    suggested_fix: str | None
    verification_status: str
    published: bool
    rejected_reason: str | None

    model_config = {"from_attributes": True}


class ReviewJobOut(BaseModel):
    id: uuid.UUID
    pull_request_id: uuid.UUID
    commit_sha: str
    trigger: str
    status: str
    summary: str | None
    findings_count: int
    published_count: int
    rejected_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    model_name: str | None
    duration_ms: int | None
    started_at: datetime | None
    completed_at: datetime | None
    change_summary: dict[str, Any] | None
    timeline: list[dict[str, Any]] | None
    findings: list[FindingOut] = []

    model_config = {"from_attributes": True}


@router.get("/{review_id}", response_model=ReviewJobOut)
async def get_review(
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ReviewJobOut:
    result = await db.execute(
        select(ReviewJob)
        .where(ReviewJob.id == review_id)
        .options(selectinload(ReviewJob.findings))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return ReviewJobOut.model_validate(job)


@router.get("/by-pr/{pr_id}", response_model=list[ReviewJobOut])
async def list_reviews_for_pr(
    pr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[ReviewJobOut]:
    result = await db.execute(
        select(ReviewJob)
        .where(ReviewJob.pull_request_id == pr_id)
        .options(selectinload(ReviewJob.findings))
        .order_by(ReviewJob.created_at.desc())
    )
    jobs = result.scalars().all()
    return [ReviewJobOut.model_validate(j) for j in jobs]