#!/usr/bin/env python3
"""
TODO Audit Script - LOW-010
Finds all TODO comments and ensures they're linked to GitHub issues.
Usage: python scripts/audit_todos.py [--fix] [--create-issues]
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple
import json

# Colors for terminal output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

TODO_PATTERN = re.compile(r'#\s*TODO(?:\(#(\d+)\))?\s*:\s*(.+)')
VALID_TODO_PATTERN = re.compile(r'#\s*TODO\(#\d+\)\s*:\s*.+')


def find_all_todos(root_dir: Path) -> List[Tuple[Path, int, str, str, bool]]:
    """
    Find all TODO comments in Python files.
    Returns: [(file_path, line_number, full_line, todo_text, has_issue)]
    """
    todos = []

    for py_file in root_dir.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in ['venv', '.venv', 'migrations', 'alembic', '__pycache__']):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    match = TODO_PATTERN.search(line)
                    if match:
                        issue_num = match.group(1)
                        todo_text = match.group(2).strip()
                        has_issue = issue_num is not None
                        todos.append((py_file, line_num, line.strip(), todo_text, has_issue))
        except Exception as e:
            print(f"{RED}Error reading {py_file}: {e}{RESET}")

    return todos


def print_summary(todos: List[Tuple[Path, int, str, str, bool]]):
    """Print summary of TODO findings."""
    total = len(todos)
    with_issues = sum(1 for _, _, _, _, has_issue in todos if has_issue)
    without_issues = total - with_issues

    print(f"\n{'='*80}")
    print(f"{BLUE}TODO Audit Summary{RESET}")
    print(f"{'='*80}")
    print(f"Total TODOs found: {total}")
    print(f"{GREEN}✓ TODOs with GitHub issues: {with_issues}{RESET}")
    print(f"{RED}✗ TODOs without GitHub issues: {without_issues}{RESET}")
    print(f"{'='*80}\n")


def print_todos_without_issues(todos: List[Tuple[Path, int, str, str, bool]]):
    """Print all TODOs that don't have GitHub issues."""
    todos_without_issues = [(f, ln, line, text, has) for f, ln, line, text, has in todos if not has]

    if not todos_without_issues:
        print(f"{GREEN}✓ All TODOs are linked to GitHub issues!{RESET}")
        return

    print(f"\n{YELLOW}TODOs without GitHub issues:{RESET}\n")

    for file_path, line_num, full_line, todo_text, _ in todos_without_issues:
        relative_path = file_path.relative_to(Path.cwd())
        print(f"{RED}✗{RESET} {relative_path}:{line_num}")
        print(f"  {full_line}")
        print(f"  → {todo_text}")
        print()


def generate_github_issues_template(todos: List[Tuple[Path, int, str, str, bool]]) -> str:
    """Generate a template for creating GitHub issues."""
    todos_without_issues = [(f, ln, line, text, has) for f, ln, line, text, has in todos if not has]

    if not todos_without_issues:
        return ""

    issues = []
    for file_path, line_num, full_line, todo_text, _ in todos_without_issues:
        relative_path = file_path.relative_to(Path.cwd())

        issue = {
            "title": f"TODO: {todo_text[:50]}{'...' if len(todo_text) > 50 else ''}",
            "body": f"""## TODO Found in Code

**File:** `{relative_path}`
**Line:** {line_num}

**Description:**
{todo_text}

**Code Context:**
```python
{full_line}
```

**Labels:** `code-quality`, `technical-debt`, `low-priority`
""",
            "labels": ["code-quality", "technical-debt", "low-priority"],
            "file": str(relative_path),
            "line": line_num,
            "text": todo_text
        }
        issues.append(issue)

    return json.dumps(issues, indent=2)


def main():
    """Main execution."""
    root_dir = Path.cwd() / "app"

    if not root_dir.exists():
        print(f"{RED}Error: app/ directory not found. Run from backend-hormonia root.{RESET}")
        sys.exit(1)

    print(f"{BLUE}Scanning for TODO comments in {root_dir}...{RESET}")
    todos = find_all_todos(root_dir)

    print_summary(todos)
    print_todos_without_issues(todos)

    # Generate GitHub issues template
    if '--create-issues' in sys.argv:
        template = generate_github_issues_template(todos)
        if template:
            output_file = Path("docs/code-quality/TODO_GITHUB_ISSUES.json")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(template)
            print(f"{GREEN}✓ GitHub issues template written to {output_file}{RESET}")
            print(f"{YELLOW}  You can use the GitHub CLI to create these issues:{RESET}")
            print(f"  {BLUE}cat {output_file} | jq -r '.[] | \"gh issue create --title '\\'\" + .title + \"'\\' --body '\\'\" + .body + \"'\\' --label \" + (.labels | join(\",\"))'{RESET}")

    # Exit with error if there are TODOs without issues
    todos_without_issues = [t for t in todos if not t[4]]
    if todos_without_issues:
        print(f"\n{RED}✗ Found {len(todos_without_issues)} TODOs without GitHub issues.{RESET}")
        print(f"{YELLOW}  Run with --create-issues to generate GitHub issue templates.{RESET}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}✓ All TODOs are properly tracked!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
