"""Webhook dead-letter visibility and replay."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.github import get_sync_db
from app.core.security import AuthContext, require_admin_token
from app.models.github import WebhookEvent
from app.services.audit import emit_audit_sync

router = APIRouter(prefix="/admin/webhooks", tags=["admin-webhooks"])

MAX_RETRIES = 5


@router.get("")
def list_webhooks(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_admin_token),
) -> dict[str, Any]:
    q = select(WebhookEvent).order_by(WebhookEvent.created_at.desc()).limit(limit)
    if status_filter:
        q = q.where(WebhookEvent.status == status_filter)
    rows = db.execute(q).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "delivery_id": r.delivery_id,
                "event_type": r.event_type,
                "action": r.action,
                "status": r.status,
                "retry_count": r.retry_count,
                "error_message": r.error_message,
                "dead_lettered_at": r.dead_lettered_at.isoformat() if r.dead_lettered_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "latency_ms": (
                    int((r.processed_at - r.created_at).total_seconds() * 1000)
                    if r.processed_at and r.created_at
                    else None
                ),
            }
            for r in rows
        ]
    }


@router.get("/metrics")
def webhook_metrics(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_admin_token),
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(WebhookEvent).where(WebhookEvent.created_at >= since)
    ).scalars().all()
    total = len(rows)
    processed = sum(1 for r in rows if r.status == "processed")
    failed = sum(1 for r in rows if r.status in {"failed"} or r.dead_lettered_at)
    latencies = [
        int((r.processed_at - r.created_at).total_seconds() * 1000)
        for r in rows
        if r.processed_at and r.created_at
    ]
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    p95 = None
    if latencies:
        ordered = sorted(latencies)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r.event_type] = by_type.get(r.event_type, 0) + 1
    return {
        "days": days,
        "total": total,
        "processed": processed,
        "failed": failed,
        "success_rate": round(processed / total, 4) if total else None,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency is not None else None,
        "p95_latency_ms": p95,
        "by_event_type": by_type,
    }


@router.post("/{event_id}/replay")
def replay_webhook(
    event_id: uuid.UUID,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_admin_token),
) -> dict[str, Any]:
    event = db.get(WebhookEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Webhook event not found")
    from app.github.webhook_handler import process_webhook
    from app.api.routes.webhooks import _enqueue_from_result

    event.retry_count = (event.retry_count or 0) + 1
    event.status = "processing"
    event.error_message = None
    db.flush()
    try:
        result = process_webhook(
            db,
            event.event_type,
            event.action,
            event.delivery_id,
            event.payload,
            reuse_event=event,
        )
        if isinstance(result, dict) and result.get("status") == "error":
            event.status = "failed"
            event.error_message = str(result.get("reason") or "error")
            if event.retry_count >= MAX_RETRIES:
                event.dead_lettered_at = datetime.now(timezone.utc)
            db.flush()
            return {"status": "failed", "result": result}
        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        _enqueue_from_result(result if isinstance(result, dict) else {})
        emit_audit_sync(
            db,
            action="webhook.replay",
            actor_user_id=auth.user_id,
            organization_id=auth.organization_id,
            resource_type="webhook_event",
            resource_id=str(event.id),
            metadata={"delivery_id": event.delivery_id},
        )
        return {"status": "processed", "result": result}
    except Exception as exc:
        event.status = "failed"
        event.error_message = str(exc)[:2000]
        event.retry_count = (event.retry_count or 0)
        if event.retry_count >= MAX_RETRIES:
            event.dead_lettered_at = datetime.now(timezone.utc)
        db.flush()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/redeliver/{delivery_id}")
def redeliver_from_github(
    delivery_id: str,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_admin_token),
) -> dict[str, Any]:
    """One-click GitHub redelivery by delivery ID."""
    from app.github.client import GitHubClient

    try:
        result = GitHubClient.redeliver_webhook_delivery(delivery_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emit_audit_sync(
        db,
        action="webhook.github_redeliver",
        actor_user_id=auth.user_id,
        organization_id=auth.organization_id,
        resource_type="webhook_delivery",
        resource_id=delivery_id,
        metadata={},
    )
    return {"status": "queued", "delivery_id": delivery_id, "result": result}
