"""Tree-sitter / AST parser tests."""

from __future__ import annotations

from app.indexing.file_discovery import discover_files, is_test_file
from app.indexing.parser import extract_symbols
from pathlib import Path


def test_extract_python_symbols():
    source = '''
import os

class Greeter:
    def hello(self, name):
        return f"hi {name}"

def add(a, b):
    return a + b
'''
    symbols = extract_symbols(source, "demo.py", "python")
    names = {s.name for s in symbols if s.symbol_type != "import"}
    assert "Greeter" in names
    assert "add" in names


def test_is_test_file():
    assert is_test_file(Path("tests/test_foo.py")) is True
    assert is_test_file(Path("app/main.py")) is False


def test_discover_skips_venv(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("x=1\n", encoding="utf-8")
    files = discover_files(tmp_path)
    paths = {f["path"] for f in files}
    assert "app/main.py" in paths
    assert not any(".venv" in p for p in paths)