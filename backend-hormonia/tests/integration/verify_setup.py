#!/usr/bin/env python3
"""
Integration Test Setup Verification Script

Run this script to verify that the integration test environment is properly configured.

Usage:
    python tests/integration/verify_setup.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def check_database_url():
    """Check if DATABASE_URL is set and contains 'test'."""
    print("🔍 Checking DATABASE_URL...")

    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("❌ DATABASE_URL not set")
        print("   Set it with: export DATABASE_URL='postgresql://user:password@localhost/hormonia_test'")
        return False

    if "test" not in db_url.lower():
        print(f"⚠️  DATABASE_URL does not contain 'test': {db_url}")
        print("   This is a safety check to prevent running on production!")
        return False

    print(f"✅ DATABASE_URL is set correctly: {db_url}")
    return True


def check_database_connection():
    """Check if database connection works."""
    print("\n🔍 Checking database connection...")

    try:
        from sqlalchemy import create_engine, text

        db_url = os.getenv("DATABASE_URL")
        engine = create_engine(db_url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def check_tables_exist():
    """Check if required tables exist."""
    print("\n🔍 Checking required tables...")

    required_tables = [
        "patients",
        "patient_onboarding_sagas",
        "flow_instances",
        "notifications",
    ]

    try:
        from sqlalchemy import create_engine, inspect

        db_url = os.getenv("DATABASE_URL")
        engine = create_engine(db_url)
        inspector = inspect(engine)

        existing_tables = inspector.get_table_names()

        missing_tables = []
        for table in required_tables:
            if table in existing_tables:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' not found")
                missing_tables.append(table)

        if missing_tables:
            print(f"\n⚠️  Missing tables: {', '.join(missing_tables)}")
            print("   Run migrations with: alembic upgrade head")
            return False

        return True
    except Exception as e:
        print(f"❌ Failed to check tables: {e}")
        return False


def check_pytest_installed():
    """Check if pytest is installed."""
    print("\n🔍 Checking pytest installation...")

    try:
        import pytest
        print(f"✅ pytest is installed (version {pytest.__version__})")
        return True
    except ImportError:
        print("❌ pytest not installed")
        print("   Install with: pip install pytest pytest-asyncio")
        return False


def check_test_files():
    """Check if test files exist."""
    print("\n🔍 Checking test files...")

    test_dir = Path(__file__).parent
    required_files = [
        "__init__.py",
        "conftest.py",
        "test_patient_saga.py",
        "README.md",
    ]

    all_exist = True
    for filename in required_files:
        filepath = test_dir / filename
        if filepath.exists():
            print(f"✅ {filename} exists")
        else:
            print(f"❌ {filename} not found")
            all_exist = False

    return all_exist


def check_pytest_ini():
    """Check if pytest.ini is configured correctly."""
    print("\n🔍 Checking pytest.ini configuration...")

    pytest_ini = project_root / "pytest.ini"

    if not pytest_ini.exists():
        print("❌ pytest.ini not found")
        return False

    content = pytest_ini.read_text()

    if "integration:" in content:
        print("✅ pytest.ini has integration marker")
        return True
    else:
        print("❌ pytest.ini missing integration marker")
        return False


def run_sample_test():
    """Run a simple test to verify everything works."""
    print("\n🔍 Running sample test...")

    try:
        import subprocess
        result = subprocess.run(
            ["pytest", "-m", "integration", "--collect-only", "-q"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Count collected tests
            lines = result.stdout.strip().split('\n')
            test_count = len([l for l in lines if l.startswith("tests/integration")])
            print(f"✅ Pytest can collect {test_count} integration tests")
            return True
        else:
            print(f"⚠️  Pytest collection had issues: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Failed to run pytest: {e}")
        return False


def print_summary(results):
    """Print summary of checks."""
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    checks = [
        ("DATABASE_URL configured", results["db_url"]),
        ("Database connection", results["db_connection"]),
        ("Required tables exist", results["tables"]),
        ("pytest installed", results["pytest"]),
        ("Test files exist", results["files"]),
        ("pytest.ini configured", results["pytest_ini"]),
        ("Tests collectible", results["sample_test"]),
    ]

    all_passed = all(result for _, result in checks)

    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")

    print("="*60)

    if all_passed:
        print("\n🎉 All checks passed! Integration tests are ready to run.")
        print("\nNext steps:")
        print("  1. Run tests: pytest -m integration")
        print("  2. View results: pytest -m integration -v")
        print("  3. Run specific test: pytest -m integration tests/integration/test_patient_saga.py")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")

    return all_passed


def main():
    """Run all verification checks."""
    print("="*60)
    print("INTEGRATION TEST SETUP VERIFICATION")
    print("="*60)

    results = {
        "db_url": check_database_url(),
        "db_connection": False,
        "tables": False,
        "pytest": check_pytest_installed(),
        "files": check_test_files(),
        "pytest_ini": check_pytest_ini(),
        "sample_test": False,
    }

    # Only check database connection and tables if URL is set
    if results["db_url"]:
        results["db_connection"] = check_database_connection()
        if results["db_connection"]:
            results["tables"] = check_tables_exist()

    # Only run sample test if pytest is installed
    if results["pytest"]:
        results["sample_test"] = run_sample_test()

    success = print_summary(results)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
