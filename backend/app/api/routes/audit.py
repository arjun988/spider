"""Audit log listing and metrics summary."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.github import get_sync_db
from app.core.security import AuthContext, require_user
from app.models.audit import AuditLog
from app.models.github import WebhookEvent
from app.models.review import ReviewJob
from app.models.usage import ApiUsageRecord

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
def list_audit_logs(
    action: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
) -> dict[str, Any]:
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if auth.organization_id:
        q = q.where(
            (AuditLog.organization_id == auth.organization_id) | (AuditLog.organization_id.is_(None))
        )
    if action:
        q = q.where(AuditLog.action == action)
    rows = db.execute(q).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "action": r.action,
                "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
                "organization_id": str(r.organization_id) if r.organization_id else None,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "metadata": r.metadata_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/metrics")
def metrics_summary(
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    reviews_started = db.execute(
        select(func.count()).select_from(ReviewJob).where(ReviewJob.created_at >= since)
    ).scalar() or 0
    reviews_failed = db.execute(
        select(func.count())
        .select_from(ReviewJob)
        .where(ReviewJob.created_at >= since, ReviewJob.status == "failed")
    ).scalar() or 0
    webhook_failed = db.execute(
        select(func.count())
        .select_from(WebhookEvent)
        .where(WebhookEvent.status == "failed")
    ).scalar() or 0
    cost_q = select(func.coalesce(func.sum(ApiUsageRecord.estimated_cost_usd), 0.0)).where(
        ApiUsageRecord.created_at >= since
    )
    if auth.organization_id:
        cost_q = cost_q.where(ApiUsageRecord.organization_id == auth.organization_id)
    week_cost = float(db.execute(cost_q).scalar() or 0)
    return {
        "window_days": 7,
        "reviews_started": reviews_started,
        "reviews_failed": reviews_failed,
        "webhook_failures": webhook_failed,
        "week_cost_usd": week_cost,
        "cost_spike": week_cost > 50,
    }
