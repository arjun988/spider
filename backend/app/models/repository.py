"""Repository and indexing job models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    from app.models.code_index import CodeChunk, CodeSymbol
    from app.models.organization import Organization
    from app.models.pull_request import PullRequest


class Repository(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("organization_id", "github_repo_id", name="uq_org_github_repo"),
        UniqueConstraint("full_name", name="uq_repo_full_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_repo_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    owner_login: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    primary_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clone_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    html_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_review_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    indexing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )  # pending | indexing | ready | failed | stale
    last_indexed_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    index_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    local_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    prs_reviewed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="repositories")
    files: Mapped[list[RepositoryFile]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    index_jobs: Mapped[list[RepositoryIndexJob]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    pull_requests: Mapped[list[PullRequest]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list[CodeChunk]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    symbols: Mapped[list[CodeSymbol]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class RepositoryFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_files"
    __table_args__ = (
        UniqueConstraint("repository_id", "path", "commit_sha", name="uq_repo_file_path_commit"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    repository: Mapped[Repository] = relationship(back_populates="files")


class RepositoryIndexJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_index_jobs"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="full",
    )  # full | incremental
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="queued",
        index=True,
    )  # queued | running | completed | failed
    from_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    files_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    symbols_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    repository: Mapped[Repository] = relationship(back_populates="index_jobs")