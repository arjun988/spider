"""CSV/JSON export endpoints for findings and usage."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.routes.github import get_sync_db
from app.core.security import AuthContext, require_user
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewFinding, ReviewJob
from app.models.usage import ApiUsageRecord

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/findings.csv")
def export_findings_csv(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(ReviewFinding, ReviewJob, PullRequest, Repository)
        .join(ReviewJob, ReviewFinding.review_job_id == ReviewJob.id)
        .join(PullRequest, ReviewJob.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(ReviewFinding.created_at >= since)
        .order_by(ReviewFinding.created_at.desc())
    )
    if auth.organization_id:
        q = q.where(Repository.organization_id == auth.organization_id)
    rows = db.execute(q).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "finding_id",
            "repository",
            "pr_number",
            "severity",
            "category",
            "confidence",
            "title",
            "file_path",
            "start_line",
            "published",
            "created_at",
        ]
    )
    for finding, job, pr, repo in rows:
        writer.writerow(
            [
                str(finding.id),
                repo.full_name,
                pr.number,
                finding.severity,
                finding.category,
                finding.confidence,
                finding.title,
                finding.file_path,
                finding.start_line,
                finding.published,
                finding.created_at.isoformat() if finding.created_at else "",
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=spider-findings.csv"},
    )


@router.get("/usage.csv")
def export_usage_csv(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = select(ApiUsageRecord).where(ApiUsageRecord.created_at >= since).order_by(ApiUsageRecord.created_at.desc())
    if auth.organization_id:
        q = q.where(ApiUsageRecord.organization_id == auth.organization_id)
    rows = db.execute(q).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "model",
            "operation",
            "input_tokens",
            "output_tokens",
            "estimated_cost_usd",
            "created_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                str(r.id),
                r.model_name,
                getattr(r, "operation", None) or getattr(r, "request_type", ""),
                getattr(r, "input_tokens", 0),
                getattr(r, "output_tokens", 0),
                getattr(r, "estimated_cost_usd", 0),
                r.created_at.isoformat() if r.created_at else "",
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=spider-usage.csv"},
    )


@router.get("/findings.json")
def export_findings_json(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_sync_db),
    auth: AuthContext = Depends(require_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(ReviewFinding)
        .join(ReviewJob, ReviewFinding.review_job_id == ReviewJob.id)
        .join(PullRequest, ReviewJob.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(ReviewFinding.created_at >= since)
    )
    if auth.organization_id:
        q = q.where(Repository.organization_id == auth.organization_id)
    findings = db.execute(q).scalars().all()
    return {
        "count": len(findings),
        "items": [
            {
                "id": str(f.id),
                "severity": f.severity,
                "category": f.category,
                "title": f.title,
                "file_path": f.file_path,
                "published": f.published,
                "confidence": f.confidence,
            }
            for f in findings
        ],
    }
