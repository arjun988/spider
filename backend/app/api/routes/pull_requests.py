"""Pull request listing endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.github import get_sync_db
from app.core.security import AuthContext, require_admin_token, require_user
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob

router = APIRouter(prefix="/pull-requests", tags=["pull-requests"])


def _latest_review_job_id(db: Session, pr_id: uuid.UUID) -> uuid.UUID | None:
    job = db.execute(
        select(ReviewJob)
        .where(ReviewJob.pull_request_id == pr_id)
        .order_by(ReviewJob.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return job.id if job else None


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
    latest_review_job_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PullRequestListResponse(BaseModel):
    items: list[PullRequestOut]
    total: int


@router.get("", response_model=PullRequestListResponse)
def list_pull_requests(
    repository_id: uuid.UUID | None = None,
    review_status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_sync_db),
    _: AuthContext = Depends(require_user),
) -> PullRequestListResponse:
    query = select(PullRequest).order_by(PullRequest.created_at.desc())
    if repository_id:
        query = query.where(PullRequest.repository_id == repository_id)
    if review_status:
        query = query.where(PullRequest.review_status == review_status)

    count_query = select(func.count()).select_from(PullRequest)
    if repository_id:
        count_query = count_query.where(PullRequest.repository_id == repository_id)
    if review_status:
        count_query = count_query.where(PullRequest.review_status == review_status)
    total = db.scalar(count_query) or 0

    prs = db.execute(query.offset(offset).limit(limit)).scalars().all()
    items: list[PullRequestOut] = []
    for pr in prs:
        out = PullRequestOut.model_validate(pr)
        repo = db.get(Repository, pr.repository_id)
        out.repository_full_name = repo.full_name if repo else None
        out.latest_review_job_id = _latest_review_job_id(db, pr.id)
        items.append(out)
    return PullRequestListResponse(items=items, total=total)


@router.get("/{pr_id}", response_model=PullRequestOut)
def get_pull_request(
    pr_id: uuid.UUID,
    db: Session = Depends(get_sync_db),
    _: AuthContext = Depends(require_user),
) -> PullRequestOut:
    pr = db.get(PullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull request not found")
    out = PullRequestOut.model_validate(pr)
    repo = db.get(Repository, pr.repository_id)
    out.repository_full_name = repo.full_name if repo else None
    out.latest_review_job_id = _latest_review_job_id(db, pr.id)
    return out


@router.post("/{pr_id}/review")
def trigger_review(
    pr_id: uuid.UUID,
    force: bool = False,
    db: Session = Depends(get_sync_db),
    _: None = Depends(require_admin_token),
) -> dict:
    pr = db.get(PullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    from app.workers.tasks import review_pull_request

    existing = db.execute(
        select(ReviewJob).where(
            ReviewJob.pull_request_id == pr.id,
            ReviewJob.commit_sha == pr.head_sha,
        )
    ).scalar_one_or_none()
    active = {"queued", "analyzing", "retrieving", "detecting", "verifying", "publishing"}
    if existing and existing.status in active and not force:
        return {"status": "exists", "review_job_id": str(existing.id), "job_status": existing.status}
    if existing and existing.status == "completed" and not force:
        return {"status": "exists", "review_job_id": str(existing.id), "job_status": existing.status}
    if force and existing:
        db.delete(existing)
        db.flush()
    elif existing and existing.status == "failed":
        # Requeue the same job row after a failure.
        existing.status = "queued"
        existing.error_message = None
        existing.celery_task_id = None
        existing.completed_at = None
        pr.review_status = "queued"
        db.flush()
        task = review_pull_request.delay(str(pr.id), pr.head_sha)
        existing.celery_task_id = task.id
        return {"status": "queued", "review_job_id": str(existing.id), "task_id": task.id}

    job = ReviewJob(
        pull_request_id=pr.id,
        commit_sha=pr.head_sha,
        trigger="manual",
        status="queued",
    )
    db.add(job)
    pr.review_status = "queued"
    db.flush()
    task = review_pull_request.delay(str(pr.id), pr.head_sha)
    job.celery_task_id = task.id
    return {"status": "queued", "review_job_id": str(job.id), "task_id": task.id}