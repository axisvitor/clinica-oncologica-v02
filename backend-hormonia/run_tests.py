#!/usr/bin/env python3
"""
Main test execution script for Hormonia Backend System.
This script can be used locally or in CI/CD pipelines.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description, cwd=None, timeout=None):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"RUNNING: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            timeout=timeout,
            check=False
        )
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False


def main():
    """Main test execution function."""
    parser = argparse.ArgumentParser(description="Run Hormonia Backend System tests")
    parser.add_argument("--quick", action="store_true", help="Run only unit tests")
    parser.add_argument("--full", action="store_true", help="Run all tests including load tests")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--smoke-only", action="store_true", help="Run only smoke tests")
    parser.add_argument("--no-install", action="store_true", help="Skip dependency installation")
    
    args = parser.parse_args()
    
    # Get project root
    project_root = Path(__file__).parent
    
    print(f"🚀 Hormonia Backend System - Test Execution")
    print(f"Project Root: {project_root}")
    print(f"Python Version: {sys.version}")
    
    success = True
    
    # Install dependencies unless skipped
    if not args.no_install:
        success &= run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            "Installing dependencies",
            cwd=project_root,
            timeout=300
        )
        
        if not success:
            print("❌ Failed to install dependencies")
            return 1
    
    # Run smoke tests only
    if args.smoke_only:
        success &= run_command(
            [sys.executable, "tests/deployment/test_smoke_tests.py"],
            "Smoke tests",
            cwd=project_root,
            timeout=300
        )
        
        return 0 if success else 1
    
    # Quick mode - unit tests only
    if args.quick:
        cmd = [sys.executable, "-m", "pytest", "tests/unit/", "-v"]
        if args.coverage:
            cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
        
        success &= run_command(
            cmd,
            "Unit tests",
            cwd=project_root,
            timeout=600
        )
        
        return 0 if success else 1
    
    # Full test suite
    test_categories = [
        ("tests/unit/", "Unit tests", 600),
        ("tests/integration/", "Integration tests", 900),
        ("tests/e2e/", "End-to-end tests", 1200),
        ("tests/performance/", "Performance tests", 600),
    ]
    
    for test_path, description, timeout in test_categories:
        if not (project_root / test_path).exists():
            print(f"⚠️  Skipping {description} - directory not found: {test_path}")
            continue
        
        cmd = [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"]
        
        # Add coverage for unit and integration tests
        if "unit" in test_path or "integration" in test_path:
            if args.coverage:
                cmd.extend([
                    "--cov=app",
                    f"--cov-report=html:htmlcov/{test_path.split('/')[1]}",
                    "--cov-report=term-missing"
                ])
        
        success &= run_command(cmd, description, cwd=project_root, timeout=timeout)
    
    # Run smoke tests
    if (project_root / "tests/deployment/test_smoke_tests.py").exists():
        success &= run_command(
            [sys.executable, "tests/deployment/test_smoke_tests.py"],
            "Smoke tests",
            cwd=project_root,
            timeout=300
        )
    
    # Run load tests if full mode
    if args.full and (project_root / "tests/performance/test_load_testing.py").exists():
        success &= run_command(
            [sys.executable, "tests/performance/test_load_testing.py"],
            "Load tests",
            cwd=project_root,
            timeout=900
        )
    
    # Final summary
    print(f"\n{'='*80}")
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("The Hormonia Backend System is ready for deployment.")
    else:
        print("💥 SOME TESTS FAILED!")
        print("Please review the test output and fix any issues.")
    print(f"{'='*80}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())