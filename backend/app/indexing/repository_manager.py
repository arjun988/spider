"""Clone/fetch repositories and run indexing pipelines."""

from __future__ import annotations

import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.github.client import GitHubClient
from app.indexing.chunker import chunk_file
from app.indexing.embeddings import embed_chunks
from app.indexing.file_discovery import discover_files
from app.indexing.parser import extract_symbols
from app.models.code_index import CodeChunk, CodeDependency, CodeSymbol
from app.models.github import GitHubInstallation
from app.models.repository import Repository, RepositoryFile, RepositoryIndexJob

logger = get_logger(__name__)


def repo_local_path(repository: Repository) -> Path:
    base = Path(settings.repos_base_path)
    base.mkdir(parents=True, exist_ok=True)
    safe = repository.full_name.replace("/", "__")
    return base / safe


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git failed")
    return result.stdout.strip()


def clone_or_fetch(db: Session, repository: Repository) -> tuple[Path, str]:
    installation = db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.organization_id == repository.organization_id,
            GitHubInstallation.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not installation:
        raise RuntimeError("No active GitHub installation for repository organization")

    client = GitHubClient(installation.installation_id)
    clone_url = client.authenticated_clone_url(repository.owner_login, repository.name)
    path = repo_local_path(repository)
    repository.local_path = str(path)

    if (path / ".git").exists():
        _run_git(["remote", "set-url", "origin", clone_url], cwd=path)
        _run_git(["fetch", "--all", "--prune"], cwd=path)
        _run_git(["checkout", repository.default_branch], cwd=path)
        _run_git(["reset", "--hard", f"origin/{repository.default_branch}"], cwd=path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            # incomplete dir
            import shutil

            shutil.rmtree(path)
        _run_git(["clone", "--depth", "1", clone_url, str(path)])

    sha = _run_git(["rev-parse", "HEAD"], cwd=path)
    db.flush()
    return path, sha


def index_repository(db: Session, repository_id: str | uuid.UUID, full: bool = False) -> dict:
    repo = db.get(Repository, uuid.UUID(str(repository_id)))
    if not repo:
        raise ValueError(f"Repository {repository_id} not found")

    job = RepositoryIndexJob(
        repository_id=repo.id,
        job_type="full" if full or repo.index_version == 0 else "incremental",
        status="running",
        from_commit_sha=repo.last_indexed_commit_sha,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    repo.indexing_status = "indexing"
    db.flush()

    try:
        path, sha = clone_or_fetch(db, repo)
        job.to_commit_sha = sha

        files = discover_files(Path(path))
        # Apply repo language allow-list when configured
        from app.models.rules import RepositoryReviewRules

        rules = db.execute(
            select(RepositoryReviewRules).where(RepositoryReviewRules.repository_id == repo.id)
        ).scalar_one_or_none()
        if rules and rules.enabled_languages:
            allowed = {str(x).lower() for x in rules.enabled_languages}
            files = [f for f in files if (f.get("language") or "").lower() in allowed]

        # Incremental: only reindex changed content hashes when not full
        existing_hashes: dict[str, str] = {}
        if job.job_type == "incremental" and repo.last_indexed_commit_sha:
            rows = db.execute(
                select(RepositoryFile).where(
                    RepositoryFile.repository_id == repo.id,
                )
            ).scalars().all()
            existing_hashes = {r.path: r.content_hash for r in rows}

        changed_files = []
        for f in files:
            if job.job_type == "incremental" and existing_hashes.get(f["path"]) == f["content_hash"]:
                continue
            changed_files.append(f)

        job.total_files = len(changed_files if job.job_type == "incremental" else files)
        job.files_processed = 0
        db.flush()

        if job.job_type == "full":
            db.execute(delete(CodeChunk).where(CodeChunk.repository_id == repo.id))
            db.execute(delete(CodeDependency).where(CodeDependency.repository_id == repo.id))
            db.execute(delete(CodeSymbol).where(CodeSymbol.repository_id == repo.id))
            db.execute(delete(RepositoryFile).where(RepositoryFile.repository_id == repo.id))
            db.flush()
        else:
            # Remove stale rows for changed paths
            for f in changed_files:
                db.execute(
                    delete(CodeChunk).where(
                        CodeChunk.repository_id == repo.id,
                        CodeChunk.file_path == f["path"],
                    )
                )
                db.execute(
                    delete(CodeSymbol).where(
                        CodeSymbol.repository_id == repo.id,
                        CodeSymbol.file_path == f["path"],
                    )
                )
                db.execute(
                    delete(RepositoryFile).where(
                        RepositoryFile.repository_id == repo.id,
                        RepositoryFile.path == f["path"],
                    )
                )
            # Prune files deleted from the tree
            current_paths = {f["path"] for f in files}
            stale_paths = [p for p in existing_hashes if p not in current_paths]
            for path in stale_paths:
                db.execute(
                    delete(CodeChunk).where(
                        CodeChunk.repository_id == repo.id,
                        CodeChunk.file_path == path,
                    )
                )
                db.execute(
                    delete(CodeSymbol).where(
                        CodeSymbol.repository_id == repo.id,
                        CodeSymbol.file_path == path,
                    )
                )
                db.execute(
                    delete(RepositoryFile).where(
                        RepositoryFile.repository_id == repo.id,
                        RepositoryFile.path == path,
                    )
                )
            db.flush()

        new_version = repo.index_version + 1
        chunk_payloads: list[tuple] = []
        symbols_created = 0
        work_list = changed_files if job.job_type == "incremental" else files

        for idx, f in enumerate(work_list):
            db.add(
                RepositoryFile(
                    repository_id=repo.id,
                    path=f["path"],
                    language=f["language"],
                    is_test=f["is_test"],
                    is_generated=False,
                    content_hash=f["content_hash"],
                    commit_sha=sha,
                    line_count=f["line_count"],
                    size_bytes=f["size_bytes"],
                )
            )
            symbols = extract_symbols(f["content"], f["path"], f["language"])
            for sym in symbols:
                if sym.symbol_type == "import":
                    for imp in sym.imports:
                        db.add(
                            CodeDependency(
                                repository_id=repo.id,
                                source_file=f["path"],
                                target_name=imp,
                                dependency_type="import",
                                commit_sha=sha,
                                confidence=1.0,
                            )
                        )
                    continue
                db.add(
                    CodeSymbol(
                        repository_id=repo.id,
                        name=sym.name,
                        qualified_name=sym.qualified_name,
                        symbol_type=sym.symbol_type,
                        file_path=f["path"],
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        language=f["language"],
                        signature=sym.signature,
                        docstring=sym.docstring,
                        is_exported=not sym.name.startswith("_"),
                        is_test=f["is_test"],
                        commit_sha=sha,
                        index_version=new_version,
                    )
                )
                symbols_created += 1

            chunks = chunk_file(f["path"], f["content"], f["language"], symbols)
            for ch in chunks:
                chunk_payloads.append(ch)

            job.files_processed = idx + 1
            if (idx + 1) % 5 == 0 or (idx + 1) == len(work_list):
                db.flush()

        # Embeddings
        vectors: list[list[float]] = []
        if chunk_payloads:
            try:
                vectors = embed_chunks(
                    [c.content[:6000] for c in chunk_payloads],
                    db=db,
                    organization_id=repo.organization_id,
                    repository_id=repo.id,
                )
            except Exception as exc:
                logger.warning("embedding_failed", error=str(exc))
                vectors = [None] * len(chunk_payloads)  # type: ignore

        for idx, ch in enumerate(chunk_payloads):
            emb = vectors[idx] if idx < len(vectors) else None
            db.add(
                CodeChunk(
                    repository_id=repo.id,
                    file_path=ch.file_path,
                    language=ch.language,
                    chunk_type=ch.chunk_type,
                    symbol_name=ch.symbol_name,
                    start_line=ch.start_line,
                    end_line=ch.end_line,
                    content=ch.content,
                    content_hash=ch.content_hash,
                    commit_sha=sha,
                    index_version=new_version,
                    embedding=emb,
                )
            )

        repo.index_version = new_version
        repo.last_indexed_commit_sha = sha
        repo.last_indexed_at = datetime.now(timezone.utc)
        repo.indexing_status = "ready"
        job.status = "completed"
        job.files_processed = len(changed_files if job.job_type == "incremental" else files)
        job.chunks_created = len(chunk_payloads)
        job.symbols_created = symbols_created
        job.completed_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "index_complete",
            repo=repo.full_name,
            files=job.files_processed,
            chunks=job.chunks_created,
            symbols=symbols_created,
        )
        return {
            "status": "completed",
            "repository_id": str(repo.id),
            "commit_sha": sha,
            "files": job.files_processed,
            "chunks": job.chunks_created,
            "symbols": symbols_created,
        }
    except Exception as exc:
        repo.indexing_status = "failed"
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        db.flush()
        logger.exception("index_failed", repository_id=str(repository_id))
        raise