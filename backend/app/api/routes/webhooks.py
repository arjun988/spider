"""GitHub webhook endpoint — acknowledge quickly, process async."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import verify_github_webhook_signature
from app.database.session import get_sync_session_factory
from app.github.webhook_handler import process_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)


class WebhookAck(BaseModel):
    status: str
    message: str
    event: str | None = None
    delivery_id: str | None = None


def _enqueue_from_result(result: dict) -> None:
    if not result:
        return
    from app.workers.tasks import index_repository, review_pull_request
    import uuid

    SessionLocal = get_sync_session_factory()
    assert SessionLocal is not None

    if result.get("enqueue_index") and result.get("repository_id"):
        try:
            index_repository.delay(result["repository_id"], True)
        except Exception as exc:
            logger.exception("enqueue_index_failed", error=str(exc))

    if result.get("enqueue_review") and result.get("pull_request_id"):
        try:
            task = review_pull_request.delay(
                result["pull_request_id"],
                result["commit_sha"],
            )
            job_id = result.get("review_job_id")
            if job_id and SessionLocal is not None:
                from app.models.review import ReviewJob

                with SessionLocal() as db:
                    job = db.get(ReviewJob, uuid.UUID(str(job_id)))
                    if job:
                        job.celery_task_id = task.id
                        db.commit()
        except Exception as exc:
            logger.exception("enqueue_review_failed", error=str(exc), result=result)
            # Leave job queued with null celery_task_id — reclaim task will pick it up.


def _process_in_background(
    event_type: str,
    action: str | None,
    delivery_id: str,
    payload: dict,
) -> None:
    # Ping only validates connectivity — acknowledge with no DB work.
    if event_type == "ping":
        logger.info("webhook_ping_ok", delivery_id=delivery_id)
        return

    SessionLocal = get_sync_session_factory()
    assert SessionLocal is not None
    with SessionLocal() as db:
        try:
            result = process_webhook(db, event_type, action, delivery_id, payload)
            # Soft errors (e.g. install race) stay retryable via GitHub redelivery.
            if isinstance(result, dict) and result.get("status") == "error":
                db.rollback()
                logger.warning(
                    "webhook_soft_error_not_acked",
                    delivery_id=delivery_id,
                    reason=result.get("reason"),
                    github_event=event_type,
                )
                return
            db.commit()
            _enqueue_from_result(result)
        except Exception:
            db.rollback()
            logger.exception(
                "webhook_background_failed",
                delivery_id=delivery_id,
                github_event=event_type,
            )


@router.post("/github", response_model=WebhookAck)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
) -> WebhookAck:
    payload_bytes = await request.body()

    if settings.github_app_webhook_secret:
        if not verify_github_webhook_signature(
            payload_bytes,
            x_hub_signature_256,
            settings.github_app_webhook_secret,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
    elif settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    try:
        payload = json.loads(payload_bytes.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    action = payload.get("action")
    delivery_id = x_github_delivery or f"local-{id(payload)}"
    event_type = x_github_event or "unknown"

    logger.info(
        "webhook_received",
        github_event=event_type,
        action=action,
        delivery_id=delivery_id,
    )

    background_tasks.add_task(
        _process_in_background,
        event_type,
        action,
        delivery_id,
        payload,
    )

    return WebhookAck(
        status="accepted",
        message="Webhook accepted for async processing",
        event=event_type,
        delivery_id=delivery_id,
    )