#!/usr/bin/env python3
"""
Test script to verify environment variable validation at startup.

This script tests the startup validation logic by simulating different
environment configurations and verifying that the application fails fast
with clear error messages when required variables are missing.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


def test_production_missing_vars():
    """Test that production environment fails when required vars are missing."""
    print("\n" + "=" * 80)
    print("TEST 1: Production Environment - Missing Required Variables")
    print("=" * 80)

    # Set production environment
    os.environ["APP_ENVIRONMENT"] = "production"

    # Remove required variables
    for var in [
        "SECURITY_CSRF_SECRET_KEY",
        "ENCRYPTION_KEY_CURRENT",
        "HASH_SALT",
        "FIREBASE_ADMIN_PROJECT_ID",
        "FIREBASE_ADMIN_PRIVATE_KEY",
        "FIREBASE_ADMIN_CLIENT_EMAIL",
    ]:
        os.environ.pop(var, None)

    try:
        from app.config.settings import SecuritySettings

        settings = SecuritySettings()
        print("❌ FAILED: Settings initialized without required variables!")
        return False
    except ValueError as e:
        print("✅ PASSED: Validation correctly failed")
        print(f"\nError message:\n{str(e)}")
        return True
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False


def test_production_with_vars():
    """Test that production environment succeeds when all required vars are set."""
    print("\n" + "=" * 80)
    print("TEST 2: Production Environment - All Required Variables Set")
    print("=" * 80)

    # Set production environment
    os.environ["APP_ENVIRONMENT"] = "production"

    # Set all required variables with valid values
    os.environ["SECURITY_CSRF_SECRET_KEY"] = "test_csrf_secret_key_with_sufficient_length_for_validation"
    os.environ["ENCRYPTION_KEY_CURRENT"] = "fZgOQvXqKl3yVJ7Y9p8aB2cNmD4xE5wR6tH7uI8oP9kL0mJ1nA2sD3fG4hK5jL6zX7cV8bN9mQ0="
    os.environ["HASH_SALT"] = "test_hash_salt_with_sufficient_entropy_for_hashing_operations_minimum_32_bytes"

    # Set Firebase variables (empty to test optional Firebase)
    for var in ["FIREBASE_ADMIN_PROJECT_ID", "FIREBASE_ADMIN_PRIVATE_KEY", "FIREBASE_ADMIN_CLIENT_EMAIL"]:
        os.environ.pop(var, None)

    try:
        # Import fresh to avoid cached settings
        import importlib
        import app.config.settings
        importlib.reload(app.config.settings)
        from app.config.settings import SecuritySettings

        settings = SecuritySettings()
        print("✅ PASSED: Settings initialized successfully with all required variables")
        return True
    except ValueError as e:
        print(f"❌ FAILED: Validation failed unexpectedly: {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_firebase_partial_config():
    """Test that Firebase validation fails when only some Firebase vars are set."""
    print("\n" + "=" * 80)
    print("TEST 3: Firebase Partial Configuration - Should Fail")
    print("=" * 80)

    # Set development environment
    os.environ["APP_ENVIRONMENT"] = "development"

    # Set only some Firebase variables (should fail)
    os.environ["FIREBASE_ADMIN_PROJECT_ID"] = "test-project-id"
    os.environ.pop("FIREBASE_ADMIN_PRIVATE_KEY", None)
    os.environ.pop("FIREBASE_ADMIN_CLIENT_EMAIL", None)

    try:
        import importlib
        import app.config.settings
        importlib.reload(app.config.settings)
        from app.config.settings import SecuritySettings

        settings = SecuritySettings()
        print("❌ FAILED: Settings initialized with partial Firebase config!")
        return False
    except ValueError as e:
        if "FIREBASE" in str(e):
            print("✅ PASSED: Firebase partial configuration correctly rejected")
            print(f"\nError message:\n{str(e)}")
            return True
        else:
            print(f"❌ FAILED: Wrong error: {e}")
            return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False


def test_development_without_encryption():
    """Test that development environment works without encryption keys."""
    print("\n" + "=" * 80)
    print("TEST 4: Development Environment - Without Encryption Keys")
    print("=" * 80)

    # Set development environment
    os.environ["APP_ENVIRONMENT"] = "development"

    # Remove encryption keys (should pass in development)
    for var in ["ENCRYPTION_KEY_CURRENT", "HASH_SALT", "SECURITY_CSRF_SECRET_KEY"]:
        os.environ.pop(var, None)

    # Remove Firebase variables
    for var in ["FIREBASE_ADMIN_PROJECT_ID", "FIREBASE_ADMIN_PRIVATE_KEY", "FIREBASE_ADMIN_CLIENT_EMAIL"]:
        os.environ.pop(var, None)

    try:
        import importlib
        import app.config.settings
        importlib.reload(app.config.settings)
        from app.config.settings import SecuritySettings

        settings = SecuritySettings()
        print("✅ PASSED: Development environment works without encryption keys")
        return True
    except ValueError as e:
        print(f"❌ FAILED: Development should not require encryption keys: {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False


def main():
    """Run all validation tests."""
    print("\n" + "=" * 80)
    print("ENVIRONMENT VARIABLE VALIDATION TESTS")
    print("=" * 80)

    results = []

    # Run tests
    results.append(("Production Missing Vars", test_production_missing_vars()))
    results.append(("Production With Vars", test_production_with_vars()))
    results.append(("Firebase Partial Config", test_firebase_partial_config()))
    results.append(("Development Without Encryption", test_development_without_encryption()))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")

    print("\n" + "=" * 80)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 80)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
