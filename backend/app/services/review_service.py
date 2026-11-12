"""Orchestrates end-to-end PR review: AI pipeline, verification, GitHub publish."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import run_review_pipeline
from app.agents.schemas import FindingDraft
from app.core.logging import get_logger
from app.github.client import GitHubClient
from app.github.pull_request_service import fetch_pr_diff_bundle
from app.github.review_publisher import publish_review
from app.models.github import GitHubInstallation
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewFinding, ReviewJob, VerificationResult
from app.verification.static_analysis import scan_files
from app.verification.test_runner import run_relevant_checks

logger = get_logger(__name__)


def _sum_usage(usage: list[dict]) -> tuple[int, int, float]:
    inp = sum(int(u.get("input_tokens") or 0) for u in usage)
    out = sum(int(u.get("output_tokens") or 0) for u in usage)
    cost = sum(float(u.get("estimated_cost_usd") or 0) for u in usage)
    return inp, out, cost


def run_review_job(db: Session, pull_request_id: str, commit_sha: str) -> dict:
    pr = db.get(PullRequest, uuid.UUID(str(pull_request_id)))
    if not pr:
        raise ValueError("Pull request not found")
    repo = db.get(Repository, pr.repository_id)
    if not repo:
        raise ValueError("Repository not found")

    job = db.execute(
        select(ReviewJob).where(
            ReviewJob.pull_request_id == pr.id,
            ReviewJob.commit_sha == commit_sha,
        )
    ).scalar_one_or_none()
    if not job:
        job = ReviewJob(
            pull_request_id=pr.id,
            commit_sha=commit_sha,
            trigger="manual",
            status="queued",
        )
        db.add(job)
        db.flush()

    if job.status == "completed":
        return {"status": "already_completed", "review_job_id": str(job.id)}

    started = datetime.now(timezone.utc)
    job.status = "analyzing"
    job.started_at = started
    pr.review_status = "reviewing"
    db.flush()

    installation = db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.organization_id == repo.organization_id,
            GitHubInstallation.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not installation:
        job.status = "failed"
        job.error_message = "No active GitHub installation"
        pr.review_status = "failed"
        db.flush()
        raise RuntimeError(job.error_message)

    client = GitHubClient(installation.installation_id)
    files = (job.change_summary or {}).get("files")
    if not files:
        bundle = fetch_pr_diff_bundle(client, repo, pr.number)
        files = bundle["files"]
        job.change_summary = {
            "files": files,
            "base_sha": bundle["base_sha"],
            "head_sha": bundle["head_sha"],
        }
        db.flush()

    try:
        # Static analysis supplements
        static_hits = scan_files(files)
        static_drafts: list[FindingDraft] = []
        for i, hit in enumerate(static_hits):
            static_drafts.append(
                FindingDraft(
                    finding_key=f"static-{hit.rule}-{i}",
                    file_path=hit.file_path,
                    start_line=hit.line,
                    end_line=hit.line,
                    category="security" if "secret" in hit.rule or "sql" in hit.rule else "bug",
                    severity=hit.severity,  # type: ignore[arg-type]
                    confidence=0.85,
                    title=hit.message,
                    explanation=hit.message,
                    failure_scenario=f"Static rule `{hit.rule}` matched introduced code.",
                    suggested_fix="Remove secrets / use parameterized queries as appropriate.",
                    verification_status="confirmed_static",
                    should_publish=True,
                )
            )

        job.status = "detecting"
        db.flush()
        decision, usage, timeline = run_review_pipeline(
            db,
            repo,
            pr.title,
            pr.body,
            files,
            review_job_id=job.id,
        )

        # Merge static findings (already confirmed)
        for draft in static_drafts:
            decision.findings.append(draft)
            if draft.should_publish:
                decision.published_count += 1

        # Optional sandbox checks — annotate only, do not claim reproduction unless success
        job.status = "verifying"
        db.flush()
        sandbox_note = None
        if repo.local_path:
            results = run_relevant_checks(repo.local_path)
            if results:
                sandbox_note = [
                    {
                        "method": r.method,
                        "success": r.success,
                        "exit_code": r.exit_code,
                        "stderr": r.stderr[-500:],
                    }
                    for r in results
                ]
                timeline.append({"stage": "sandbox", "status": "completed", "results": sandbox_note})

        # Persist findings
        for draft in decision.findings:
            finding = ReviewFinding(
                review_job_id=job.id,
                finding_key=draft.finding_key,
                file_path=draft.file_path,
                start_line=draft.start_line,
                end_line=draft.end_line,
                category=draft.category,
                severity=draft.severity,
                confidence=draft.confidence,
                title=draft.title,
                explanation=draft.explanation,
                failure_scenario=draft.failure_scenario,
                suggested_fix=draft.suggested_fix,
                supporting_evidence=draft.supporting_evidence,
                verification_status=draft.verification_status,
                published=False,
                rejected_reason=draft.rejected_reason,
            )
            db.add(finding)
            db.flush()
            db.add(
                VerificationResult(
                    finding_id=finding.id,
                    method="ai_review" if draft.verification_status != "confirmed_static" else "static_analysis",
                    status="confirmed" if draft.should_publish else "rejected",
                    details=draft.rejected_reason or draft.verification_status,
                )
            )

        inp, out, cost = _sum_usage(usage)
        job.input_tokens = inp
        job.output_tokens = out
        job.estimated_cost_usd = cost
        job.model_name = next((u.get("model") for u in usage if u.get("model")), None)
        job.summary = decision.summary
        job.findings_count = len(decision.findings)
        job.rejected_count = decision.rejected_count
        job.timeline = timeline
        job.change_summary = {
            **(job.change_summary or {}),
            "analysis_summary": decision.summary,
            "sandbox": sandbox_note,
        }

        # Publish to GitHub
        job.status = "publishing"
        db.flush()
        publishable = [f.model_dump() for f in decision.findings if f.should_publish]
        file_patches = {f.get("filename"): f.get("patch") for f in files}
        owner, name = repo.full_name.split("/", 1)
        pub = publish_review(
            client,
            owner,
            name,
            pr.number,
            commit_sha,
            publishable,
            file_patches,
            change_summary=decision.summary,
        )
        job.github_review_id = pub.get("review_id")
        job.published_count = pub.get("published_comments") or 0

        # Mark published findings
        rows = db.execute(
            select(ReviewFinding).where(ReviewFinding.review_job_id == job.id)
        ).scalars().all()
        publish_keys = {f["finding_key"] for f in publishable}
        for row in rows:
            if row.finding_key in publish_keys:
                row.published = True

        finished = datetime.now(timezone.utc)
        job.status = "completed"
        job.completed_at = finished
        job.duration_ms = int((finished - started).total_seconds() * 1000)
        pr.review_status = "completed"
        pr.findings_count = job.published_count
        pr.last_reviewed_at = finished
        pr.last_reviewed_sha = commit_sha
        pr.critical_count = sum(1 for f in decision.findings if f.should_publish and f.severity == "critical")
        pr.high_count = sum(1 for f in decision.findings if f.should_publish and f.severity == "high")
        repo.prs_reviewed_count = (repo.prs_reviewed_count or 0) + 1
        repo.last_review_at = finished
        db.flush()

        logger.info(
            "review_complete",
            pr=pr.number,
            published=job.published_count,
            cost=job.estimated_cost_usd,
        )
        return {
            "status": "completed",
            "review_job_id": str(job.id),
            "published": job.published_count,
            "findings": job.findings_count,
            "cost_usd": job.estimated_cost_usd,
            "github_review_id": job.github_review_id,
        }
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        pr.review_status = "failed"
        db.flush()
        logger.exception("review_failed", pr=pr.number)
        raise