"""Stage 7: Severity prioritization and publish thresholding."""

from __future__ import annotations

from app.agents.schemas import FindingDraft, ReviewDecision
from app.core.config import settings

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
) -> ReviewDecision:
    sev_thresh = severity_threshold or settings.review_severity_threshold
    conf_thresh = confidence_threshold if confidence_threshold is not None else settings.review_confidence_threshold
    min_rank = SEVERITY_RANK.get(sev_thresh, 2)

    published = 0
    rejected = 0
    for f in findings:
        if f.verification_status == "rejected":
            f.should_publish = False
            rejected += 1
            continue
        if f.verification_status == "unverifiable":
            f.should_publish = False
            rejected += 1
            continue
        if SEVERITY_RANK.get(f.severity, 0) < min_rank:
            f.should_publish = False
            f.rejected_reason = f.rejected_reason or f"Below severity threshold ({sev_thresh})"
            rejected += 1
            continue
        if f.confidence < conf_thresh:
            f.should_publish = False
            f.rejected_reason = f.rejected_reason or f"Below confidence threshold ({conf_thresh})"
            rejected += 1
            continue
        if not f.failure_scenario.strip():
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

    if published == 0:
        summary = (
            f"{change_summary}\n\nNo findings met the quality threshold "
            f"(severity ≥ {sev_thresh}, confidence ≥ {conf_thresh})."
        )
    else:
        summary = f"{change_summary}\n\nPublishing {published} verified finding(s); rejected {rejected}."

    return ReviewDecision(
        summary=summary.strip(),
        findings=findings,
        published_count=published,
        rejected_count=rejected,
    )