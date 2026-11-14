"""Review quality scorecard and labeled eval harness."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewFeedback, ReviewFinding, ReviewJob


def quality_scorecard(
    db: Session,
    *,
    organization_id: UUID | None = None,
    days: int = 30,
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    repo_q = select(Repository.id, Repository.full_name)
    if organization_id:
        repo_q = repo_q.where(Repository.organization_id == organization_id)
    repos = {r.id: r.full_name for r in db.execute(repo_q).all()}

    fb = db.execute(
        select(
            PullRequest.repository_id,
            ReviewFeedback.feedback_type,
            func.count(),
        )
        .select_from(ReviewFeedback)
        .join(ReviewFinding, ReviewFinding.id == ReviewFeedback.finding_id)
        .join(ReviewJob, ReviewJob.id == ReviewFinding.review_job_id)
        .join(PullRequest, PullRequest.id == ReviewJob.pull_request_id)
        .where(ReviewFeedback.created_at >= since)
        .group_by(PullRequest.repository_id, ReviewFeedback.feedback_type)
    ).all()

    by_repo: dict[str, dict[str, Any]] = {}
    for repo_id, ftype, count in fb:
        if organization_id and repo_id not in repos:
            continue
        key = str(repo_id)
        slot = by_repo.setdefault(
            key,
            {
                "repository_id": key,
                "repository": repos.get(repo_id, key),
                "helpful": 0,
                "false_positive": 0,
                "dismissed": 0,
                "fixed": 0,
                "labeled": 0,
            },
        )
        if ftype in {"helpful", "false_positive", "dismissed", "fixed"}:
            slot[ftype] = int(count)
        slot["labeled"] += int(count)

    durations = db.execute(
        select(PullRequest.repository_id, func.avg(ReviewJob.duration_ms))
        .select_from(ReviewJob)
        .join(PullRequest, PullRequest.id == ReviewJob.pull_request_id)
        .where(
            ReviewJob.status == "completed",
            ReviewJob.completed_at >= since,
            ReviewJob.duration_ms.is_not(None),
        )
        .group_by(PullRequest.repository_id)
    ).all()
    duration_map = {rid: float(avg or 0) for rid, avg in durations}

    org_helpful = org_fp = org_total = 0
    per_repo: list[dict[str, Any]] = []
    for slot in by_repo.values():
        helpful = slot["helpful"] + slot["fixed"]
        fp = slot["false_positive"]
        labeled = slot["labeled"] or 1
        precision = helpful / max(helpful + fp, 1)
        fp_rate = fp / labeled
        rid = UUID(slot["repository_id"])
        slot["precision"] = round(precision, 4)
        slot["fp_rate"] = round(fp_rate, 4)
        slot["time_to_first_comment_ms"] = duration_map.get(rid)
        org_helpful += helpful
        org_fp += fp
        org_total += slot["labeled"]
        per_repo.append(slot)

    for rid, avg_ms in duration_map.items():
        key = str(rid)
        if key not in by_repo and (not organization_id or rid in repos):
            per_repo.append(
                {
                    "repository_id": key,
                    "repository": repos.get(rid, key),
                    "helpful": 0,
                    "false_positive": 0,
                    "dismissed": 0,
                    "fixed": 0,
                    "labeled": 0,
                    "precision": None,
                    "fp_rate": None,
                    "time_to_first_comment_ms": avg_ms,
                }
            )

    return {
        "days": days,
        "org": {
            "precision": round(org_helpful / max(org_helpful + org_fp, 1), 4) if org_total else None,
            "fp_rate": round(org_fp / org_total, 4) if org_total else None,
            "labeled_findings": org_total,
            "avg_time_to_first_comment_ms": (
                sum(duration_map.values()) / len(duration_map) if duration_map else None
            ),
        },
        "by_repository": sorted(per_repo, key=lambda x: x["repository"]),
    }


def eval_harness(
    db: Session,
    *,
    organization_id: UUID | None = None,
    days: int = 90,
) -> dict[str, Any]:
    """Track precision/recall proxy against human labels over time."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(
            func.date_trunc("week", ReviewFeedback.created_at).label("week"),
            ReviewFeedback.feedback_type,
            func.count(),
        )
        .select_from(ReviewFeedback)
        .join(ReviewFinding, ReviewFinding.id == ReviewFeedback.finding_id)
        .join(ReviewJob, ReviewJob.id == ReviewFinding.review_job_id)
        .join(PullRequest, PullRequest.id == ReviewJob.pull_request_id)
        .join(Repository, Repository.id == PullRequest.repository_id)
        .where(ReviewFeedback.created_at >= since)
        .group_by("week", ReviewFeedback.feedback_type)
        .order_by("week")
    )
    if organization_id:
        q = q.where(Repository.organization_id == organization_id)

    rows = db.execute(q).all()
    weeks: dict[str, dict[str, int]] = {}
    for week, ftype, count in rows:
        key = week.date().isoformat() if hasattr(week, "date") else str(week)
        slot = weeks.setdefault(
            key, {"helpful": 0, "false_positive": 0, "fixed": 0, "dismissed": 0}
        )
        if ftype in slot:
            slot[ftype] = int(count)

    series = []
    for week, counts in sorted(weeks.items()):
        tp = counts["helpful"] + counts["fixed"]
        fp = counts["false_positive"]
        precision = tp / max(tp + fp, 1)
        recall = counts["fixed"] / max(counts["fixed"] + counts["dismissed"], 1)
        series.append(
            {
                "week": week,
                "precision": round(precision, 4),
                "recall_proxy": round(recall, 4),
                "tp": tp,
                "fp": fp,
                "fixed": counts["fixed"],
                "dismissed": counts["dismissed"],
            }
        )

    return {
        "days": days,
        "series": series,
        "note": (
            "Precision from helpful+fixed vs false_positive labels. "
            "Recall proxy uses fixed/(fixed+dismissed). Label more PRs to tighten the loop."
        ),
    }
