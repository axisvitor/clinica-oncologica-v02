#!/usr/bin/env python
"""Run backend tests with coverage and generate report"""

import subprocess
import sys
import os
from pathlib import Path

def run_tests():
    """Run pytest with coverage and display results"""

    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)

    print("=" * 80)
    print("RUNNING BACKEND TESTS WITH COVERAGE")
    print("=" * 80)

    # First, try to collect tests
    print("\n1. Collecting tests...")
    collect_cmd = [sys.executable, "-m", "pytest", "--co", "-q"]
    result = subprocess.run(collect_cmd, capture_output=True, text=True)

    # Count collected tests
    collected_line = [line for line in result.stdout.split('\n') if 'collected' in line]
    if collected_line:
        print(f"✅ {collected_line[0]}")

    # Check for errors
    if "error" in result.stderr.lower() or "error" in result.stdout.lower():
        print("\n⚠️ Collection errors found:")
        errors = [line for line in result.stdout.split('\n') if 'ERROR' in line]
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")

    # Run tests with coverage
    print("\n2. Running tests with coverage...")
    test_cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "--cov=app",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=html:htmlcov",
        "--tb=short",
        "-x",  # Stop on first failure
        "--maxfail=10",
        "-q"  # Quiet mode
    ]

    result = subprocess.run(test_cmd, capture_output=True, text=True)

    # Parse output
    output_lines = result.stdout.split('\n')

    # Show test results
    print("\n3. Test Results:")
    for line in output_lines:
        if 'passed' in line or 'failed' in line or 'error' in line:
            print(f"  {line}")
            break

    # Show coverage summary
    print("\n4. Coverage Summary:")
    coverage_started = False
    for line in output_lines:
        if 'Name' in line and 'Stmts' in line:
            coverage_started = True
        if coverage_started:
            if 'TOTAL' in line:
                print(f"  📊 {line}")
                # Extract coverage percentage
                parts = line.split()
                if len(parts) >= 4:
                    coverage = parts[-1]
                    print(f"\n  🎯 Total Coverage: {coverage}")
                break

    # Show top uncovered modules
    print("\n5. Top Modules Needing Tests (lowest coverage):")
    module_coverage = []
    for line in output_lines:
        if line.startswith('app/') and '%' in line:
            parts = line.split()
            if len(parts) >= 4:
                module = parts[0]
                coverage = parts[-1].rstrip('%')
                try:
                    coverage_float = float(coverage)
                    module_coverage.append((module, coverage_float))
                except:
                    pass

    # Sort by coverage and show bottom 10
    module_coverage.sort(key=lambda x: x[1])
    for module, cov in module_coverage[:10]:
        print(f"  - {module}: {cov}%")

    print("\n" + "=" * 80)
    print("TEST RUN COMPLETE")
    print("=" * 80)

    # Return exit code
    return result.returncode

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)