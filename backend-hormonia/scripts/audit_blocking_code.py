"""
Simple static audit for potentially blocking operations.

Used by performance tests to generate an informational report.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Dict, List


_EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    "node_modules",
    "venv",
    "env",
    ".venv",
    "migrations",
    "alembic",
    "tests",
}


def _python_files(base_dir: str) -> List[Path]:
    files: List[Path] = []
    for root, dirs, filenames in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
        for filename in filenames:
            if filename.endswith(".py"):
                files.append(Path(root) / filename)
    return files


def _op(file_path: Path, line: int, pattern: str, severity: str) -> Dict[str, object]:
    return {
        "file": str(file_path),
        "line": line,
        "pattern": pattern,
        "severity": severity,
    }


def find_blocking_operations(base_dir: str) -> List[Dict[str, object]]:
    """
    Return a list of potential blocking operations found in Python files.

    Output schema:
    - file: str
    - line: int
    - pattern: str
    - severity: HIGH|MEDIUM|LOW
    """
    findings: List[Dict[str, object]] = []

    for file_path in _python_files(base_dir):
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "requests":
                        findings.append(
                            _op(file_path, node.lineno, "import requests", "HIGH")
                        )
                    if alias.name == "psycopg2":
                        findings.append(
                            _op(file_path, node.lineno, "import psycopg2", "HIGH")
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module == "time":
                    for alias in node.names:
                        if alias.name == "sleep":
                            findings.append(
                                _op(
                                    file_path,
                                    node.lineno,
                                    "from time import sleep",
                                    "HIGH",
                                )
                            )
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "time" and node.func.attr == "sleep":
                            findings.append(
                                _op(file_path, node.lineno, "time.sleep", "HIGH")
                            )
                        if node.func.value.id == "requests":
                            findings.append(
                                _op(
                                    file_path,
                                    node.lineno,
                                    f"requests.{node.func.attr}",
                                    "HIGH",
                                )
                            )
                elif isinstance(node.func, ast.Name) and node.func.id == "open":
                    findings.append(_op(file_path, node.lineno, "open()", "LOW"))

    return findings

