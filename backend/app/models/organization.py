"""Organization model — top-level tenant boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.github import GitHubInstallation
    from app.models.repository import Repository
    from app.models.settings import ModelConfiguration


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    github_org_login: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    github_org_id: Mapped[int | None] = mapped_column(nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    installations: Mapped[list[GitHubInstallation]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    repositories: Mapped[list[Repository]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    model_config_rel: Mapped[ModelConfiguration | None] = relationship(
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan",
    )