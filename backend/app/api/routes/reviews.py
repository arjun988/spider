"""Review job and finding endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.routes.github import get_sync_db
from app.core.security import AuthContext, require_admin_token, require_user
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewFeedback, ReviewFinding, ReviewJob

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
    decision_trace: dict[str, Any] | None = None

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
    error_message: str | None = None
    started_at: datetime | None
    completed_at: datetime | None
    change_summary: dict[str, Any] | None
    timeline: list[dict[str, Any]] | None
    findings: list[FindingOut] = []
    pr_number: int | None = None
    pr_title: str | None = None
    pr_html_url: str | None = None
    repository_full_name: str | None = None

    model_config = {"from_attributes": True}


class FeedbackIn(BaseModel):
    feedback_type: Literal["helpful", "false_positive", "dismissed", "fixed"]
    comment: str | None = Field(default=None, max_length=2000)
    author_login: str | None = Field(default=None, max_length=255)


class FeedbackOut(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    feedback_type: str
    comment: str | None
    author_login: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


def _enrich_review(db: Session, job: ReviewJob) -> ReviewJobOut:
    out = ReviewJobOut.model_validate(job)
    pr = db.get(PullRequest, job.pull_request_id)
    if pr:
        out.pr_number = pr.number
        out.pr_title = pr.title
        out.pr_html_url = pr.html_url
        repo = db.get(Repository, pr.repository_id)
        out.repository_full_name = repo.full_name if repo else None
    return out


@router.get("/by-pr/{pr_id}", response_model=list[ReviewJobOut])
def list_reviews_for_pr(
    pr_id: uuid.UUID,
    db: Session = Depends(get_sync_db),
    _: AuthContext = Depends(require_user),
) -> list[ReviewJobOut]:
    jobs = db.execute(
        select(ReviewJob)
        .where(ReviewJob.pull_request_id == pr_id)
        .options(selectinload(ReviewJob.findings))
        .order_by(ReviewJob.created_at.desc())
    ).scalars().all()
    return [_enrich_review(db, j) for j in jobs]


@router.get("/{review_id}", response_model=ReviewJobOut)
def get_review(
    review_id: uuid.UUID,
    db: Session = Depends(get_sync_db),
    _: AuthContext = Depends(require_user),
) -> ReviewJobOut:
    job = db.execute(
        select(ReviewJob)
        .where(ReviewJob.id == review_id)
        .options(selectinload(ReviewJob.findings))
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return _enrich_review(db, job)


@router.post("/findings/{finding_id}/feedback", response_model=FeedbackOut)
def submit_finding_feedback(
    finding_id: uuid.UUID,
    body: FeedbackIn,
    db: Session = Depends(get_sync_db),
    _: None = Depends(require_admin_token),
) -> FeedbackOut:
    finding = db.get(ReviewFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    row = ReviewFeedback(
        finding_id=finding.id,
        feedback_type=body.feedback_type,
        comment=body.comment,
        author_login=body.author_login or "dashboard",
    )
    db.add(row)
    db.flush()
    return FeedbackOut.model_validate(row)
