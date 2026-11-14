"""Add LLM provider + LiteLLM base URL columns.

Revision ID: 005
Revises: 004
Create Date: 2026-11-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_configurations",
        sa.Column("llm_provider", sa.String(length=50), nullable=False, server_default="gemini"),
    )
    op.add_column(
        "model_configurations",
        sa.Column("litellm_base_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_configurations", "litellm_base_url")
    op.drop_column("model_configurations", "llm_provider")
