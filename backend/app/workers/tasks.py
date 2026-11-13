"""Celery tasks for indexing and reviewing."""

from __future__ import annotations

from app.core.logging import get_logger
from app.database.session import get_sync_session_factory
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="spider.ping")
def ping() -> dict[str, str]:
    logger.info("celery_ping")
    return {"status": "ok"}


@celery_app.task(name="spider.reclaim_stuck_reviews")
def reclaim_stuck_reviews(max_age_seconds: int = 120) -> dict:
    """Re-enqueue queued review jobs that never got a Celery task id (enqueue failure)."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.models.review import ReviewJob

    SessionLocal = get_sync_session_factory()
    assert SessionLocal is not None
    reclaimed = 0
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    with SessionLocal() as db:
        stuck = db.execute(
            select(ReviewJob).where(
                ReviewJob.status == "queued",
                ReviewJob.celery_task_id.is_(None),
                ReviewJob.created_at < cutoff,
            ).limit(50)
        ).scalars().all()
        for job in stuck:
            try:
                task = review_pull_request.delay(str(job.pull_request_id), job.commit_sha)
                job.celery_task_id = task.id
                reclaimed += 1
            except Exception as exc:
                logger.warning("reclaim_enqueue_failed", job_id=str(job.id), error=str(exc))
        db.commit()
    return {"reclaimed": reclaimed}


@celery_app.task(name="spider.index_repository", bind=True, max_retries=3, default_retry_delay=60)
def index_repository(self, repository_id: str, full: bool = False) -> dict:
    from app.indexing.repository_manager import index_repository as run_index
    from app.models.repository import Repository
    import uuid

    SessionLocal = get_sync_session_factory()
    assert SessionLocal is not None
    with SessionLocal() as db:
        try:
            result = run_index(db, repository_id, full=full)
            db.commit()
            return result
        except Exception as exc:
            db.rollback()
            logger.exception("index_task_failed", repository_id=repository_id)
            try:
                repo = db.get(Repository, uuid.UUID(str(repository_id)))
                if repo:
                    repo.indexing_status = "failed"
                    db.commit()
            except Exception:
                db.rollback()
            raise self.retry(exc=exc)


@celery_app.task(name="spider.review_pull_request", bind=True, max_retries=3, default_retry_delay=90)
def review_pull_request(self, pull_request_id: str, commit_sha: str) -> dict:
    from app.services.cost_service import ensure_within_budget
    from app.services.review_service import mark_review_failed, run_review_job
    from app.models.pull_request import PullRequest
    from app.models.repository import Repository
    import uuid

    SessionLocal = get_sync_session_factory()
    assert SessionLocal is not None
    with SessionLocal() as db:
        try:
            pr = db.get(PullRequest, uuid.UUID(str(pull_request_id)))
            if pr:
                repo = db.get(Repository, pr.repository_id)
                if repo:
                    ensure_within_budget(db, repo.organization_id)
            result = run_review_job(db, pull_request_id, commit_sha)
            db.commit()
            return result
        except Exception as exc:
            db.rollback()
            logger.exception("review_task_failed", pull_request_id=pull_request_id)
            # Persist failed status in a fresh transaction — otherwise rollback
            # leaves the PR stuck in queued/reviewing forever.
            try:
                mark_review_failed(db, pull_request_id, commit_sha, str(exc))
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("mark_review_failed_also_failed", pull_request_id=pull_request_id)
            if "budget exceeded" in str(exc).lower():
                return {"status": "failed", "error": str(exc)}
            if "resource_exhausted" in str(exc).lower() or "429" in str(exc):
                raise self.retry(exc=exc, countdown=120)
            raise self.retry(exc=exc)