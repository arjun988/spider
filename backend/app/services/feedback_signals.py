"""Aggregate review feedback into precision signals for agents."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.review import ReviewFeedback, ReviewFinding


def _path_prefix(path: str) -> str:
    normalized = (path or "").replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0] if parts else "(root)"


def compute_feedback_signals(db: Session, organization_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Return false-positive rates by category and path prefixes for prompt injection."""
    q = (
        select(
            ReviewFinding.category,
            ReviewFinding.file_path,
            ReviewFinding.title,
            ReviewFeedback.feedback_type,
        )
        .join(ReviewFeedback, ReviewFeedback.finding_id == ReviewFinding.id)
    )
    if organization_id is not None:
        from app.models.pull_request import PullRequest
        from app.models.repository import Repository
        from app.models.review import ReviewJob

        q = (
            q.join(ReviewJob, ReviewFinding.review_job_id == ReviewJob.id)
            .join(PullRequest, ReviewJob.pull_request_id == PullRequest.id)
            .join(Repository, PullRequest.repository_id == Repository.id)
            .where(Repository.organization_id == organization_id)
        )

    rows = db.execute(q).all()
    by_category: dict[str, dict[str, int]] = {}
    by_path: dict[str, dict[str, int]] = {}
    fp_examples: list[dict[str, str]] = []

    for category, file_path, title, feedback_type in rows:
        cat = category or "other"
        bucket = by_category.setdefault(cat, {"total": 0, "false_positive": 0, "helpful": 0, "dismissed": 0})
        bucket["total"] += 1
        if feedback_type == "false_positive":
            bucket["false_positive"] += 1
            if len(fp_examples) < 8:
                fp_examples.append(
                    {
                        "category": cat,
                        "file_path": file_path or "",
                        "title": (title or "")[:160],
                    }
                )
        elif feedback_type == "helpful":
            bucket["helpful"] += 1
        elif feedback_type == "dismissed":
            bucket["dismissed"] += 1

        prefix = _path_prefix(file_path or "")
        pb = by_path.setdefault(prefix, {"total": 0, "false_positive": 0})
        pb["total"] += 1
        if feedback_type == "false_positive":
            pb["false_positive"] += 1

    category_fp_rate: dict[str, float] = {}
    confidence_bumps: dict[str, float] = {}
    for category, stats in by_category.items():
        if stats["total"] < 3:
            continue
        rate = stats["false_positive"] / max(stats["total"], 1)
        category_fp_rate[category] = round(rate, 3)
        if rate >= 0.4:
            confidence_bumps[category] = min(0.25, 0.1 + rate * 0.2)

    path_fp_rate: dict[str, float] = {}
    for prefix, stats in by_path.items():
        if stats["total"] < 3:
            continue
        rate = stats["false_positive"] / max(stats["total"], 1)
        if rate >= 0.3:
            path_fp_rate[prefix] = round(rate, 3)

    prompt_hints: list[str] = []
    for category, rate in sorted(category_fp_rate.items(), key=lambda x: -x[1]):
        if rate >= 0.3:
            prompt_hints.append(
                f"Category `{category}` has {rate:.0%} recent false-positive feedback — "
                "be stricter and require concrete failure evidence."
            )
    for prefix, rate in sorted(path_fp_rate.items(), key=lambda x: -x[1])[:5]:
        prompt_hints.append(
            f"Path prefix `{prefix}/` has {rate:.0%} false-positive feedback — "
            "reject stylistic or speculative findings there unless impact is clear."
        )

    return {
        "category_fp_rate": category_fp_rate,
        "path_fp_rate": path_fp_rate,
        "confidence_bumps": confidence_bumps,
        "prompt_hints": prompt_hints,
        "by_category": by_category,
        "fp_examples": fp_examples,
    }


def format_verifier_guidance(signals: dict[str, Any] | None) -> str:
    """Human-readable block injected into the verifier system/user prompt."""
    if signals is None:
        return ""

    lines: list[str] = [
        "Historical human feedback (use to reject patterns that repeatedly get marked false positive):",
    ]
    rates = signals.get("category_fp_rate") or {}
    if rates:
        lines.append("Category false-positive rates:")
        for cat, rate in sorted(rates.items(), key=lambda x: -x[1]):
            bump = (signals.get("confidence_bumps") or {}).get(cat)
            extra = f" (raise bar; confidence bump +{bump:.2f})" if bump else ""
            lines.append(f"- {cat}: {rate:.0%} FP{extra}")
    else:
        lines.append("- Not enough category feedback yet (need ≥3 labeled findings per category).")

    path_rates = signals.get("path_fp_rate") or {}
    if path_rates:
        lines.append("Path prefixes with elevated false positives:")
        for prefix, rate in sorted(path_rates.items(), key=lambda x: -x[1])[:6]:
            lines.append(f"- {prefix}/ → {rate:.0%} FP")

    examples = signals.get("fp_examples") or []
    if examples:
        lines.append("Recent false-positive examples (do not accept similar weak findings):")
        for ex in examples[:6]:
            lines.append(
                f"- [{ex.get('category')}] {ex.get('title')} @ {ex.get('file_path')}"
            )

    for hint in (signals.get("prompt_hints") or [])[:6]:
        lines.append(f"- Guidance: {hint}")

    lines.append(
        "When a candidate matches a high-FP category or path, require a concrete failure "
        "scenario and clear code evidence; otherwise reject or mark unverifiable."
    )
    return "\n".join(lines)


def effective_confidence_threshold(
    base: float,
    category: str | None,
    signals: dict[str, Any] | None,
) -> float:
    if not signals:
        return base
    bump = float((signals.get("confidence_bumps") or {}).get(category or "", 0.0))
    return min(0.95, base + bump)


def path_ignored(file_path: str, ignore_paths: list[str] | None) -> bool:
    if not ignore_paths:
        return False
    normalized = file_path.replace("\\", "/")
    for pattern in ignore_paths:
        p = (pattern or "").strip().replace("\\", "/")
        if not p:
            continue
        if p.endswith("/**"):
            prefix = p[:-3]
            if normalized.startswith(prefix):
                return True
        elif p.endswith("*"):
            if normalized.startswith(p[:-1]):
                return True
        elif normalized == p or normalized.startswith(p.rstrip("/") + "/"):
            return True
        elif p in normalized:
            return True
    return False
