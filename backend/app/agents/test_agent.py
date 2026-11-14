"""Stage 5: Test coverage agent — advisory, not every missing test is a bug."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import FindingDraft
from app.services.llm_client import generate_json

SYSTEM = """You analyze whether a PR's tests adequately cover risky behavior changes.
Only report high-value missing coverage for risky logic — not every missing unit test.
Category must be "test". Prefer fewer, stronger findings."""


def review_tests(
    change_summary: str,
    files: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    *,
    db: Session | None = None,
    organization_id=None,
    review_job_id=None,
    repository_id=None,
    policy_section: str | None = None,
) -> tuple[list[FindingDraft], dict]:
    policy_block = f"\n{policy_section}\n" if policy_section else ""
    prompt = f"""Change summary: {change_summary}
{policy_block}
Files:
{json.dumps(files[:40], default=str)[:20000]}

Context (may include existing tests):
{json.dumps(contexts[:20], default=str)[:10000]}

Honor required_tests from the org policy pack when listed.
Return JSON {{"findings":[...]}} only for material coverage gaps on risky changes.
"""
    raw, meta = generate_json(
        prompt,
        system=SYSTEM,
        db=db,
        organization_id=organization_id,
        review_job_id=review_job_id,
        repository_id=repository_id,
        operation="test_review",
    )
    findings: list[FindingDraft] = []
    for i, item in enumerate((raw.get("findings") if isinstance(raw, dict) else []) or []):
        try:
            item = dict(item)
            item["category"] = "test"
            # Cap severity for test findings unless critical regression risk claimed
            if item.get("severity") in {"critical"}:
                item["severity"] = "high"
            draft = FindingDraft.model_validate(item)
            if not draft.finding_key:
                draft.finding_key = f"test-{i}-{draft.file_path}:{draft.start_line}"
            findings.append(draft)
        except Exception:
            continue
    return findings, meta
