"""Stage 4: Security review agent."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import FindingDraft
from app.services.gemini_client import generate_json

SYSTEM = """You are an application security engineer.
Report only concrete, exploitable issues with a failure scenario.
No speculative hardening advice. Prefer zero findings over weak ones."""


def review_security(
    change_summary: str,
    files: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    *,
    db: Session | None = None,
    organization_id=None,
    review_job_id=None,
    repository_id=None,
) -> tuple[list[FindingDraft], dict]:
    prompt = f"""Change summary: {change_summary}

Diff:
{json.dumps(files[:40], default=str)[:25000]}

Context:
{json.dumps(contexts[:20], default=str)[:12000]}

Focus: authn/authz, injection, XSS, secrets, insecure deserialization, path traversal.

Return JSON {{"findings":[...]}} with category "security". Empty list if none.
"""
    raw, meta = generate_json(
        prompt,
        system=SYSTEM,
        db=db,
        organization_id=organization_id,
        review_job_id=review_job_id,
        repository_id=repository_id,
        operation="security",
    )
    findings: list[FindingDraft] = []
    for i, item in enumerate((raw.get("findings") if isinstance(raw, dict) else []) or []):
        try:
            item = dict(item)
            item["category"] = "security"
            draft = FindingDraft.model_validate(item)
            if not draft.finding_key:
                draft.finding_key = f"sec-{i}-{draft.file_path}:{draft.start_line}"
            findings.append(draft)
        except Exception:
            continue
    return findings, meta