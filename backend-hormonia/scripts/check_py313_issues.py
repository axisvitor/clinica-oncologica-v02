#!/usr/bin/env python3
"""Check for Python 3.13 specific compatibility issues."""

from __future__ import annotations

import re
from pathlib import Path

class Py313Checker:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.issues = []

    def check(self):
        """Check for Python 3.13 compatibility issues."""
        print("=" * 80)
        print("PYTHON 3.13 COMPATIBILITY CHECK")
        print("=" * 80)

        self.check_string_annotations()
        self.check_union_syntax()
        self.check_optional_syntax()
        self.check_final_usage()
        self.generate_report()

    def check_string_annotations(self):
        """Check for string annotations that should use proper types."""
        print("\n[1/4] Checking string annotations...")
        count = 0

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')

                # Look for string annotations like: def foo() -> "ReturnType":
                pattern = r':\s*["\']([A-Z]\w+)["\']'
                matches = re.finditer(pattern, content)

                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    count += 1
                    if count <= 10:  # Only report first 10
                        self.issues.append({
                            'file': str(py_file.relative_to(self.root_dir)),
                            'line': line_num,
                            'issue': f'String annotation "{match.group(1)}" should use actual type',
                            'category': 'string_annotations'
                        })
            except Exception:
                pass

        print(f"  String annotations found: {count}")

    def check_union_syntax(self):
        """Check for old Union syntax vs new | syntax."""
        print("\n[2/4] Checking Union syntax...")
        count = 0

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')

                # Check if using Union[] instead of |
                if re.search(r'Union\[', content):
                    has_future = 'from __future__ import annotations' in content

                    if not has_future:
                        count += 1
                        if count <= 15:
                            self.issues.append({
                                'file': str(py_file.relative_to(self.root_dir)),
                                'issue': 'Uses Union[] without __future__ annotations',
                                'category': 'union_syntax'
                            })
            except Exception:
                pass

        print(f"  Files with Union[] issues: {count}")

    def check_optional_syntax(self):
        """Check for Optional vs | None syntax."""
        print("\n[3/4] Checking Optional syntax...")
        count = 0

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')

                # Check if using Optional[] instead of | None
                if re.search(r'Optional\[', content):
                    has_future = 'from __future__ import annotations' in content

                    if not has_future:
                        count += 1
                        if count <= 15:
                            self.issues.append({
                                'file': str(py_file.relative_to(self.root_dir)),
                                'issue': 'Uses Optional[] without __future__ annotations',
                                'category': 'optional_syntax'
                            })
            except Exception:
                pass

        print(f"  Files with Optional[] issues: {count}")

    def check_final_usage(self):
        """Check for @final decorator usage."""
        print("\n[4/4] Checking @final usage...")
        count = 0

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')

                # Check if using @final
                if '@final' in content or 'Final[' in content:
                    count += 1
            except Exception:
                pass

        print(f"  Files using @final: {count}")

    def generate_report(self):
        """Generate report of issues."""
        print("\n" + "=" * 80)
        print("PYTHON 3.13 COMPATIBILITY REPORT")
        print("=" * 80)

        if self.issues:
            categories = {}
            for issue in self.issues:
                cat = issue['category']
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(issue)

            for category, items in categories.items():
                print(f"\n⚠️  {category.upper().replace('_', ' ')}:")
                print("-" * 80)
                for item in items[:10]:
                    print(f"  File: {item['file']}")
                    if 'line' in item:
                        print(f"  Line: {item['line']}")
                    print(f"  Issue: {item['issue']}")
                    print()
        else:
            print("\n✅ No major Python 3.13 compatibility issues found")

        print("=" * 80)

if __name__ == "__main__":
    checker = Py313Checker("app")
    checker.check()
