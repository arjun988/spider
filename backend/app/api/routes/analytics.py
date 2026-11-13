"""Overview and usage analytics — metrics from database records only."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.github import get_sync_db
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewFinding, ReviewJob
from app.models.usage import ApiUsageRecord
from app.services.analytics_service import cost_per_repo, model_breakdown, review_volume, usage_timeseries

router = APIRouter(prefix="/analytics", tags=["analytics"])


class OverviewMetrics(BaseModel):
    total_repositories: int
    total_prs_reviewed: int
    total_findings: int
    critical_findings: int
    high_findings: int
    average_review_time_ms: float | None
    total_api_spend_usd: float
    recent_reviews: list[dict]


class OverviewResponse(BaseModel):
    metrics: OverviewMetrics
    generated_at: datetime


@router.get("/overview", response_model=OverviewResponse)
def get_overview(db: Session = Depends(get_sync_db)) -> OverviewResponse:
    total_repos = db.scalar(select(func.count()).select_from(Repository)) or 0
    total_prs = db.scalar(
        select(func.count()).select_from(ReviewJob).where(ReviewJob.status == "completed")
    ) or 0
    total_findings = db.scalar(select(func.count()).select_from(ReviewFinding)) or 0
    critical = db.scalar(
        select(func.count()).select_from(ReviewFinding).where(ReviewFinding.severity == "critical")
    ) or 0
    high = db.scalar(
        select(func.count()).select_from(ReviewFinding).where(ReviewFinding.severity == "high")
    ) or 0
    avg_duration = db.scalar(
        select(func.avg(ReviewJob.duration_ms)).where(
            ReviewJob.status == "completed",
            ReviewJob.duration_ms.isnot(None),
        )
    )
    total_spend = db.scalar(
        select(func.coalesce(func.sum(ApiUsageRecord.estimated_cost_usd), 0.0))
    ) or 0.0

    recent_jobs = db.execute(
        select(ReviewJob)
        .order_by(ReviewJob.created_at.desc())
        .limit(10)
    ).scalars().all()

    recent_reviews = []
    for job in recent_jobs:
        pr = db.get(PullRequest, job.pull_request_id)
        recent_reviews.append(
            {
                "id": str(job.id),
                "pr_number": pr.number if pr else None,
                "pr_title": pr.title if pr else None,
                "status": job.status,
                "findings_count": job.findings_count,
                "duration_ms": job.duration_ms,
                "cost_usd": job.estimated_cost_usd,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
        )

    return OverviewResponse(
        metrics=OverviewMetrics(
            total_repositories=total_repos,
            total_prs_reviewed=total_prs,
            total_findings=total_findings,
            critical_findings=critical,
            high_findings=high,
            average_review_time_ms=float(avg_duration) if avg_duration is not None else None,
            total_api_spend_usd=float(total_spend),
            recent_reviews=recent_reviews,
        ),
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/usage")
def get_usage(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_sync_db)) -> dict:
    return {
        "timeseries": usage_timeseries(db, days=days),
        "models": model_breakdown(db, days=days),
        "reviews": review_volume(db, days=days),
        "by_repository": cost_per_repo(db),
    }