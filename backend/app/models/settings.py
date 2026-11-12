"""Organization-level Gemini BYOK and review configuration."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class ModelConfiguration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Centralized Gemini model configuration — never hardcode model names elsewhere."""

    __tablename__ = "model_configurations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Encrypted at rest — never return raw key via API
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_last_four: Mapped[str | None] = mapped_column(String(8), nullable=True)
    api_key_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    connection_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="not_configured",
    )  # not_configured | connected | invalid | rate_limited | error

    primary_model: Mapped[str] = mapped_column(String(255), nullable=False, default="gemini-2.0-flash")
    embedding_model: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="text-embedding-004",
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=8192, nullable=False)

    # Review settings
    auto_review_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    severity_threshold: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    max_files_per_review: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    context_retrieval_limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    monthly_budget_usd: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    budget_alert_threshold: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="model_config_rel")