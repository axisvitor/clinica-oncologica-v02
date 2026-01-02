#!/usr/bin/env python3
"""
Import and Dependency Validator
Scans all Python files for import issues, circular dependencies, and missing packages.
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict


class ImportValidator:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.app_dir = self.root_dir / "app"
        self.all_imports = defaultdict(list)
        self.import_errors = []
        self.circular_deps = []
        self.unused_imports = []
        self.missing_deps = set()
        self.module_graph = defaultdict(set)

    def scan_file(self, filepath: Path) -> Dict:
        """Scan a single Python file for imports."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(filepath))

            imports = {
                'regular': [],  # import x
                'from': [],     # from x import y
                'relative': [], # from .x import y
                'type_checking': []  # imports inside TYPE_CHECKING
            }

            in_type_checking = False

            for node in ast.walk(tree):
                # Check for TYPE_CHECKING block
                if isinstance(node, ast.If):
                    if hasattr(node.test, 'id') and node.test.id == 'TYPE_CHECKING':
                        in_type_checking = True
                        for item in node.body:
                            if isinstance(item, (ast.Import, ast.ImportFrom)):
                                self._extract_import(item, imports, is_type_checking=True)
                        in_type_checking = False
                        continue

                if not in_type_checking:
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports['regular'].append({
                                'module': alias.name,
                                'asname': alias.asname,
                                'line': node.lineno
                            })

                    elif isinstance(node, ast.ImportFrom):
                        level = node.level if node.level else 0
                        module = node.module if node.module else ''

                        import_type = 'relative' if level > 0 else 'from'

                        for alias in node.names:
                            imports[import_type].append({
                                'module': module,
                                'name': alias.name,
                                'asname': alias.asname,
                                'level': level,
                                'line': node.lineno
                            })

            return {
                'filepath': filepath,
                'imports': imports,
                'errors': []
            }

        except SyntaxError as e:
            return {
                'filepath': filepath,
                'imports': None,
                'errors': [f"Syntax error: {e}"]
            }
        except Exception as e:
            return {
                'filepath': filepath,
                'imports': None,
                'errors': [f"Parse error: {e}"]
            }

    def _extract_import(self, node, imports, is_type_checking=False):
        """Helper to extract import information."""
        target = 'type_checking' if is_type_checking else 'from'

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports['regular' if not is_type_checking else 'type_checking'].append({
                    'module': alias.name,
                    'asname': alias.asname,
                    'line': node.lineno
                })

        elif isinstance(node, ast.ImportFrom):
            level = node.level if node.level else 0
            module = node.module if node.module else ''

            for alias in node.names:
                imports[target].append({
                    'module': module,
                    'name': alias.name,
                    'asname': alias.asname,
                    'level': level,
                    'line': node.lineno
                })

    def build_module_graph(self, scan_results: List[Dict]):
        """Build dependency graph for circular dependency detection."""
        for result in scan_results:
            if result['imports'] is None:
                continue

            filepath = result['filepath']
            module_name = self._filepath_to_module(filepath)

            imports = result['imports']

            # Add all imported modules to graph
            for imp in imports['regular']:
                self.module_graph[module_name].add(imp['module'])

            for imp in imports['from']:
                if imp['module']:
                    self.module_graph[module_name].add(imp['module'])

            for imp in imports['relative']:
                resolved = self._resolve_relative_import(module_name, imp)
                if resolved:
                    self.module_graph[module_name].add(resolved)

    def _filepath_to_module(self, filepath: Path) -> str:
        """Convert filepath to Python module name."""
        try:
            rel_path = filepath.relative_to(self.app_dir)
            parts = list(rel_path.parts)
            if parts[-1] == '__init__.py':
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1].replace('.py', '')
            return '.'.join(['app'] + parts)
        except:
            return str(filepath)

    def _resolve_relative_import(self, current_module: str, import_info: Dict) -> str:
        """Resolve relative import to absolute module name."""
        parts = current_module.split('.')
        level = import_info['level']

        # Go up 'level' directories
        base_parts = parts[:-(level-1)] if level > 1 else parts

        if import_info['module']:
            return '.'.join(base_parts[:-1] + [import_info['module']])
        else:
            return '.'.join(base_parts[:-1])

    def detect_circular_dependencies(self):
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node, path):
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.module_graph.get(node, []):
                dfs(neighbor, path.copy())

            rec_stack.remove(node)

        for node in self.module_graph:
            if node not in visited:
                dfs(node, [])

        self.circular_deps = cycles
        return cycles

    def check_external_dependencies(self, scan_results: List[Dict]) -> Set[str]:
        """Check which external packages are imported."""
        external_imports = set()

        for result in scan_results:
            if result['imports'] is None:
                continue

            imports = result['imports']

            for imp in imports['regular']:
                module = imp['module'].split('.')[0]
                if not module.startswith('app'):
                    external_imports.add(module)

            for imp in imports['from']:
                module = imp['module'].split('.')[0] if imp['module'] else ''
                if module and not module.startswith('app'):
                    external_imports.add(module)

        return external_imports

    def validate_dependencies(self, external_imports: Set[str], requirements_file: Path):
        """Check if all external imports are in requirements.txt."""
        try:
            with open(requirements_file, 'r') as f:
                lines = f.readlines()

            installed_packages = set()
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name (before >=, ==, <, etc.)
                    pkg = line.split('[')[0]  # Remove extras
                    for sep in ['>=', '==', '<=', '<', '>', '~=']:
                        if sep in pkg:
                            pkg = pkg.split(sep)[0]
                            break
                    installed_packages.add(pkg.strip().lower())

            # Common stdlib modules (not in requirements.txt)
            stdlib_modules = {
                'os', 'sys', 'logging', 'typing', 'datetime', 'json', 'uuid',
                'collections', 'functools', 'itertools', 'pathlib', 'dataclasses',
                'enum', 'abc', 'asyncio', 'time', 're', 'io', 'warnings',
                'contextlib', 'copy', 'pickle', 'hashlib', 'secrets', 'string',
                'math', 'random', 'traceback', '__future__'
            }

            # Package name mappings (import name -> package name)
            package_mappings = {
                'pydantic_settings': 'pydantic-settings',
                'jose': 'python-jose',
                'dotenv': 'python-dotenv',
                'google.generativeai': 'google-generativeai',
                'google.ai': 'google-ai-generativelanguage',
                'PIL': 'pillow',
                'reportlab': 'reportlab',
                'httpx': 'httpx',
                'aiohttp': 'aiohttp',
                'magic': 'python-magic',
                'PyPDF2': 'pypdf2',
            }

            missing = set()
            for imp in external_imports:
                if imp in stdlib_modules:
                    continue

                # Check direct match or mapping
                pkg_name = package_mappings.get(imp, imp).lower()

                if pkg_name not in installed_packages:
                    # Check if it's a sub-package of an installed package
                    found = False
                    for installed in installed_packages:
                        if pkg_name.startswith(installed + '.') or installed.startswith(pkg_name):
                            found = True
                            break
                    if not found:
                        missing.add(imp)

            self.missing_deps = missing
            return missing

        except FileNotFoundError:
            self.import_errors.append(f"Requirements file not found: {requirements_file}")
            return set()

    def scan_all(self):
        """Scan all Python files in the app directory."""
        py_files = list(self.app_dir.rglob("*.py"))

        print(f"Scanning {len(py_files)} Python files...")

        results = []
        for py_file in py_files:
            result = self.scan_file(py_file)
            results.append(result)

            if result['errors']:
                self.import_errors.extend([
                    f"{py_file}: {err}" for err in result['errors']
                ])

        return results

    def generate_report(self):
        """Generate comprehensive validation report."""
        print("\n" + "="*80)
        print("IMPORT AND DEPENDENCY VALIDATION REPORT")
        print("="*80)

        # Scan all files
        scan_results = self.scan_all()

        # Build module graph
        self.build_module_graph(scan_results)

        # Detect circular dependencies
        print("\n[1] CIRCULAR DEPENDENCIES")
        print("-" * 80)
        cycles = self.detect_circular_dependencies()
        if cycles:
            print(f"❌ Found {len(cycles)} circular dependency cycles:")
            for i, cycle in enumerate(cycles, 1):
                print(f"  Cycle {i}: {' -> '.join(cycle)}")
        else:
            print("✅ No circular dependencies detected")

        # Check external dependencies
        print("\n[2] EXTERNAL PACKAGE IMPORTS")
        print("-" * 80)
        external_imports = self.check_external_dependencies(scan_results)
        print(f"Found {len(external_imports)} unique external packages:")
        for pkg in sorted(external_imports):
            print(f"  - {pkg}")

        # Validate against requirements.txt
        print("\n[3] MISSING DEPENDENCIES")
        print("-" * 80)
        requirements_file = self.root_dir / "requirements.txt"
        missing = self.validate_dependencies(external_imports, requirements_file)
        if missing:
            print(f"❌ Found {len(missing)} missing packages in requirements.txt:")
            for pkg in sorted(missing):
                print(f"  - {pkg}")
        else:
            print("✅ All external packages are in requirements.txt")

        # Import errors
        print("\n[4] IMPORT/PARSE ERRORS")
        print("-" * 80)
        if self.import_errors:
            print(f"❌ Found {len(self.import_errors)} errors:")
            for err in self.import_errors:
                print(f"  {err}")
        else:
            print("✅ No import or parse errors")

        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total files scanned: {len(scan_results)}")
        print(f"Circular dependencies: {len(cycles)}")
        print(f"External packages: {len(external_imports)}")
        print(f"Missing dependencies: {len(missing)}")
        print(f"Import errors: {len(self.import_errors)}")

        # Return status
        has_issues = bool(cycles or missing or self.import_errors)
        if has_issues:
            print("\n❌ VALIDATION FAILED - Issues detected")
            return 1
        else:
            print("\n✅ VALIDATION PASSED - No issues detected")
            return 0


if __name__ == "__main__":
    # Get the backend-hormonia directory
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent.parent

    validator = ImportValidator(str(backend_dir))
    exit_code = validator.generate_report()
    sys.exit(exit_code)
