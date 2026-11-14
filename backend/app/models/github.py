"""GitHub App installation and webhook event models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class GitHubInstallation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "github_installations"
    __table_args__ = (
        UniqueConstraint("installation_id", name="uq_github_installation_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Organization")
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    permissions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="installations")


class WebhookEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_webhook_delivery_id"),
    )

    delivery_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    installation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="received",
        index=True,
    )  # received | processing | processed | failed | duplicate
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)