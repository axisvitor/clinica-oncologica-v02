#!/usr/bin/env python3
"""
Test Infrastructure Validation Script

This script validates that the test infrastructure is working correctly
and can collect tests without errors.
"""

import os
import sys
import importlib
from pathlib import Path


def setup_test_environment():
    """Setup test environment variables."""
    test_env = {
        "ENVIRONMENT": "test",
        "DEBUG": "false",
        "DATABASE_URL": "sqlite:///./test.db",
        "REDIS_URL": "redis://localhost:6379/1",
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "JWT_SECRET_KEY": "test-jwt-secret-key-for-testing",
        "PYTHONPATH": str(Path.cwd()),
    }

    for key, value in test_env.items():
        os.environ[key] = value

    print("✓ Test environment configured")


def test_critical_imports():
    """Test critical module imports."""
    critical_modules = [
        "app.config",
        "app.models.user",
        "app.services",
        "tests.helpers.jwt_helper",
        "tests.conftest"
    ]

    failed_imports = []

    for module_name in critical_modules:
        try:
            importlib.import_module(module_name)
            print(f"✓ {module_name}")
        except Exception as e:
            print(f"✗ {module_name}: {e}")
            failed_imports.append((module_name, str(e)))

    return failed_imports


def test_pytest_collection():
    """Test pytest collection."""
    try:
        import pytest

        # Set up test environment
        setup_test_environment()

        # Try to collect tests from the setup validation file
        test_file = "tests/test_setup_validation.py"
        if Path(test_file).exists():
            # Just try to import the test file
            sys.path.insert(0, str(Path.cwd()))
            spec = importlib.util.spec_from_file_location("test_setup", test_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                print("✓ Test setup validation file can be imported")
                return True
        else:
            print("✗ Test setup validation file not found")
            return False

    except Exception as e:
        print(f"✗ Pytest collection failed: {e}")
        return False


def validate_fixtures():
    """Validate that key fixtures work."""
    try:
        # Import conftest and check fixtures
        import tests.conftest as conftest

        # Check if key fixture functions exist
        required_fixtures = [
            'test_engine',
            'async_test_engine',
            'db_session',
            'async_db_session',
            'doctor_a_credentials',
            'admin_credentials'
        ]

        missing_fixtures = []
        for fixture_name in required_fixtures:
            if not hasattr(conftest, fixture_name):
                missing_fixtures.append(fixture_name)

        if missing_fixtures:
            print(f"✗ Missing fixtures: {missing_fixtures}")
            return False
        else:
            print("✓ All required fixtures are available")
            return True

    except Exception as e:
        print(f"✗ Fixture validation failed: {e}")
        return False


def main():
    """Run test infrastructure validation."""
    print("🔍 Validating Test Infrastructure")
    print("=" * 50)

    # Change to backend directory
    os.chdir(Path(__file__).parent)

    success = True

    # Test critical imports
    print("\n📦 Testing Critical Imports")
    print("-" * 30)
    failed_imports = test_critical_imports()
    if failed_imports:
        success = False

    # Test pytest collection
    print("\n🧪 Testing Pytest Collection")
    print("-" * 30)
    if not test_pytest_collection():
        success = False

    # Validate fixtures
    print("\n⚙️ Validating Fixtures")
    print("-" * 30)
    if not validate_fixtures():
        success = False

    # Summary
    print("\n" + "=" * 50)
    if success:
        print("🎉 Test infrastructure validation PASSED!")
        print("   All tests should be able to collect and run successfully.")
        return 0
    else:
        print("❌ Test infrastructure validation FAILED!")
        print("   Some issues need to be resolved before tests can run.")
        return 1


if __name__ == "__main__":
    # Add the necessary import for importlib.util
    import importlib.util
    sys.exit(main())