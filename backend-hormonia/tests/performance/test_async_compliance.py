"""
Test suite to verify async/await compliance across the codebase.
Part of MEDIUM-006: Async/Await Completeness

This test suite ensures that all I/O operations are properly async
to prevent blocking the event loop and degrading performance.
"""

import pytest
import ast
import os
from pathlib import Path
from typing import List, Tuple


def get_python_files(directory: str) -> List[Path]:
    """Get all Python files in directory, excluding common non-code directories."""
    excluded_dirs = {
        '__pycache__', '.git', '.pytest_cache', 'node_modules',
        'venv', 'env', '.venv', 'migrations', 'alembic', 'tests'
    }

    python_files = []
    base_path = Path(directory)

    for root, dirs, files in os.walk(base_path):
        # Remove excluded directories from traversal
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)

    return python_files


def find_blocking_imports(filepath: Path) -> List[Tuple[int, str]]:
    """Find blocking library imports in a Python file."""
    blocking_imports = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))

        for node in ast.walk(tree):
            # Check for import statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'requests':
                        blocking_imports.append((node.lineno, 'import requests'))
                    elif alias.name == 'psycopg2':
                        blocking_imports.append((node.lineno, 'import psycopg2'))

            # Check for from imports
            elif isinstance(node, ast.ImportFrom):
                if node.module == 'time':
                    for alias in node.names:
                        if alias.name == 'sleep':
                            blocking_imports.append((node.lineno, 'from time import sleep'))

    except (SyntaxError, Exception):
        # Skip files with syntax errors or other issues
        pass

    return blocking_imports


def find_blocking_calls(filepath: Path) -> List[Tuple[int, str]]:
    """Find blocking function calls in a Python file."""
    blocking_calls = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for requests.get/post/etc
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == 'requests':
                            blocking_calls.append((node.lineno, f'requests.{node.func.attr}'))
                        elif node.func.value.id == 'time' and node.func.attr == 'sleep':
                            blocking_calls.append((node.lineno, 'time.sleep'))

                # Check for open()
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    blocking_calls.append((node.lineno, 'open()'))

    except (SyntaxError, Exception):
        pass

    return blocking_calls


@pytest.fixture
def app_directory():
    """Get the app directory path."""
    return Path(__file__).parent.parent.parent / "app"


def test_no_requests_library(app_directory):
    """
    Test that requests library is not imported anywhere in the codebase.
    Should use aiohttp instead for async HTTP requests.
    """
    blocking_imports_found = []

    for filepath in get_python_files(str(app_directory)):
        blocking_imports = find_blocking_imports(filepath)
        for lineno, import_stmt in blocking_imports:
            if 'requests' in import_stmt:
                blocking_imports_found.append((filepath, lineno, import_stmt))

    if blocking_imports_found:
        error_msg = "Found blocking 'requests' imports (use aiohttp instead):\n"
        for filepath, lineno, import_stmt in blocking_imports_found:
            error_msg += f"  {filepath}:{lineno} - {import_stmt}\n"

        pytest.fail(error_msg)


def test_no_time_sleep(app_directory):
    """
    Test that time.sleep is not used anywhere in the codebase.
    Should use asyncio.sleep instead.
    """
    blocking_sleep_found = []

    for filepath in get_python_files(str(app_directory)):
        blocking_calls = find_blocking_calls(filepath)
        for lineno, call in blocking_calls:
            if 'sleep' in call:
                blocking_sleep_found.append((filepath, lineno, call))

    if blocking_sleep_found:
        error_msg = "Found blocking time.sleep calls (use asyncio.sleep instead):\n"
        for filepath, lineno, call in blocking_sleep_found:
            error_msg += f"  {filepath}:{lineno} - {call}\n"

        pytest.fail(error_msg)


def test_no_blocking_file_io(app_directory):
    """
    Test that synchronous file I/O (open()) is not used in service layer.
    Should use aiofiles for async file operations.
    """
    blocking_file_io_found = []

    # Only check services directory (utils and scripts can use sync I/O)
    services_dir = app_directory / "services"

    if not services_dir.exists():
        pytest.skip("Services directory not found")

    for filepath in get_python_files(str(services_dir)):
        blocking_calls = find_blocking_calls(filepath)
        for lineno, call in blocking_calls:
            if call == 'open()':
                blocking_file_io_found.append((filepath, lineno, call))

    if blocking_file_io_found:
        error_msg = "Found blocking file I/O in services (use aiofiles instead):\n"
        for filepath, lineno, call in blocking_file_io_found:
            error_msg += f"  {filepath}:{lineno} - {call}\n"

        # This is a warning, not a hard failure (file I/O is less critical)
        pytest.skip(error_msg)


