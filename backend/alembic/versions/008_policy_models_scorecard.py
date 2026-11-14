"""Org policy packs, stage models, finding decision traces.

Revision ID: 008
Revises: 007
Create Date: 2026-11-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_configurations",
        sa.Column("triage_model", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "model_configurations",
        sa.Column("verify_model", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "model_configurations",
        sa.Column("policy_pack", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "model_configurations",
        sa.Column(
            "block_on_secrets",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "model_configurations",
        sa.Column(
            "block_on_critical",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "model_configurations",
        sa.Column(
            "require_spider_check",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "review_findings",
        sa.Column("decision_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_findings", "decision_trace")
    op.drop_column("model_configurations", "require_spider_check")
    op.drop_column("model_configurations", "block_on_critical")
    op.drop_column("model_configurations", "block_on_secrets")
    op.drop_column("model_configurations", "policy_pack")
    op.drop_column("model_configurations", "verify_model")
    op.drop_column("model_configurations", "triage_model")
