#!/usr/bin/env python3
"""
Check naming conventions - LOW-008
Validates that all names follow PEP 8 conventions:
- Functions/variables: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE
Usage: python scripts/check_naming_conventions.py
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Naming patterns
SNAKE_CASE = re.compile(r'^[a-z_][a-z0-9_]*$')
PASCAL_CASE = re.compile(r'^[A-Z][a-zA-Z0-9]*$')
UPPER_SNAKE_CASE = re.compile(r'^[A-Z_][A-Z0-9_]*$')
CAMEL_CASE = re.compile(r'^[a-z][a-zA-Z0-9]*$')

# Exceptions
ALLOWED_NAMES = {
    # Common exceptions
    'setUp', 'tearDown', 'setUpClass', 'tearDownClass',
    # Single letters for iterators
    'i', 'j', 'k', 'x', 'y', 'z', 'f', 'e',
    # Django/Flask conventions
    'pk', 'id', 'db',
    # Pydantic/FastAPI
    'orm_mode', 'env_file',
}


class NamingChecker(ast.NodeVisitor):
    """AST visitor to check naming conventions."""

    def __init__(self):
        self.violations: List[Tuple[str, int, str, str, str]] = []
        self.current_file = ""
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Check class names (should be PascalCase)."""
        if not PASCAL_CASE.match(node.name):
            if SNAKE_CASE.match(node.name):
                self.violations.append((
                    self.current_file,
                    node.lineno,
                    "class",
                    node.name,
                    f"Should be PascalCase (e.g., {self._to_pascal_case(node.name)})"
                ))
            elif CAMEL_CASE.match(node.name):
                self.violations.append((
                    self.current_file,
                    node.lineno,
                    "class",
                    node.name,
                    f"Should be PascalCase (capitalize first letter)"
                ))

        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check function names (should be snake_case)."""
        # Skip magic methods
        if node.name.startswith('__') and node.name.endswith('__'):
            self.generic_visit(node)
            return

        # Skip allowed names
        if node.name in ALLOWED_NAMES:
            self.generic_visit(node)
            return

        if not SNAKE_CASE.match(node.name):
            if CAMEL_CASE.match(node.name):
                self.violations.append((
                    self.current_file,
                    node.lineno,
                    "function",
                    node.name,
                    f"Should be snake_case (e.g., {self._to_snake_case(node.name)})"
                ))
            elif PASCAL_CASE.match(node.name):
                self.violations.append((
                    self.current_file,
                    node.lineno,
                    "function",
                    node.name,
                    f"Should be snake_case (e.g., {self._to_snake_case(node.name)})"
                ))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """Check variable/constant names."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_variable_name(target.name, node.lineno)
        self.generic_visit(node)

    def _check_variable_name(self, name: str, lineno: int):
        """Check if variable follows naming conventions."""
        # Skip private/protected names
        if name.startswith('_'):
            return

        # Skip allowed names
        if name in ALLOWED_NAMES:
            return

        # Check if it's a constant (all uppercase)
        if UPPER_SNAKE_CASE.match(name):
            return

        # Check if it's a variable (snake_case)
        if not SNAKE_CASE.match(name):
            if CAMEL_CASE.match(name) or PASCAL_CASE.match(name):
                self.violations.append((
                    self.current_file,
                    lineno,
                    "variable",
                    name,
                    f"Should be snake_case (e.g., {self._to_snake_case(name)})"
                ))

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert name to snake_case."""
        # Insert underscore before uppercase letters
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    @staticmethod
    def _to_pascal_case(name: str) -> str:
        """Convert name to PascalCase."""
        return ''.join(word.capitalize() for word in name.split('_'))


def check_file(file_path: Path) -> List[Tuple[str, int, str, str, str]]:
    """Check a single Python file for naming violations."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        checker = NamingChecker()
        checker.current_file = str(file_path)
        checker.visit(tree)
        return checker.violations

    except SyntaxError as e:
        print(f"{RED}Syntax error in {file_path}: {e}{RESET}")
        return []
    except Exception as e:
        print(f"{RED}Error processing {file_path}: {e}{RESET}")
        return []


def main():
    """Main execution."""
    root_dir = Path.cwd() / "app"
    if not root_dir.exists():
        print(f"{RED}Error: app/ directory not found{RESET}")
        sys.exit(1)

    print(f"{BLUE}Checking naming conventions (PEP 8)...{RESET}\n")

    all_violations = []
    for py_file in root_dir.rglob("*.py"):
        if any(x in py_file.parts for x in ['__pycache__', 'migrations', 'alembic', 'venv']):
            continue

        violations = check_file(py_file)
        all_violations.extend(violations)

    if not all_violations:
        print(f"{GREEN}✓ All naming conventions follow PEP 8!{RESET}")
        sys.exit(0)

    # Group by type
    by_type = {}
    for file_path, line_num, violation_type, name, suggestion in all_violations:
        if violation_type not in by_type:
            by_type[violation_type] = []
        by_type[violation_type].append((file_path, line_num, name, suggestion))

    print(f"{RED}✗ Found {len(all_violations)} naming convention violations:{RESET}\n")

    for violation_type, violations in sorted(by_type.items()):
        print(f"\n{YELLOW}  {violation_type.upper()} NAMES ({len(violations)}):{RESET}")
        for file_path, line_num, name, suggestion in violations[:10]:  # Show first 10
            relative_path = Path(file_path).relative_to(Path.cwd())
            print(f"    {relative_path}:{line_num} | {name}")
            print(f"      → {suggestion}")

        if len(violations) > 10:
            print(f"    ... and {len(violations) - 10} more")

    print(f"\n{YELLOW}Naming Convention Rules (PEP 8):{RESET}")
    print(f"  • Functions/variables: {GREEN}snake_case{RESET}")
    print(f"  • Classes: {GREEN}PascalCase{RESET}")
    print(f"  • Constants: {GREEN}UPPER_SNAKE_CASE{RESET}")
    print(f"\n{BLUE}See: docs/code-quality/CODE_STYLE_GUIDE.md{RESET}")

    sys.exit(1)


if __name__ == "__main__":
    main()
