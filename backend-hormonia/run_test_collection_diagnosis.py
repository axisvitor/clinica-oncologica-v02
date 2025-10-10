#!/usr/bin/env python3
"""
Test Collection Diagnosis Script

This script identifies specific test collection issues by attempting to import
and run pytest collection in a controlled manner.
"""

import os
import sys
import subprocess
import traceback
from pathlib import Path

def set_test_environment():
    """Set up test environment variables."""
    os.environ.update({
        "ENVIRONMENT": "test",
        "DEBUG": "false",
        "DATABASE_URL": "sqlite:///./test.db",
        "REDIS_URL": "redis://localhost:6379/1",
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "JWT_SECRET_KEY": "test-jwt-secret-key-for-testing",
        "PYTHONPATH": str(Path.cwd())
    })
    print("✓ Test environment variables set")

def test_core_imports():
    """Test core module imports."""
    imports_to_test = [
        ("app.config", "Application configuration"),
        ("app.models.user", "User model"),
        ("app.dependencies.auth_dependencies", "Auth dependencies"),
        ("app.services", "Services module"),
        ("app.core.redis_manager", "Redis manager"),
        ("tests.helpers.jwt_helper", "JWT test helper"),
        ("tests.conftest", "Pytest configuration"),
    ]

    failed_imports = []

    for module_name, description in imports_to_test:
        try:
            __import__(module_name)
            print(f"✓ {module_name} - {description}")
        except Exception as e:
            print(f"✗ {module_name} - {description}: {e}")
            failed_imports.append((module_name, str(e)))

    return failed_imports

def test_pytest_collection():
    """Test pytest collection without running tests."""
    try:
        # Run pytest --collect-only in a subprocess
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "--collect-only", "-q",
            "tests/"
        ], capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            print("✓ Pytest collection successful")
            return True, result.stdout
        else:
            print("✗ Pytest collection failed")
            return False, result.stderr
    except Exception as e:
        print(f"✗ Pytest collection error: {e}")
        return False, str(e)

def test_specific_modules():
    """Test specific problematic modules."""
    modules_to_test = [
        "app.integrations.whatsapp.queue.schemas",
        "app.integrations.whatsapp.queue.manager",
        "app.core.application_factory",
        "app.middleware.cors",
        "app.middleware.security_headers"
    ]

    failed_modules = []

    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✓ {module_name}")
        except Exception as e:
            print(f"✗ {module_name}: {e}")
            failed_modules.append((module_name, str(e)))

    return failed_modules

def check_pytest_configuration():
    """Check pytest configuration files."""
    config_files = [
        "pytest.ini",
        "tests/middleware/pytest.ini"
    ]

    issues = []

    for config_file in config_files:
        if Path(config_file).exists():
            print(f"✓ Found {config_file}")
            if config_file == "tests/middleware/pytest.ini":
                issues.append(f"Conflicting pytest.ini found at {config_file}")
        else:
            print(f"✗ Missing {config_file}")

    return issues

def main():
    """Run comprehensive test collection diagnosis."""
    print("🔍 Starting Test Collection Diagnosis")
    print("=" * 60)

    # Change to backend directory
    os.chdir(Path(__file__).parent)

    # Set test environment
    set_test_environment()
    print()

    # Test core imports
    print("📦 Testing Core Imports")
    print("-" * 30)
    failed_imports = test_core_imports()
    print()

    # Test specific modules
    print("🔧 Testing Specific Modules")
    print("-" * 30)
    failed_modules = test_specific_modules()
    print()

    # Check pytest configuration
    print("⚙️ Checking Pytest Configuration")
    print("-" * 30)
    config_issues = check_pytest_configuration()
    print()

    # Test pytest collection
    print("🧪 Testing Pytest Collection")
    print("-" * 30)
    collection_success, collection_output = test_pytest_collection()
    print()

    # Summary
    print("📋 Diagnosis Summary")
    print("=" * 60)

    total_issues = len(failed_imports) + len(failed_modules) + len(config_issues)

    if failed_imports:
        print("❌ Failed Imports:")
        for module, error in failed_imports:
            print(f"   • {module}: {error}")
        print()

    if failed_modules:
        print("❌ Failed Modules:")
        for module, error in failed_modules:
            print(f"   • {module}: {error}")
        print()

    if config_issues:
        print("⚠️ Configuration Issues:")
        for issue in config_issues:
            print(f"   • {issue}")
        print()

    if not collection_success:
        print("❌ Pytest Collection Output:")
        print(collection_output)
        print()

    if total_issues == 0 and collection_success:
        print("🎉 All tests should collect successfully!")
        return 0
    else:
        print(f"⚠️ Found {total_issues} issues that may prevent test collection")
        return 1

if __name__ == "__main__":
    sys.exit(main())