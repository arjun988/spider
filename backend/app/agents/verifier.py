"""Stage 6: Independent finding verifier — may reject findings."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import FindingDraft, VerificationDecision
from app.services.feedback_signals import (
    compute_feedback_signals,
    effective_confidence_threshold,
    format_verifier_guidance,
)
from app.services.llm_client import generate_json

SYSTEM = """You independently verify code-review findings.
Reject speculative, incorrect, already-handled, or non-actionable findings.
Accept only when the failure scenario is plausible given the code.
Be skeptical. Returning zero accepted findings is success when warranted.

When historical false-positive feedback is provided, treat high-FP categories and
paths as hostile to weak claims: demand concrete evidence or reject.
Do not accept findings that closely resemble labeled false-positive examples
unless the new evidence is clearly stronger."""


def verify_findings(
    findings: list[FindingDraft],
    files: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    *,
    db: Session | None = None,
    organization_id=None,
    review_job_id=None,
    repository_id=None,
    feedback_signals: dict[str, Any] | None = None,
) -> tuple[list[FindingDraft], dict]:
    if not findings:
        return [], {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}

    signals = feedback_signals
    if signals is None and db is not None:
        try:
            signals = compute_feedback_signals(db, organization_id)
        except Exception:
            signals = None

    guidance = format_verifier_guidance(signals)
    system = SYSTEM if not guidance else f"{SYSTEM}\n\n{guidance}"

    # Tag each finding with its category FP rate so the model can weigh it
    finding_payloads = []
    for f in findings:
        payload = f.model_dump()
        rate = (signals or {}).get("category_fp_rate", {}).get(f.category)
        bump = (signals or {}).get("confidence_bumps", {}).get(f.category)
        if rate is not None:
            payload["historical_fp_rate"] = rate
        if bump is not None:
            payload["suggested_confidence_floor_bump"] = bump
        finding_payloads.append(payload)

    prompt = f"""Candidate findings:
{json.dumps(finding_payloads, default=str)[:20000]}

Relevant diffs:
{json.dumps(files[:40], default=str)[:20000]}

Context:
{json.dumps(contexts[:25], default=str)[:12000]}

{guidance if guidance else "No historical feedback signals available yet."}

Verification rules:
- Prefer reject/unverifiable over accept when evidence is thin.
- If historical_fp_rate for a finding's category is ≥ 0.4, only accept with a clear
  failure scenario grounded in the diff/context.
- Cap accepted confidence when feedback suggests a category is noisy.

Return JSON:
{{
  "decisions": [
    {{
      "finding_key": "",
      "accepted": true,
      "verification_status": "verified"|"rejected"|"unverifiable",
      "reason": "",
      "confidence": 0.0
    }}
  ]
}}
"""
    raw, meta = generate_json(
        prompt,
        system=system,
        db=db,
        organization_id=organization_id,
        review_job_id=review_job_id,
        repository_id=repository_id,
        operation="verify",
    )
    decisions_raw = (raw.get("decisions") if isinstance(raw, dict) else []) or []
    by_key: dict[str, VerificationDecision] = {}
    for d in decisions_raw:
        try:
            decision = VerificationDecision.model_validate(d)
            by_key[decision.finding_key] = decision
        except Exception:
            continue

    verified: list[FindingDraft] = []
    for finding in findings:
        decision = by_key.get(finding.finding_key)
        if decision is None:
            finding.verification_status = "unverifiable"
            finding.should_publish = False
            finding.rejected_reason = "Verifier did not return a decision"
            verified.append(finding)
            continue

        # Apply feedback confidence floor post-model
        floor = effective_confidence_threshold(0.0, finding.category, signals)
        adjusted_conf = min(finding.confidence, decision.confidence)
        if floor > 0:
            # floor here is bump amount when base=0 via confidence_bumps path;
            # recompute against decision confidence using a sensible base of 0.6
            required = effective_confidence_threshold(0.6, finding.category, signals)
            if adjusted_conf < required and decision.accepted:
                finding.verification_status = "rejected"
                finding.should_publish = False
                finding.rejected_reason = (
                    decision.reason
                    or f"Below feedback-adjusted confidence floor ({required:.2f})"
                )
                finding.confidence = adjusted_conf
                verified.append(finding)
                continue

        finding.confidence = adjusted_conf
        if decision.accepted and decision.verification_status != "rejected":
            finding.verification_status = (
                decision.verification_status
                if decision.verification_status != "pending"
                else "verified"
            )
            finding.should_publish = True
            finding.rejected_reason = None
        else:
            finding.verification_status = "rejected"
            finding.should_publish = False
            finding.rejected_reason = decision.reason
        verified.append(finding)
    return verified, meta
