#!/usr/bin/env python3
"""
Coverage test runner script to verify backend test coverage improvements.
"""
import subprocess
import sys
import os
from pathlib import Path

def main():
    """Run pytest with coverage reporting."""
    # Ensure we're in the correct directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)

    print("🚀 Running pytest with coverage reporting...")
    print(f"📁 Working directory: {os.getcwd()}")

    # Run pytest with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "-v"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        print("📊 COVERAGE TEST RESULTS:")
        print("=" * 60)
        print(result.stdout)

        if result.stderr:
            print("\n⚠️  STDERR OUTPUT:")
            print("=" * 60)
            print(result.stderr)

        print(f"\n✅ Process completed with return code: {result.returncode}")

        return result.returncode

    except subprocess.TimeoutExpired:
        print("❌ Test execution timed out after 5 minutes")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())