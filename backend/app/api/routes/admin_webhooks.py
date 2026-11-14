"""Webhook dead-letter visibility and replay."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
            }
            for r in rows
        ]
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
