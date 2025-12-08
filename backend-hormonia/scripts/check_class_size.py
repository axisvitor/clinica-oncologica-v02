#!/usr/bin/env python3
"""
Check class size - LOW-014
Finds classes exceeding max line count (default: 300 lines)
Usage: python scripts/check_class_size.py [--max-lines 300]
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple
import argparse

# Colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'


class ClassSizeChecker(ast.NodeVisitor):
    """AST visitor to check class sizes."""

    def __init__(self, max_lines: int = 300):
        self.max_lines = max_lines
        self.large_classes: List[Tuple[str, int, int, str]] = []
        self.current_file = ""

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition."""
        start_line = node.lineno
        end_line = node.end_lineno or node.lineno
        length = end_line - start_line + 1

        if length > self.max_lines:
            self.large_classes.append((
                self.current_file,
                node.lineno,
                length,
                node.name
            ))

        self.generic_visit(node)


def check_file(file_path: Path, max_lines: int) -> List[Tuple[str, int, int, str]]:
    """Check a single Python file for large classes."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        checker = ClassSizeChecker(max_lines)
        checker.current_file = str(file_path)
        checker.visit(tree)
        return checker.large_classes

    except SyntaxError as e:
        print(f"{RED}Syntax error in {file_path}: {e}{RESET}")
        return []
    except Exception as e:
        print(f"{RED}Error processing {file_path}: {e}{RESET}")
        return []


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description='Check class size')
    parser.add_argument('--max-lines', type=int, default=300,
                        help='Maximum allowed lines per class (default: 300)')
    args = parser.parse_args()

    root_dir = Path.cwd() / "app"
    if not root_dir.exists():
        print(f"{RED}Error: app/ directory not found{RESET}")
        sys.exit(1)

    print(f"{YELLOW}Checking for classes > {args.max_lines} lines...{RESET}\n")

    all_large_classes = []
    for py_file in root_dir.rglob("*.py"):
        if any(x in py_file.parts for x in ['__pycache__', 'migrations', 'alembic', 'venv']):
            continue

        large_classes = check_file(py_file, args.max_lines)
        all_large_classes.extend(large_classes)

    if not all_large_classes:
        print(f"{GREEN}✓ All classes are ≤ {args.max_lines} lines!{RESET}")
        sys.exit(0)

    # Sort by length (longest first)
    all_large_classes.sort(key=lambda x: x[2], reverse=True)

    print(f"{RED}✗ Found {len(all_large_classes)} classes exceeding {args.max_lines} lines:{RESET}\n")

    for file_path, line_num, length, name in all_large_classes:
        relative_path = Path(file_path).relative_to(Path.cwd())
        print(f"{RED}  {length:3d} lines{RESET} | {relative_path}:{line_num} | class {name}")

    print(f"\n{YELLOW}Recommendation: Split these classes following Single Responsibility Principle{RESET}")
    print(f"{YELLOW}Target: ≤ {args.max_lines} lines per class{RESET}")

    sys.exit(1)


if __name__ == "__main__":
    main()
