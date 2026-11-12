"""Celery task stubs — implemented in later phases."""

from __future__ import annotations

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="spider.ping")
def ping() -> dict[str, str]:
    logger.info("celery_ping")
    return {"status": "ok"}


@celery_app.task(name="spider.index_repository", bind=True, max_retries=3)
def index_repository(self, repository_id: str, full: bool = False) -> dict[str, str]:
    """Placeholder — full indexing pipeline in Phase 3."""
    logger.info("index_repository_queued", repository_id=repository_id, full=full)
    return {"status": "queued", "repository_id": repository_id}


@celery_app.task(name="spider.review_pull_request", bind=True, max_retries=3)
def review_pull_request(self, pull_request_id: str, commit_sha: str) -> dict[str, str]:
    """Placeholder — multi-stage review engine in Phase 4."""
    logger.info(
        "review_pull_request_queued",
        pull_request_id=pull_request_id,
        commit_sha=commit_sha,
    )
    return {"status": "queued", "pull_request_id": pull_request_id, "commit_sha": commit_sha}