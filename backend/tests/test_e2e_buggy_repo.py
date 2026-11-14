"""E2E: intentional bugs in samples/buggy_repo are caught by static + decision gating."""

from __future__ import annotations

from pathlib import Path

from app.agents.decision_agent import prioritize_findings
from app.agents.schemas import FindingDraft
from app.verification.static_analysis import scan_files

CANDIDATES = [
    Path(__file__).resolve().parents[2] / "samples" / "buggy_repo" / "app.py",
    Path("/app/../samples/buggy_repo/app.py"),
    Path("/samples/buggy_repo/app.py"),
]

BUGGY_SOURCE = '''"""Sample application with intentional bugs for pipeline validation."""

import sqlite3

API_KEY = "sk_live_this_is_a_fake_secret_key_123456"

def get_user(conn: sqlite3.Connection, user_id: str):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return conn.execute(query).fetchone()

def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()
'''


def _load_buggy_source() -> str:
    for path in CANDIDATES:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return BUGGY_SOURCE


def _as_pr_file(source: str) -> dict:
    lines = source.splitlines()
    patch_lines = ["@@ -0,0 +1,{} @@".format(len(lines))]
    for line in lines:
        patch_lines.append("+" + line)
    return {
        "filename": "app.py",
        "patch": "\n".join(patch_lines),
        "status": "added",
    }


def test_buggy_repo_static_findings_cover_known_issues():
    files = [_as_pr_file(_load_buggy_source())]
    hits = scan_files(files)
    rules = {h.rule for h in hits}
    assert "hardcoded_secret" in rules or any("secret" in h.message.lower() for h in hits)
    assert "sql_concatenation" in rules or any("sql" in h.message.lower() for h in hits)


def test_buggy_repo_decision_publishes_high_confidence_security():
    files = [_as_pr_file(_load_buggy_source())]
    hits = scan_files(files)
    drafts = [
        FindingDraft(
            finding_key=f"static-{h.rule}-{i}",
            file_path=h.file_path,
            start_line=h.line,
            end_line=h.line,
            category="security",
            severity=h.severity,  # type: ignore[arg-type]
            confidence=0.9,
            title=h.message,
            explanation=h.message,
            failure_scenario=f"Rule `{h.rule}` matched introduced code.",
            suggested_fix="Fix the vulnerability.",
            verification_status="confirmed_static",
            should_publish=True,
        )
        for i, h in enumerate(hits)
    ]
    drafts.append(
        FindingDraft(
            finding_key="path-traversal",
            file_path="app.py",
            start_line=29,
            end_line=31,
            category="security",
            severity="high",
            confidence=0.88,
            title="Path traversal in read_file",
            explanation="User-controlled path is opened without validation.",
            failure_scenario="Attacker passes ../../etc/passwd and reads secrets.",
            suggested_fix="Resolve path under an allowlisted directory.",
            verification_status="verified",
            should_publish=True,
        )
    )
    decision = prioritize_findings(
        drafts,
        "Intentional buggy sample",
        severity_threshold="medium",
        confidence_threshold=0.6,
    )
    published_titles = " ".join(f.title.lower() for f in decision.findings if f.should_publish)
    assert decision.published_count >= 2
    assert "secret" in published_titles or "sql" in published_titles
    assert "path traversal" in published_titles


def test_ignore_paths_suppress_findings():
    drafts = [
        FindingDraft(
            finding_key="x",
            file_path="vendor/lib.py",
            start_line=1,
            end_line=1,
            category="security",
            severity="critical",
            confidence=0.99,
            title="Secret",
            explanation="x",
            failure_scenario="leak",
            suggested_fix="remove",
            verification_status="verified",
            should_publish=True,
        )
    ]
    decision = prioritize_findings(
        drafts,
        "summary",
        ignore_paths=["vendor/**"],
    )
    assert decision.published_count == 0
    assert decision.findings[0].rejected_reason
