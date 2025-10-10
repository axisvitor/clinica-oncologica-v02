#!/usr/bin/env python3
"""
Test runner for comprehensive audit service tests.

This script runs the comprehensive audit service tests and provides
coverage information for both audit_service.py and audit_log.py.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Run the comprehensive audit service tests."""

    # Get the backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)

    print("=" * 60)
    print("RUNNING COMPREHENSIVE AUDIT SERVICE TESTS")
    print("=" * 60)

    # Test files to run
    test_files = [
        "tests/unit/services/test_audit_service_comprehensive.py",
        "tests/unit/services/test_audit_log.py"  # Include existing test
    ]

    # Run tests with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",
        "--tb=short",
        "--cov=app.services.audit_service",
        "--cov=app.services.audit_log",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov_audit",
        *test_files
    ]

    print(f"Running command: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        print("STDOUT:")
        print(result.stdout)
        print()

        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            print()

        print(f"Return code: {result.returncode}")

        if result.returncode == 0:
            print("✅ ALL TESTS PASSED!")
            print()
            print("Coverage report generated in: htmlcov_audit/index.html")
        else:
            print("❌ SOME TESTS FAILED")

    except subprocess.TimeoutExpired:
        print("⏰ Tests timed out after 120 seconds")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

    return result.returncode

if __name__ == "__main__":
    sys.exit(main())