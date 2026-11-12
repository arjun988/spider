"""Stage 2: Context retrieval agent."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import ChangeAnalysis
from app.indexing.retrieval import retrieve_for_change
from app.models.repository import Repository


def gather_context(
    db: Session,
    repository: Repository,
    analysis: ChangeAnalysis,
    files: list[dict[str, Any]],
    limit: int = 20,
) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    patch_by_file = {f.get("filename"): f.get("patch") for f in files}

    # Group symbols by file
    symbols_by_file: dict[str, list[str]] = {}
    for sym in analysis.changed_symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)

    files_to_query = analysis.changed_files or list(patch_by_file.keys())
    per_file = max(3, limit // max(1, len(files_to_query)))

    for path in files_to_query[:30]:
        ctx = retrieve_for_change(
            db,
            repository,
            changed_file=path,
            changed_symbols=symbols_by_file.get(path, []),
            patch=patch_by_file.get(path),
            limit=per_file,
        )
        contexts.extend(ctx)

    # Dedup
    seen = set()
    unique = []
    for c in contexts:
        key = (c.get("file_path"), c.get("start_line"), c.get("end_line"), c.get("source"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
        if len(unique) >= limit:
            break
    return unique