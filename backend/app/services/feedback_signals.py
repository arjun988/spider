"""Aggregate review feedback into precision signals for agents."""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.review import ReviewFeedback, ReviewFinding


def compute_feedback_signals(db: Session, organization_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Return false-positive rates by category and path prefixes."""
    q = (
        select(
            ReviewFinding.category,
            ReviewFeedback.feedback_type,
            func.count().label("cnt"),
        )
        .join(ReviewFeedback, ReviewFeedback.finding_id == ReviewFinding.id)
        .group_by(ReviewFinding.category, ReviewFeedback.feedback_type)
    )
    rows = db.execute(q).all()
    by_category: dict[str, dict[str, int]] = {}
    for category, feedback_type, cnt in rows:
        bucket = by_category.setdefault(category or "other", {"total": 0, "false_positive": 0, "helpful": 0})
        bucket["total"] += int(cnt)
        if feedback_type == "false_positive":
            bucket["false_positive"] += int(cnt)
        if feedback_type == "helpful":
            bucket["helpful"] += int(cnt)

    category_fp_rate: dict[str, float] = {}
    confidence_bumps: dict[str, float] = {}
    for category, stats in by_category.items():
        if stats["total"] < 3:
            continue
        rate = stats["false_positive"] / max(stats["total"], 1)
        category_fp_rate[category] = round(rate, 3)
        # Auto-bump confidence floor when FP rate is high
        if rate >= 0.4:
            confidence_bumps[category] = min(0.25, 0.1 + rate * 0.2)

    prompt_hints: list[str] = []
    for category, rate in sorted(category_fp_rate.items(), key=lambda x: -x[1]):
        if rate >= 0.3:
            prompt_hints.append(
                f"Category `{category}` has {rate:.0%} recent false-positive feedback — "
                "be stricter and require concrete failure evidence."
            )

    return {
        "category_fp_rate": category_fp_rate,
        "confidence_bumps": confidence_bumps,
        "prompt_hints": prompt_hints,
        "by_category": by_category,
    }


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
