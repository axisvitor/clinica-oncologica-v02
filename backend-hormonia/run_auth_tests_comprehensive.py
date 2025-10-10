#!/usr/bin/env python3
"""
Comprehensive test runner for authentication services.

This script runs all authentication-related tests including:
- Firebase Auth Service tests
- Legacy Auth Service tests
- Audit Service tests
- Integration tests for authentication flows
- Coverage reporting
"""

import sys
import os
import subprocess
from pathlib import Path


def main():
    """Run comprehensive authentication tests."""
    # Get the backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)

    print("🔒 Running Comprehensive Authentication Service Tests")
    print("=" * 60)

    # Test files to run
    test_files = [
        "tests/unit/services/test_firebase_auth_service_comprehensive.py",
        "tests/unit/services/test_auth_service_comprehensive.py",
        "tests/unit/services/test_audit_service_comprehensive.py",
        "tests/integration/test_auth_flows_comprehensive.py"
    ]

    # Check if test files exist
    missing_files = []
    for test_file in test_files:
        if not Path(test_file).exists():
            missing_files.append(test_file)

    if missing_files:
        print("❌ Missing test files:")
        for file in missing_files:
            print(f"   - {file}")
        return 1

    # Pytest command with comprehensive options
    cmd = [
        sys.executable, "-m", "pytest",
        "-c", "tests/auth_pytest.ini",
        "--verbose",
        "--tb=short",
        "--durations=10",
        "--cov=app.services.firebase_auth_service",
        "--cov=app.services.auth",
        "--cov=app.services.audit_service",
        "--cov-report=term-missing",
        "--cov-report=html:tests/htmlcov",
        "--cov-report=xml:tests/coverage.xml",
        "--cov-fail-under=80",
        "--junitxml=tests/auth_test_results.xml",
        "--markers"
    ] + test_files

    print(f"Running command: {' '.join(cmd)}")
    print("-" * 60)

    # Run the tests
    try:
        result = subprocess.run(cmd, check=False)

        print("\n" + "=" * 60)
        if result.returncode == 0:
            print("✅ All authentication tests passed!")
            print("\n📊 Coverage Report:")
            print("   - HTML report: tests/htmlcov/index.html")
            print("   - XML report: tests/coverage.xml")
            print("   - JUnit XML: tests/auth_test_results.xml")
        else:
            print("❌ Some tests failed or coverage below threshold")
            print(f"   Exit code: {result.returncode}")

        return result.returncode

    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())