"""Rules, check runs, index progress, audit logs.

Revision ID: 007
Revises: 006
Create Date: 2026-11-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repository_review_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ignore_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("severity_threshold", sa.String(length=50), nullable=True),
        sa.Column("confidence_threshold", sa.Float(), nullable=True),
        sa.Column("enabled_languages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("max_findings", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", name="uq_repo_review_rules"),
    )
    op.create_index("ix_repository_review_rules_repository_id", "repository_review_rules", ["repository_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])

    op.add_column("review_jobs", sa.Column("github_check_run_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "repository_index_jobs",
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "webhook_events",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("webhook_events", "dead_lettered_at")
    op.drop_column("repository_index_jobs", "total_files")
    op.drop_column("review_jobs", "github_check_run_id")
    op.drop_table("audit_logs")
    op.drop_table("repository_review_rules")
