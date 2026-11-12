"""Tree-sitter based symbol extraction for supported languages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_PARSERS: dict[str, Any] = {}


@dataclass
class SymbolInfo:
    name: str
    qualified_name: str
    symbol_type: str
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None
    imports: list[str] = field(default_factory=list)


def _get_parser(language: str):
    if language in _PARSERS:
        return _PARSERS[language]
    try:
        import tree_sitter_python as tspython
        import tree_sitter_javascript as tsjs
        import tree_sitter_typescript as tsts
        import tree_sitter_go as tsgo
        import tree_sitter_rust as tsrust
        import tree_sitter_java as tsjava
        from tree_sitter import Language, Parser

        mapping = {
            "python": tspython.language(),
            "javascript": tsjs.language(),
            "typescript": tsts.language_typescript(),
            "tsx": tsts.language_tsx(),
            "go": tsgo.language(),
            "rust": tsrust.language(),
            "java": tsjava.language(),
        }
        lang_ptr = mapping.get(language)
        if language == "typescript" and language not in mapping:
            lang_ptr = tsts.language_typescript()
        if not lang_ptr:
            return None
        parser = Parser(Language(lang_ptr))
        _PARSERS[language] = parser
        return parser
    except Exception as exc:
        logger.warning("tree_sitter_init_failed", language=language, error=str(exc))
        return None


def _node_text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def parse_python(source: str, file_path: str) -> list[SymbolInfo]:
    parser = _get_parser("python")
    if not parser:
        return _fallback_python(source, file_path)
    raw = source.encode("utf-8")
    tree = parser.parse(raw)
    symbols: list[SymbolInfo] = []
    imports: list[str] = []

    for node in _walk(tree.root_node):
        if node.type in {"import_statement", "import_from_statement"}:
            imports.append(_node_text(raw, node).strip())
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            name = _node_text(raw, name_node)
            symbols.append(
                SymbolInfo(
                    name=name,
                    qualified_name=f"{file_path}::{name}",
                    symbol_type="function",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=_node_text(raw, node).split("\n", 1)[0][:300],
                )
            )
        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            name = _node_text(raw, name_node)
            symbols.append(
                SymbolInfo(
                    name=name,
                    qualified_name=f"{file_path}::{name}",
                    symbol_type="class",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=_node_text(raw, node).split("\n", 1)[0][:300],
                )
            )

    if imports:
        symbols.append(
            SymbolInfo(
                name="__imports__",
                qualified_name=f"{file_path}::__imports__",
                symbol_type="import",
                start_line=1,
                end_line=1,
                imports=imports,
            )
        )
    return symbols


def _fallback_python(source: str, file_path: str) -> list[SymbolInfo]:
    import ast

    symbols: list[SymbolInfo] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return symbols
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            symbols.append(
                SymbolInfo(
                    name=node.name,
                    qualified_name=f"{file_path}::{node.name}",
                    symbol_type="function",
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
                )
            )
        elif isinstance(node, ast.ClassDef):
            symbols.append(
                SymbolInfo(
                    name=node.name,
                    qualified_name=f"{file_path}::{node.name}",
                    symbol_type="class",
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
                )
            )
    return symbols


def parse_generic_braced(source: str, file_path: str, language: str) -> list[SymbolInfo]:
    """Best-effort extraction for JS/TS/Go/Java/Rust via tree-sitter or line heuristics."""
    lang_key = "tsx" if file_path.endswith(".tsx") else language
    if language == "javascript":
        lang_key = "javascript"
    parser = _get_parser(lang_key if lang_key != "typescript" else "typescript")
    type_map = {
        "function_declaration": "function",
        "method_definition": "method",
        "class_declaration": "class",
        "function_item": "function",
        "impl_item": "class",
        "struct_item": "class",
        "method_declaration": "method",
        "constructor_declaration": "method",
        "function_definition": "function",
        "type_declaration": "class",
        "method_elem": "method",
    }
    symbols: list[SymbolInfo] = []
    if not parser:
        return symbols
    raw = source.encode("utf-8")
    try:
        tree = parser.parse(raw)
    except Exception:
        return symbols

    for node in _walk(tree.root_node):
        stype = type_map.get(node.type)
        if not stype:
            continue
        name_node = node.child_by_field_name("name")
        if not name_node:
            # try first identifier child
            for child in node.children:
                if "identifier" in child.type or child.type in {"property_identifier", "type_identifier"}:
                    name_node = child
                    break
        if not name_node:
            continue
        name = _node_text(raw, name_node)
        symbols.append(
            SymbolInfo(
                name=name,
                qualified_name=f"{file_path}::{name}",
                symbol_type=stype,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=_node_text(raw, node).split("\n", 1)[0][:300],
            )
        )
    return symbols


def extract_symbols(source: str, file_path: str, language: str) -> list[SymbolInfo]:
    if language == "python":
        return parse_python(source, file_path)
    if language in {"javascript", "typescript", "go", "rust", "java"}:
        return parse_generic_braced(source, file_path, language)
    return []