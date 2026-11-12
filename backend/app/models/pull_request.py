"""Pull request and commit tracking models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.review import ReviewJob


class PullRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "number", name="uq_repo_pr_number"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_pr_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="open", index=True)
    author_login: Mapped[str] = mapped_column(String(255), nullable=False)
    author_avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    head_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    html_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )  # pending | queued | reviewing | completed | failed | skipped
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    repository: Mapped[Repository] = relationship(back_populates="pull_requests")
    commits: Mapped[list[PullRequestCommit]] = relationship(
        back_populates="pull_request",
        cascade="all, delete-orphan",
    )
    review_jobs: Mapped[list[ReviewJob]] = relationship(
        back_populates="pull_request",
        cascade="all, delete-orphan",
    )


class PullRequestCommit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pull_request_commits"
    __table_args__ = (
        UniqueConstraint("pull_request_id", "sha", name="uq_pr_commit_sha"),
    )

    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_login: Mapped[str | None] = mapped_column(String(255), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed: Mapped[bool] = mapped_column(default=False, nullable=False)

    pull_request: Mapped[PullRequest] = relationship(back_populates="commits")