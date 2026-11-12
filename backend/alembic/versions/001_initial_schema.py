"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-11-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("github_org_login", sa.String(255), nullable=True),
        sa.Column("github_org_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("github_org_login"),
        sa.UniqueConstraint("github_org_id"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.create_table(
        "github_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(50), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("permissions", postgresql.JSONB(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("installation_id", name="uq_github_installation_id"),
    )
    op.create_index("ix_github_installations_organization_id", "github_installations", ["organization_id"])

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=True),
        sa.Column("installation_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="received"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("delivery_id", name="uq_webhook_delivery_id"),
    )
    op.create_index("ix_webhook_events_delivery_id", "webhook_events", ["delivery_id"])
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_status", "webhook_events", ["status"])

    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(512), nullable=False),
        sa.Column("owner_login", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("primary_language", sa.String(100), nullable=True),
        sa.Column("clone_url", sa.String(1024), nullable=True),
        sa.Column("html_url", sa.String(1024), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_review_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("indexing_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("last_indexed_commit_sha", sa.String(64), nullable=True),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("index_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("local_path", sa.String(1024), nullable=True),
        sa.Column("prs_reviewed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "github_repo_id", name="uq_org_github_repo"),
        sa.UniqueConstraint("full_name", name="uq_repo_full_name"),
    )
    op.create_index("ix_repositories_organization_id", "repositories", ["organization_id"])
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"])
    op.create_index("ix_repositories_indexing_status", "repositories", ["indexing_status"])

    op.create_table(
        "repository_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("repository_id", "path", "commit_sha", name="uq_repo_file_path_commit"),
    )
    op.create_index("ix_repository_files_repository_id", "repository_files", ["repository_id"])
    op.create_index("ix_repository_files_path", "repository_files", ["path"])
    op.create_index("ix_repository_files_commit_sha", "repository_files", ["commit_sha"])

    op.create_table(
        "repository_index_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False, server_default="full"),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("from_commit_sha", sa.String(64), nullable=True),
        sa.Column("to_commit_sha", sa.String(64), nullable=True),
        sa.Column("files_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("symbols_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_repository_index_jobs_repository_id", "repository_index_jobs", ["repository_id"])
    op.create_index("ix_repository_index_jobs_status", "repository_index_jobs", ["status"])

    op.create_table(
        "code_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column("chunk_type", sa.String(50), nullable=False, server_default="function"),
        sa.Column("symbol_name", sa.String(512), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "repository_id", "file_path", "start_line", "end_line", "commit_sha",
            name="uq_chunk_location_commit",
        ),
    )
    op.create_index("ix_code_chunks_repository_id", "code_chunks", ["repository_id"])
    op.create_index("ix_code_chunks_file_path", "code_chunks", ["file_path"])
    op.create_index("ix_code_chunks_symbol_name", "code_chunks", ["symbol_name"])
    op.create_index("ix_code_chunks_commit_sha", "code_chunks", ["commit_sha"])
    # HNSW works on empty tables; IVFFlat requires existing rows
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_code_chunks_embedding "
        "ON code_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "code_symbols",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("qualified_name", sa.String(1024), nullable=False),
        sa.Column("symbol_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("is_exported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("repository_id", "qualified_name", "commit_sha", name="uq_symbol_qualified_commit"),
    )
    op.create_index("ix_code_symbols_repository_id", "code_symbols", ["repository_id"])
    op.create_index("ix_code_symbols_name", "code_symbols", ["name"])
    op.create_index("ix_code_symbols_file_path", "code_symbols", ["file_path"])
    op.create_index("ix_code_symbols_commit_sha", "code_symbols", ["commit_sha"])

    op.create_table(
        "code_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_symbol_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("code_symbols.id", ondelete="CASCADE"), nullable=True),
        sa.Column("target_symbol_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("code_symbols.id", ondelete="CASCADE"), nullable=True),
        sa.Column("source_file", sa.String(1024), nullable=False),
        sa.Column("target_name", sa.String(1024), nullable=False),
        sa.Column("dependency_type", sa.String(50), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "repository_id", "source_symbol_id", "target_symbol_id", "dependency_type", "commit_sha",
            name="uq_dependency_edge",
        ),
    )
    op.create_index("ix_code_dependencies_repository_id", "code_dependencies", ["repository_id"])

    op.create_table(
        "pull_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_pr_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(50), nullable=False, server_default="open"),
        sa.Column("author_login", sa.String(255), nullable=False),
        sa.Column("author_avatar_url", sa.String(1024), nullable=True),
        sa.Column("base_branch", sa.String(255), nullable=False),
        sa.Column("head_branch", sa.String(255), nullable=False),
        sa.Column("base_sha", sa.String(64), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("html_url", sa.String(1024), nullable=True),
        sa.Column("review_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("findings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_sha", sa.String(64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("repository_id", "number", name="uq_repo_pr_number"),
    )
    op.create_index("ix_pull_requests_repository_id", "pull_requests", ["repository_id"])
    op.create_index("ix_pull_requests_number", "pull_requests", ["number"])
    op.create_index("ix_pull_requests_state", "pull_requests", ["state"])
    op.create_index("ix_pull_requests_review_status", "pull_requests", ["review_status"])
    op.create_index("ix_pull_requests_head_sha", "pull_requests", ["head_sha"])

    op.create_table(
        "pull_request_commits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pull_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sha", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("author_login", sa.String(255), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pull_request_id", "sha", name="uq_pr_commit_sha"),
    )
    op.create_index("ix_pull_request_commits_pull_request_id", "pull_request_commits", ["pull_request_id"])
    op.create_index("ix_pull_request_commits_sha", "pull_request_commits", ["sha"])

    op.create_table(
        "review_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pull_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False, server_default="webhook"),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("findings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("github_review_id", sa.BigInteger(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_summary", postgresql.JSONB(), nullable=True),
        sa.Column("timeline", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pull_request_id", "commit_sha", name="uq_review_pr_commit"),
    )
    op.create_index("ix_review_jobs_pull_request_id", "review_jobs", ["pull_request_id"])
    op.create_index("ix_review_jobs_commit_sha", "review_jobs", ["commit_sha"])
    op.create_index("ix_review_jobs_status", "review_jobs", ["status"])

    op.create_table(
        "review_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("review_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_key", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("failure_scenario", sa.Text(), nullable=False),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("supporting_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("verification_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("github_comment_id", sa.Integer(), nullable=True),
        sa.Column("diff_position", sa.Integer(), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_review_findings_review_job_id", "review_findings", ["review_job_id"])
    op.create_index("ix_review_findings_finding_key", "review_findings", ["finding_key"])
    op.create_index("ix_review_findings_category", "review_findings", ["category"])
    op.create_index("ix_review_findings_severity", "review_findings", ["severity"])
    op.create_index("ix_review_findings_verification_status", "review_findings", ["verification_status"])

    op.create_table(
        "verification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("command_output", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("finding_id"),
    )
    op.create_index("ix_verification_results_finding_id", "verification_results", ["finding_id"])

    op.create_table(
        "review_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feedback_type", sa.String(50), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("author_login", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_review_feedback_finding_id", "review_feedback", ["finding_id"])

    op.create_table(
        "model_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("api_key_last_four", sa.String(8), nullable=True),
        sa.Column("api_key_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("connection_status", sa.String(50), nullable=False, server_default="not_configured"),
        sa.Column("primary_model", sa.String(255), nullable=False, server_default="gemini-2.0-flash"),
        sa.Column("embedding_model", sa.String(255), nullable=False, server_default="text-embedding-004"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="8192"),
        sa.Column("auto_review_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("severity_threshold", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default="0.6"),
        sa.Column("max_files_per_review", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("context_retrieval_limit", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("monthly_budget_usd", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("budget_alert_threshold", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_model_configurations_organization_id", "model_configurations", ["organization_id"])

    op.create_table(
        "api_usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.String(1024), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_api_usage_records_organization_id", "api_usage_records", ["organization_id"])
    op.create_index("ix_api_usage_records_review_job_id", "api_usage_records", ["review_job_id"])
    op.create_index("ix_api_usage_records_model_name", "api_usage_records", ["model_name"])
    op.create_index("ix_api_usage_records_operation", "api_usage_records", ["operation"])

    op.create_table(
        "cost_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cost_records_organization_id", "cost_records", ["organization_id"])
    op.create_index("ix_cost_records_date", "cost_records", ["date"])


def downgrade() -> None:
    for table in [
        "cost_records",
        "api_usage_records",
        "model_configurations",
        "review_feedback",
        "verification_results",
        "review_findings",
        "review_jobs",
        "pull_request_commits",
        "pull_requests",
        "code_dependencies",
        "code_symbols",
        "code_chunks",
        "repository_index_jobs",
        "repository_files",
        "repositories",
        "webhook_events",
        "github_installations",
        "organizations",
    ]:
        op.drop_table(table)