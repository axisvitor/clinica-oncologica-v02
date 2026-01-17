#!/usr/bin/env python3
"""Check Alembic migrations for standardized headers and signatures."""

from __future__ import annotations

from dataclasses import dataclass
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = (
    "WHY",
    "WHAT",
    "IMPACT",
    "BENCHMARK",
    "ROLLBACK",
    "RELATED",
    "MIGRATION TYPE",
)


@dataclass
class Issue:
    path: Path
    message: str
    level: str  # "ERROR" or "WARN"


def extract_docstring(text: str) -> str | None:
    match = re.match(r"\s*(\"\"\"|''')", text)
    if not match:
        return None
    quote = match.group(1)
    start = match.end()
    end = text.find(quote, start)
    if end == -1:
        return None
    return text[start:end]


def find_pattern(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.M)
    return match.group(1).strip() if match else None


def check_migration(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    text = path.read_text(encoding="utf-8", errors="ignore")

    docstring = extract_docstring(text)
    if not docstring:
        return [Issue(path, "Missing module docstring.", "ERROR")]

    if not re.search(r"^Revision ID:", docstring, re.M):
        issues.append(Issue(path, "Docstring missing 'Revision ID:' line.", "ERROR"))
    if not re.search(r"^Revises:", docstring, re.M):
        issues.append(Issue(path, "Docstring missing 'Revises:' line.", "ERROR"))
    if not re.search(r"^Create Date:", docstring, re.M):
        issues.append(Issue(path, "Docstring missing 'Create Date:' line.", "ERROR"))

    for section in REQUIRED_SECTIONS:
        if not re.search(rf"(?im)^\s*{re.escape(section)}\s*:", docstring):
            issues.append(
                Issue(path, f"Docstring missing '{section}:' section.", "ERROR")
            )

    revision = find_pattern(
        text,
        r"^revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]",
    )
    down_revision = find_pattern(
        text,
        r"^down_revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]",
    )
    if not revision:
        issues.append(Issue(path, "Missing revision variable.", "ERROR"))
    if "down_revision" not in text:
        issues.append(Issue(path, "Missing down_revision variable.", "ERROR"))

    if not re.search(r"^def\s+upgrade\(\)\s*->\s*None:", text, re.M):
        issues.append(Issue(path, "upgrade() missing '-> None' annotation.", "ERROR"))
    if not re.search(r"^def\s+downgrade\(\)\s*->\s*None:", text, re.M):
        issues.append(
            Issue(path, "downgrade() missing '-> None' annotation.", "ERROR")
        )

    doc_revision = find_pattern(docstring, r"^Revision ID:\s*(.+)$")
    doc_revises = find_pattern(docstring, r"^Revises:\s*(.*)$")
    if revision and doc_revision and revision != doc_revision:
        issues.append(
            Issue(
                path,
                f"Docstring Revision ID '{doc_revision}' != revision '{revision}'.",
                "WARN",
            )
        )
    if down_revision and doc_revises and down_revision != doc_revises:
        issues.append(
            Issue(
                path,
                f"Docstring Revises '{doc_revises}' != down_revision '{down_revision}'.",
                "WARN",
            )
        )
    if revision and not path.stem.startswith(revision):
        issues.append(
            Issue(
                path,
                f"Filename '{path.stem}' does not start with revision '{revision}'.",
                "WARN",
            )
        )

    return issues


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    versions_dir = root / "alembic" / "versions"
    if not versions_dir.exists():
        print(f"[ERROR] Alembic versions path not found: {versions_dir}")
        return 2

    all_issues: list[Issue] = []
    for path in sorted(versions_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        all_issues.extend(check_migration(path))

    errors = [issue for issue in all_issues if issue.level == "ERROR"]
    warnings = [issue for issue in all_issues if issue.level == "WARN"]

    if all_issues:
        print("Alembic migration checks:")
        for issue in all_issues:
            print(f"- [{issue.level}] {issue.path}: {issue.message}")

    print(f"\nSummary: {len(errors)} error(s), {len(warnings)} warning(s).")
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
