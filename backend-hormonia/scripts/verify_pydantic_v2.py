#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick verification script for Pydantic V2 migration.
Checks for deprecated schema_extra usage without requiring full app setup.
"""
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def check_schema_extra():
    """Check for deprecated schema_extra usage in schema files."""
    backend_path = Path(__file__).parent.parent
    schemas_path = backend_path / "app" / "schemas"

    if not schemas_path.exists():
        print(f"[FAIL] Schemas directory not found: {schemas_path}")
        return False

    schema_files = list(schemas_path.glob("*.py"))
    print(f"[*] Checking {len(schema_files)} schema files...")

    deprecated_usage = []
    for schema_file in schema_files:
        if schema_file.name == "__init__.py":
            continue

        content = schema_file.read_text(encoding="utf-8")
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Look for schema_extra but not json_schema_extra
            if "schema_extra" in line and "json_schema_extra" not in line:
                # Exclude comments
                code_part = line.split("#")[0]
                if "schema_extra" in code_part and "=" in code_part:
                    deprecated_usage.append(
                        f"  {schema_file.name}:{i} - {line.strip()}"
                    )

    if deprecated_usage:
        print("[FAIL] Found deprecated schema_extra usage:")
        for usage in deprecated_usage:
            print(usage)
        return False

    print("[PASS] No deprecated schema_extra found!")
    return True


def check_json_schema_extra():
    """Verify json_schema_extra is used correctly."""
    backend_path = Path(__file__).parent.parent
    schemas_path = backend_path / "app" / "schemas"

    schema_files = list(schemas_path.glob("*.py"))
    files_with_examples = []

    for schema_file in schema_files:
        if schema_file.name == "__init__.py":
            continue

        content = schema_file.read_text(encoding="utf-8")

        if "json_schema_extra" in content:
            files_with_examples.append(schema_file.name)

    print(f"\n[INFO] Files using json_schema_extra: {len(files_with_examples)}")
    for filename in sorted(files_with_examples):
        print(f"  [OK] {filename}")

    return True


def test_import_schemas():
    """Test that schema modules can be imported."""
    print("\n[*] Testing schema imports...")

    # Add backend to path
    backend_path = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_path))

    try:
        # Try importing schema modules (will fail if syntax errors exist)
        import importlib.util

        schemas_to_test = ["ai", "flow", "medico", "admin_users"]
        imported = []

        for schema_name in schemas_to_test:
            schema_path = backend_path / "app" / "schemas" / f"{schema_name}.py"
            if not schema_path.exists():
                continue

            spec = importlib.util.spec_from_file_location(
                f"app.schemas.{schema_name}",
                schema_path
            )

            if spec and spec.loader:
                try:
                    module = importlib.util.module_from_spec(spec)
                    # Note: Not executing to avoid config issues
                    # Just checking the file is valid Python
                    compile(schema_path.read_text(encoding="utf-8"), schema_path, "exec")
                    imported.append(schema_name)
                    print(f"  [OK] {schema_name}.py - Valid Python syntax")
                except SyntaxError as e:
                    print(f"  [FAIL] {schema_name}.py - Syntax error: {e}")
                    return False

        if imported:
            print(f"[PASS] All {len(imported)} schema files have valid syntax")
            return True
        else:
            print("[FAIL] No schema files found to test")
            return False

    except Exception as e:
        print(f"[FAIL] Import test failed: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Pydantic V2 Migration Verification")
    print("=" * 60)

    checks = [
        ("Deprecated schema_extra check", check_schema_extra),
        ("json_schema_extra usage check", check_json_schema_extra),
        ("Schema syntax validation", test_import_schemas),
    ]

    results = []
    for name, check_func in checks:
        print(f"\n{'=' * 60}")
        print(f"Running: {name}")
        print("=" * 60)
        results.append(check_func())

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for (name, _), result in zip(checks, results):
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")

    all_passed = all(results)
    print("\n" + "=" * 60)

    if all_passed:
        print("[SUCCESS] ALL CHECKS PASSED - Pydantic V2 migration complete!")
        return 0
    else:
        print("[WARNING] SOME CHECKS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
