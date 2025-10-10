"""
Comprehensive test runner for initialization system tests.

This script runs all initialization tests, generates coverage reports,
and provides detailed analysis of test results.
"""
import os
import sys
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime
import argparse
import tempfile
import shutil


class InitializationTestRunner:
    """Test runner for initialization system tests."""

    def __init__(self, verbose=False, coverage=True, performance=True):
        self.verbose = verbose
        self.coverage = coverage
        self.performance = performance
        self.test_results = {}
        self.start_time = None
        self.end_time = None

        # Set up paths
        self.backend_dir = Path(__file__).parent.parent
        self.test_dir = Path(__file__).parent
        self.init_test_dir = self.test_dir / "unit" / "initialization"
        self.integration_test_dir = self.test_dir / "integration" / "initialization"

        # Set up environment for testing
        self._setup_test_environment()

    def _setup_test_environment(self):
        """Set up test environment variables."""
        test_env = {
            'ENVIRONMENT': 'test',
            'DEBUG': 'false',
            'SECRET_KEY': 'test-secret-key-for-initialization-testing-only',
            'JWT_SECRET_KEY': 'test-jwt-secret-key-for-testing',
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_init_db',
            'REDIS_URL': 'redis://localhost:6379/15',  # Use DB 15 for testing
            'CSRF_SECRET_KEY': 'test-csrf-secret-key-32-characters-long',
            'ENCRYPTION_KEY': 'test-encryption-key-for-testing-only',
            'RATE_LIMIT_ENABLED': 'false',  # Disable for testing
            'MONITORING_ENABLED': 'false',  # Disable for testing
            'FIREBASE_ALLOWED_DOMAINS': '[]',
            'ALLOWED_ORIGINS': '[]',
            'AI_HUMANIZATION_ENABLED': 'false'  # Disable for testing
        }

        for key, value in test_env.items():
            os.environ[key] = value

        if self.verbose:
            print("✓ Test environment configured")

    def run_all_tests(self):
        """Run all initialization tests."""
        self.start_time = time.time()

        print("🚀 Running Initialization System Tests")
        print("=" * 50)

        # Run different test categories
        test_categories = [
            ("Configuration Tests", "test_config_initialization.py"),
            ("Authentication Tests", "test_auth_initialization.py"),
            ("Middleware Tests", "test_middleware_initialization.py"),
            ("Service Tests", "test_service_initialization.py"),
            ("Edge Case Tests", "test_initialization_edge_cases.py"),
            ("Performance Tests", "test_initialization_performance.py"),
            ("Integration Tests", "../integration/initialization/test_system_startup_integration.py")
        ]

        all_success = True
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_skipped = 0

        for category_name, test_file in test_categories:
            print(f"\n📋 {category_name}")
            print("-" * 30)

            result = self._run_test_file(test_file)
            self.test_results[category_name] = result

            if result['success']:
                print(f"✅ {category_name}: PASSED")
            else:
                print(f"❌ {category_name}: FAILED")
                all_success = False

            total_tests += result['total']
            total_passed += result['passed']
            total_failed += result['failed']
            total_skipped += result['skipped']

            if self.verbose and result['output']:
                print(f"Output:\n{result['output']}")

        self.end_time = time.time()

        # Generate summary
        self._generate_summary(all_success, total_tests, total_passed, total_failed, total_skipped)

        # Generate coverage report if requested
        if self.coverage:
            self._generate_coverage_report()

        # Generate performance report if requested
        if self.performance:
            self._generate_performance_report()

        return all_success

    def _run_test_file(self, test_file):
        """Run a specific test file."""
        if test_file.startswith("../"):
            test_path = self.test_dir / test_file
        else:
            test_path = self.init_test_dir / test_file

        if not test_path.exists():
            return {
                'success': False,
                'total': 0,
                'passed': 0,
                'failed': 1,
                'skipped': 0,
                'duration': 0,
                'output': f"Test file not found: {test_path}",
                'error': f"File not found: {test_path}"
            }

        # Build pytest command
        cmd = [
            sys.executable, '-m', 'pytest',
            str(test_path),
            '-v',
            '--tb=short',
            '--disable-warnings'
        ]

        if self.coverage:
            cmd.extend(['--cov=app', '--cov-report=term-missing'])

        if self.performance:
            cmd.extend(['-m', 'not slow'])  # Skip slow tests by default

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=self.backend_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            duration = time.time() - start_time

            # Parse pytest output
            output = result.stdout + result.stderr
            success = result.returncode == 0

            # Extract test counts from output
            total, passed, failed, skipped = self._parse_pytest_output(output)

            return {
                'success': success,
                'total': total,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'duration': duration,
                'output': output,
                'returncode': result.returncode
            }

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return {
                'success': False,
                'total': 0,
                'passed': 0,
                'failed': 1,
                'skipped': 0,
                'duration': duration,
                'output': 'Test timed out after 5 minutes',
                'error': 'Timeout'
            }

        except Exception as e:
            duration = time.time() - start_time
            return {
                'success': False,
                'total': 0,
                'passed': 0,
                'failed': 1,
                'skipped': 0,
                'duration': duration,
                'output': str(e),
                'error': str(e)
            }

    def _parse_pytest_output(self, output):
        """Parse pytest output to extract test counts."""
        total = passed = failed = skipped = 0

        lines = output.split('\n')
        for line in lines:
            line = line.strip()

            # Look for summary line like "5 passed, 2 skipped in 1.23s"
            if ' passed' in line or ' failed' in line or ' skipped' in line:
                # Parse different formats
                if 'passed' in line:
                    try:
                        passed = int(line.split(' passed')[0].split()[-1])
                    except (ValueError, IndexError):
                        pass

                if 'failed' in line:
                    try:
                        failed = int(line.split(' failed')[0].split()[-1])
                    except (ValueError, IndexError):
                        pass

                if 'skipped' in line:
                    try:
                        skipped = int(line.split(' skipped')[0].split()[-1])
                    except (ValueError, IndexError):
                        pass

        total = passed + failed + skipped
        return total, passed, failed, skipped

    def _generate_summary(self, all_success, total_tests, total_passed, total_failed, total_skipped):
        """Generate test summary report."""
        duration = self.end_time - self.start_time

        print("\n" + "=" * 50)
        print("📊 INITIALIZATION TESTS SUMMARY")
        print("=" * 50)

        print(f"⏱️  Total Duration: {duration:.2f} seconds")
        print(f"📈 Total Tests: {total_tests}")
        print(f"✅ Passed: {total_passed}")
        print(f"❌ Failed: {total_failed}")
        print(f"⏭️  Skipped: {total_skipped}")

        if total_tests > 0:
            success_rate = (total_passed / total_tests) * 100
            print(f"📊 Success Rate: {success_rate:.1f}%")

        print("\n📋 Category Breakdown:")
        for category, result in self.test_results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            duration_str = f"{result['duration']:.2f}s"
            print(f"  {category}: {status} ({result['passed']}/{result['total']}) [{duration_str}]")

        if all_success:
            print("\n🎉 ALL INITIALIZATION TESTS PASSED!")
        else:
            print("\n⚠️  SOME TESTS FAILED - REVIEW REQUIRED")

        # Generate detailed JSON report
        self._save_json_report(total_tests, total_passed, total_failed, total_skipped, duration)

    def _save_json_report(self, total_tests, total_passed, total_failed, total_skipped, duration):
        """Save detailed JSON report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed': total_passed,
                'failed': total_failed,
                'skipped': total_skipped,
                'success_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0,
                'duration': duration
            },
            'categories': {}
        }

        for category, result in self.test_results.items():
            report['categories'][category] = {
                'success': result['success'],
                'total': result['total'],
                'passed': result['passed'],
                'failed': result['failed'],
                'skipped': result['skipped'],
                'duration': result['duration']
            }

        report_file = self.backend_dir / 'initialization_test_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Detailed report saved to: {report_file}")

    def _generate_coverage_report(self):
        """Generate coverage report."""
        print("\n📊 GENERATING COVERAGE REPORT")
        print("-" * 30)

        # Run coverage for initialization modules
        coverage_cmd = [
            sys.executable, '-m', 'pytest',
            str(self.init_test_dir),
            str(self.integration_test_dir),
            '--cov=app.config',
            '--cov=app.core',
            '--cov=app.middleware',
            '--cov=app.services',
            '--cov-report=html',
            '--cov-report=term',
            '--cov-report=json',
            '--cov-fail-under=80',  # Require 80% coverage
            '--disable-warnings'
        ]

        try:
            result = subprocess.run(
                coverage_cmd,
                cwd=self.backend_dir,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                print("✅ Coverage target (80%) achieved!")
            else:
                print("⚠️  Coverage below 80% threshold")

            # Parse coverage percentage
            coverage_output = result.stdout + result.stderr
            coverage_percentage = self._parse_coverage_output(coverage_output)

            if coverage_percentage:
                print(f"📊 Overall Coverage: {coverage_percentage}%")

            # Check if HTML report was generated
            html_report = self.backend_dir / 'htmlcov' / 'index.html'
            if html_report.exists():
                print(f"📄 HTML Coverage Report: {html_report}")

        except subprocess.TimeoutExpired:
            print("❌ Coverage generation timed out")
        except Exception as e:
            print(f"❌ Coverage generation failed: {e}")

    def _parse_coverage_output(self, output):
        """Parse coverage percentage from output."""
        lines = output.split('\n')
        for line in lines:
            if 'TOTAL' in line and '%' in line:
                try:
                    # Extract percentage from line like "TOTAL      100     10    90%"
                    parts = line.split()
                    for part in parts:
                        if part.endswith('%'):
                            return int(part.rstrip('%'))
                except (ValueError, IndexError):
                    continue
        return None

    def _generate_performance_report(self):
        """Generate performance report."""
        print("\n⚡ PERFORMANCE ANALYSIS")
        print("-" * 30)

        # Extract performance metrics from test results
        performance_data = {
            'test_durations': {},
            'total_duration': self.end_time - self.start_time,
            'performance_thresholds': {
                'config_init': 0.1,  # seconds
                'app_creation': 2.0,  # seconds
                'middleware_setup': 1.0,  # seconds
                'service_init': 1.0   # seconds
            }
        }

        # Collect test durations
        for category, result in self.test_results.items():
            performance_data['test_durations'][category] = result['duration']

        # Analyze performance
        slow_categories = []
        for category, duration in performance_data['test_durations'].items():
            if duration > 10.0:  # Consider > 10s as slow
                slow_categories.append((category, duration))

        if slow_categories:
            print("⚠️  Slow test categories detected:")
            for category, duration in slow_categories:
                print(f"   {category}: {duration:.2f}s")
        else:
            print("✅ All test categories completed within acceptable time")

        # Save performance report
        perf_file = self.backend_dir / 'initialization_performance_report.json'
        with open(perf_file, 'w') as f:
            json.dump(performance_data, f, indent=2)

        print(f"📄 Performance report saved to: {perf_file}")

    def run_specific_category(self, category):
        """Run tests for a specific category."""
        category_map = {
            'config': 'test_config_initialization.py',
            'auth': 'test_auth_initialization.py',
            'middleware': 'test_middleware_initialization.py',
            'service': 'test_service_initialization.py',
            'edge': 'test_initialization_edge_cases.py',
            'performance': 'test_initialization_performance.py',
            'integration': '../integration/initialization/test_system_startup_integration.py'
        }

        if category not in category_map:
            print(f"❌ Unknown category: {category}")
            print(f"Available categories: {', '.join(category_map.keys())}")
            return False

        test_file = category_map[category]
        print(f"🚀 Running {category} tests...")

        result = self._run_test_file(test_file)

        if result['success']:
            print(f"✅ {category} tests: PASSED ({result['passed']}/{result['total']})")
        else:
            print(f"❌ {category} tests: FAILED ({result['failed']} failures)")

        if self.verbose and result['output']:
            print(f"\nOutput:\n{result['output']}")

        return result['success']


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run initialization system tests')

    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--no-coverage', action='store_true',
                       help='Skip coverage report generation')
    parser.add_argument('--no-performance', action='store_true',
                       help='Skip performance analysis')
    parser.add_argument('--category', '-c',
                       choices=['config', 'auth', 'middleware', 'service', 'edge', 'performance', 'integration'],
                       help='Run specific test category only')
    parser.add_argument('--quick', '-q', action='store_true',
                       help='Quick test run (no coverage, no performance)')

    args = parser.parse_args()

    # Configure test runner
    coverage = not (args.no_coverage or args.quick)
    performance = not (args.no_performance or args.quick)

    runner = InitializationTestRunner(
        verbose=args.verbose,
        coverage=coverage,
        performance=performance
    )

    # Run tests
    if args.category:
        success = runner.run_specific_category(args.category)
    else:
        success = runner.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()