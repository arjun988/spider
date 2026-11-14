"""Stage 1: PR change analyzer."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import ChangeAnalysis, ChangedSymbol
from app.services.llm_client import generate_json


SYSTEM = """You are a senior engineer summarizing a pull request.
Identify purpose, changed files/functions, categories, and risky areas.
Only report what is supported by the provided diff. Return JSON matching the schema."""


def analyze_changes(
    pr_title: str,
    pr_body: str | None,
    files: list[dict[str, Any]],
    *,
    db: Session | None = None,
    organization_id=None,
    review_job_id=None,
    repository_id=None,
) -> tuple[ChangeAnalysis, dict]:
    compact_files = []
    for f in files[:50]:
        compact_files.append(
            {
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
                "patch": (f.get("patch") or "")[:4000],
            }
        )

    prompt = f"""PR title: {pr_title}
PR body: {pr_body or ''}

Changed files JSON:
{json.dumps(compact_files)}

Return JSON:
{{
  "summary": "...",
  "purpose": "...",
  "categories": ["feature"|"bugfix"|"refactor"|"test"|"docs"|"chore"],
  "risky_areas": ["..."],
  "changed_files": ["path"],
  "changed_symbols": [{{"file_path":"","name":"","symbol_type":"function","start_line":1,"end_line":1}}]
}}
"""
    raw, meta = generate_json(
        prompt,
        system=SYSTEM,
        db=db,
        organization_id=organization_id,
        review_job_id=review_job_id,
        repository_id=repository_id,
        operation="analyze",
    )
    if not isinstance(raw, dict):
        raw = {}

    symbols = []
    for s in raw.get("changed_symbols") or []:
        try:
            symbols.append(ChangedSymbol.model_validate(s))
        except Exception:
            continue

    analysis = ChangeAnalysis(
        summary=raw.get("summary") or pr_title,
        purpose=raw.get("purpose") or "",
        categories=list(raw.get("categories") or []),
        risky_areas=list(raw.get("risky_areas") or []),
        changed_files=list(raw.get("changed_files") or [f.get("filename") for f in files if f.get("filename")]),
        changed_symbols=symbols,
    )
    return analysis, meta
