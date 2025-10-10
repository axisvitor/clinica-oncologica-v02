#!/usr/bin/env python3
"""
Direct test of audit service comprehensive tests.
This script sets environment variables to avoid production validation.
"""

import os
import sys
from pathlib import Path

# Set environment variables before any imports
os.environ['ENVIRONMENT'] = 'development'
os.environ['DEBUG'] = 'true'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only-do-not-use-in-production'
os.environ['FIREBASE_API_KEY'] = 'test-firebase-api-key'
os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/test_hormonia_db'
os.environ['REDIS_URL'] = 'redis://localhost:6379/1'
os.environ['ALLOWED_ORIGINS'] = 'http://localhost:3000,http://localhost:5173'
os.environ['SESSION_COOKIE_SECURE'] = 'false'
os.environ['SECURE_SSL_REDIRECT'] = 'false'

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

import subprocess

def main():
    """Run the comprehensive audit service tests with proper environment."""

    print("=" * 60)
    print("RUNNING COMPREHENSIVE AUDIT SERVICE TESTS")
    print("=" * 60)
    print(f"Environment: {os.environ.get('ENVIRONMENT')}")
    print(f"Debug: {os.environ.get('DEBUG')}")
    print()

    # Change to backend directory
    os.chdir(backend_dir)

    # Run tests with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/unit/services/test_audit_service_comprehensive.py",
        "-v",
        "--tb=short",
        "--no-cov",  # Disable coverage for now to focus on test execution
        "--disable-warnings"
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