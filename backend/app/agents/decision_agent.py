"""Stage 7: Severity prioritization and publish thresholding."""

from __future__ import annotations

from typing import Any

from app.agents.schemas import FindingDraft, ReviewDecision
from app.core.config import settings
from app.services.feedback_signals import effective_confidence_threshold, path_ignored

SEVERITY_RANK = {
    "informational": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def prioritize_findings(
    findings: list[FindingDraft],
    change_summary: str,
    *,
    severity_threshold: str | None = None,
    confidence_threshold: float | None = None,
    ignore_paths: list[str] | None = None,
    max_findings: int | None = None,
    feedback_signals: dict[str, Any] | None = None,
    enabled_languages: list[str] | None = None,
) -> ReviewDecision:
    sev_thresh = severity_threshold or settings.review_severity_threshold
    base_conf = (
        confidence_threshold
        if confidence_threshold is not None
        else settings.review_confidence_threshold
    )
    # Slightly stricter default floor for precision
    conf_thresh = max(base_conf, 0.65) if confidence_threshold is None else base_conf
    min_rank = SEVERITY_RANK.get(sev_thresh, 2)

    published = 0
    rejected = 0
    for f in findings:
        if path_ignored(f.file_path, ignore_paths):
            f.should_publish = False
            f.rejected_reason = f.rejected_reason or "Path matched repository ignore rules"
            rejected += 1
            continue
        if f.verification_status == "rejected":
            f.should_publish = False
            rejected += 1
            continue
        if f.verification_status in {"unverifiable", "skipped"}:
            # Unverified findings need higher confidence to publish
            f.confidence = min(f.confidence, 0.55)
            f.should_publish = False
            f.rejected_reason = f.rejected_reason or "Unverified — withheld for precision"
            rejected += 1
            continue
        if SEVERITY_RANK.get(f.severity, 0) < min_rank:
            f.should_publish = False
            f.rejected_reason = f.rejected_reason or f"Below severity threshold ({sev_thresh})"
            rejected += 1
            continue
        cat_thresh = effective_confidence_threshold(conf_thresh, f.category, feedback_signals)
        if f.confidence < cat_thresh:
            f.should_publish = False
            f.rejected_reason = f.rejected_reason or f"Below confidence threshold ({cat_thresh:.2f})"
            rejected += 1
            continue
        if not (f.failure_scenario or "").strip():
            f.should_publish = False
            f.rejected_reason = "Missing concrete failure scenario"
            rejected += 1
            continue
        f.should_publish = True
        published += 1

    # Sort publishable first by severity then confidence
    findings.sort(
        key=lambda x: (
            0 if x.should_publish else 1,
            -SEVERITY_RANK.get(x.severity, 0),
            -x.confidence,
        )
    )

    if max_findings and max_findings > 0:
        kept = 0
        for f in findings:
            if not f.should_publish:
                continue
            kept += 1
            if kept > max_findings:
                f.should_publish = False
                f.rejected_reason = f.rejected_reason or f"Exceeded max_findings ({max_findings})"
                published -= 1
                rejected += 1

    if published == 0:
        summary = (
            f"{change_summary}\n\nNo findings met the quality threshold "
            f"(severity ≥ {sev_thresh}, confidence ≥ {conf_thresh})."
        )
    else:
        summary = f"{change_summary}\n\nPublishing {published} verified finding(s); rejected {rejected}."

    hints = (feedback_signals or {}).get("prompt_hints") or []
    if hints:
        summary += "\n\nPrecision signals: " + " ".join(hints[:3])

    return ReviewDecision(
        summary=summary.strip(),
        findings=findings,
        published_count=published,
        rejected_count=rejected,
    )
