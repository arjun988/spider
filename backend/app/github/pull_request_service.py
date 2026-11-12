"""Pull request fetching, diff extraction, and persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.github.client import GitHubClient
from app.models.pull_request import PullRequest, PullRequestCommit
from app.models.repository import Repository

logger = get_logger(__name__)


def upsert_pull_request(
    db: Session,
    repository: Repository,
    pr_data: dict[str, Any],
) -> PullRequest:
    number = pr_data["number"]
    existing = db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repository.id,
            PullRequest.number == number,
        )
    ).scalar_one_or_none()

    head = pr_data.get("head") or {}
    base = pr_data.get("base") or {}
    user = pr_data.get("user") or {}

    fields = {
        "github_pr_id": pr_data["id"],
        "title": pr_data.get("title") or "",
        "body": pr_data.get("body"),
        "state": pr_data.get("state") or "open",
        "author_login": user.get("login") or "unknown",
        "author_avatar_url": user.get("avatar_url"),
        "base_branch": base.get("ref") or repository.default_branch,
        "head_branch": head.get("ref") or "",
        "base_sha": base.get("sha") or "",
        "head_sha": head.get("sha") or "",
        "html_url": pr_data.get("html_url"),
    }

    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        pr = existing
    else:
        pr = PullRequest(
            repository_id=repository.id,
            number=number,
            **fields,
        )
        db.add(pr)

    db.flush()
    return pr


def sync_pr_commits(
    db: Session,
    client: GitHubClient,
    repository: Repository,
    pr: PullRequest,
) -> list[PullRequestCommit]:
    owner, name = repository.full_name.split("/", 1)
    raw_commits = client.get_pull_request_commits(owner, name, pr.number)
    results: list[PullRequestCommit] = []

    for item in raw_commits:
        sha = item["sha"]
        existing = db.execute(
            select(PullRequestCommit).where(
                PullRequestCommit.pull_request_id == pr.id,
                PullRequestCommit.sha == sha,
            )
        ).scalar_one_or_none()
        if existing:
            results.append(existing)
            continue

        commit = item.get("commit") or {}
        author = (item.get("author") or {}) or {}
        committed_at = None
        date_str = (commit.get("author") or {}).get("date")
        if date_str:
            committed_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

        row = PullRequestCommit(
            pull_request_id=pr.id,
            sha=sha,
            message=commit.get("message"),
            author_login=author.get("login"),
            committed_at=committed_at,
            reviewed=False,
        )
        db.add(row)
        results.append(row)

    db.flush()
    return results


def fetch_pr_diff_bundle(
    client: GitHubClient,
    repository: Repository,
    pr_number: int,
) -> dict[str, Any]:
    """Fetch PR metadata, files, and patches for review."""
    owner, name = repository.full_name.split("/", 1)
    pr = client.get_pull_request(owner, name, pr_number)
    files = client.get_pull_request_files(owner, name, pr_number)
    commits = client.get_pull_request_commits(owner, name, pr_number)

    changed_files = []
    for f in files:
        changed_files.append(
            {
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
                "patch": f.get("patch"),
                "previous_filename": f.get("previous_filename"),
                "blob_url": f.get("blob_url"),
                "raw_url": f.get("raw_url"),
                "sha": f.get("sha"),
            }
        )

    return {
        "pull_request": pr,
        "files": changed_files,
        "commits": commits,
        "base_sha": (pr.get("base") or {}).get("sha"),
        "head_sha": (pr.get("head") or {}).get("sha"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def already_reviewed_commit(db: Session, pr_id: uuid.UUID, commit_sha: str) -> bool:
    from app.models.review import ReviewJob

    existing = db.execute(
        select(ReviewJob).where(
            ReviewJob.pull_request_id == pr_id,
            ReviewJob.commit_sha == commit_sha,
            ReviewJob.status.in_(["queued", "analyzing", "retrieving", "detecting", "verifying", "publishing", "completed"]),
        )
    ).scalar_one_or_none()
    return existing is not None