#!/usr/bin/env python3
"""
Check type hint coverage - LOW-012
Calculates percentage of functions with type hints
Target: 95% coverage
Usage: python scripts/check_type_coverage.py [--min-coverage 95]
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
BLUE = '\033[94m'
RESET = '\033[0m'


class TypeHintChecker(ast.NodeVisitor):
    """AST visitor to check type hint coverage."""

    def __init__(self):
        self.total_functions = 0
        self.typed_functions = 0
        self.untyped_functions: List[Tuple[str, int, str]] = []
        self.current_file = ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check function type hints."""
        # Skip magic methods and private methods
        if node.name.startswith('__'):
            self.generic_visit(node)
            return

        self.total_functions += 1

        # Check if has type hints
        has_param_hints = self._has_parameter_hints(node)
        has_return_hint = node.returns is not None

        if has_param_hints and has_return_hint:
            self.typed_functions += 1
        else:
            missing = []
            if not has_param_hints:
                missing.append("parameters")
            if not has_return_hint:
                missing.append("return type")

            self.untyped_functions.append((
                self.current_file,
                node.lineno,
                f"{node.name} (missing: {', '.join(missing)})"
            ))

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Check async function type hints."""
        # Same logic as regular functions
        self.visit_FunctionDef(node)

    def _has_parameter_hints(self, node) -> bool:
        """Check if function parameters have type hints."""
        # Skip 'self' and 'cls' parameters
        params = [arg for arg in node.args.args if arg.arg not in ('self', 'cls')]

        if not params:
            return True  # No parameters to type

        # Check if all parameters have annotations
        return all(arg.annotation is not None for arg in params)


def check_file(file_path: Path) -> Tuple[int, int, List[Tuple[str, int, str]]]:
    """
    Check type hint coverage in a single file.
    Returns: (total_functions, typed_functions, untyped_list)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        checker = TypeHintChecker()
        checker.current_file = str(file_path)
        checker.visit(tree)
        return checker.total_functions, checker.typed_functions, checker.untyped_functions

    except SyntaxError as e:
        print(f"{RED}Syntax error in {file_path}: {e}{RESET}")
        return 0, 0, []
    except Exception as e:
        print(f"{RED}Error processing {file_path}: {e}{RESET}")
        return 0, 0, []


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description='Check type hint coverage')
    parser.add_argument('--min-coverage', type=float, default=95.0,
                        help='Minimum required coverage percentage (default: 95.0)')
    args = parser.parse_args()

    root_dir = Path.cwd() / "app"
    if not root_dir.exists():
        print(f"{RED}Error: app/ directory not found{RESET}")
        sys.exit(1)

    print(f"{BLUE}Checking type hint coverage...{RESET}\n")

    total_functions = 0
    typed_functions = 0
    all_untyped = []

    for py_file in root_dir.rglob("*.py"):
        if any(x in py_file.parts for x in ['__pycache__', 'migrations', 'alembic', 'venv', 'tests']):
            continue

        file_total, file_typed, file_untyped = check_file(py_file)
        total_functions += file_total
        typed_functions += file_typed
        all_untyped.extend(file_untyped)

    if total_functions == 0:
        print(f"{YELLOW}No functions found to check{RESET}")
        sys.exit(0)

    coverage = (typed_functions / total_functions) * 100

    print(f"{BLUE}Type Hint Coverage Report:{RESET}")
    print(f"  Total functions: {total_functions}")
    print(f"  Typed functions: {typed_functions}")
    print(f"  Untyped functions: {len(all_untyped)}")
    print(f"  Coverage: {coverage:.1f}%")

    if coverage >= args.min_coverage:
        print(f"\n{GREEN}✓ Type hint coverage {coverage:.1f}% >= {args.min_coverage}%{RESET}")

        if all_untyped:
            print(f"\n{YELLOW}Remaining untyped functions:{RESET}")
            for file_path, line_num, name in all_untyped[:5]:
                relative_path = Path(file_path).relative_to(Path.cwd())
                print(f"  {relative_path}:{line_num} | {name}")
            if len(all_untyped) > 5:
                print(f"  ... and {len(all_untyped) - 5} more")

        sys.exit(0)
    else:
        print(f"\n{RED}✗ Type hint coverage {coverage:.1f}% < {args.min_coverage}%{RESET}")
        print(f"\n{YELLOW}Untyped functions (showing first 20):{RESET}")

        for file_path, line_num, name in all_untyped[:20]:
            relative_path = Path(file_path).relative_to(Path.cwd())
            print(f"  {relative_path}:{line_num} | {name}")

        if len(all_untyped) > 20:
            print(f"  ... and {len(all_untyped) - 20} more")

        print(f"\n{BLUE}Add type hints following CODE_STYLE_GUIDE.md{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
