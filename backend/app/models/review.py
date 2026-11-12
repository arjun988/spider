"""Review jobs, findings, verification results, and feedback."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
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
    from app.models.pull_request import PullRequest


class ReviewJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_jobs"
    __table_args__ = (
        UniqueConstraint("pull_request_id", "commit_sha", name="uq_review_pr_commit"),
    )

    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="webhook",
    )  # webhook | manual | comment | reindex
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="queued",
        index=True,
    )  # queued | analyzing | retrieving | detecting | verifying | publishing | completed | failed
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    github_review_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    timeline: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    pull_request: Mapped[PullRequest] = relationship(back_populates="review_jobs")
    findings: Mapped[list[ReviewFinding]] = relationship(
        back_populates="review_job",
        cascade="all, delete-orphan",
    )


class ReviewFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_findings"

    review_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # bug | security | test | performance | style | other
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # critical | high | medium | low | informational
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    failure_scenario: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )  # pending | verified | rejected | confirmed_static | confirmed_test | unverifiable
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    github_comment_id: Mapped[int | None] = mapped_column(nullable=True)
    diff_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    review_job: Mapped[ReviewJob] = relationship(back_populates="findings")
    verification: Mapped[VerificationResult | None] = relationship(
        back_populates="finding",
        uselist=False,
        cascade="all, delete-orphan",
    )
    feedback: Mapped[list[ReviewFeedback]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
    )


class VerificationResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "verification_results"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_findings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )  # ai_review | static_analysis | unit_test | type_check | lint | sandbox
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # confirmed | rejected | inconclusive | error
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    finding: Mapped[ReviewFinding] = relationship(back_populates="verification")


class ReviewFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_feedback"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feedback_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # helpful | false_positive | dismissed | fixed
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_login: Mapped[str | None] = mapped_column(String(255), nullable=True)

    finding: Mapped[ReviewFinding] = relationship(back_populates="feedback")