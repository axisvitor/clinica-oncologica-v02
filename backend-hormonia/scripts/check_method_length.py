#!/usr/bin/env python3
"""
Check method length - LOW-013
Finds methods exceeding max line count (default: 50 lines)
Usage: python scripts/check_method_length.py [--max-lines 50]
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


class MethodLengthChecker(ast.NodeVisitor):
    """AST visitor to check method/function lengths."""

    def __init__(self, max_lines: int = 50):
        self.max_lines = max_lines
        self.long_methods: List[Tuple[str, int, int, str]] = []
        self.current_file = ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition."""
        self._check_length(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition."""
        self._check_length(node)
        self.generic_visit(node)

    def _check_length(self, node):
        """Check if function/method exceeds max lines."""
        # Calculate actual code lines (exclude docstring)
        start_line = node.lineno
        end_line = node.end_lineno or node.lineno

        # Skip docstring if present
        if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, (ast.Str, ast.Constant))):
            # Find first real code line after docstring
            if len(node.body) > 1:
                start_line = node.body[1].lineno

        length = end_line - start_line + 1

        if length > self.max_lines:
            # Determine if it's a method (inside class) or function
            context = "method" if hasattr(node, 'parent_class') else "function"
            self.long_methods.append((
                self.current_file,
                node.lineno,
                length,
                f"{node.name} ({context})"
            ))


def check_file(file_path: Path, max_lines: int) -> List[Tuple[str, int, int, str]]:
    """Check a single Python file for long methods."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        checker = MethodLengthChecker(max_lines)
        checker.current_file = str(file_path)

        # Mark methods that are inside classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        item.parent_class = node.name

        checker.visit(tree)
        return checker.long_methods

    except SyntaxError as e:
        print(f"{RED}Syntax error in {file_path}: {e}{RESET}")
        return []
    except Exception as e:
        print(f"{RED}Error processing {file_path}: {e}{RESET}")
        return []


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description='Check method/function length')
    parser.add_argument('--max-lines', type=int, default=50,
                        help='Maximum allowed lines per method (default: 50)')
    args = parser.parse_args()

    root_dir = Path.cwd() / "app"
    if not root_dir.exists():
        print(f"{RED}Error: app/ directory not found{RESET}")
        sys.exit(1)

    print(f"{YELLOW}Checking for methods/functions > {args.max_lines} lines...{RESET}\n")

    all_long_methods = []
    for py_file in root_dir.rglob("*.py"):
        if any(x in py_file.parts for x in ['__pycache__', 'migrations', 'alembic', 'venv']):
            continue

        long_methods = check_file(py_file, args.max_lines)
        all_long_methods.extend(long_methods)

    if not all_long_methods:
        print(f"{GREEN}✓ All methods/functions are ≤ {args.max_lines} lines!{RESET}")
        sys.exit(0)

    # Sort by length (longest first)
    all_long_methods.sort(key=lambda x: x[2], reverse=True)

    print(f"{RED}✗ Found {len(all_long_methods)} methods/functions exceeding {args.max_lines} lines:{RESET}\n")

    for file_path, line_num, length, name in all_long_methods:
        relative_path = Path(file_path).relative_to(Path.cwd())
        print(f"{RED}  {length:3d} lines{RESET} | {relative_path}:{line_num} | {name}")

    print(f"\n{YELLOW}Recommendation: Refactor these methods into smaller functions{RESET}")
    print(f"{YELLOW}Target: ≤ {args.max_lines} lines per method/function{RESET}")

    sys.exit(1)


if __name__ == "__main__":
    main()
