"""Create semantic code chunks from symbols and file content."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.indexing.parser import SymbolInfo


@dataclass
class CodeChunkData:
    file_path: str
    language: str | None
    chunk_type: str
    symbol_name: str | None
    start_line: int
    end_line: int
    content: str
    content_hash: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_file(
    file_path: str,
    content: str,
    language: str | None,
    symbols: list[SymbolInfo],
) -> list[CodeChunkData]:
    lines = content.splitlines()
    chunks: list[CodeChunkData] = []

    meaningful = [s for s in symbols if s.symbol_type in {"function", "class", "method"}]
    if meaningful:
        for sym in meaningful:
            start = max(1, sym.start_line)
            end = min(len(lines), sym.end_line)
            snippet = "\n".join(lines[start - 1 : end])
            if not snippet.strip():
                continue
            chunks.append(
                CodeChunkData(
                    file_path=file_path,
                    language=language,
                    chunk_type=sym.symbol_type,
                    symbol_name=sym.name,
                    start_line=start,
                    end_line=end,
                    content=snippet,
                    content_hash=_hash(snippet),
                )
            )
    else:
        # Fall back to sliding windows of ~80 lines
        window = 80
        overlap = 10
        i = 0
        while i < len(lines):
            start = i + 1
            end = min(len(lines), i + window)
            snippet = "\n".join(lines[i:end])
            if snippet.strip():
                chunks.append(
                    CodeChunkData(
                        file_path=file_path,
                        language=language,
                        chunk_type="block",
                        symbol_name=None,
                        start_line=start,
                        end_line=end,
                        content=snippet,
                        content_hash=_hash(snippet),
                    )
                )
            if end >= len(lines):
                break
            i = end - overlap

    return chunks