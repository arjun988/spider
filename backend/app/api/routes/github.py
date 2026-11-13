"""GitHub App installation and repository discovery endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin_token
from app.database.session import get_sync_session_factory
from app.github.webhook_handler import sync_installation_repositories, upsert_repository
from app.models.github import GitHubInstallation
from app.models.organization import Organization
from app.models.repository import Repository

router = APIRouter(prefix="/github", tags=["github"])


def get_sync_db():
    factory = get_sync_session_factory()
    assert factory is not None
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class InstallationOut(BaseModel):
    id: uuid.UUID
    installation_id: int
    account_login: str
    account_type: str
    is_active: bool
    organization_id: uuid.UUID

    model_config = {"from_attributes": True}


class GitHubStatusOut(BaseModel):
    configured: bool
    app_id: str | None
    app_name: str | None
    install_url: str | None
    installations: list[InstallationOut]


@router.get("/status", response_model=GitHubStatusOut)
def github_status(db: Session = Depends(get_sync_db)) -> GitHubStatusOut:
    rows = db.execute(
        select(GitHubInstallation).where(GitHubInstallation.is_active.is_(True))
    ).scalars().all()
    install_url = None
    if settings.github_app_name:
        install_url = f"https://github.com/apps/{settings.github_app_name}/installations/new"
    return GitHubStatusOut(
        configured=settings.github_app_configured,
        app_id=settings.github_app_id or None,
        app_name=settings.github_app_name or None,
        install_url=install_url,
        installations=[InstallationOut.model_validate(r) for r in rows],
    )


@router.post("/installations/{installation_id}/sync-repos")
def sync_repos(
    installation_id: int,
    db: Session = Depends(get_sync_db),
    _: None = Depends(require_admin_token),
) -> dict:
    row = db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.installation_id == installation_id,
            GitHubInstallation.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Installation not found")
    try:
        count = sync_installation_repositories(db, installation_id, row.organization_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}") from exc
    return {"synced": count, "installation_id": installation_id}


@router.post("/repositories/{repository_id}/enable")
def enable_repo(repository_id: uuid.UUID, db: Session = Depends(get_sync_db)) -> dict:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.auto_review_enabled = True
    return {"id": str(repo.id), "auto_review_enabled": True}


@router.post("/repositories/{repository_id}/disable")
def disable_repo(repository_id: uuid.UUID, db: Session = Depends(get_sync_db)) -> dict:
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.auto_review_enabled = False
    return {"id": str(repo.id), "auto_review_enabled": False}