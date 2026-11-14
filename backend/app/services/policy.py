"""Org policy packs and merge-blocking policy evaluation."""

from __future__ import annotations

from typing import Any

from app.agents.schemas import FindingDraft


DEFAULT_POLICY: dict[str, Any] = {
    "banned_apis": [],
    "required_tests": [],
    "security_policies": [
        "No hardcoded secrets in introduced lines",
        "No SQL string concatenation with user input",
    ],
    "notes": "",
}


def normalize_policy_pack(raw: dict[str, Any] | None) -> dict[str, Any]:
    pack = dict(DEFAULT_POLICY)
    if not raw:
        return pack
    for key in ("banned_apis", "required_tests", "security_policies"):
        val = raw.get(key)
        if isinstance(val, list):
            pack[key] = [str(x).strip() for x in val if str(x).strip()]
    if isinstance(raw.get("notes"), str):
        pack["notes"] = raw["notes"]
    return pack


def policy_prompt_section(pack: dict[str, Any] | None) -> str:
    p = normalize_policy_pack(pack)
    lines = ["Organization policy pack (must honor):"]
    if p["security_policies"]:
        lines.append("Security policies:")
        lines.extend(f"- {x}" for x in p["security_policies"])
    if p["banned_apis"]:
        lines.append("Banned APIs / patterns (flag if newly introduced):")
        lines.extend(f"- {x}" for x in p["banned_apis"])
    if p["required_tests"]:
        lines.append("Required tests / coverage expectations:")
        lines.extend(f"- {x}" for x in p["required_tests"])
    if p["notes"]:
        lines.append(f"Notes: {p['notes']}")
    return "\n".join(lines)


def evaluate_merge_block(
    findings: list[FindingDraft] | list[Any],
    *,
    block_on_secrets: bool = True,
    block_on_critical: bool = True,
) -> dict[str, Any]:
    """Decide Check Run conclusion from published findings + policy."""
    published = []
    for f in findings:
        should = getattr(f, "should_publish", None)
        if should is None and isinstance(f, dict):
            should = f.get("should_publish") or f.get("published")
        if not should:
            continue
        published.append(f)

    secrets = 0
    critical = 0
    high = 0
    reasons: list[str] = []
    for f in published:
        sev = getattr(f, "severity", None) or (f.get("severity") if isinstance(f, dict) else "")
        cat = getattr(f, "category", None) or (f.get("category") if isinstance(f, dict) else "")
        title = getattr(f, "title", None) or (f.get("title") if isinstance(f, dict) else "")
        key = getattr(f, "finding_key", None) or (f.get("finding_key") if isinstance(f, dict) else "")
        text = f"{title} {key} {cat}".lower()
        if sev == "critical":
            critical += 1
        if sev == "high":
            high += 1
        if "secret" in text or "hardcoded" in text or (
            cat == "security" and ("credential" in text or "token" in text or "key" in text)
        ):
            secrets += 1

    block = False
    if block_on_critical and critical > 0:
        block = True
        reasons.append(f"{critical} critical finding(s) published")
    if high > 0:
        block = True
        reasons.append(f"{high} high finding(s) published")
    if block_on_secrets and secrets > 0:
        block = True
        reasons.append(f"{secrets} secret-related finding(s) published")

    return {
        "block": block,
        "conclusion": "failure" if block else "success",
        "reasons": reasons,
        "counts": {"critical": critical, "high": high, "secrets": secrets, "published": len(published)},
    }


def build_decision_trace(
    *,
    published: bool,
    rejected_reason: str | None,
    gates: list[str],
    policy_hits: list[str] | None = None,
    feedback_floor: float | None = None,
) -> dict[str, Any]:
    return {
        "outcome": "published" if published else "rejected",
        "reason": rejected_reason if not published else "Passed severity, confidence, verification, and policy gates",
        "gates": gates,
        "policy_hits": policy_hits or [],
        "feedback_confidence_floor": feedback_floor,
    }
