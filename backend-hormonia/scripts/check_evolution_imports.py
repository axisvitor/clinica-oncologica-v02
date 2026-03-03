#!/usr/bin/env python3
"""CI lint check: Verify zero imports of tombstoned Evolution API in non-tombstone files.

Evolution API (EvolutionClient, EvolutionAPIClient) was tombstoned in Phase 37.
Non-tombstone application files must not import these symbols.

Run: python scripts/check_evolution_imports.py
Exit 0 = clean, Exit 1 = violations found.

Phase 38 requirement TEST-05.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

EVOLUTION_NAMES = frozenset({"EvolutionClient", "EvolutionAPIClient"})

TOMBSTONE_DIRS = frozenset(
    {
        "app/integrations/evolution",
        "app/integrations/whatsapp/services",
    }
)


def _is_tombstone_file(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root).as_posix()
    return any(rel.startswith(t) for t in TOMBSTONE_DIRS)


def _scan_imports(path: Path) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in EVOLUTION_NAMES or (
                    alias.asname and alias.asname in EVOLUTION_NAMES
                ):
                    violations.append(
                        (node.lineno, f"from {node.module} import {alias.name}")
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[-1] in EVOLUTION_NAMES:
                    violations.append((node.lineno, f"import {alias.name}"))

    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"

    if not app_dir.exists():
        print(f"App directory not found: {app_dir}")
        return 1

    found: list[tuple[Path, int, str]] = []
    file_count = 0
    for py_file in sorted(app_dir.rglob("*.py")):
        if _is_tombstone_file(py_file, repo_root):
            continue
        file_count += 1
        for line_no, snippet in _scan_imports(py_file):
            found.append((py_file.relative_to(repo_root), line_no, snippet))

    if found:
        print("Evolution API imports found in non-tombstone files:")
        for rel, line_no, snippet in found:
            print(f"  {rel}:{line_no} -> {snippet}")
        return 1

    print(
        f"No Evolution API imports found in non-tombstone files ({file_count} files scanned)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
