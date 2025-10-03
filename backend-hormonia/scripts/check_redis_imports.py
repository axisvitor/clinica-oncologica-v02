#!/usr/bin/env python3
"""
Check for deprecated Redis import usage.

This script is designed to be used as a pre-commit hook to prevent
accidental usage of deprecated Redis clients.

Usage:
    python scripts/check_redis_imports.py

Exit codes:
    0: No deprecated imports found
    1: Deprecated imports detected
"""
import subprocess
import sys
import os
from pathlib import Path

# Deprecated import patterns to search for
DEPRECATED_PATTERNS = [
    "from app.core.redis_client_factory",
    "from app.core.redis_simple",
    "from app.utils.redis_client",
    "from app.services.async_redis_client",
    "from app.services.redis_cloud_client",
]

# Files that were previously allowed to contain these imports (now deleted)
EXCLUDED_FILES = []


def check_for_deprecated_imports():
    """Check for deprecated Redis client imports in the codebase."""
    print("🔍 Checking for deprecated Redis client imports...")

    found_issues = False
    app_dir = Path("app")

    if not app_dir.exists():
        print("❌ Error: 'app' directory not found. Run this script from project root.")
        return 1

    for pattern in DEPRECATED_PATTERNS:
        print(f"  Checking for: {pattern}")

        # Use grep to search for the pattern
        try:
            result = subprocess.run(
                ["grep", "-r", pattern, "app/", "--include=*.py"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )

            if result.stdout:
                # Filter out excluded files
                lines = result.stdout.strip().split('\n')
                filtered_lines = [
                    line for line in lines
                    if line and not any(excluded in line for excluded in EXCLUDED_FILES)
                ]

                if filtered_lines:
                    found_issues = True
                    print(f"\n❌ Found deprecated import: {pattern}")
                    for line in filtered_lines:
                        print(f"  {line}")
                    print()

        except FileNotFoundError:
            # grep not available, fall back to Python search
            print("  (grep not found, using Python search)")
            found_issues |= check_pattern_python(pattern, app_dir)

    if found_issues:
        print("\n" + "="*70)
        print("❌ FAILED: Deprecated Redis client imports detected!")
        print("="*70)
        print("\nPlease use the unified Redis client instead:")
        print("  from app.core.redis_unified import get_redis_client")
        print("  from app.core.redis_unified import get_async_redis")
        print("  from app.core.redis_unified import get_sync_redis")
        print("\nSee docs/redis/REDIS_USAGE_GUIDE.md for more information.")
        print("="*70 + "\n")
        return 1

    print("\n✅ No deprecated Redis imports found!")
    print("✅ All Redis client usage is properly unified.\n")
    return 0


def check_pattern_python(pattern: str, app_dir: Path) -> bool:
    """Fallback Python-based pattern search when grep is not available."""
    found = False

    for py_file in app_dir.rglob("*.py"):
        # Skip excluded files
        if any(excluded in str(py_file) for excluded in EXCLUDED_FILES):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if pattern in content:
                    # Find line numbers
                    for i, line in enumerate(content.split('\n'), 1):
                        if pattern in line:
                            print(f"  {py_file}:{i}: {line.strip()}")
                            found = True
        except Exception as e:
            print(f"  Warning: Could not read {py_file}: {e}")

    return found


if __name__ == "__main__":
    sys.exit(check_for_deprecated_imports())