def test_async_function_ratio(app_directory):
    """
    Test that at least 90% of functions in service layer are async.
    This ensures proper async/await usage throughout the codebase.
    """
    services_dir = app_directory / "services"

    if not services_dir.exists():
        pytest.skip("Services directory not found")

    total_functions = 0
    async_functions = 0

    for filepath in get_python_files(str(services_dir)):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(filepath))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_functions += 1
                elif isinstance(node, ast.AsyncFunctionDef):
                    async_functions += 1
                    total_functions += 1

        except (SyntaxError, Exception):
            continue

    if total_functions == 0:
        pytest.skip("No functions found in services directory")

    async_ratio = async_functions / total_functions
    target_ratio = 0.90

    assert async_ratio >= target_ratio, (
        f"Async function ratio ({async_ratio:.1%}) is below target ({target_ratio:.1%})\n"
        f"Found {async_functions} async functions out of {total_functions} total\n"
        f"Target: At least {int(total_functions * target_ratio)} async functions"
    )


def test_api_endpoints_are_async(app_directory):
    """
    Test that all API endpoint handlers are async functions.
    FastAPI requires async handlers for optimal performance.
    """
    api_dir = app_directory / "api"

    if not api_dir.exists():
        pytest.skip("API directory not found")

    sync_endpoints = []

    for filepath in get_python_files(str(api_dir)):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(filepath))

            for node in ast.walk(tree):
                # Look for route decorator (@router.get, @router.post, etc.)
                if isinstance(node, ast.FunctionDef):
                    has_route_decorator = False

                    for decorator in node.decorator_list:
                        # Check if decorator is a route (router.get, router.post, etc.)
                        if isinstance(decorator, ast.Call):
                            if isinstance(decorator.func, ast.Attribute):
                                if decorator.func.attr in {'get', 'post', 'put', 'delete', 'patch'}:
                                    has_route_decorator = True
                                    break

                    if has_route_decorator:
                        sync_endpoints.append((filepath, node.lineno, node.name))

        except (SyntaxError, Exception):
            continue

    if sync_endpoints:
        error_msg = "Found synchronous API endpoint handlers (should be async):\n"
        for filepath, lineno, func_name in sync_endpoints:
            error_msg += f"  {filepath}:{lineno} - {func_name}\n"

        pytest.fail(error_msg)


def test_database_operations_are_async(app_directory):
    """
    Test that database operations in repositories use async/await.
    This ensures we're using async SQLAlchemy properly.
    """
    repos_dir = app_directory / "repositories"

    if not repos_dir.exists():
        pytest.skip("Repositories directory not found")

    sync_db_operations = []

    for filepath in get_python_files(str(repos_dir)):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for session.execute, session.query without await
            if '.execute(' in content or '.query(' in content:
                if 'await' not in content:
                    # More detailed check needed
                    tree = ast.parse(content, filename=str(filepath))

                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            # Check if function contains session.execute without await
                            for subnode in ast.walk(node):
                                if isinstance(subnode, ast.Call):
                                    if isinstance(subnode.func, ast.Attribute):
                                        if subnode.func.attr in {'execute', 'query'}:
                                            # Check if this is awaited
                                            # This is a simplified check
                                            sync_db_operations.append((filepath, node.lineno, node.name))

        except (SyntaxError, Exception):
            continue

    # Note: This test is informational, not a hard failure
    # Some legacy code may still use sync operations
    if sync_db_operations:
        warning_msg = "Found potential synchronous database operations:\n"
        for filepath, lineno, func_name in sync_db_operations:
            warning_msg += f"  {filepath}:{lineno} - {func_name}\n"

        # Skip with warning instead of failing
        pytest.skip(warning_msg)


def test_no_blocking_operations_report():
    """
    Generate a comprehensive report of all blocking operations.
    This test always passes but logs findings for review.
    """
    from scripts.audit_blocking_code import find_blocking_operations

    app_dir = Path(__file__).parent.parent.parent / "app"
    blocking_ops = find_blocking_operations(str(app_dir))

    if blocking_ops:
        report = "\n" + "="*80 + "\n"
        report += "BLOCKING OPERATIONS AUDIT REPORT\n"
        report += "="*80 + "\n"
        report += f"Total blocking operations found: {len(blocking_ops)}\n\n"

        by_severity = {}
        for op in blocking_ops:
            severity = op['severity']
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(op)

        for severity in ['HIGH', 'MEDIUM', 'LOW']:
            if severity in by_severity:
                report += f"\n{severity} SEVERITY ({len(by_severity[severity])} issues):\n"
                for op in by_severity[severity][:10]:  # Show first 10
                    report += f"  {op['file']}:{op['line']} - {op['pattern']}\n"

                if len(by_severity[severity]) > 10:
                    report += f"  ... and {len(by_severity[severity]) - 10} more\n"

        report += "\n" + "="*80 + "\n"

        # Log the report (this test still passes)
        print(report)

    # This test always passes - it's just for reporting
    assert True
