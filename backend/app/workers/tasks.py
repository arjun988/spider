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


@celery_app.task(name="spider.index_repository", bind=True, max_retries=3, default_retry_delay=60)
def index_repository(self, repository_id: str, full: bool = False) -> dict:
    from app.indexing.repository_manager import index_repository as run_index

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
            raise self.retry(exc=exc)


@celery_app.task(name="spider.review_pull_request", bind=True, max_retries=3, default_retry_delay=90)
def review_pull_request(self, pull_request_id: str, commit_sha: str) -> dict:
    from app.services.cost_service import ensure_within_budget
    from app.services.review_service import run_review_job
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
            # Don't retry budget errors forever
            if "budget exceeded" in str(exc).lower():
                return {"status": "failed", "error": str(exc)}
            raise self.retry(exc=exc)