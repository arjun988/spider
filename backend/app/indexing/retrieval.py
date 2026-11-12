"""Hybrid context retrieval: semantic + symbol + ripgrep."""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.indexing.embeddings import embed_chunks
from app.models.code_index import CodeChunk, CodeDependency, CodeSymbol
from app.models.repository import Repository

logger = get_logger(__name__)


@dataclass
class RetrievedContext:
    file_path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: str | None
    relevance: float
    source: str  # semantic | symbol | search | dependency


def semantic_search(
    db: Session,
    repository_id: uuid.UUID,
    query: str,
    limit: int = 10,
) -> list[RetrievedContext]:
    repo = db.get(Repository, repository_id)
    if not repo:
        return []
    try:
        vectors = embed_chunks([query], db=db, organization_id=repo.organization_id, repository_id=repository_id)
    except Exception as exc:
        logger.warning("semantic_query_embed_failed", error=str(exc))
        return []
    if not vectors:
        return []
    vector = vectors[0]
    # pgvector cosine distance
    sql = text(
        """
        SELECT id, file_path, start_line, end_line, content, symbol_name,
               1 - (embedding <=> :embedding) AS score
        FROM code_chunks
        WHERE repository_id = :repo_id AND embedding IS NOT NULL
        ORDER BY embedding <=> :embedding
        LIMIT :limit
        """
    )
    rows = db.execute(
        sql,
        {"embedding": str(vector), "repo_id": str(repository_id), "limit": limit},
    ).mappings().all()
    return [
        RetrievedContext(
            file_path=r["file_path"],
            start_line=r["start_line"],
            end_line=r["end_line"],
            content=r["content"],
            symbol_name=r["symbol_name"],
            relevance=float(r["score"] or 0),
            source="semantic",
        )
        for r in rows
    ]


def symbol_search(
    db: Session,
    repository_id: uuid.UUID,
    names: list[str],
    limit: int = 20,
) -> list[RetrievedContext]:
    if not names:
        return []
    results: list[RetrievedContext] = []
    for name in names[:20]:
        rows = db.execute(
            select(CodeSymbol).where(
                CodeSymbol.repository_id == repository_id,
                CodeSymbol.name == name,
            ).limit(5)
        ).scalars().all()
        for sym in rows:
            chunk = db.execute(
                select(CodeChunk).where(
                    CodeChunk.repository_id == repository_id,
                    CodeChunk.file_path == sym.file_path,
                    CodeChunk.symbol_name == sym.name,
                ).limit(1)
            ).scalar_one_or_none()
            content = chunk.content if chunk else (sym.signature or sym.name)
            results.append(
                RetrievedContext(
                    file_path=sym.file_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    content=content,
                    symbol_name=sym.name,
                    relevance=0.9,
                    source="symbol",
                )
            )
            if len(results) >= limit:
                return results
    return results


def dependency_context(
    db: Session,
    repository_id: uuid.UUID,
    file_path: str,
    limit: int = 10,
) -> list[RetrievedContext]:
    deps = db.execute(
        select(CodeDependency).where(
            CodeDependency.repository_id == repository_id,
            CodeDependency.source_file == file_path,
        ).limit(limit)
    ).scalars().all()
    results: list[RetrievedContext] = []
    for dep in deps:
        results.append(
            RetrievedContext(
                file_path=dep.source_file,
                start_line=1,
                end_line=1,
                content=f"{dep.dependency_type}: {dep.target_name}",
                symbol_name=None,
                relevance=0.7,
                source="dependency",
            )
        )
    return results


def ripgrep_search(repo_path: str | None, pattern: str, limit: int = 10) -> list[RetrievedContext]:
    if not repo_path or not Path(repo_path).exists():
        return []
    try:
        result = subprocess.run(
            ["rg", "-n", "--no-heading", "-m", str(limit), pattern, repo_path],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    contexts: list[RetrievedContext] = []
    for line in result.stdout.splitlines()[:limit]:
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        path, lineno, text_line = parts
        try:
            rel = str(Path(path).resolve().relative_to(Path(repo_path).resolve())).replace("\\", "/")
        except Exception:
            rel = path
        contexts.append(
            RetrievedContext(
                file_path=rel,
                start_line=int(lineno),
                end_line=int(lineno),
                content=text_line,
                symbol_name=None,
                relevance=0.6,
                source="search",
            )
        )
    return contexts


def retrieve_for_change(
    db: Session,
    repository: Repository,
    changed_file: str,
    changed_symbols: list[str],
    patch: str | None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    query_bits = [changed_file, *changed_symbols]
    if patch:
        query_bits.append(patch[:1500])
    query = "\n".join(query_bits)

    combined: list[RetrievedContext] = []
    combined.extend(symbol_search(db, repository.id, changed_symbols, limit=10))
    combined.extend(dependency_context(db, repository.id, changed_file, limit=8))
    combined.extend(semantic_search(db, repository.id, query, limit=10))
    for sym in changed_symbols[:5]:
        combined.extend(ripgrep_search(repository.local_path, sym, limit=5))

    # Deduplicate by file+lines
    seen: set[tuple] = set()
    unique: list[RetrievedContext] = []
    for item in sorted(combined, key=lambda c: c.relevance, reverse=True):
        key = (item.file_path, item.start_line, item.end_line, item.source)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break

    return [asdict(c) for c in unique]