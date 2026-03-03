#!/usr/bin/env python3
"""CI lint check: Block direct pydantic-ai agent.run() calls outside PIISafeAgent.

All AI agent invocations MUST go through PIISafeAgent._safe_run() to ensure
mandatory PII redaction (LGPD Art. 46) and structured logging.

Run: python scripts/check_agent_run_calls.py
Exit 0 = clean, Exit 1 = violations found.

Phase 11 success criterion 2: "confirmed by CI lint rule that blocks direct
.run() calls outside PIISafeAgent"
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RUN_CALL_PATTERN = re.compile(
    r"\b\w*agent\b\.run(?:_sync|_stream)?\s*\(",
    flags=re.IGNORECASE,
)
ADK_RUN_PATTERN = re.compile(
    r"\b\w*runner\b\.run(?:_async)?\s*\(",
    flags=re.IGNORECASE,
)
TRIPLE_DOUBLE = '"""'
TRIPLE_SINGLE = "'''"


def _is_exempt(path: Path) -> bool:
    as_posix = path.as_posix()
    return as_posix.endswith(
        "app/ai/agents/base.py"
    ) or as_posix.endswith("app/ai/adk/wrapper.py")


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

        if RUN_CALL_PATTERN.search(line) or ADK_RUN_PATTERN.search(line):
            violations.append((line_no, stripped))

    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"
    if not app_dir.exists():
        print(f"App directory not found: {app_dir}")
        return 1

    found: list[tuple[Path, int, str]] = []
    for py_file in sorted(app_dir.rglob("*.py")):
        if _is_exempt(py_file):
            continue
        for line_no, snippet in _find_violations(py_file):
            found.append((py_file, line_no, snippet))

    if found:
        print("Direct agent/adk run() calls found outside approved wrappers:")
        for path, line_no, snippet in found:
            rel = path.relative_to(repo_root)
            print(f"- {rel}:{line_no} -> {snippet}")
        return 1

    print("No direct agent/adk run() calls found outside approved wrappers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
