"""Stage 6: Independent finding verifier — may reject findings."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import FindingDraft, VerificationDecision
from app.services.llm_client import generate_json

SYSTEM = """You independently verify code-review findings.
Reject speculative, incorrect, already-handled, or non-actionable findings.
Accept only when the failure scenario is plausible given the code.
Be skeptical. Returning zero accepted findings is success when warranted."""


def verify_findings(
    findings: list[FindingDraft],
    files: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    *,
    db: Session | None = None,
    organization_id=None,
    review_job_id=None,
    repository_id=None,
) -> tuple[list[FindingDraft], dict]:
    if not findings:
        return [], {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}

    prompt = f"""Candidate findings:
{json.dumps([f.model_dump() for f in findings], default=str)[:20000]}

Relevant diffs:
{json.dumps(files[:40], default=str)[:20000]}

Context:
{json.dumps(contexts[:25], default=str)[:12000]}

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
        system=SYSTEM,
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
            # Conservative: mark unverifiable rather than auto-publish
            finding.verification_status = "unverifiable"
            finding.should_publish = False
            finding.rejected_reason = "Verifier did not return a decision"
            verified.append(finding)
            continue
        finding.confidence = min(finding.confidence, decision.confidence)
        if decision.accepted and decision.verification_status != "rejected":
            finding.verification_status = decision.verification_status if decision.verification_status != "pending" else "verified"
            finding.should_publish = True
            finding.rejected_reason = None
        else:
            finding.verification_status = "rejected"
            finding.should_publish = False
            finding.rejected_reason = decision.reason
        verified.append(finding)
    return verified, meta
