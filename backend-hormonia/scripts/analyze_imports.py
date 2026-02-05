#!/usr/bin/env python3
"""Analyze import patterns and circular dependencies."""

from __future__ import annotations

import ast
from pathlib import Path
from collections import defaultdict

class ImportAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.imports = defaultdict(set)
        self.circular_deps = []
        self.missing_imports = []
        self.duplicate_imports = []

    def analyze(self):
        """Run import analysis."""
        print("=" * 80)
        print("IMPORT ANALYSIS")
        print("=" * 80)

        self.collect_imports()
        self.check_circular_dependencies()
        self.check_duplicate_imports()
        self.generate_report()

    def collect_imports(self):
        """Collect all imports from Python files."""
        print("\n[1/3] Collecting imports...")

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                tree = ast.parse(content)

                file_imports = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            file_imports.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            file_imports.add(node.module)

                rel_path = str(py_file.relative_to(self.root_dir))
                self.imports[rel_path] = file_imports
            except Exception:
                pass

        print(f"  Analyzed {len(self.imports)} files")

    def check_circular_dependencies(self):
        """Check for circular dependencies."""
        print("\n[2/3] Checking circular dependencies...")

        # Build dependency graph
        dep_graph = defaultdict(set)

        for file_path, imports in self.imports.items():
            module_name = file_path.replace('/', '.').replace('.py', '')

            for imp in imports:
                if imp.startswith('app.'):
                    dep_graph[module_name].add(imp)

        # Simple circular dependency detection
        visited = set()
        rec_stack = set()

        def has_cycle(node, path):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in dep_graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, path + [neighbor]):
                        return True
                elif neighbor in rec_stack:
                    cycle_path = path + [neighbor]
                    self.circular_deps.append(cycle_path)
                    return True

            rec_stack.remove(node)
            return False

        for node in list(dep_graph.keys())[:50]:  # Check first 50 modules
            if node not in visited:
                has_cycle(node, [node])

        print(f"  Potential circular dependencies: {len(self.circular_deps)}")

    def check_duplicate_imports(self):
        """Check for duplicate imports in files."""
        print("\n[3/3] Checking duplicate imports...")

        for py_file in self.root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                lines = content.split('\n')

                import_lines = []
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith('import ') or stripped.startswith('from '):
                        import_lines.append((i + 1, stripped))

                # Check for duplicates
                seen = {}
                for line_num, import_stmt in import_lines:
                    if import_stmt in seen:
                        self.duplicate_imports.append({
                            'file': str(py_file.relative_to(self.root_dir)),
                            'line': line_num,
                            'previous_line': seen[import_stmt],
                            'import': import_stmt
                        })
                    else:
                        seen[import_stmt] = line_num
            except Exception:
                pass

        print(f"  Duplicate imports found: {len(self.duplicate_imports)}")

    def generate_report(self):
        """Generate import analysis report."""
        print("\n" + "=" * 80)
        print("IMPORT ANALYSIS REPORT")
        print("=" * 80)

        # Circular dependencies
        if self.circular_deps:
            print("\n⚠️  POTENTIAL CIRCULAR DEPENDENCIES:")
            print("-" * 80)
            for i, cycle in enumerate(self.circular_deps[:5], 1):
                print(f"{i}. Cycle: {' -> '.join(cycle[:4])}")
        else:
            print("\n✅ No obvious circular dependencies found")

        # Duplicate imports
        if self.duplicate_imports:
            print("\n⚠️  DUPLICATE IMPORTS:")
            print("-" * 80)
            for i, dup in enumerate(self.duplicate_imports[:10], 1):
                print(f"{i}. {dup['file']}")
                print(f"   Line {dup['line']}: {dup['import']}")
                print(f"   (Previously at line {dup['previous_line']})")
                print()
        else:
            print("\n✅ No duplicate imports found")

        # Most common imports
        print("\n📊 MOST COMMON IMPORTS:")
        print("-" * 80)
        all_imports = defaultdict(int)
        for imports in self.imports.values():
            for imp in imports:
                all_imports[imp] += 1

        sorted_imports = sorted(all_imports.items(), key=lambda x: x[1], reverse=True)
        for imp, count in sorted_imports[:15]:
            print(f"  {imp}: {count} files")

        print("\n" + "=" * 80)

if __name__ == "__main__":
    analyzer = ImportAnalyzer("app")
    analyzer.analyze()
