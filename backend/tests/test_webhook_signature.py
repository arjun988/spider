"""GitHub webhook signature and idempotency helpers."""

from __future__ import annotations

import hashlib
import hmac
import json

from app.core.security import verify_github_webhook_signature
from app.github.review_publisher import compute_diff_side_line, format_finding_comment
from app.services.gemini_client import estimate_cost
from app.verification.static_analysis import scan_patch


def test_webhook_signature_valid():
    payload = b'{"action":"opened"}'
    secret = "super-secret"
    sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_github_webhook_signature(payload, sig, secret) is True


def test_webhook_signature_invalid():
    assert verify_github_webhook_signature(b"{}", "sha256=dead", "secret") is False


def test_diff_line_mapping():
    patch = "@@ -1,3 +1,4 @@\n context\n+added line\n context\n context\n"
    assert compute_diff_side_line(patch, 2) == 2


def test_format_finding_comment():
    body = format_finding_comment(
        {
            "severity": "high",
            "title": "Missing authz",
            "explanation": "No ownership check.",
            "failure_scenario": "Attacker reads another user.",
            "suggested_fix": "Check ownership.",
            "category": "security",
            "confidence": 0.9,
            "verification_status": "verified",
        }
    )
    assert "[HIGH]" in body
    assert "Suggested fix" in body


def test_cost_estimate():
    cost = estimate_cost("gemini-2.0-flash", 1_000_000, 1_000_000)
    assert cost == 0.5


def test_static_secret_detection():
    patch = "@@ -1,1 +1,2 @@\n keep\n+api_key = 'sk_live_abcdefghijklmnopqrstuv'\n"
    hits = scan_patch("app.py", patch)
    assert any(h.rule == "hardcoded_secret" for h in hits)


def test_decision_rejects_low_confidence():
    from app.agents.decision_agent import prioritize_findings
    from app.agents.schemas import FindingDraft

    findings = [
        FindingDraft(
            finding_key="1",
            file_path="a.py",
            start_line=1,
            end_line=1,
            category="bug",
            severity="high",
            confidence=0.2,
            title="Maybe bug",
            explanation="x",
            failure_scenario="could fail",
            verification_status="verified",
        )
    ]
    decision = prioritize_findings(findings, "summary", confidence_threshold=0.6)
    assert decision.published_count == 0
    assert decision.rejected_count == 1


def test_chunker_produces_chunks():
    from app.indexing.chunker import chunk_file
    from app.indexing.parser import SymbolInfo

    content = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    symbols = [
        SymbolInfo("foo", "a.py::foo", "function", 1, 2),
        SymbolInfo("bar", "a.py::bar", "function", 4, 5),
    ]
    chunks = chunk_file("a.py", content, "python", symbols)
    assert len(chunks) == 2
    assert chunks[0].symbol_name == "foo"