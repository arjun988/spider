"""LangGraph multi-stage review orchestration."""

from __future__ import annotations

from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.agents.bug_hunter import hunt_bugs
from app.agents.change_analyzer import analyze_changes
from app.agents.context_agent import gather_context
from app.agents.decision_agent import prioritize_findings
from app.agents.schemas import FindingDraft, ReviewDecision
from app.agents.security_agent import review_security
from app.agents.test_agent import review_tests
from app.agents.verifier import verify_findings
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.settings import ModelConfiguration

logger = get_logger(__name__)


class ReviewState(TypedDict, total=False):
    pr_title: str
    pr_body: str | None
    files: list[dict[str, Any]]
    analysis: dict[str, Any]
    contexts: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    decision: dict[str, Any]
    usage: list[dict[str, Any]]
    timeline: list[dict[str, Any]]


def _merge_usage(bucket: list[dict], meta: dict) -> None:
    if meta:
        bucket.append(meta)


def run_review_pipeline(
    db: Session,
    repository: Repository,
    pr_title: str,
    pr_body: str | None,
    files: list[dict[str, Any]],
    *,
    review_job_id=None,
) -> tuple[ReviewDecision, list[dict], list[dict]]:
    """Execute the multi-stage review. Returns decision, usage metas, timeline."""
    usage: list[dict] = []
    timeline: list[dict] = []
    org_id = repository.organization_id

    config = db.query(ModelConfiguration).filter(
        ModelConfiguration.organization_id == org_id
    ).first()
    context_limit = config.context_retrieval_limit if config else 20
    max_files = config.max_files_per_review if config else 50
    sev = config.severity_threshold if config else None
    conf = config.confidence_threshold if config else None

    files = files[:max_files]

    timeline.append({"stage": "change_analyzer", "status": "started"})
    analysis, meta = analyze_changes(
        pr_title, pr_body, files,
        db=db, organization_id=org_id, review_job_id=review_job_id, repository_id=repository.id,
    )
    _merge_usage(usage, meta)
    timeline.append({"stage": "change_analyzer", "status": "completed"})

    timeline.append({"stage": "context_retrieval", "status": "started"})
    contexts = gather_context(db, repository, analysis, files, limit=context_limit)
    timeline.append({"stage": "context_retrieval", "status": "completed", "count": len(contexts)})

    all_findings: list[FindingDraft] = []

    timeline.append({"stage": "bug_hunter", "status": "started"})
    bugs, meta = hunt_bugs(
        analysis.summary, files, contexts,
        db=db, organization_id=org_id, review_job_id=review_job_id, repository_id=repository.id,
    )
    _merge_usage(usage, meta)
    all_findings.extend(bugs)
    timeline.append({"stage": "bug_hunter", "status": "completed", "count": len(bugs)})

    timeline.append({"stage": "security", "status": "started"})
    secs, meta = review_security(
        analysis.summary, files, contexts,
        db=db, organization_id=org_id, review_job_id=review_job_id, repository_id=repository.id,
    )
    _merge_usage(usage, meta)
    all_findings.extend(secs)
    timeline.append({"stage": "security", "status": "completed", "count": len(secs)})

    timeline.append({"stage": "test_coverage", "status": "started"})
    tests, meta = review_tests(
        analysis.summary, files, contexts,
        db=db, organization_id=org_id, review_job_id=review_job_id, repository_id=repository.id,
    )
    _merge_usage(usage, meta)
    all_findings.extend(tests)
    timeline.append({"stage": "test_coverage", "status": "completed", "count": len(tests)})

    timeline.append({"stage": "verifier", "status": "started"})
    verified, meta = verify_findings(
        all_findings, files, contexts,
        db=db, organization_id=org_id, review_job_id=review_job_id, repository_id=repository.id,
    )
    _merge_usage(usage, meta)
    timeline.append({"stage": "verifier", "status": "completed", "count": len(verified)})

    timeline.append({"stage": "decision", "status": "started"})
    decision = prioritize_findings(
        verified,
        analysis.summary,
        severity_threshold=sev,
        confidence_threshold=conf,
    )
    timeline.append({
        "stage": "decision",
        "status": "completed",
        "published": decision.published_count,
        "rejected": decision.rejected_count,
    })

    # Attach analysis into decision summary already done
    decision.summary = f"{analysis.summary}\n\n{decision.summary}" if analysis.summary not in decision.summary else decision.summary

    try:
        from langgraph.graph import END, StateGraph

        # Build a graph representation for observability / future expansion
        graph = StateGraph(ReviewState)
        graph.add_node("analyze", lambda s: s)
        graph.add_node("retrieve", lambda s: s)
        graph.add_node("detect", lambda s: s)
        graph.add_node("verify", lambda s: s)
        graph.add_node("decide", lambda s: s)
        graph.set_entry_point("analyze")
        graph.add_edge("analyze", "retrieve")
        graph.add_edge("retrieve", "detect")
        graph.add_edge("detect", "verify")
        graph.add_edge("verify", "decide")
        graph.add_edge("decide", END)
        compiled = graph.compile()
        compiled.invoke({
            "pr_title": pr_title,
            "files": files,
            "analysis": analysis.model_dump(),
            "contexts": contexts,
            "findings": [f.model_dump() for f in decision.findings],
            "decision": decision.model_dump(),
            "timeline": timeline,
        })
    except Exception as exc:
        logger.warning("langgraph_compile_skipped", error=str(exc))

    return decision, usage, timeline
