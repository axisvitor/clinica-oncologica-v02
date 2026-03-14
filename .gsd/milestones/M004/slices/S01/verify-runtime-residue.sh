#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage:' \
    '  bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report <backend|frontend|all>' \
    '  bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check <backend|frontend|all>'
}

MODE="${1:-}"
SCOPE="${2:-}"

case "$MODE" in
  --report|--check) ;;
  *)
    usage
    exit 64
    ;;
esac

case "$SCOPE" in
  backend|frontend|all) ;;
  *)
    usage
    exit 64
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
REPO_ROOT="${RUNTIME_RESIDUE_REPO_ROOT:-$DEFAULT_REPO_ROOT}"
ALLOWLIST_PATH="${RUNTIME_RESIDUE_ALLOWLIST:-$SCRIPT_DIR/runtime-residue-allowlist.json}"

python3 - "$MODE" "$SCOPE" "$REPO_ROOT" "$ALLOWLIST_PATH" <<'PY'
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Tuple

mode, scope_arg, repo_root_raw, allowlist_raw = sys.argv[1:5]
repo_root = Path(repo_root_raw).resolve()
allowlist_path = Path(allowlist_raw).resolve()

if not allowlist_path.is_file():
    print(f"missing allowlist: {allowlist_path}")
    sys.exit(66)

with allowlist_path.open("r", encoding="utf-8") as handle:
    config = json.load(handle)

selected_scopes = ["backend", "frontend"] if scope_arg == "all" else [scope_arg]
scope_defaults: Dict[str, Dict[str, Any]] = config.get("scope_defaults", {})
categories: List[Dict[str, Any]] = config.get("categories", [])

failures: List[str] = []
reports: Dict[str, List[Tuple[str, str, int]]] = {scope: [] for scope in selected_scopes}
text_cache: Dict[str, str] = {}


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(repo_root).as_posix()


def has_glob(pattern: str) -> bool:
    return any(token in pattern for token in "*?[")


def matches_pattern(path: str, pattern: str) -> bool:
    return PurePosixPath(path).match(pattern) or fnmatch.fnmatch(path, pattern)


def is_excluded(path: str, patterns: Iterable[str]) -> bool:
    return any(matches_pattern(path, pattern) for pattern in patterns)


def expand_roots(roots: Iterable[str], extensions: Iterable[str]) -> List[Path]:
    extension_set = set(extensions or [])
    candidates: Dict[str, Path] = {}
    for root in roots:
        if has_glob(root):
            matches = repo_root.glob(root)
        else:
            resolved = repo_root / root
            if resolved.is_dir():
                matches = resolved.rglob("*")
            elif resolved.exists():
                matches = [resolved]
            else:
                matches = []

        for candidate in matches:
            if not candidate.is_file():
                continue
            if extension_set and candidate.suffix not in extension_set:
                continue
            rel = relative_path(candidate)
            candidates[rel] = candidate.resolve()
    return [candidates[key] for key in sorted(candidates)]


def get_text(path: Path) -> str:
    rel = relative_path(path)
    if rel not in text_cache:
        text_cache[rel] = path.read_text(encoding="utf-8", errors="ignore")
    return text_cache[rel]


def matcher_hits_text(matcher: Dict[str, str], text: str) -> bool:
    pattern = matcher["pattern"]
    if matcher.get("type") == "literal":
        return pattern in text
    return re.search(pattern, text, flags=re.MULTILINE) is not None


def count_matching_lines(matchers: List[Dict[str, str]], text: str) -> int:
    total = 0
    for line in text.splitlines():
        if any(matcher_hits_text(matcher, line) for matcher in matchers):
            total += 1
    return total


for category in categories:
    category_id = category["id"]
    matchers = category.get("matchers", [])
    scope_configs = category.get("scopes", {})

    for scope_name in selected_scopes:
        scope_config = scope_configs.get(scope_name)
        if not scope_config:
            continue

        defaults = scope_defaults.get(scope_name, {})
        roots = scope_config.get("roots", [])
        extensions = scope_config.get("extensions", defaults.get("extensions", []))
        exclude_patterns = list(defaults.get("exclude", [])) + list(scope_config.get("exclude", []))
        approved_entries = {
            entry["path"]: entry for entry in scope_config.get("approved", [])
        }

        actual_counts: Dict[str, int] = {}
        for candidate in expand_roots(roots, extensions):
            rel = relative_path(candidate)
            if is_excluded(rel, exclude_patterns):
                continue
            text = get_text(candidate)
            count = count_matching_lines(matchers, text)
            if count > 0:
                actual_counts[rel] = count

        for rel_path in sorted(actual_counts):
            if rel_path in approved_entries:
                reports[scope_name].append((category_id, rel_path, actual_counts[rel_path]))
            else:
                failures.append(
                    f"category={category_id} unexpected_file={rel_path} count={actual_counts[rel_path]}"
                )

        for approved_path, entry in sorted(approved_entries.items()):
            target = repo_root / approved_path
            if approved_path not in actual_counts:
                detail = (
                    "approved file missing"
                    if not target.exists()
                    else "approved residue no longer matches current scan"
                )
                failures.append(
                    f"category={category_id} moved_hotspot={approved_path} detail={detail}"
                )
                continue

            text = get_text(target)
            for anchor in entry.get("anchors", []):
                if not matcher_hits_text(anchor, text):
                    failures.append(
                        f"category={category_id} moved_hotspot={approved_path} anchor={anchor['label']}"
                    )
                    break

for scope_name in selected_scopes:
    print(f"[{scope_name}]")
    scope_report = sorted(reports[scope_name], key=lambda item: (item[0], item[1]))
    if not scope_report:
        print("  - no approved residue")
        continue
    for category_id, rel_path, count in scope_report:
        print(f"  - category={category_id} file={rel_path} count={count}")

if not failures:
    print(f"\nRESULT: {mode} {scope_arg} OK")
    sys.exit(0)

if mode == "--report":
    print("\n[drift-notes]")
    for failure in failures:
        print(f"  - {failure}")
    print(f"\nRESULT: --report {scope_arg} completed with {len(failures)} drift note(s)")
    sys.exit(0)

print("\n[failures]")
for failure in failures:
    print(f"  - {failure}")
print(f"\nRESULT: --check {scope_arg} FAILED with {len(failures)} issue(s)")
sys.exit(1)
PY
