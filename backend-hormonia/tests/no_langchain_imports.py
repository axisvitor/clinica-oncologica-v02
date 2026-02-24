"""Permanent gate: zero LangChain imports anywhere in production code.

This test uses AST parsing to detect langchain imports in any .py file
under app/. It must NEVER be removed - it is the safety net against
LangChain re-introduction.
"""

import ast
import pathlib

import pytest

_BANNED = {"langchain", "langchain_core", "langchain_google_genai", "langchain_google"}


@pytest.mark.parametrize("py_file", sorted(pathlib.Path("app").rglob("*.py")))
def test_no_langchain_imports(py_file: pathlib.Path) -> None:
    """Fail if any langchain import detected in production code."""
    try:
        tree = ast.parse(py_file.read_bytes())
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for banned in _BANNED:
                    if alias.name and alias.name.startswith(banned):
                        pytest.fail(f"{py_file}: LangChain import detected: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for banned in _BANNED:
                if mod.startswith(banned):
                    pytest.fail(f"{py_file}: LangChain import detected: from {mod}")
