"""Idempotent GitHub webhook processing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.github.client import GitHubClient
from app.github.pull_request_service import (
    already_reviewed_commit,
    fetch_pr_diff_bundle,
    sync_pr_commits,
    upsert_pull_request,
)
from app.models.github import GitHubInstallation, WebhookEvent
from app.models.organization import Organization
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob
from app.models.settings import ModelConfiguration

logger = get_logger(__name__)


def record_webhook_event(
    db: Session,
    delivery_id: str,
    event_type: str,
    action: str | None,
    installation_id: int | None,
    payload: dict[str, Any],
) -> WebhookEvent | None:
    """Persist webhook with idempotency on delivery_id. Returns None if duplicate."""
    existing = db.execute(
        select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id)
    ).scalar_one_or_none()
    if existing:
        existing.status = "duplicate"
        db.flush()
        logger.info("webhook_duplicate", delivery_id=delivery_id)
        return None

    event = WebhookEvent(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        installation_id=installation_id,
        payload=payload,
        status="received",
    )
    db.add(event)
    db.flush()
    return event


def _ensure_org_for_installation(db: Session, account: dict[str, Any]) -> Organization:
    login = account.get("login") or "unknown"
    account_id = account.get("id")
    org = None
    if account_id:
        org = db.execute(
            select(Organization).where(Organization.github_org_id == account_id)
        ).scalar_one_or_none()
    if not org:
        org = db.execute(
            select(Organization).where(Organization.github_org_login == login)
        ).scalar_one_or_none()
    if not org:
        slug = login.lower().replace(" ", "-")
        org = Organization(
            name=login,
            slug=slug,
            github_org_login=login,
            github_org_id=account_id,
        )
        db.add(org)
        db.flush()
        # Default model config
        db.add(
            ModelConfiguration(
                organization_id=org.id,
                primary_model=settings.gemini_model,
                embedding_model=settings.gemini_embedding_model,
            )
        )
        db.flush()
    else:
        org.github_org_login = login
        org.github_org_id = account_id
        db.flush()
    return org


def handle_installation(db: Session, payload: dict[str, Any], action: str | None) -> dict[str, Any]:
    installation = payload.get("installation") or {}
    account = installation.get("account") or {}
    installation_id = installation.get("id")
    if not installation_id:
        return {"status": "ignored", "reason": "missing_installation_id"}

    if action == "deleted":
        row = db.execute(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == installation_id
            )
        ).scalar_one_or_none()
        if row:
            row.is_active = False
            db.flush()
        return {"status": "ok", "action": "deleted", "installation_id": installation_id}

    org = _ensure_org_for_installation(db, account)
    row = db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.installation_id == installation_id
        )
    ).scalar_one_or_none()
    if not row:
        row = GitHubInstallation(
            organization_id=org.id,
            installation_id=installation_id,
            account_login=account.get("login") or "",
            account_type=account.get("type") or "Organization",
            account_id=account.get("id") or 0,
            permissions=installation.get("permissions"),
            is_active=True,
        )
        db.add(row)
    else:
        row.organization_id = org.id
        row.account_login = account.get("login") or row.account_login
        row.is_active = True
        row.permissions = installation.get("permissions")
    db.flush()

    # Discover repositories
    synced = sync_installation_repositories(db, installation_id, org.id)
    return {
        "status": "ok",
        "action": action,
        "installation_id": installation_id,
        "repositories_synced": synced,
    }


def sync_installation_repositories(
    db: Session,
    installation_id: int,
    organization_id: uuid.UUID,
) -> int:
    client = GitHubClient(installation_id)
    repos = client.list_installation_repos()
    count = 0
    for repo_data in repos:
        upsert_repository(db, organization_id, repo_data)
        count += 1
    db.flush()
    return count


def upsert_repository(
    db: Session,
    organization_id: uuid.UUID,
    repo_data: dict[str, Any],
) -> Repository:
    github_repo_id = repo_data["id"]
    existing = db.execute(
        select(Repository).where(
            Repository.organization_id == organization_id,
            Repository.github_repo_id == github_repo_id,
        )
    ).scalar_one_or_none()

    owner = (repo_data.get("owner") or {}).get("login") or repo_data.get("full_name", "/").split("/")[0]
    fields = {
        "name": repo_data.get("name") or "",
        "full_name": repo_data.get("full_name") or "",
        "owner_login": owner,
        "default_branch": repo_data.get("default_branch") or "main",
        "primary_language": repo_data.get("language"),
        "clone_url": repo_data.get("clone_url"),
        "html_url": repo_data.get("html_url"),
        "is_private": bool(repo_data.get("private", True)),
    }

    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        return existing

    repo = Repository(
        organization_id=organization_id,
        github_repo_id=github_repo_id,
        **fields,
    )
    db.add(repo)
    db.flush()
    return repo


def _get_installation_for_payload(db: Session, payload: dict[str, Any]) -> GitHubInstallation | None:
    inst = payload.get("installation") or {}
    installation_id = inst.get("id")
    if not installation_id:
        return None
    return db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.installation_id == installation_id,
            GitHubInstallation.is_active.is_(True),
        )
    ).scalar_one_or_none()


def handle_pull_request(
    db: Session,
    payload: dict[str, Any],
    action: str | None,
) -> dict[str, Any]:
    if action not in {"opened", "synchronize", "reopened", "closed"}:
        return {"status": "ignored", "reason": f"action_{action}"}

    installation = _get_installation_for_payload(db, payload)
    if not installation:
        return {"status": "error", "reason": "installation_not_found"}

    repo_data = payload.get("repository") or {}
    pr_data = payload.get("pull_request") or {}
    repository = upsert_repository(db, installation.organization_id, repo_data)
    pr = upsert_pull_request(db, repository, pr_data)

    if action == "closed":
        pr.state = "closed" if not pr_data.get("merged") else "merged"
        pr.review_status = "skipped" if pr.review_status == "pending" else pr.review_status
        db.flush()
        return {"status": "ok", "action": "closed", "pr": pr.number}

    client = GitHubClient(installation.installation_id)
    sync_pr_commits(db, client, repository, pr)

    head_sha = pr.head_sha
    if already_reviewed_commit(db, pr.id, head_sha):
        logger.info("skip_duplicate_review", pr=pr.number, sha=head_sha)
        return {"status": "ok", "action": "skipped_duplicate", "pr": pr.number, "sha": head_sha}

    # Check auto-review settings (repo flag AND org model config)
    if not repository.auto_review_enabled:
        return {"status": "ok", "action": "auto_review_disabled", "pr": pr.number}
    from app.models.settings import ModelConfiguration

    org_cfg = db.execute(
        select(ModelConfiguration).where(
            ModelConfiguration.organization_id == repository.organization_id
        )
    ).scalar_one_or_none()
    if org_cfg and not org_cfg.auto_review_enabled:
        return {"status": "ok", "action": "org_auto_review_disabled", "pr": pr.number}

    job = ReviewJob(
        pull_request_id=pr.id,
        commit_sha=head_sha,
        trigger="webhook",
        status="queued",
    )
    db.add(job)
    pr.review_status = "queued"
    db.flush()

    # Prefetch diff into metadata for worker
    try:
        bundle = fetch_pr_diff_bundle(client, repository, pr.number)
        pr.metadata_json = {**(pr.metadata_json or {}), "last_diff": {
            "files": [
                {k: v for k, v in f.items() if k != "patch"}
                for f in bundle["files"]
            ],
            "file_count": len(bundle["files"]),
            "head_sha": bundle["head_sha"],
            "base_sha": bundle["base_sha"],
        }}
        # Store patches separately keyed for worker (keep in job change_summary later)
        job.change_summary = {
            "files": bundle["files"],
            "base_sha": bundle["base_sha"],
            "head_sha": bundle["head_sha"],
        }
        db.flush()
    except Exception as exc:
        logger.exception("diff_prefetch_failed", error=str(exc))

    return {
        "status": "ok",
        "action": action,
        "pr": pr.number,
        "review_job_id": str(job.id),
        "enqueue_review": True,
        "enqueue_index": repository.indexing_status in {"pending", "failed", "stale"},
        "repository_id": str(repository.id),
        "pull_request_id": str(pr.id),
        "commit_sha": head_sha,
    }


def handle_issue_comment(
    db: Session,
    payload: dict[str, Any],
    action: str | None,
) -> dict[str, Any]:
    if action != "created":
        return {"status": "ignored", "reason": f"action_{action}"}

    comment = payload.get("comment") or {}
    body = (comment.get("body") or "").strip()
    if not body.startswith("/review"):
        return {"status": "ignored", "reason": "not_a_command"}

    force = body.startswith("/review-again")
    issue = payload.get("issue") or {}
    if "pull_request" not in issue:
        return {"status": "ignored", "reason": "not_a_pr_comment"}

    installation = _get_installation_for_payload(db, payload)
    if not installation:
        return {"status": "error", "reason": "installation_not_found"}

    repo_data = payload.get("repository") or {}
    repository = upsert_repository(db, installation.organization_id, repo_data)
    client = GitHubClient(installation.installation_id)
    owner, name = repository.full_name.split("/", 1)
    pr_number = issue["number"]
    pr_data = client.get_pull_request(owner, name, pr_number)
    pr = upsert_pull_request(db, repository, pr_data)
    sync_pr_commits(db, client, repository, pr)

    if not force and already_reviewed_commit(db, pr.id, pr.head_sha):
        client.create_issue_comment(
            owner, name, pr_number,
            "Spider already reviewed this commit. Use `/review-again` to force a new review.",
        )
        return {"status": "ok", "action": "already_reviewed"}

    # Unique constraint is (pr_id, commit_sha) — reuse or replace any prior job safely.
    prior = db.execute(
        select(ReviewJob).where(
            ReviewJob.pull_request_id == pr.id,
            ReviewJob.commit_sha == pr.head_sha,
        )
    ).scalar_one_or_none()
    if prior:
        if force or prior.status == "failed":
            db.delete(prior)
            db.flush()
        elif already_reviewed_commit(db, pr.id, pr.head_sha):
            return {"status": "ok", "action": "skipped_duplicate"}

    if already_reviewed_commit(db, pr.id, pr.head_sha) and not force:
        return {"status": "ok", "action": "skipped_duplicate"}

    job = ReviewJob(
        pull_request_id=pr.id,
        commit_sha=pr.head_sha,
        trigger="comment",
        status="queued",
    )
    db.add(job)
    pr.review_status = "queued"
    try:
        bundle = fetch_pr_diff_bundle(client, repository, pr.number)
        job.change_summary = {
            "files": bundle["files"],
            "base_sha": bundle["base_sha"],
            "head_sha": bundle["head_sha"],
        }
    except Exception as exc:
        logger.exception("diff_prefetch_failed", error=str(exc))
    db.flush()

    client.create_issue_comment(
        owner, name, pr_number,
        f"Spider queued a review for `{pr.head_sha[:7]}`.",
    )

    return {
        "status": "ok",
        "action": "manual_review",
        "review_job_id": str(job.id),
        "enqueue_review": True,
        "repository_id": str(repository.id),
        "pull_request_id": str(pr.id),
        "commit_sha": pr.head_sha,
    }


def process_webhook(
    db: Session,
    event_type: str,
    action: str | None,
    delivery_id: str,
    payload: dict[str, Any],
    *,
    reuse_event: WebhookEvent | None = None,
) -> dict[str, Any]:
    installation_id = (payload.get("installation") or {}).get("id")
    if reuse_event is not None:
        event = reuse_event
        event.payload = payload
        event.event_type = event_type
        event.action = action
    else:
        event = record_webhook_event(db, delivery_id, event_type, action, installation_id, payload)
        if event is None:
            return {"status": "duplicate", "delivery_id": delivery_id}

    event.status = "processing"
    db.flush()

    try:
        if event_type == "installation":
            result = handle_installation(db, payload, action)
        elif event_type == "pull_request":
            result = handle_pull_request(db, payload, action)
        elif event_type == "issue_comment":
            result = handle_issue_comment(db, payload, action)
        elif event_type == "installation_repositories":
            installation = _get_installation_for_payload(db, payload)
            if installation:
                n = sync_installation_repositories(
                    db, installation.installation_id, installation.organization_id
                )
                result = {"status": "ok", "repositories_synced": n}
            else:
                result = {"status": "error", "reason": "installation_not_found"}
        elif event_type == "ping":
            result = {"status": "ok", "action": "ping"}
        else:
            result = {"status": "ignored", "github_event": event_type}

        if isinstance(result, dict) and result.get("status") == "error":
            event.status = "failed"
            event.error_message = str(result.get("reason") or "error")
            event.retry_count = (event.retry_count or 0) + 1
            event.processed_at = datetime.now(timezone.utc)
            db.flush()
            return result

        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        return result
    except Exception as exc:
        event.status = "failed"
        event.error_message = str(exc)
        event.retry_count = (event.retry_count or 0) + 1
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        logger.exception("webhook_processing_failed", delivery_id=delivery_id)
        raise