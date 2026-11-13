"""Publish verified findings as GitHub PR review comments."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.github.client import GitHubClient

logger = get_logger(__name__)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}


def format_finding_comment(finding: dict[str, Any]) -> str:
    severity = (finding.get("severity") or "medium").upper()
    title = finding.get("title") or "Finding"
    explanation = finding.get("explanation") or ""
    scenario = finding.get("failure_scenario") or ""
    fix = finding.get("suggested_fix")

    lines = [
        f"**[{severity}] {title}**",
        "",
        explanation.strip(),
    ]
    if scenario.strip():
        lines.extend(["", scenario.strip()])
    if fix and fix.strip():
        lines.extend(["", f"Suggested fix: {fix.strip()}"])

    category = finding.get("category")
    confidence = finding.get("confidence")
    meta = []
    if category:
        meta.append(f"category: `{category}`")
    if confidence is not None:
        meta.append(f"confidence: `{confidence:.2f}`")
    verification = finding.get("verification_status")
    if verification:
        meta.append(f"verification: `{verification}`")
    if meta:
        lines.extend(["", "—", ", ".join(meta)])

    return "\n".join(lines)


def build_review_summary(
    findings: list[dict[str, Any]],
    change_summary: str | None = None,
) -> str:
    published = [f for f in findings if f.get("published") or f.get("verification_status") in (
        "verified", "confirmed_static", "confirmed_test"
    )]
    # Prefer explicitly publishable list when provided via decision agent
    to_report = [f for f in findings if f.get("should_publish", True) and f.get("verification_status") != "rejected"]

    if not to_report:
        body = [
            "## Spider review",
            "",
            "No high-confidence, actionable issues found in this change set.",
            "",
            "_Optimized for real bugs — speculative findings are filtered out._",
        ]
        if change_summary:
            body.extend(["", "### Change summary", change_summary])
        return "\n".join(body)

    by_sev: dict[str, int] = {}
    for f in to_report:
        sev = f.get("severity") or "medium"
        by_sev[sev] = by_sev.get(sev, 0) + 1

    counts = ", ".join(
        f"{sev}: {by_sev[sev]}"
        for sev in sorted(by_sev.keys(), key=lambda s: SEVERITY_ORDER.get(s, 99))
    )

    lines = [
        "## Spider review",
        "",
        f"Published **{len(to_report)}** verified finding(s) ({counts}).",
        "",
    ]
    if change_summary:
        lines.extend(["### Change summary", change_summary, ""])
    lines.append("Inline comments include failure scenarios and suggested fixes.")
    return "\n".join(lines)


def compute_diff_side_line(patch: str | None, target_line: int) -> int | None:
    """
    Map a file line number to a RIGHT-side diff line suitable for GitHub
    multi-line review comments (line + side=RIGHT).
    Returns the line number only if it appears as an added/context line in the patch.
    Without a patch, skip inline comments (summary-only) to avoid failing the whole review.
    """
    if not patch:
        return None

    new_line = 0
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            # @@ -a,b +c,d @@
            try:
                plus = raw.split("+")[1].split(" ")[0]
                new_line = int(plus.split(",")[0]) - 1
            except (IndexError, ValueError):
                continue
            continue
        if raw.startswith("\\"):
            continue
        if raw.startswith("-"):
            continue
        # context or addition
        new_line += 1
        if new_line == target_line:
            return target_line
    return None


def publish_review(
    client: GitHubClient,
    owner: str,
    repo: str,
    pr_number: int,
    commit_sha: str,
    findings: list[dict[str, Any]],
    file_patches: dict[str, str | None],
    change_summary: str | None = None,
) -> dict[str, Any]:
    """Create a GitHub pull request review with inline comments."""
    publishable = [
        f for f in findings
        if f.get("verification_status") != "rejected"
        and f.get("should_publish", True)
        and f.get("file_path")
        and f.get("start_line")
    ]

    comments: list[dict[str, Any]] = []
    published_keys: list[str] = []
    skipped_keys: list[str] = []
    for finding in publishable:
        path = finding["file_path"]
        line = int(finding.get("end_line") or finding["start_line"])
        patch = file_patches.get(path)
        mapped = compute_diff_side_line(patch, line)
        if mapped is None:
            logger.warning("skip_comment_outdated_line", path=path, line=line)
            key = finding.get("finding_key")
            if key:
                skipped_keys.append(key)
            continue
        comments.append(
            {
                "path": path,
                "line": mapped,
                "side": "RIGHT",
                "body": format_finding_comment(finding),
                "finding_key": finding.get("finding_key"),
            }
        )
        if finding.get("finding_key"):
            published_keys.append(finding["finding_key"])

    event = "COMMENT"
    body = build_review_summary(publishable, change_summary)

    # Prefer summary-only when no valid inline anchors — never fail the whole review.
    max_per_review = 30
    first_batch = [
        {k: v for k, v in c.items() if k != "finding_key"}
        for c in comments[:max_per_review]
    ]
    try:
        result = client.create_pull_request_review(
            owner=owner,
            repo=repo,
            number=pr_number,
            body=body,
            event=event,
            comments=first_batch or None,
            commit_id=commit_sha,
        )
    except Exception as exc:
        # Retry once as summary-only if inline comments are rejected by GitHub.
        logger.warning("inline_review_failed_retry_summary", error=str(exc))
        result = client.create_pull_request_review(
            owner=owner,
            repo=repo,
            number=pr_number,
            body=body,
            event=event,
            comments=None,
            commit_id=commit_sha,
        )
        published_keys = []
        skipped_keys = [f.get("finding_key") for f in publishable if f.get("finding_key")]

    extra_ids = []
    remaining = comments[max_per_review:]
    while remaining:
        batch_raw = remaining[:max_per_review]
        remaining = remaining[max_per_review:]
        batch = [{k: v for k, v in c.items() if k != "finding_key"} for c in batch_raw]
        try:
            extra = client.create_pull_request_review(
                owner=owner,
                repo=repo,
                number=pr_number,
                body="Additional Spider findings.",
                event="COMMENT",
                comments=batch,
                commit_id=commit_sha,
            )
            extra_ids.append(extra.get("id"))
        except Exception as exc:
            logger.warning("extra_review_batch_failed", error=str(exc), count=len(batch))
            for c in batch_raw:
                key = c.get("finding_key")
                if key and key in published_keys:
                    published_keys.remove(key)
                    skipped_keys.append(key)

    logger.info(
        "review_published",
        pr=pr_number,
        comments=len(published_keys),
        skipped=len(skipped_keys),
        review_id=result.get("id"),
    )
    return {
        "review_id": result.get("id"),
        "html_url": result.get("html_url"),
        "published_comments": len(published_keys),
        "published_finding_keys": published_keys,
        "skipped_finding_keys": skipped_keys,
        "extra_review_ids": extra_ids,
    }