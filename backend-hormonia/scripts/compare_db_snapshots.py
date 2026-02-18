"""Compare editorial Markdown with DB snapshot Markdown (no DB access required)."""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path
from typing import Iterable, List, Sequence, Set, Tuple


DEFAULT_PAIRS = [
    (
        "FLUXO HORMON[IA] - 1 A 15.md",
        "db_snapshot/FLUXO HORMON[IA] - 1 A 15 [DB].md",
    ),
    (
        "Fluxo HORMON[IA] - 16 A 45.md",
        "db_snapshot/Fluxo HORMON[IA] - 16 A 45 [DB].md",
    ),
    (
        "Fluxo Hormon[IA] MENSAL PADRÃO .md",
        "db_snapshot/Fluxo Hormon[IA] MENSAL PADRÃO [DB].md",
    ),
    (
        "Quizz de Bem-Estar Mensal.md",
        "db_snapshot/Quizz de Bem-Estar Mensal [DB].md",
    ),
]


def _read_lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _strip_snapshot_headers(lines: Sequence[str]) -> List[str]:
    if not lines:
        return []
    if not lines[0].startswith("# Snapshot DB"):
        return list(lines)
    filtered: List[str] = []
    for line in lines:
        if line.startswith("# Snapshot DB"):
            continue
        if line.startswith("- Gerado em:"):
            continue
        if line.startswith("- Template:"):
            continue
        filtered.append(line)
    return filtered


def _extract_days(lines: Iterable[str]) -> Set[int]:
    days: Set[int] = set()
    pattern = re.compile(r"^\s*[^A-Za-z0-9]*DIA\s*(\d+)\b", re.IGNORECASE)
    for line in lines:
        match = pattern.search(line)
        if not match:
            continue
        try:
            days.add(int(match.group(1)))
        except ValueError:
            continue
    return days


def _extract_questions_editorial(lines: Iterable[str]) -> List[str]:
    questions: List[str] = []
    for line in lines:
        if line.strip().startswith("###"):
            text = re.sub(r"[*#_`]", "", line).strip()
            text = re.sub(r"^\d+(\.\d+)*\.\s*", "", text).strip()
            if text:
                questions.append(text)
    return questions


def _extract_questions_snapshot(lines: Iterable[str]) -> List[str]:
    questions: List[str] = []
    for line in lines:
        if line.strip().startswith("- texto:"):
            text = line.split(":", 1)[1].strip()
            if text:
                questions.append(text)
    return questions


def _print_section(title: str, out_lines: List[str]) -> None:
    out_lines.append("")
    out_lines.append(title)
    out_lines.append("-" * len(title))


def _print_list(label: str, items: Sequence[str], out_lines: List[str], max_items: int) -> None:
    out_lines.append(f"{label}: {len(items)}")
    if items:
        for item in items[:max_items]:
            out_lines.append(f"- {item}")
        if len(items) > max_items:
            out_lines.append(f"... ({len(items) - max_items} more)")


def _analyze_flow(editorial: Path, snapshot: Path, max_items: int) -> List[str]:
    out: List[str] = []
    out.append(f"[FLOW] {editorial.name}")
    out.append(f"editorial: {editorial}")
    out.append(f"db_snapshot: {snapshot}")

    editorial_lines = _read_lines(editorial)
    snapshot_lines = _strip_snapshot_headers(_read_lines(snapshot))

    days_editorial = sorted(_extract_days(editorial_lines))
    days_db = sorted(_extract_days(snapshot_lines))

    missing_in_db = [str(d) for d in days_editorial if d not in days_db]
    missing_in_editorial = [str(d) for d in days_db if d not in days_editorial]

    _print_section("Days coverage", out)
    _print_list("Days in editorial", [str(d) for d in days_editorial], out, max_items)
    _print_list("Days in DB snapshot", [str(d) for d in days_db], out, max_items)
    _print_list("Missing in DB", missing_in_db, out, max_items)
    _print_list("Missing in editorial", missing_in_editorial, out, max_items)

    return out


def _analyze_quiz(editorial: Path, snapshot: Path, max_items: int) -> List[str]:
    out: List[str] = []
    out.append(f"[QUIZ] {editorial.name}")
    out.append(f"editorial: {editorial}")
    out.append(f"db_snapshot: {snapshot}")

    editorial_lines = _read_lines(editorial)
    snapshot_lines = _strip_snapshot_headers(_read_lines(snapshot))

    questions_editorial = _extract_questions_editorial(editorial_lines)
    questions_db = _extract_questions_snapshot(snapshot_lines)

    set_editorial = {q.strip().lower() for q in questions_editorial if q.strip()}
    set_db = {q.strip().lower() for q in questions_db if q.strip()}

    missing_in_db = sorted(set_editorial - set_db)
    missing_in_editorial = sorted(set_db - set_editorial)

    _print_section("Questions coverage", out)
    _print_list("Questions in editorial", questions_editorial, out, max_items)
    _print_list("Questions in DB snapshot", questions_db, out, max_items)
    _print_list("Missing in DB", missing_in_db, out, max_items)
    _print_list("Missing in editorial", missing_in_editorial, out, max_items)

    return out


def _diff_lines(
    editorial_lines: Sequence[str],
    snapshot_lines: Sequence[str],
    context: int,
) -> List[str]:
    return list(
        difflib.unified_diff(
            editorial_lines,
            snapshot_lines,
            fromfile="editorial",
            tofile="db_snapshot",
            lineterm="",
            n=context,
        )
    )


def _is_quiz_file(path: Path) -> bool:
    name = path.name.lower()
    return "quiz" in name or "quizz" in name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare editorial Markdown with DB snapshot Markdown."
    )
    parser.add_argument(
        "--base-dir",
        default=str(Path("app/templates/arquivo")),
        help="Base directory for editorial and db_snapshot files.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Include unified diff output.",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=3,
        help="Context lines for unified diff.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="Max items to list in coverage sections.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output file path for the report.",
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir)

    report: List[str] = []

    for editorial_rel, snapshot_rel in DEFAULT_PAIRS:
        editorial = base_dir / editorial_rel
        snapshot = base_dir / snapshot_rel
        report.append("")
        report.append("=" * 80)

        if not editorial.exists():
            report.append(f"[MISSING] editorial not found: {editorial}")
            continue
        if not snapshot.exists():
            report.append(f"[MISSING] db snapshot not found: {snapshot}")
            continue

        if _is_quiz_file(editorial):
            report.extend(_analyze_quiz(editorial, snapshot, args.max_items))
        else:
            report.extend(_analyze_flow(editorial, snapshot, args.max_items))

        if args.diff:
            report.append("")
            report.append("Unified diff")
            report.append("-" * 12)
            editorial_lines = _read_lines(editorial)
            snapshot_lines = _strip_snapshot_headers(_read_lines(snapshot))
            report.extend(_diff_lines(editorial_lines, snapshot_lines, args.context))

    output = "\n".join(report).lstrip() + "\n"

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
