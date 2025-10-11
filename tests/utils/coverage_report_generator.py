"""
Comprehensive Test Coverage Report Generator
==========================================

This utility generates comprehensive test coverage reports and quality metrics
for the oncology clinic system, providing insights into test effectiveness
and areas needing additional coverage.

Features:
- Code coverage analysis
- Test execution metrics
- Quality score calculation
- Coverage gap identification
- Performance metrics
- Security test coverage
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import xml.etree.ElementTree as ET


class TestCoverageAnalyzer:
    """Analyzes test coverage and generates comprehensive reports."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backend_root = self.project_root / "backend-hormonia"
        self.frontend_root = self.project_root / "frontend-hormonia"
        self.tests_root = self.project_root / "tests"

    def generate_backend_coverage(self) -> Dict[str, Any]:
        """Generate backend test coverage report."""
        try:
            # Run pytest with coverage
            result = subprocess.run([
                "python", "-m", "pytest",
                "--cov=app",
                "--cov-report=json",
                "--cov-report=html",
                "--cov-report=xml",
                "--cov-fail-under=80",
                str(self.tests_root)
            ], cwd=self.backend_root, capture_output=True, text=True)

            coverage_data = self._parse_coverage_json()

            return {
                "status": "success" if result.returncode == 0 else "warning",
                "overall_coverage": coverage_data.get("totals", {}).get("percent_covered", 0),
                "line_coverage": coverage_data.get("totals", {}).get("covered_lines", 0),
                "total_lines": coverage_data.get("totals", {}).get("num_statements", 0),
                "files": self._analyze_file_coverage(coverage_data),
                "test_execution_time": self._extract_execution_time(result.stdout),
                "failed_tests": self._extract_failed_tests(result.stdout),
                "coverage_report_path": str(self.backend_root / "htmlcov" / "index.html")
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "overall_coverage": 0
            }

    def generate_frontend_coverage(self) -> Dict[str, Any]:
        """Generate frontend test coverage report."""
        try:
            # Run Vitest with coverage
            result = subprocess.run([
                "npm", "run", "test:coverage"
            ], cwd=self.frontend_root, capture_output=True, text=True)

            # Parse coverage report (assumes istanbul/c8 format)
            coverage_summary = self._parse_frontend_coverage()

            return {
                "status": "success" if result.returncode == 0 else "warning",
                "overall_coverage": coverage_summary.get("total", {}).get("lines", {}).get("pct", 0),
                "line_coverage": coverage_summary.get("total", {}).get("lines", {}).get("covered", 0),
                "branch_coverage": coverage_summary.get("total", {}).get("branches", {}).get("pct", 0),
                "function_coverage": coverage_summary.get("total", {}).get("functions", {}).get("pct", 0),
                "files": self._analyze_frontend_file_coverage(coverage_summary),
                "test_execution_time": self._extract_frontend_execution_time(result.stdout),
                "coverage_report_path": str(self.frontend_root / "coverage" / "index.html")
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "overall_coverage": 0
            }

    def generate_e2e_coverage(self) -> Dict[str, Any]:
        """Generate E2E test coverage report."""
        try:
            # Run Playwright tests
            result = subprocess.run([
                "npx", "playwright", "test", "--reporter=json"
            ], cwd=self.frontend_root, capture_output=True, text=True)

            e2e_results = self._parse_e2e_results(result.stdout)

            return {
                "status": "success" if result.returncode == 0 else "warning",
                "total_tests": e2e_results.get("total_tests", 0),
                "passed_tests": e2e_results.get("passed", 0),
                "failed_tests": e2e_results.get("failed", 0),
                "skipped_tests": e2e_results.get("skipped", 0),
                "success_rate": e2e_results.get("success_rate", 0),
                "average_duration": e2e_results.get("average_duration", 0),
                "test_execution_time": e2e_results.get("total_duration", 0)
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "total_tests": 0
            }

    def analyze_test_quality(self) -> Dict[str, Any]:
        """Analyze overall test quality and coverage gaps."""
        backend_coverage = self.generate_backend_coverage()
        frontend_coverage = self.generate_frontend_coverage()
        e2e_coverage = self.generate_e2e_coverage()

        # Calculate quality scores
        quality_metrics = {
            "backend_score": self._calculate_backend_quality_score(backend_coverage),
            "frontend_score": self._calculate_frontend_quality_score(frontend_coverage),
            "e2e_score": self._calculate_e2e_quality_score(e2e_coverage),
            "overall_score": 0
        }

        # Calculate overall score
        quality_metrics["overall_score"] = (
            quality_metrics["backend_score"] * 0.4 +
            quality_metrics["frontend_score"] * 0.4 +
            quality_metrics["e2e_score"] * 0.2
        )

        # Identify coverage gaps
        coverage_gaps = self._identify_coverage_gaps(backend_coverage, frontend_coverage)

        # Security test coverage
        security_coverage = self._analyze_security_test_coverage()

        # Performance test coverage
        performance_coverage = self._analyze_performance_test_coverage()

        return {
            "timestamp": datetime.now().isoformat(),
            "quality_metrics": quality_metrics,
            "backend_coverage": backend_coverage,
            "frontend_coverage": frontend_coverage,
            "e2e_coverage": e2e_coverage,
            "coverage_gaps": coverage_gaps,
            "security_coverage": security_coverage,
            "performance_coverage": performance_coverage,
            "recommendations": self._generate_recommendations(quality_metrics, coverage_gaps)
        }

    def generate_html_report(self, analysis_data: Dict[str, Any]) -> str:
        """Generate HTML coverage report."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Coverage Report - Oncology Clinic System</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #f0f0f0; padding: 20px; border-radius: 5px; }
                .metric { display: inline-block; margin: 10px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                .coverage-high { background: #d4edda; }
                .coverage-medium { background: #fff3cd; }
                .coverage-low { background: #f8d7da; }
                .section { margin: 20px 0; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Test Coverage Report</h1>
                <p>Generated: {timestamp}</p>
                <p>Overall Quality Score: <strong>{overall_score:.1f}/100</strong></p>
            </div>

            <div class="section">
                <h2>Coverage Summary</h2>
                <div class="metric {backend_class}">
                    <h3>Backend Coverage</h3>
                    <p>{backend_coverage:.1f}%</p>
                </div>
                <div class="metric {frontend_class}">
                    <h3>Frontend Coverage</h3>
                    <p>{frontend_coverage:.1f}%</p>
                </div>
                <div class="metric {e2e_class}">
                    <h3>E2E Test Success</h3>
                    <p>{e2e_success:.1f}%</p>
                </div>
            </div>

            <div class="section">
                <h2>Backend Coverage Details</h2>
                <table>
                    <tr>
                        <th>File</th>
                        <th>Line Coverage</th>
                        <th>Branch Coverage</th>
                        <th>Status</th>
                    </tr>
                    {backend_files}
                </table>
            </div>

            <div class="section">
                <h2>Frontend Coverage Details</h2>
                <table>
                    <tr>
                        <th>File</th>
                        <th>Line Coverage</th>
                        <th>Function Coverage</th>
                        <th>Status</th>
                    </tr>
                    {frontend_files}
                </table>
            </div>

            <div class="section">
                <h2>Coverage Gaps</h2>
                <ul>
                    {coverage_gaps}
                </ul>
            </div>

            <div class="section">
                <h2>Recommendations</h2>
                <ul>
                    {recommendations}
                </ul>
            </div>

            <div class="section">
                <h2>Security Test Coverage</h2>
                <p>Security tests implemented: {security_tests}</p>
                <p>Critical security areas covered: {security_coverage:.1f}%</p>
            </div>

            <div class="section">
                <h2>Performance Test Coverage</h2>
                <p>Performance tests implemented: {performance_tests}</p>
                <p>Critical performance areas covered: {performance_coverage:.1f}%</p>
            </div>
        </body>
        </html>
        """

        # Prepare template data
        template_data = self._prepare_html_template_data(analysis_data)

        # Generate HTML
        html_content = html_template.format(**template_data)

        # Save HTML report
        report_path = self.project_root / "test-coverage-report.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return str(report_path)

    def _parse_coverage_json(self) -> Dict[str, Any]:
        """Parse coverage.json file generated by pytest-cov."""
        coverage_file = self.backend_root / "coverage.json"
        if coverage_file.exists():
            with open(coverage_file, 'r') as f:
                return json.load(f)
        return {}

    def _parse_frontend_coverage(self) -> Dict[str, Any]:
        """Parse frontend coverage summary."""
        coverage_file = self.frontend_root / "coverage" / "coverage-summary.json"
        if coverage_file.exists():
            with open(coverage_file, 'r') as f:
                return json.load(f)
        return {}

    def _analyze_file_coverage(self, coverage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze coverage for individual files."""
        files = []
        for file_path, file_data in coverage_data.get("files", {}).items():
            summary = file_data.get("summary", {})
            files.append({
                "path": file_path,
                "line_coverage": summary.get("percent_covered", 0),
                "covered_lines": summary.get("covered_lines", 0),
                "total_lines": summary.get("num_statements", 0),
                "missing_lines": file_data.get("missing_lines", [])
            })
        return sorted(files, key=lambda x: x["line_coverage"])

    def _analyze_frontend_file_coverage(self, coverage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze frontend file coverage."""
        files = []
        for file_path, file_data in coverage_data.items():
            if file_path != "total":
                files.append({
                    "path": file_path,
                    "line_coverage": file_data.get("lines", {}).get("pct", 0),
                    "function_coverage": file_data.get("functions", {}).get("pct", 0),
                    "branch_coverage": file_data.get("branches", {}).get("pct", 0)
                })
        return sorted(files, key=lambda x: x["line_coverage"])

    def _calculate_backend_quality_score(self, coverage: Dict[str, Any]) -> float:
        """Calculate backend quality score."""
        if coverage.get("status") == "error":
            return 0.0

        line_coverage = coverage.get("overall_coverage", 0)
        test_success = 100 if coverage.get("failed_tests", 0) == 0 else 80

        return (line_coverage * 0.7 + test_success * 0.3)

    def _calculate_frontend_quality_score(self, coverage: Dict[str, Any]) -> float:
        """Calculate frontend quality score."""
        if coverage.get("status") == "error":
            return 0.0

        line_coverage = coverage.get("overall_coverage", 0)
        branch_coverage = coverage.get("branch_coverage", 0)
        function_coverage = coverage.get("function_coverage", 0)

        return (line_coverage * 0.4 + branch_coverage * 0.3 + function_coverage * 0.3)

    def _calculate_e2e_quality_score(self, e2e_data: Dict[str, Any]) -> float:
        """Calculate E2E test quality score."""
        if e2e_data.get("status") == "error":
            return 0.0

        success_rate = e2e_data.get("success_rate", 0)
        test_count_score = min(100, e2e_data.get("total_tests", 0) * 10)  # 10 points per test, max 100

        return (success_rate * 0.8 + test_count_score * 0.2)

    def _identify_coverage_gaps(self, backend: Dict[str, Any], frontend: Dict[str, Any]) -> List[str]:
        """Identify areas with insufficient test coverage."""
        gaps = []

        # Backend gaps
        if backend.get("overall_coverage", 0) < 80:
            gaps.append("Backend overall coverage below 80%")

        backend_files = backend.get("files", [])
        low_coverage_files = [f for f in backend_files if f["line_coverage"] < 60]
        if low_coverage_files:
            gaps.append(f"Backend files with low coverage: {len(low_coverage_files)} files")

        # Frontend gaps
        if frontend.get("overall_coverage", 0) < 80:
            gaps.append("Frontend overall coverage below 80%")

        if frontend.get("branch_coverage", 0) < 70:
            gaps.append("Frontend branch coverage below 70%")

        # Specific area gaps
        if not self._has_adequate_security_tests():
            gaps.append("Insufficient security test coverage")

        if not self._has_adequate_performance_tests():
            gaps.append("Insufficient performance test coverage")

        return gaps

    def _analyze_security_test_coverage(self) -> Dict[str, Any]:
        """Analyze security test coverage."""
        security_test_areas = [
            "authentication",
            "authorization",
            "input_validation",
            "sql_injection",
            "xss_protection",
            "csrf_protection",
            "rate_limiting"
        ]

        covered_areas = []

        # Check if security test file exists and analyze content
        security_test_file = self.tests_root / "integration" / "api_security_rate_limiting.test.py"
        if security_test_file.exists():
            with open(security_test_file, 'r') as f:
                content = f.read().lower()

            for area in security_test_areas:
                if area.replace("_", " ") in content or area in content:
                    covered_areas.append(area)

        return {
            "total_areas": len(security_test_areas),
            "covered_areas": len(covered_areas),
            "coverage_percentage": (len(covered_areas) / len(security_test_areas)) * 100,
            "covered_areas_list": covered_areas,
            "missing_areas": [area for area in security_test_areas if area not in covered_areas]
        }

    def _analyze_performance_test_coverage(self) -> Dict[str, Any]:
        """Analyze performance test coverage."""
        performance_test_areas = [
            "load_testing",
            "stress_testing",
            "api_response_time",
            "database_performance",
            "memory_usage",
            "concurrent_requests"
        ]

        covered_areas = []

        # Check if performance test file exists
        perf_test_file = self.tests_root / "performance" / "railway_deployment_load_tests.py"
        if perf_test_file.exists():
            with open(perf_test_file, 'r') as f:
                content = f.read().lower()

            for area in performance_test_areas:
                if area.replace("_", " ") in content or area in content:
                    covered_areas.append(area)

        return {
            "total_areas": len(performance_test_areas),
            "covered_areas": len(covered_areas),
            "coverage_percentage": (len(covered_areas) / len(performance_test_areas)) * 100,
            "covered_areas_list": covered_areas
        }

    def _generate_recommendations(self, quality_metrics: Dict[str, Any], gaps: List[str]) -> List[str]:
        """Generate recommendations for improving test coverage."""
        recommendations = []

        # Backend recommendations
        if quality_metrics["backend_score"] < 80:
            recommendations.append("Increase backend test coverage by adding unit tests for uncovered modules")
            recommendations.append("Focus on testing error handling and edge cases")

        # Frontend recommendations
        if quality_metrics["frontend_score"] < 80:
            recommendations.append("Add more frontend component tests with user interaction scenarios")
            recommendations.append("Improve branch coverage by testing all conditional logic paths")

        # E2E recommendations
        if quality_metrics["e2e_score"] < 70:
            recommendations.append("Add more end-to-end test scenarios covering critical user workflows")
            recommendations.append("Test error scenarios and edge cases in E2E tests")

        # Security recommendations
        if "security test coverage" in " ".join(gaps).lower():
            recommendations.append("Implement comprehensive security tests including OWASP Top 10 scenarios")
            recommendations.append("Add penetration testing and vulnerability scanning")

        # Performance recommendations
        if "performance test coverage" in " ".join(gaps).lower():
            recommendations.append("Add load testing for high-traffic scenarios")
            recommendations.append("Implement monitoring and alerting for performance regressions")

        return recommendations

    def _has_adequate_security_tests(self) -> bool:
        """Check if adequate security tests are present."""
        security_test_file = self.tests_root / "integration" / "api_security_rate_limiting.test.py"
        return security_test_file.exists()

    def _has_adequate_performance_tests(self) -> bool:
        """Check if adequate performance tests are present."""
        performance_test_file = self.tests_root / "performance" / "railway_deployment_load_tests.py"
        return performance_test_file.exists()

    def _prepare_html_template_data(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for HTML template."""
        backend = analysis_data.get("backend_coverage", {})
        frontend = analysis_data.get("frontend_coverage", {})
        e2e = analysis_data.get("e2e_coverage", {})
        security = analysis_data.get("security_coverage", {})
        performance = analysis_data.get("performance_coverage", {})

        def get_coverage_class(coverage):
            if coverage >= 80:
                return "coverage-high"
            elif coverage >= 60:
                return "coverage-medium"
            else:
                return "coverage-low"

        return {
            "timestamp": analysis_data.get("timestamp", ""),
            "overall_score": analysis_data.get("quality_metrics", {}).get("overall_score", 0),
            "backend_coverage": backend.get("overall_coverage", 0),
            "frontend_coverage": frontend.get("overall_coverage", 0),
            "e2e_success": e2e.get("success_rate", 0),
            "backend_class": get_coverage_class(backend.get("overall_coverage", 0)),
            "frontend_class": get_coverage_class(frontend.get("overall_coverage", 0)),
            "e2e_class": get_coverage_class(e2e.get("success_rate", 0)),
            "backend_files": self._format_backend_files_html(backend.get("files", [])),
            "frontend_files": self._format_frontend_files_html(frontend.get("files", [])),
            "coverage_gaps": "\n".join(f"<li>{gap}</li>" for gap in analysis_data.get("coverage_gaps", [])),
            "recommendations": "\n".join(f"<li>{rec}</li>" for rec in analysis_data.get("recommendations", [])),
            "security_tests": security.get("covered_areas", 0),
            "security_coverage": security.get("coverage_percentage", 0),
            "performance_tests": performance.get("covered_areas", 0),
            "performance_coverage": performance.get("coverage_percentage", 0)
        }

    def _format_backend_files_html(self, files: List[Dict[str, Any]]) -> str:
        """Format backend files for HTML table."""
        rows = []
        for file_data in files[:10]:  # Show top 10 files
            status = "Good" if file_data["line_coverage"] >= 80 else "Needs Improvement"
            rows.append(f"""
                <tr>
                    <td>{file_data['path']}</td>
                    <td>{file_data['line_coverage']:.1f}%</td>
                    <td>N/A</td>
                    <td>{status}</td>
                </tr>
            """)
        return "\n".join(rows)

    def _format_frontend_files_html(self, files: List[Dict[str, Any]]) -> str:
        """Format frontend files for HTML table."""
        rows = []
        for file_data in files[:10]:  # Show top 10 files
            status = "Good" if file_data["line_coverage"] >= 80 else "Needs Improvement"
            rows.append(f"""
                <tr>
                    <td>{file_data['path']}</td>
                    <td>{file_data['line_coverage']:.1f}%</td>
                    <td>{file_data['function_coverage']:.1f}%</td>
                    <td>{status}</td>
                </tr>
            """)
        return "\n".join(rows)

    def _extract_execution_time(self, stdout: str) -> float:
        """Extract test execution time from pytest output."""
        # This would parse pytest output for timing information
        return 0.0

    def _extract_failed_tests(self, stdout: str) -> int:
        """Extract number of failed tests from pytest output."""
        # This would parse pytest output for failure count
        return 0

    def _extract_frontend_execution_time(self, stdout: str) -> float:
        """Extract frontend test execution time."""
        # This would parse Vitest output for timing information
        return 0.0

    def _parse_e2e_results(self, stdout: str) -> Dict[str, Any]:
        """Parse E2E test results from Playwright output."""
        # This would parse Playwright JSON output
        return {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "success_rate": 0,
            "average_duration": 0,
            "total_duration": 0
        }


def main():
    """Generate comprehensive test coverage report."""
    project_root = os.getcwd()
    analyzer = TestCoverageAnalyzer(project_root)

    print("Generating comprehensive test coverage report...")

    # Generate analysis
    analysis = analyzer.analyze_test_quality()

    # Generate HTML report
    html_path = analyzer.generate_html_report(analysis)

    # Generate JSON report
    json_path = Path(project_root) / "test-coverage-report.json"
    with open(json_path, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)

    # Print summary
    print(f"\nTest Coverage Analysis Complete!")
    print(f"Overall Quality Score: {analysis['quality_metrics']['overall_score']:.1f}/100")
    print(f"Backend Coverage: {analysis['backend_coverage'].get('overall_coverage', 0):.1f}%")
    print(f"Frontend Coverage: {analysis['frontend_coverage'].get('overall_coverage', 0):.1f}%")
    print(f"E2E Success Rate: {analysis['e2e_coverage'].get('success_rate', 0):.1f}%")
    print(f"\nReports generated:")
    print(f"  HTML: {html_path}")
    print(f"  JSON: {json_path}")

    # Print recommendations
    recommendations = analysis.get('recommendations', [])
    if recommendations:
        print(f"\nRecommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")


if __name__ == "__main__":
    main()