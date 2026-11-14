"""Repository listing, indexing, and review rules."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.github import get_sync_db
from app.core.security import AuthContext, require_admin_token, require_member, require_user
from app.models.repository import Repository, RepositoryIndexJob
from app.models.rules import RepositoryReviewRules
from app.services.audit import emit_audit_sync

router = APIRouter(prefix="/repositories", tags=["repositories"])


class RepositoryOut(BaseModel):
    id: uuid.UUID
    name: str
    full_name: str
    owner_login: str
    primary_language: str | None
    indexing_status: str
    last_indexed_commit_sha: str | None
    last_indexed_at: datetime | None
    auto_review_enabled: bool
    prs_reviewed_count: int
    last_review_at: datetime | None
    html_url: str | None

    model_config = {"from_attributes": True}


class RepositoryListResponse(BaseModel):
    items: list[RepositoryOut]
    total: int


class ReviewRulesIn(BaseModel):
    ignore_paths: list[str] | None = None
    severity_threshold: str | None = None
    confidence_threshold: float | None = Field(default=None, ge=0, le=1)
    enabled_languages: list[str] | None = None
    max_findings: int | None = Field(default=None, ge=1, le=200)


class ReviewRulesOut(ReviewRulesIn):
    repository_id: uuid.UUID


class IndexJobOut(BaseModel):
    id: uuid.UUID
    job_type: str
    status: str
    files_processed: int
    total_files: int
    chunks_created: int
    symbols_created: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    progress_pct: float

    model_config = {"from_attributes": True}


def _scoped_repos(db: Session, auth: AuthContext) -> list[Repository]:
    q = select(Repository).order_by(Repository.full_name)
    if auth.organization_id:
        q = q.where(Repository.organization_id == auth.organization_id)
    return list(db.execute(q).scalars().all())


@router.get("", response_model=RepositoryListResponse)
def list_repositories(
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
) -> RepositoryListResponse:
    repos = _scoped_repos(db, auth)
    return RepositoryListResponse(
        items=[RepositoryOut.model_validate(r) for r in repos],
        total=len(repos),
    )


@router.get("/{repository_id}", response_model=RepositoryOut)
def get_repository(
    repository_id: uuid.UUID,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
) -> RepositoryOut:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if auth.organization_id and repo.organization_id != auth.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return RepositoryOut.model_validate(repo)


@router.post("/{repository_id}/reindex")
def reindex_repository(
    repository_id: uuid.UUID,
    full: bool = False,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_member),
) -> dict:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if auth.organization_id and repo.organization_id != auth.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    repo.indexing_status = "pending"
    db.flush()
    from app.workers.tasks import index_repository

    task = index_repository.delay(str(repository_id), full)
    emit_audit_sync(
        db,
        action="repository.reindex",
        actor_user_id=auth.user_id,
        organization_id=repo.organization_id,
        resource_type="repository",
        resource_id=str(repo.id),
        metadata={"full": full, "task_id": task.id},
    )
    return {
        "status": "queued",
        "task_id": task.id,
        "repository_id": str(repository_id),
        "full": full,
    }


@router.get("/{repository_id}/index-jobs")
def list_index_jobs(
    repository_id: uuid.UUID,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
) -> dict[str, Any]:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if auth.organization_id and repo.organization_id != auth.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    jobs = (
        db.execute(
            select(RepositoryIndexJob)
            .where(RepositoryIndexJob.repository_id == repository_id)
            .order_by(RepositoryIndexJob.created_at.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )
    items = []
    for j in jobs:
        pct = 0.0
        if j.total_files > 0:
            pct = round(100.0 * j.files_processed / j.total_files, 1)
        elif j.status == "completed":
            pct = 100.0
        items.append(
            IndexJobOut(
                id=j.id,
                job_type=j.job_type,
                status=j.status,
                files_processed=j.files_processed,
                total_files=j.total_files,
                chunks_created=j.chunks_created,
                symbols_created=j.symbols_created,
                error_message=j.error_message,
                started_at=j.started_at,
                completed_at=j.completed_at,
                progress_pct=pct,
            )
        )
    latest = items[0] if items else None
    return {"items": items, "latest": latest}


@router.get("/{repository_id}/rules", response_model=ReviewRulesOut)
def get_rules(
    repository_id: uuid.UUID,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
) -> ReviewRulesOut:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if auth.organization_id and repo.organization_id != auth.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rules = db.execute(
        select(RepositoryReviewRules).where(RepositoryReviewRules.repository_id == repository_id)
    ).scalar_one_or_none()
    if not rules:
        return ReviewRulesOut(repository_id=repository_id)
    return ReviewRulesOut(
        repository_id=repository_id,
        ignore_paths=list(rules.ignore_paths or []),
        severity_threshold=rules.severity_threshold,
        confidence_threshold=rules.confidence_threshold,
        enabled_languages=list(rules.enabled_languages or []) if rules.enabled_languages else None,
        max_findings=rules.max_findings,
    )


@router.put("/{repository_id}/rules", response_model=ReviewRulesOut)
def put_rules(
    repository_id: uuid.UUID,
    body: ReviewRulesIn,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_member),
) -> ReviewRulesOut:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if auth.organization_id and repo.organization_id != auth.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rules = db.execute(
        select(RepositoryReviewRules).where(RepositoryReviewRules.repository_id == repository_id)
    ).scalar_one_or_none()
    if rules is None:
        rules = RepositoryReviewRules(repository_id=repository_id)
        db.add(rules)
    rules.ignore_paths = body.ignore_paths
    rules.severity_threshold = body.severity_threshold
    rules.confidence_threshold = body.confidence_threshold
    rules.enabled_languages = body.enabled_languages
    rules.max_findings = body.max_findings
    emit_audit_sync(
        db,
        action="repository.rules_updated",
        actor_user_id=auth.user_id,
        organization_id=repo.organization_id,
        resource_type="repository",
        resource_id=str(repo.id),
        metadata=body.model_dump(),
    )
    db.flush()
    return get_rules(repository_id, db, auth)


@router.post("/{repository_id}/auto-review")
def set_auto_review(
    repository_id: uuid.UUID,
    enabled: bool = True,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_admin_token),
) -> dict:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if auth.organization_id and repo.organization_id != auth.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    repo.auto_review_enabled = enabled
    emit_audit_sync(
        db,
        action="repository.auto_review",
        actor_user_id=auth.user_id,
        organization_id=repo.organization_id,
        resource_type="repository",
        resource_id=str(repo.id),
        metadata={"enabled": enabled},
    )
    return {"id": str(repo.id), "auto_review_enabled": repo.auto_review_enabled}


@router.post("/{repository_id}/branch-protection")
def enable_spider_branch_protection(
    repository_id: uuid.UUID,
    branch: str | None = None,
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_admin_token),
) -> dict:
    """Require the Spider Review Check Run to pass before merge."""
    from app.models.github import GitHubInstallation
    from app.github.client import GitHubClient
    from app.models.settings import ModelConfiguration

    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if auth.organization_id and repo.organization_id != auth.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    cfg = db.execute(
        select(ModelConfiguration).where(
            ModelConfiguration.organization_id == repo.organization_id
        )
    ).scalar_one_or_none()
    if cfg and not cfg.require_spider_check:
        raise HTTPException(
            status_code=400,
            detail="require_spider_check is disabled in org settings",
        )

    installation = db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.organization_id == repo.organization_id,
            GitHubInstallation.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not installation:
        raise HTTPException(status_code=400, detail="No active GitHub installation")

    target_branch = branch or repo.default_branch or "main"
    client = GitHubClient(installation.installation_id)
    owner, name = repo.full_name.split("/", 1)
    try:
        result = client.require_status_checks(
            owner,
            name,
            target_branch,
            contexts=["Spider Review"],
            strict=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"GitHub branch protection failed: {exc}",
        ) from exc

    emit_audit_sync(
        db,
        action="repository.branch_protection",
        actor_user_id=auth.user_id,
        organization_id=repo.organization_id,
        resource_type="repository",
        resource_id=str(repo.id),
        metadata={"branch": target_branch, "contexts": ["Spider Review"]},
    )
    return {
        "status": "ok",
        "branch": target_branch,
        "required_contexts": ["Spider Review"],
        "protection": result,
    }
