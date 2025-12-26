#!/usr/bin/env python3
"""Comprehensive codebase analysis for Python 3.13 compatibility and standardization."""

from __future__ import annotations

import os
import py_compile
import re
import ast
import sys
from pathlib import Path
from typing import Any
from collections import defaultdict

class CodebaseAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.compilation_errors = []
        self.files_without_future = []
        self.files_with_future = []
        self.import_issues = []
        self.type_hint_issues = []
        self.init_file_issues = []
        self.deprecated_patterns = []

    def analyze(self):
        """Run all analysis checks."""
        print("=" * 80)
        print("CODEBASE ANALYSIS STARTING")
        print("=" * 80)

        self.check_compilation()
        self.check_future_annotations()
        self.check_init_files()
        self.check_deprecated_patterns()
        self.generate_report()

    def check_compilation(self):
        """Check all Python files for compilation errors."""
        print("\n[1/4] Checking compilation...")
        checked = 0

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            checked += 1
            try:
                py_compile.compile(str(py_file), doraise=True)
            except py_compile.PyCompileError as e:
                self.compilation_errors.append({
                    'file': str(py_file.relative_to(self.root_dir)),
                    'error': str(e)
                })
            except SyntaxError as e:
                self.compilation_errors.append({
                    'file': str(py_file.relative_to(self.root_dir)),
                    'error': f"SyntaxError: {e.msg} at line {e.lineno}"
                })

        print(f"  Checked: {checked} files")
        print(f"  Errors: {len(self.compilation_errors)}")

    def check_future_annotations(self):
        """Check for __future__ annotations standardization."""
        print("\n[2/4] Checking __future__ annotations...")

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                if 'from __future__ import annotations' in content:
                    self.files_with_future.append(str(py_file.relative_to(self.root_dir)))
                else:
                    # Check if file has type hints that would benefit from __future__
                    if self._has_type_hints(content):
                        self.files_without_future.append(str(py_file.relative_to(self.root_dir)))
            except Exception as e:
                pass

        print(f"  With annotations: {len(self.files_with_future)}")
        print(f"  Without annotations (has type hints): {len(self.files_without_future)}")

    def _has_type_hints(self, content: str) -> bool:
        """Check if file contains type hints."""
        patterns = [
            r':\s*[A-Z]\w+\[',  # Generic types like List[
            r':\s*[A-Z]\w+\s*=',  # Type hints with defaults
            r'->\s*[A-Z]\w+',  # Return type hints
            r':\s*Optional\[',
            r':\s*Union\[',
            r':\s*Dict\[',
            r':\s*List\[',
        ]
        return any(re.search(pattern, content) for pattern in patterns)

    def check_init_files(self):
        """Check __init__.py files for proper exports."""
        print("\n[3/4] Checking __init__.py files...")

        for init_file in self.root_dir.rglob("__init__.py"):
            if "venv" in str(init_file) or ".venv" in str(init_file):
                continue

            try:
                content = init_file.read_text(encoding='utf-8')

                # Check if empty or only has docstring
                if not content.strip() or (content.strip().startswith('"""') and content.strip().count('"""') == 2):
                    parent_dir = init_file.parent
                    py_files = [f for f in parent_dir.glob("*.py") if f.name != "__init__.py"]

                    if py_files:
                        self.init_file_issues.append({
                            'file': str(init_file.relative_to(self.root_dir)),
                            'issue': f'Empty __init__.py but has {len(py_files)} modules',
                            'modules': [f.stem for f in py_files]
                        })
            except Exception as e:
                pass

        print(f"  Issues found: {len(self.init_file_issues)}")

    def check_deprecated_patterns(self):
        """Check for deprecated patterns and imports."""
        print("\n[4/4] Checking deprecated patterns...")

        deprecated_imports = [
            (r'from typing import.*\bList\b', 'Use list[] instead of List[] (Python 3.9+)'),
            (r'from typing import.*\bDict\b', 'Use dict[] instead of Dict[] (Python 3.9+)'),
            (r'from typing import.*\bSet\b', 'Use set[] instead of Set[] (Python 3.9+)'),
            (r'from typing import.*\bTuple\b', 'Use tuple[] instead of Tuple[] (Python 3.9+)'),
            (r'import collections\n.*\.Mapping', 'Use collections.abc.Mapping'),
            (r'import collections\n.*\.Sequence', 'Use collections.abc.Sequence'),
        ]

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')

                for pattern, message in deprecated_imports:
                    if re.search(pattern, content, re.MULTILINE):
                        self.deprecated_patterns.append({
                            'file': str(py_file.relative_to(self.root_dir)),
                            'pattern': message
                        })
            except Exception as e:
                pass

        print(f"  Deprecated patterns: {len(self.deprecated_patterns)}")

    def generate_report(self):
        """Generate comprehensive analysis report."""
        print("\n" + "=" * 80)
        print("ANALYSIS REPORT")
        print("=" * 80)

        # Compilation Errors
        if self.compilation_errors:
            print("\n🔴 COMPILATION ERRORS:")
            print("-" * 80)
            for i, error in enumerate(self.compilation_errors[:10], 1):
                print(f"{i}. {error['file']}")
                print(f"   Error: {error['error']}")
                print()
        else:
            print("\n✅ No compilation errors found")

        # Future Annotations
        print("\n📊 FUTURE ANNOTATIONS STATUS:")
        print("-" * 80)
        total = len(self.files_with_future) + len(self.files_without_future)
        if total > 0:
            percentage = (len(self.files_with_future) / total) * 100
            print(f"Standardization: {percentage:.1f}% ({len(self.files_with_future)}/{total})")

        if self.files_without_future:
            print(f"\nFiles needing __future__ annotations (first 30):")
            for f in self.files_without_future[:30]:
                print(f"  - {f}")

        # Init File Issues
        if self.init_file_issues:
            print("\n⚠️  __INIT__ FILE ISSUES:")
            print("-" * 80)
            for issue in self.init_file_issues[:15]:
                print(f"  {issue['file']}")
                print(f"    Issue: {issue['issue']}")
                print(f"    Modules: {', '.join(issue['modules'][:5])}")
                print()

        # Deprecated Patterns
        if self.deprecated_patterns:
            print("\n⚠️  DEPRECATED PATTERNS:")
            print("-" * 80)
            pattern_counts = defaultdict(list)
            for item in self.deprecated_patterns:
                pattern_counts[item['pattern']].append(item['file'])

            for pattern, files in pattern_counts.items():
                print(f"\n  {pattern}")
                print(f"  Found in {len(files)} files:")
                for f in files[:5]:
                    print(f"    - {f}")

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)

        # Return summary for memory storage
        return {
            'compilation_errors': len(self.compilation_errors),
            'files_without_future': len(self.files_without_future),
            'init_file_issues': len(self.init_file_issues),
            'deprecated_patterns': len(self.deprecated_patterns),
            'total_files': len(self.files_with_future) + len(self.files_without_future)
        }

if __name__ == "__main__":
    analyzer = CodebaseAnalyzer("app")
    analyzer.analyze()
