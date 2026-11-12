"""Analytics queries over real usage and review tables."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewFinding, ReviewJob
from app.models.usage import ApiUsageRecord


def usage_timeseries(db: Session, days: int = 30, organization_id: uuid.UUID | None = None) -> list[dict]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    q = select(
        func.date_trunc("day", ApiUsageRecord.created_at).label("day"),
        func.sum(ApiUsageRecord.input_tokens).label("input_tokens"),
        func.sum(ApiUsageRecord.output_tokens).label("output_tokens"),
        func.sum(ApiUsageRecord.estimated_cost_usd).label("cost_usd"),
        func.count().label("requests"),
    ).where(ApiUsageRecord.created_at >= start)
    if organization_id:
        q = q.where(ApiUsageRecord.organization_id == organization_id)
    q = q.group_by("day").order_by("day")
    rows = db.execute(q).all()
    return [
        {
            "date": r.day.date().isoformat() if r.day else None,
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "cost_usd": float(r.cost_usd or 0),
            "requests": int(r.requests or 0),
        }
        for r in rows
    ]


def model_breakdown(db: Session, days: int = 30) -> list[dict]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(
            ApiUsageRecord.model_name,
            func.sum(ApiUsageRecord.input_tokens),
            func.sum(ApiUsageRecord.output_tokens),
            func.sum(ApiUsageRecord.estimated_cost_usd),
            func.count(),
        ).where(ApiUsageRecord.created_at >= start)
        .group_by(ApiUsageRecord.model_name)
    ).all()
    return [
        {
            "model": m,
            "input_tokens": int(i or 0),
            "output_tokens": int(o or 0),
            "cost_usd": float(c or 0),
            "requests": int(n or 0),
        }
        for m, i, o, c, n in rows
    ]


def review_volume(db: Session, days: int = 30) -> list[dict]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(
            func.date_trunc("day", ReviewJob.created_at).label("day"),
            func.count().label("reviews"),
            func.sum(ReviewJob.findings_count).label("findings"),
            func.sum(ReviewJob.estimated_cost_usd).label("cost_usd"),
        ).where(ReviewJob.created_at >= start)
        .group_by("day")
        .order_by("day")
    ).all()
    return [
        {
            "date": r.day.date().isoformat() if r.day else None,
            "reviews": int(r.reviews or 0),
            "findings": int(r.findings or 0),
            "cost_usd": float(r.cost_usd or 0),
        }
        for r in rows
    ]


def cost_per_repo(db: Session) -> list[dict]:
    rows = db.execute(
        select(
            Repository.full_name,
            func.count(ReviewJob.id),
            func.coalesce(func.sum(ReviewJob.estimated_cost_usd), 0.0),
        )
        .join(PullRequest, PullRequest.repository_id == Repository.id)
        .join(ReviewJob, ReviewJob.pull_request_id == PullRequest.id)
        .group_by(Repository.full_name)
        .order_by(func.sum(ReviewJob.estimated_cost_usd).desc())
    ).all()
    return [
        {"repository": name, "reviews": int(n or 0), "cost_usd": float(cost or 0)}
        for name, n, cost in rows
    ]