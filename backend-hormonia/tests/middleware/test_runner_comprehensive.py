#!/usr/bin/env python3
"""
Comprehensive test runner for middleware unit tests.

This script runs all middleware tests and generates coverage reports
to validate that each middleware achieves 80%+ code coverage.

Usage:
    python test_runner_comprehensive.py

    # Run specific middleware tests
    python test_runner_comprehensive.py --middleware cors
    python test_runner_comprehensive.py --middleware security-headers
    python test_runner_comprehensive.py --middleware rate-limiting
    python test_runner_comprehensive.py --middleware logging
    python test_runner_comprehensive.py --middleware enhanced-security
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Tuple


class MiddlewareTestRunner:
    """Test runner for middleware components with coverage analysis."""

    def __init__(self):
        """Initialize the test runner."""
        self.base_dir = Path(__file__).parent.parent.parent
        self.test_dir = Path(__file__).parent
        self.middleware_dir = self.base_dir / "app" / "middleware"

        # Define middleware test mappings
        self.middleware_tests = {
            "cors": {
                "test_file": "test_cors_comprehensive.py",
                "source_files": ["cors.py"],
                "description": "CORS middleware with production security validation"
            },
            "security-headers": {
                "test_file": "test_security_headers_comprehensive.py",
                "source_files": ["security_headers.py"],
                "description": "Security headers middleware with OWASP compliance"
            },
            "rate-limiting": {
                "test_file": "test_rate_limiting_comprehensive.py",
                "source_files": ["rate_limit.py", "enhanced_middleware.py"],
                "description": "Rate limiting middleware with Redis and memory backends"
            },
            "logging": {
                "test_file": "test_logging_comprehensive.py",
                "source_files": ["logging.py", "enhanced_middleware.py"],
                "description": "Request/response logging middleware with correlation IDs"
            },
            "enhanced-security": {
                "test_file": "test_enhanced_security_comprehensive.py",
                "source_files": ["enhanced_middleware.py", "security.py"],
                "description": "Enhanced security middleware with threat detection"
            }
        }

    def run_tests(self, middleware_name: str = None) -> Dict[str, Dict]:
        """
        Run tests for specified middleware or all middleware.

        Args:
            middleware_name: Specific middleware to test, or None for all

        Returns:
            Dictionary with test results and coverage data
        """
        results = {}

        if middleware_name:
            if middleware_name not in self.middleware_tests:
                raise ValueError(f"Unknown middleware: {middleware_name}")
            middlewares_to_test = [middleware_name]
        else:
            middlewares_to_test = list(self.middleware_tests.keys())

        print(f"🧪 Running comprehensive middleware tests...")
        print(f"📁 Base directory: {self.base_dir}")
        print(f"🎯 Testing {len(middlewares_to_test)} middleware component(s)")
        print("=" * 80)

        for middleware in middlewares_to_test:
            print(f"\n🔍 Testing {middleware} middleware...")
            result = self._run_single_middleware_test(middleware)
            results[middleware] = result

            # Print immediate results
            self._print_test_result(middleware, result)

        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE TEST SUMMARY")
        print("=" * 80)

        self._print_summary(results)

        return results

    def _run_single_middleware_test(self, middleware_name: str) -> Dict:
        """Run tests for a single middleware component."""
        config = self.middleware_tests[middleware_name]
        test_file = self.test_dir / config["test_file"]

        if not test_file.exists():
            return {
                "status": "error",
                "message": f"Test file not found: {test_file}",
                "coverage": 0,
                "tests_passed": 0,
                "tests_failed": 0
            }

        # Run pytest with coverage
        coverage_sources = []
        for source_file in config["source_files"]:
            source_path = self.middleware_dir / source_file
            if source_path.exists():
                coverage_sources.append(str(source_path))

        if not coverage_sources:
            return {
                "status": "error",
                "message": "No source files found for coverage",
                "coverage": 0,
                "tests_passed": 0,
                "tests_failed": 0
            }

        # Build pytest command with coverage
        cmd = [
            sys.executable, "-m", "pytest",
            str(test_file),
            "-v",
            "--tb=short",
            f"--cov={','.join(coverage_sources)}",
            "--cov-report=term-missing",
            "--cov-report=json",
            "--cov-fail-under=80"
        ]

        try:
            # Change to base directory for proper imports
            result = subprocess.run(
                cmd,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            return self._parse_test_output(result)

        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "message": "Test execution timed out after 120 seconds",
                "coverage": 0,
                "tests_passed": 0,
                "tests_failed": 0
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Test execution failed: {str(e)}",
                "coverage": 0,
                "tests_passed": 0,
                "tests_failed": 0
            }

    def _parse_test_output(self, result: subprocess.CompletedProcess) -> Dict:
        """Parse pytest output to extract test results and coverage."""
        output = result.stdout + result.stderr

        # Parse test results
        tests_passed = 0
        tests_failed = 0
        coverage_percentage = 0

        # Extract test counts
        for line in output.split('\n'):
            if 'passed' in line and 'failed' in line:
                # Format: "X passed, Y failed"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed':
                        tests_passed = int(parts[i-1])
                    elif part == 'failed':
                        tests_failed = int(parts[i-1])
            elif line.strip().endswith('passed'):
                # Format: "X passed"
                parts = line.split()
                if len(parts) >= 2 and parts[-1] == 'passed':
                    tests_passed = int(parts[-2])

            # Extract coverage percentage
            if 'TOTAL' in line and '%' in line:
                parts = line.split()
                for part in parts:
                    if part.endswith('%'):
                        try:
                            coverage_percentage = int(part[:-1])
                        except ValueError:
                            pass

        # Determine status
        if result.returncode == 0:
            status = "success"
            message = "All tests passed with sufficient coverage"
        elif tests_failed > 0:
            status = "test_failures"
            message = f"{tests_failed} test(s) failed"
        elif coverage_percentage < 80:
            status = "low_coverage"
            message = f"Coverage {coverage_percentage}% is below 80% threshold"
        else:
            status = "error"
            message = "Unknown test failure"

        return {
            "status": status,
            "message": message,
            "coverage": coverage_percentage,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "output": output
        }

    def _print_test_result(self, middleware_name: str, result: Dict) -> None:
        """Print test result for a single middleware."""
        config = self.middleware_tests[middleware_name]

        print(f"  📝 {config['description']}")
        print(f"  📄 Test file: {config['test_file']}")

        if result["status"] == "success":
            print(f"  ✅ Status: PASSED")
            print(f"  🎯 Coverage: {result['coverage']}%")
            print(f"  🧪 Tests: {result['tests_passed']} passed, {result['tests_failed']} failed")
        elif result["status"] == "test_failures":
            print(f"  ❌ Status: FAILED")
            print(f"  🎯 Coverage: {result['coverage']}%")
            print(f"  🧪 Tests: {result['tests_passed']} passed, {result['tests_failed']} failed")
            print(f"  💬 Message: {result['message']}")
        elif result["status"] == "low_coverage":
            print(f"  ⚠️  Status: LOW COVERAGE")
            print(f"  🎯 Coverage: {result['coverage']}% (< 80%)")
            print(f"  🧪 Tests: {result['tests_passed']} passed, {result['tests_failed']} failed")
        else:
            print(f"  💥 Status: ERROR")
            print(f"  💬 Message: {result['message']}")

    def _print_summary(self, results: Dict[str, Dict]) -> None:
        """Print comprehensive summary of all test results."""
        total_tests = len(results)
        successful_tests = sum(1 for r in results.values() if r["status"] == "success")
        total_coverage = sum(r["coverage"] for r in results.values()) / len(results) if results else 0
        total_test_count = sum(r["tests_passed"] + r["tests_failed"] for r in results.values())
        total_passed = sum(r["tests_passed"] for r in results.values())
        total_failed = sum(r["tests_failed"] for r in results.values())

        print(f"🏆 Success Rate: {successful_tests}/{total_tests} middleware components")
        print(f"📊 Average Coverage: {total_coverage:.1f}%")
        print(f"🧪 Total Tests: {total_test_count} ({total_passed} passed, {total_failed} failed)")

        print("\n📋 DETAILED RESULTS:")
        for middleware_name, result in results.items():
            status_emoji = {
                "success": "✅",
                "test_failures": "❌",
                "low_coverage": "⚠️",
                "error": "💥",
                "timeout": "⏰"
            }.get(result["status"], "❓")

            print(f"  {status_emoji} {middleware_name:20} | "
                  f"Coverage: {result['coverage']:3d}% | "
                  f"Tests: {result['tests_passed']:2d}P/{result['tests_failed']:2d}F")

        # Print recommendations
        print("\n💡 RECOMMENDATIONS:")

        low_coverage_middleware = [
            name for name, result in results.items()
            if result["coverage"] < 80
        ]

        if low_coverage_middleware:
            print(f"  📈 Improve coverage for: {', '.join(low_coverage_middleware)}")

        failed_middleware = [
            name for name, result in results.items()
            if result["tests_failed"] > 0
        ]

        if failed_middleware:
            print(f"  🔧 Fix failing tests in: {', '.join(failed_middleware)}")

        if successful_tests == total_tests and total_coverage >= 80:
            print("  🎉 All middleware components meet quality standards!")

        # Overall grade
        print(f"\n🎯 OVERALL GRADE: ", end="")
        if successful_tests == total_tests and total_coverage >= 80:
            print("A+ (Excellent)")
        elif successful_tests >= total_tests * 0.8 and total_coverage >= 75:
            print("B+ (Good)")
        elif successful_tests >= total_tests * 0.6 and total_coverage >= 70:
            print("C+ (Acceptable)")
        else:
            print("D (Needs Improvement)")


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive middleware tests with coverage analysis"
    )
    parser.add_argument(
        "--middleware",
        choices=["cors", "security-headers", "rate-limiting", "logging", "enhanced-security"],
        help="Run tests for specific middleware only"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed test output"
    )

    args = parser.parse_args()

    runner = MiddlewareTestRunner()

    try:
        results = runner.run_tests(args.middleware)

        if args.verbose:
            print("\n" + "=" * 80)
            print("🔍 VERBOSE OUTPUT")
            print("=" * 80)
            for middleware_name, result in results.items():
                if "output" in result:
                    print(f"\n--- {middleware_name} output ---")
                    print(result["output"])

        # Exit with appropriate code
        all_successful = all(
            result["status"] == "success" for result in results.values()
        )

        sys.exit(0 if all_successful else 1)

    except KeyboardInterrupt:
        print("\n\n⏹️  Test execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Test runner error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()