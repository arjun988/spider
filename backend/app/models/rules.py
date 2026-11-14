"""Per-repository review rules."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RepositoryReviewRules(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_review_rules"
    __table_args__ = (
        UniqueConstraint("repository_id", name="uq_repo_review_rules"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ignore_paths: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    severity_threshold: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled_languages: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    max_findings: Mapped[int | None] = mapped_column(Integer, nullable=True)

    repository = relationship("Repository", back_populates="review_rules")
