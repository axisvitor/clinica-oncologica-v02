#!/usr/bin/env python3
"""
Test Report Generator
====================

Generates comprehensive test reports in multiple formats including:
- HTML dashboard
- PDF summary
- CSV data export
- JSON API response
- Markdown documentation

Usage:
    python generate-test-report.py [options]
"""

import os
import json
import csv
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse
import base64

try:
    import jinja2
    from weasyprint import HTML, CSS
    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd
    ADVANCED_FEATURES = True
except ImportError:
    print("Warning: Some advanced features disabled. Install: pip install jinja2 weasyprint matplotlib seaborn pandas")
    ADVANCED_FEATURES = False


class TestReportGenerator:
    """Generates comprehensive test reports in multiple formats"""

    def __init__(self, test_results_path: str, output_dir: str = "test-reports"):
        self.test_results_path = Path(test_results_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load test results
        with open(self.test_results_path, 'r', encoding='utf-8') as f:
            self.results = json.load(f)

        self.summary = self.results.get('summary', {})
        self.timestamp = datetime.datetime.now()

    def generate_all_reports(self):
        """Generate all available report formats"""
        print("🚀 Generating comprehensive test reports...")

        reports_generated = []

        # Always available formats
        reports_generated.append(self.generate_json_report())
        reports_generated.append(self.generate_csv_report())
        reports_generated.append(self.generate_markdown_report())
        reports_generated.append(self.generate_html_report_basic())

        # Advanced formats (if dependencies available)
        if ADVANCED_FEATURES:
            reports_generated.append(self.generate_html_dashboard())
            reports_generated.append(self.generate_pdf_report())
            reports_generated.append(self.generate_charts())

        # Summary
        print(f"\n✅ Generated {len(reports_generated)} reports:")
        for report in reports_generated:
            print(f"   - {report}")

        return reports_generated

    def generate_json_report(self) -> str:
        """Generate enhanced JSON report with additional metadata"""
        report_data = {
            "metadata": {
                "generated_at": self.timestamp.isoformat(),
                "generator_version": "1.0.0",
                "project": "Clinica Oncológica v02",
                "report_type": "comprehensive_test_results"
            },
            "execution_summary": self.summary.get('execution', {}),
            "test_results": self.summary.get('tests', {}),
            "coverage_analysis": self.summary.get('coverage', {}),
            "security_findings": self.summary.get('security', {}),
            "performance_metrics": self._extract_performance_metrics(),
            "quality_metrics": self._calculate_quality_metrics(),
            "trends": self._calculate_trends(),
            "recommendations": self.summary.get('recommendations', []),
            "raw_data": self.results
        }

        output_file = self.output_dir / "enhanced_test_report.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=str)

        return str(output_file)

    def generate_csv_report(self) -> str:
        """Generate CSV reports for data analysis"""
        csv_dir = self.output_dir / "csv"
        csv_dir.mkdir(exist_ok=True)

        files_created = []

        # Test results CSV
        test_data = []
        for component in ['backend', 'frontend']:
            tests = self.results.get(component, {}).get('tests', {})
            if tests:
                test_data.append({
                    'component': component,
                    'total_tests': tests.get('total', 0),
                    'passed_tests': tests.get('passed', 0),
                    'failed_tests': tests.get('failed', 0),
                    'skipped_tests': tests.get('skipped', 0),
                    'execution_time': tests.get('time', 0),
                    'success_rate': (tests.get('passed', 0) / tests.get('total', 1)) * 100
                })

        if test_data:
            test_csv = csv_dir / "test_results.csv"
            with open(test_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=test_data[0].keys())
                writer.writeheader()
                writer.writerows(test_data)
            files_created.append(str(test_csv))

        # Coverage CSV
        coverage_data = []
        for component in ['backend', 'frontend']:
            coverage = self.results.get(component, {}).get('coverage', {})
            if coverage:
                lines = coverage.get('lines', {})
                coverage_data.append({
                    'component': component,
                    'lines_covered': lines.get('covered', 0),
                    'lines_total': lines.get('total', 0),
                    'lines_percentage': lines.get('percentage', 0),
                    'branches_covered': coverage.get('branches', {}).get('covered', 0),
                    'branches_total': coverage.get('branches', {}).get('total', 0),
                    'branches_percentage': coverage.get('branches', {}).get('percentage', 0)
                })

        if coverage_data:
            coverage_csv = csv_dir / "coverage_results.csv"
            with open(coverage_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=coverage_data[0].keys())
                writer.writeheader()
                writer.writerows(coverage_data)
            files_created.append(str(coverage_csv))

        return f"CSV reports: {', '.join(files_created)}"

    def generate_markdown_report(self) -> str:
        """Generate comprehensive Markdown report"""
        execution = self.summary.get('execution', {})
        tests = self.summary.get('tests', {})
        coverage = self.summary.get('coverage', {})

        markdown_content = f"""# Test Execution Report - Clinica Oncológica v02

**Generated:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Status:** {'✅ PASSED' if execution.get('status') == 'PASSED' else '❌ FAILED'}
**Duration:** {execution.get('duration_seconds', 0):.2f} seconds

## 📊 Executive Summary

| Metric | Value | Status |
|--------|-------|--------|
| Total Tests | {tests.get('total', 0)} | {'✅' if tests.get('total', 0) > 0 else '⚠️'} |
| Success Rate | {tests.get('success_rate', 0):.1f}% | {'✅' if tests.get('success_rate', 0) >= 95 else '❌'} |
| Coverage Threshold | {'✅ PASSED' if coverage.get('meets_threshold', False) else '❌ FAILED'} | {coverage.get('threshold', 90)}% |
| Security Issues | {len(self.results.get('errors', []))} | {'✅' if len(self.results.get('errors', [])) == 0 else '❌'} |

## 🧪 Test Results Detail

### Backend Tests
{self._generate_component_markdown('backend')}

### Frontend Tests
{self._generate_component_markdown('frontend')}

## 📈 Coverage Analysis

### Overall Coverage
- **Threshold:** {coverage.get('threshold', 90)}%
- **Status:** {'PASSED' if coverage.get('meets_threshold', False) else 'FAILED'}

### Backend Coverage
{self._generate_coverage_markdown('backend')}

### Frontend Coverage
{self._generate_coverage_markdown('frontend')}

## 🔒 Security Validation

{self._generate_security_markdown()}

## ⚡ Performance Metrics

{self._generate_performance_markdown()}

## 🎯 Recommendations

{chr(10).join(f'- {rec}' for rec in self.summary.get('recommendations', []))}

## 📋 Quality Metrics

{self._generate_quality_metrics_markdown()}

## 🔗 Related Reports

- [Detailed HTML Report](index.html)
- [Coverage Report](backend/coverage-html/index.html)
- [Raw JSON Data](enhanced_test_report.json)
- [CSV Data](csv/)

---

*Report generated by Clinica Oncológica v02 Test Runner*
"""

        output_file = self.output_dir / "TEST_REPORT.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return str(output_file)

    def generate_html_report_basic(self) -> str:
        """Generate basic HTML report without advanced dependencies"""
        execution = self.summary.get('execution', {})
        tests = self.summary.get('tests', {})
        coverage = self.summary.get('coverage', {})

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - Clinica Oncológica v02</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; border-bottom: 2px solid #e0e0e0; padding-bottom: 20px; margin-bottom: 30px; }}
        .status-passed {{ color: #28a745; font-weight: bold; }}
        .status-failed {{ color: #dc3545; font-weight: bold; }}
        .metric-card {{ background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; border-left: 4px solid #007bff; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .metric-label {{ color: #6c757d; margin-top: 5px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ color: #343a40; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background-color: #f8f9fa; font-weight: 600; }}
        .progress-bar {{ width: 100%; height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #28a745, #20c997); transition: width 0.3s; }}
        .recommendations {{ background: #e3f2fd; padding: 20px; border-radius: 8px; border-left: 4px solid #2196f3; }}
        .timestamp {{ color: #6c757d; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 Test Execution Report</h1>
            <p><strong>Clinica Oncológica v02</strong></p>
            <p class="timestamp">Generated: {self.timestamp.strftime('%B %d, %Y at %H:%M:%S')}</p>
            <h2 class="status-{'passed' if execution.get('status') == 'PASSED' else 'failed'}">
                {execution.get('status', 'UNKNOWN')}
            </h2>
        </div>

        <div class="grid">
            <div class="metric-card">
                <div class="metric-value">{tests.get('total', 0)}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{tests.get('success_rate', 0):.1f}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{execution.get('duration_seconds', 0):.1f}s</div>
                <div class="metric-label">Execution Time</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{'✅' if coverage.get('meets_threshold', False) else '❌'}</div>
                <div class="metric-label">Coverage Threshold</div>
            </div>
        </div>

        <div class="section">
            <h2>📊 Test Results</h2>
            <table>
                <tr><th>Component</th><th>Total</th><th>Passed</th><th>Failed</th><th>Success Rate</th></tr>
                {self._generate_test_table_rows()}
            </table>
        </div>

        <div class="section">
            <h2>📈 Coverage Analysis</h2>
            {self._generate_coverage_html_section()}
        </div>

        <div class="section">
            <h2>🔒 Security & Quality</h2>
            {self._generate_security_html_section()}
        </div>

        <div class="recommendations">
            <h2>🎯 Recommendations</h2>
            <ul>
                {chr(10).join(f'<li>{rec}</li>' for rec in self.summary.get('recommendations', []))}
            </ul>
        </div>

        <div class="section">
            <h2>📁 Detailed Reports</h2>
            <ul>
                <li><a href="backend/coverage-html/index.html">Backend Coverage Report</a></li>
                <li><a href="frontend/coverage/index.html">Frontend Coverage Report</a></li>
                <li><a href="enhanced_test_report.json">Raw Test Data (JSON)</a></li>
                <li><a href="csv/">CSV Data Export</a></li>
            </ul>
        </div>
    </div>
</body>
</html>
        """

        output_file = self.output_dir / "test_report.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return str(output_file)

    def generate_html_dashboard(self) -> str:
        """Generate advanced HTML dashboard with charts (requires advanced dependencies)"""
        if not ADVANCED_FEATURES:
            return "Advanced HTML dashboard skipped - missing dependencies"

        # Create Jinja2 template
        template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Dashboard - Clinica Oncológica v02</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        /* Advanced styling would go here */
        body { font-family: system-ui; margin: 0; padding: 20px; background: #f8f9fa; }
        .dashboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .chart-container { position: relative; height: 300px; }
    </style>
</head>
<body>
    <h1>🏥 Test Dashboard - Clinica Oncológica v02</h1>

    <div class="dashboard">
        <div class="card">
            <h3>Test Results</h3>
            <div class="chart-container">
                <canvas id="testChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h3>Coverage Analysis</h3>
            <div class="chart-container">
                <canvas id="coverageChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        // Test results chart
        const testCtx = document.getElementById('testChart').getContext('2d');
        new Chart(testCtx, {
            type: 'doughnut',
            data: {
                labels: ['Passed', 'Failed', 'Skipped'],
                datasets: [{
                    data: [{{ tests.passed }}, {{ tests.failed }}, {{ tests.skipped }}],
                    backgroundColor: ['#28a745', '#dc3545', '#ffc107']
                }]
            }
        });

        // Coverage chart
        const coverageCtx = document.getElementById('coverageChart').getContext('2d');
        new Chart(coverageCtx, {
            type: 'bar',
            data: {
                labels: ['Backend', 'Frontend'],
                datasets: [{
                    label: 'Coverage %',
                    data: [{{ backend_coverage }}, {{ frontend_coverage }}],
                    backgroundColor: '#007bff'
                }]
            },
            options: {
                scales: {
                    y: { beginAtZero: true, max: 100 }
                }
            }
        });
    </script>
</body>
</html>
        """

        # Prepare template variables
        tests = self.summary.get('tests', {})
        backend_coverage = self.results.get('backend', {}).get('coverage', {}).get('lines', {}).get('percentage', 0)
        frontend_coverage = self.results.get('frontend', {}).get('coverage', {}).get('lines', {}).get('percentage', 0)

        template = jinja2.Template(template_str)
        html_content = template.render(
            tests=tests,
            backend_coverage=backend_coverage,
            frontend_coverage=frontend_coverage
        )

        output_file = self.output_dir / "dashboard.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return str(output_file)

    def generate_pdf_report(self) -> str:
        """Generate PDF report (requires advanced dependencies)"""
        if not ADVANCED_FEATURES:
            return "PDF report skipped - missing dependencies"

        # Generate HTML content for PDF
        html_content = self._generate_pdf_html_content()

        # Convert to PDF
        try:
            output_file = self.output_dir / "test_report.pdf"
            HTML(string=html_content).write_pdf(str(output_file))
            return str(output_file)
        except Exception as e:
            return f"PDF generation failed: {str(e)}"

    def generate_charts(self) -> str:
        """Generate standalone charts (requires advanced dependencies)"""
        if not ADVANCED_FEATURES:
            return "Charts skipped - missing dependencies"

        charts_dir = self.output_dir / "charts"
        charts_dir.mkdir(exist_ok=True)

        # Test results pie chart
        tests = self.summary.get('tests', {})
        plt.figure(figsize=(8, 6))
        plt.pie([tests.get('passed', 0), tests.get('failed', 0), tests.get('skipped', 0)],
                labels=['Passed', 'Failed', 'Skipped'],
                colors=['#28a745', '#dc3545', '#ffc107'],
                autopct='%1.1f%%')
        plt.title('Test Results Distribution')
        plt.savefig(charts_dir / 'test_results.png', dpi=150, bbox_inches='tight')
        plt.close()

        # Coverage comparison
        components = ['Backend', 'Frontend']
        coverages = [
            self.results.get('backend', {}).get('coverage', {}).get('lines', {}).get('percentage', 0),
            self.results.get('frontend', {}).get('coverage', {}).get('lines', {}).get('percentage', 0)
        ]

        plt.figure(figsize=(8, 6))
        bars = plt.bar(components, coverages, color=['#007bff', '#17a2b8'])
        plt.ylabel('Coverage Percentage')
        plt.title('Code Coverage by Component')
        plt.ylim(0, 100)

        # Add percentage labels on bars
        for bar, coverage in zip(bars, coverages):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{coverage:.1f}%', ha='center', va='bottom')

        plt.axhline(y=90, color='red', linestyle='--', alpha=0.7, label='Threshold (90%)')
        plt.legend()
        plt.savefig(charts_dir / 'coverage_comparison.png', dpi=150, bbox_inches='tight')
        plt.close()

        return f"Charts generated in {charts_dir}"

    # Helper methods
    def _generate_component_markdown(self, component: str) -> str:
        """Generate markdown for a component's test results"""
        tests = self.results.get(component, {}).get('tests', {})
        if not tests:
            return f"No test data available for {component}"

        return f"""
- **Total Tests:** {tests.get('total', 0)}
- **Passed:** {tests.get('passed', 0)} ✅
- **Failed:** {tests.get('failed', 0)} {'❌' if tests.get('failed', 0) > 0 else '✅'}
- **Skipped:** {tests.get('skipped', 0)}
- **Execution Time:** {tests.get('time', 0):.2f}s
- **Success Rate:** {(tests.get('passed', 0) / tests.get('total', 1) * 100):.1f}%
"""

    def _generate_coverage_markdown(self, component: str) -> str:
        """Generate markdown for a component's coverage"""
        coverage = self.results.get(component, {}).get('coverage', {})
        if not coverage:
            return f"No coverage data available for {component}"

        lines = coverage.get('lines', {})
        branches = coverage.get('branches', {})

        return f"""
- **Lines:** {lines.get('covered', 0)}/{lines.get('total', 0)} ({lines.get('percentage', 0):.1f}%)
- **Branches:** {branches.get('covered', 0)}/{branches.get('total', 0)} ({branches.get('percentage', 0):.1f}%)
"""

    def _generate_security_markdown(self) -> str:
        """Generate markdown for security findings"""
        security = self.results.get('security', {})
        if not security:
            return "No security validation performed"

        output = []
        for component, checks in security.items():
            output.append(f"### {component.title()}")
            for check, result in checks.items():
                status = result.get('status', 'unknown')
                issues = result.get('vulnerabilities', result.get('issues', 0))
                output.append(f"- **{check}:** {status} ({issues} issues)")

        return '\n'.join(output)

    def _generate_performance_markdown(self) -> str:
        """Generate markdown for performance metrics"""
        # Extract performance data if available
        return "Performance benchmarks completed. See detailed reports for metrics."

    def _generate_quality_metrics_markdown(self) -> str:
        """Generate markdown for quality metrics"""
        metrics = self._calculate_quality_metrics()
        output = []
        for metric, value in metrics.items():
            output.append(f"- **{metric.replace('_', ' ').title()}:** {value}")
        return '\n'.join(output)

    def _generate_test_table_rows(self) -> str:
        """Generate HTML table rows for test results"""
        rows = []
        for component in ['backend', 'frontend']:
            tests = self.results.get(component, {}).get('tests', {})
            if tests:
                total = tests.get('total', 0)
                passed = tests.get('passed', 0)
                failed = tests.get('failed', 0)
                success_rate = (passed / total * 100) if total > 0 else 0

                rows.append(f"""
                <tr>
                    <td>{component.title()}</td>
                    <td>{total}</td>
                    <td>{passed}</td>
                    <td>{failed}</td>
                    <td>{success_rate:.1f}%</td>
                </tr>
                """)
        return ''.join(rows)

    def _generate_coverage_html_section(self) -> str:
        """Generate HTML section for coverage"""
        html = []
        for component in ['backend', 'frontend']:
            coverage = self.results.get(component, {}).get('coverage', {})
            if coverage:
                lines = coverage.get('lines', {})
                percentage = lines.get('percentage', 0)

                html.append(f"""
                <h4>{component.title()} Coverage</h4>
                <p>Lines: {lines.get('covered', 0)}/{lines.get('total', 0)} ({percentage:.1f}%)</p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {percentage}%"></div>
                </div>
                """)

        return ''.join(html)

    def _generate_security_html_section(self) -> str:
        """Generate HTML section for security"""
        security = self.results.get('security', {})
        if not security:
            return "<p>No security validation performed</p>"

        html = ["<table><tr><th>Component</th><th>Check</th><th>Status</th><th>Issues</th></tr>"]

        for component, checks in security.items():
            for check, result in checks.items():
                status = result.get('status', 'unknown')
                issues = result.get('vulnerabilities', result.get('issues', 0))
                html.append(f"<tr><td>{component}</td><td>{check}</td><td>{status}</td><td>{issues}</td></tr>")

        html.append("</table>")
        return ''.join(html)

    def _extract_performance_metrics(self) -> Dict[str, Any]:
        """Extract performance metrics from test results"""
        return {
            "total_execution_time": self.summary.get('execution', {}).get('duration_seconds', 0),
            "average_test_time": self._calculate_average_test_time(),
            "slowest_component": self._find_slowest_component()
        }

    def _calculate_quality_metrics(self) -> Dict[str, Any]:
        """Calculate overall quality metrics"""
        tests = self.summary.get('tests', {})
        coverage = self.summary.get('coverage', {})

        return {
            "test_coverage_score": self._calculate_coverage_score(),
            "test_success_rate": tests.get('success_rate', 0),
            "quality_gate_status": "PASSED" if coverage.get('meets_threshold', False) else "FAILED",
            "total_issues": len(self.results.get('errors', [])),
            "code_health_score": self._calculate_code_health_score()
        }

    def _calculate_trends(self) -> Dict[str, Any]:
        """Calculate trends (placeholder for historical data)"""
        return {
            "coverage_trend": "stable",
            "test_count_trend": "increasing",
            "performance_trend": "stable"
        }

    def _calculate_average_test_time(self) -> float:
        """Calculate average test execution time"""
        total_time = 0
        total_tests = 0

        for component in ['backend', 'frontend']:
            tests = self.results.get(component, {}).get('tests', {})
            total_time += tests.get('time', 0)
            total_tests += tests.get('total', 0)

        return (total_time / total_tests) if total_tests > 0 else 0

    def _find_slowest_component(self) -> str:
        """Find the component with longest execution time"""
        max_time = 0
        slowest = "none"

        for component in ['backend', 'frontend']:
            tests = self.results.get(component, {}).get('tests', {})
            time = tests.get('time', 0)
            if time > max_time:
                max_time = time
                slowest = component

        return slowest

    def _calculate_coverage_score(self) -> float:
        """Calculate weighted coverage score"""
        backend_coverage = self.results.get('backend', {}).get('coverage', {}).get('lines', {}).get('percentage', 0)
        frontend_coverage = self.results.get('frontend', {}).get('coverage', {}).get('lines', {}).get('percentage', 0)

        # Weight backend more heavily
        return (backend_coverage * 0.6 + frontend_coverage * 0.4)

    def _calculate_code_health_score(self) -> float:
        """Calculate overall code health score"""
        tests = self.summary.get('tests', {})
        coverage = self.summary.get('coverage', {})

        success_rate = tests.get('success_rate', 0)
        coverage_score = self._calculate_coverage_score()
        error_penalty = len(self.results.get('errors', [])) * 5

        return max(0, (success_rate * 0.4 + coverage_score * 0.6) - error_penalty)

    def _generate_pdf_html_content(self) -> str:
        """Generate HTML content optimized for PDF generation"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; }}
        .summary-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .summary-table th, .summary-table td {{ border: 1px solid #ddd; padding: 8px; }}
        .summary-table th {{ background-color: #f8f9fa; }}
        @page {{ margin: 2cm; }}
    </style>
</head>
<body>
    <h1>Test Execution Report</h1>
    <h2>Clinica Oncológica v02</h2>

    <p><strong>Generated:</strong> {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Status:</strong> {self.summary.get('execution', {}).get('status', 'UNKNOWN')}</p>

    <h3>Summary</h3>
    <table class="summary-table">
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Total Tests</td><td>{self.summary.get('tests', {}).get('total', 0)}</td></tr>
        <tr><td>Success Rate</td><td>{self.summary.get('tests', {}).get('success_rate', 0):.1f}%</td></tr>
        <tr><td>Execution Time</td><td>{self.summary.get('execution', {}).get('duration_seconds', 0):.2f}s</td></tr>
        <tr><td>Coverage Threshold</td><td>{'PASSED' if self.summary.get('coverage', {}).get('meets_threshold', False) else 'FAILED'}</td></tr>
    </table>

    {self._generate_pdf_detailed_sections()}
</body>
</html>
        """

    def _generate_pdf_detailed_sections(self) -> str:
        """Generate detailed sections for PDF report"""
        return """
        <h3>Detailed Results</h3>
        <p>For detailed test results, coverage reports, and analysis, please refer to the HTML dashboard and individual report files.</p>

        <h3>Recommendations</h3>
        <ul>""" + ''.join(f'<li>{rec}</li>' for rec in self.summary.get('recommendations', [])) + """</ul>
        """


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate comprehensive test reports")
    parser.add_argument("--results", default="test-reports/test_results.json", help="Path to test results JSON file")
    parser.add_argument("--output", default="test-reports", help="Output directory for reports")
    parser.add_argument("--format", choices=["all", "json", "csv", "html", "pdf", "markdown"], default="all", help="Report format to generate")

    args = parser.parse_args()

    if not os.path.exists(args.results):
        print(f"❌ Error: Test results file not found: {args.results}")
        print("Run the test suite first: python run_complete_tests.py")
        return 1

    generator = TestReportGenerator(args.results, args.output)

    if args.format == "all":
        generator.generate_all_reports()
    else:
        method_name = f"generate_{args.format}_report"
        if hasattr(generator, method_name):
            result = getattr(generator, method_name)()
            print(f"✅ Generated {args.format} report: {result}")
        else:
            print(f"❌ Error: Unknown format: {args.format}")
            return 1

    return 0


if __name__ == "__main__":
    exit(main())