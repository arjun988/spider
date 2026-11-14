"""Stage 3: Bug detection agent."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import FindingDraft
from app.services.llm_client import generate_json

SYSTEM = """You are a meticulous bug hunter.
Only report concrete bugs with a real failure scenario.
Do NOT invent issues for style, naming, or speculative concerns.
Prefer zero findings over weak findings. Return JSON."""


def hunt_bugs(
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

Diff files:
{json.dumps([{k: v for k, v in f.items()} for f in files[:40]], default=str)[:25000]}

Repository context:
{json.dumps(contexts[:30], default=str)[:15000]}

Return JSON:
{{
  "findings": [
    {{
      "file_path": "",
      "start_line": 1,
      "end_line": 1,
      "category": "bug",
      "severity": "high",
      "confidence": 0.8,
      "title": "",
      "explanation": "",
      "failure_scenario": "",
      "suggested_fix": ""
    }}
  ]
}}
If none, return {{"findings": []}}.
"""
    raw, meta = generate_json(
        prompt,
        system=SYSTEM,
        db=db,
        organization_id=organization_id,
        review_job_id=review_job_id,
        repository_id=repository_id,
        operation="bug_hunt",
    )
    findings: list[FindingDraft] = []
    items = raw.get("findings") if isinstance(raw, dict) else []
    for i, item in enumerate(items or []):
        try:
            draft = FindingDraft.model_validate(item)
            if not draft.finding_key:
                draft.finding_key = f"bug-{i}-{draft.file_path}:{draft.start_line}"
            findings.append(draft)
        except Exception:
            continue
    return findings, meta
