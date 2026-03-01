#!/usr/bin/env python3
"""CI lint check: Block async DB usage in Celery task files.

Celery tasks run in sync worker processes and MUST use sync Session
(get_db / get_scoped_session). Using AsyncSession or get_async_db in task
code causes MissingGreenlet errors at runtime.

This guard scans all files under app/tasks/ for:
- Imports of get_async_db (from any module)
- Imports of AsyncSession (from any module)
- Direct usage of get_async_db() calls

Run: python scripts/check_async_isolation.py
Exit 0 = clean, Exit 1 = violations found.

Phase 21 requirement FOUND-03: Celery tasks continue using sync get_db.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ASYNC_DB_IMPORT = re.compile(r"\bget_async_db\b")
ASYNC_SESSION_IMPORT = re.compile(r"\bAsyncSession\b")
ASYNC_SESSIONMAKER = re.compile(r"\basync_sessionmaker\b")
IMPORT_LINE = re.compile(r"^\s*(from\s+\S+\s+import\s+.+|import\s+.+)$")

TRIPLE_DOUBLE = '"""'
TRIPLE_SINGLE = "'''"


def _find_violations(path: Path) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    in_docstring = False
    doc_delimiter = ""

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()

        if not in_docstring and stripped.startswith("#"):
            continue

        if not in_docstring:
            if TRIPLE_DOUBLE in stripped:
                if stripped.count(TRIPLE_DOUBLE) % 2 == 1:
                    in_docstring = True
                    doc_delimiter = TRIPLE_DOUBLE
                continue
            if TRIPLE_SINGLE in stripped:
                if stripped.count(TRIPLE_SINGLE) % 2 == 1:
                    in_docstring = True
                    doc_delimiter = TRIPLE_SINGLE
                continue
        elif doc_delimiter and doc_delimiter in stripped:
            if stripped.count(doc_delimiter) % 2 == 1:
                in_docstring = False
                doc_delimiter = ""
            continue

        if in_docstring:
            continue

        if ASYNC_DB_IMPORT.search(line):
            violations.append((line_no, stripped))
        elif IMPORT_LINE.match(stripped) and ASYNC_SESSION_IMPORT.search(line):
            violations.append((line_no, stripped))
        elif IMPORT_LINE.match(stripped) and ASYNC_SESSIONMAKER.search(line):
            violations.append((line_no, stripped))

    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    tasks_dir = repo_root / "app" / "tasks"
    if not tasks_dir.exists():
        print(f"Tasks directory not found: {tasks_dir}")
        return 1

    found: list[tuple[Path, int, str]] = []
    file_count = 0
    for py_file in sorted(tasks_dir.rglob("*.py")):
        file_count += 1
        for line_no, snippet in _find_violations(py_file):
            found.append((py_file, line_no, snippet))

    if found:
        print("Async DB usage found in Celery task files:")
        for path, line_no, snippet in found:
            rel = path.relative_to(repo_root)
            print(f"- {rel}:{line_no} -> {snippet}")
        print(
            "\nCelery tasks must use sync get_db() or get_scoped_session(), "
            "not get_async_db or AsyncSession."
        )
        return 1

    print(f"No async DB usage found in Celery task files ({file_count} files scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
