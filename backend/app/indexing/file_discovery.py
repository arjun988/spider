"""Source file discovery with sensible exclusions."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "dist", "build",
    "target", "out", ".next", ".nuxt", "coverage", "__pycache__", ".tox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "vendor", "third_party",
    "Pods", "DerivedData", ".idea", ".vscode", "bin", "obj",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".pdf", ".zip",
    ".tar", ".gz", ".bz2", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib",
    ".class", ".jar", ".war", ".o", ".a", ".lib", ".wasm", ".pyc", ".pyo",
    ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".avi",
    ".lock", ".min.js", ".min.css", ".map", ".bin", ".dat",
}

LANGUAGE_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".swift": "swift",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md": "markdown",
}

MAX_FILE_BYTES = 512_000


def detect_language(path: Path) -> str | None:
    return LANGUAGE_BY_EXT.get(path.suffix.lower())


def is_test_file(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    if "test" in parts or "tests" in parts or "__tests__" in parts or "spec" in parts:
        return True
    if name.startswith("test_") or name.endswith("_test.py") or name.endswith(".test.ts"):
        return True
    if name.endswith(".test.js") or name.endswith(".spec.ts") or name.endswith(".spec.js"):
        return True
    return False


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part in SKIP_DIRS or part.startswith("."):
            return True
    suffix = path.suffix.lower()
    if suffix in SKIP_EXTENSIONS:
        return True
    name = path.name.lower()
    if name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "cargo.lock"}:
        return True
    if name.endswith(".min.js") or name.endswith(".min.css"):
        return True
    return False


def content_hash(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8", errors="replace")
    return hashlib.sha256(content).hexdigest()


def discover_files(root: Path) -> list[dict]:
    """Return metadata for indexable source files under root."""
    results: list[dict] = []
    root = root.resolve()
    if not root.exists():
        return results

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size == 0 or size > MAX_FILE_BYTES:
            continue
        language = detect_language(path)
        if not language:
            continue
        # Skip non-code config-heavy languages for symbol indexing but keep py/js/ts/go/rs/java
        if language in {"json", "yaml", "toml", "markdown"}:
            continue
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        rel = str(path.relative_to(root)).replace("\\", "/")
        results.append(
            {
                "path": rel,
                "absolute": str(path),
                "language": language,
                "is_test": is_test_file(path),
                "content_hash": content_hash(raw),
                "line_count": text.count("\n") + 1,
                "size_bytes": size,
                "content": text,
            }
        )
    logger.info("files_discovered", root=str(root), count=len(results))
    return results