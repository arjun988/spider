"""Code intelligence models — chunks, symbols, dependencies with pgvector."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class CodeChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "code_chunks"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "file_path",
            "start_line",
            "end_line",
            "commit_sha",
            name="uq_chunk_location_commit",
        ),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    chunk_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="function",
    )  # function | class | method | module | block
    symbol_name: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    index_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding = mapped_column(
        Vector(settings.gemini_embedding_dimensions),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    repository: Mapped[Repository] = relationship(back_populates="chunks")


class CodeSymbol(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "code_symbols"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "qualified_name",
            "commit_sha",
            name="uq_symbol_qualified_commit",
        ),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    qualified_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    symbol_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # function | class | method | variable | import | module
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_exported: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_test: Mapped[bool] = mapped_column(default=False, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    index_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    repository: Mapped[Repository] = relationship(back_populates="symbols")


class CodeDependency(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "code_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "source_symbol_id",
            "target_symbol_id",
            "dependency_type",
            "commit_sha",
            name="uq_dependency_edge",
        ),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_symbols.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    target_symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_symbols.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_file: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    dependency_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # import | call | inherit | reference
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)