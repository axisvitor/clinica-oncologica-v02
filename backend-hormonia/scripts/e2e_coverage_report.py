#!/usr/bin/env python3
"""
E2E Test Coverage Report Generator
Analyzes which API endpoints and features were tested during E2E test runs.

Generates:
- Coverage percentage
- List of tested endpoints
- List of untested endpoints
- HTML report
- Markdown summary
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Define all API endpoints in the application
ALL_ENDPOINTS = {
    # Authentication
    '/api/v2/auth/login': 'POST',
    '/api/v2/auth/refresh': 'POST',
    '/api/v2/auth/logout': 'POST',

    # Patients
    '/api/v2/patients': 'GET',
    '/api/v2/patients': 'POST',
    '/api/v2/patients/{id}': 'GET',
    '/api/v2/patients/{id}': 'PUT',
    '/api/v2/patients/{id}': 'DELETE',
    '/api/v2/patients/{id}/messages': 'GET',

    # Quiz
    '/api/v2/quiz/sessions': 'GET',
    '/api/v2/quiz/sessions': 'POST',
    '/api/v2/quiz/sessions/{id}': 'GET',
    '/api/v2/quiz/sessions/{id}/questions': 'GET',
    '/api/v2/quiz/sessions/{id}/responses': 'POST',
    '/api/v2/quiz/sessions/{id}/responses': 'GET',

    # Webhooks
    '/api/webhooks/evolution': 'POST',

    # Dashboard
    '/api/v2/dashboard': 'GET',
    '/api/v2/dashboard/stats': 'GET',

    # Flows
    '/api/v2/flows': 'GET',
    '/api/v2/flows/executions': 'GET',

    # Sagas
    '/api/v2/sagas': 'GET',
    '/api/v2/sagas/{id}': 'GET',

    # Reports
    '/api/v2/reports': 'GET',
    '/api/v2/reports/generate': 'POST',

    # Health
    '/health': 'GET',
    '/api/v2/health': 'GET',
}

# Critical user journeys that must be tested
CRITICAL_JOURNEYS = [
    'Patient Onboarding',
    'Webhook Processing',
    'Doctor Dashboard',
    'Saga Resilience',
]


def extract_tested_endpoints_from_logs(log_file: Path) -> Set[Tuple[str, str]]:
    """Extract tested endpoints from test logs."""
    tested = set()

    if not log_file.exists():
        return tested

    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()

        # Pattern: method URL
        pattern = r'(GET|POST|PUT|DELETE|PATCH)\s+(\/[^\s]+)'

        for match in re.finditer(pattern, content):
            method = match.group(1)
            url = match.group(2)

            # Normalize URL (replace IDs with {id})
            normalized_url = re.sub(r'/\d+', '/{id}', url)

            tested.add((normalized_url, method))

    return tested


def analyze_test_files() -> Dict[str, List[str]]:
    """Analyze E2E test files to identify tested features."""
    test_dir = Path(__file__).parent.parent / 'tests' / 'e2e'

    journey_coverage = {}

    for test_file in test_dir.glob('test_*.py'):
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()

            # Extract journey name from docstring
            journey_match = re.search(r'""".*?Journey.*?:.*?([^\n]+)', content, re.DOTALL)
            if journey_match:
                journey_name = test_file.stem.replace('test_', '').replace('_', ' ').title()

                # Extract tested endpoints from file
                endpoints = re.findall(r"'(/api/[^']+)'", content)
                journey_coverage[journey_name] = list(set(endpoints))

    return journey_coverage


def calculate_coverage(tested: Set[Tuple[str, str]]) -> Tuple[float, List[str], List[str]]:
    """Calculate endpoint coverage percentage."""
    total_endpoints = len(ALL_ENDPOINTS)

    tested_list = []
    untested_list = []

    for endpoint, method in ALL_ENDPOINTS.items():
        endpoint_method = (endpoint, method)

        if endpoint_method in tested:
            tested_list.append(f"{method} {endpoint}")
        else:
            untested_list.append(f"{method} {endpoint}")

    coverage_pct = (len(tested_list) / total_endpoints) * 100 if total_endpoints > 0 else 0

    return coverage_pct, tested_list, untested_list


def generate_html_report(coverage_pct: float, tested: List[str], untested: List[str],
                         journey_coverage: Dict[str, List[str]], output_file: Path):
    """Generate HTML coverage report."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Coverage Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .coverage-badge {{
            display: inline-block;
            background: {'#4caf50' if coverage_pct >= 70 else '#ff9800' if coverage_pct >= 50 else '#f44336'};
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 24px;
            font-weight: bold;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .endpoint-list {{
            list-style: none;
            padding: 0;
        }}
        .endpoint-list li {{
            padding: 8px;
            border-left: 3px solid #667eea;
            margin-bottom: 5px;
            background: #f9f9f9;
        }}
        .untested {{
            border-left-color: #f44336;
            background: #ffebee;
        }}
        .journey {{
            background: #e3f2fd;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
        }}
        .journey h3 {{
            margin: 0 0 10px 0;
            color: #1976d2;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .timestamp {{
            text-align: right;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 E2E Test Coverage Report</h1>
        <div class="coverage-badge">{coverage_pct:.1f}% Coverage</div>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{len(tested)}</div>
            <div class="stat-label">Tested Endpoints</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(untested)}</div>
            <div class="stat-label">Untested Endpoints</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(journey_coverage)}</div>
            <div class="stat-label">User Journeys</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(ALL_ENDPOINTS)}</div>
            <div class="stat-label">Total Endpoints</div>
        </div>
    </div>

    <div class="section">
        <h2>🎯 User Journey Coverage</h2>
        {''.join(f'''
        <div class="journey">
            <h3>{journey}</h3>
            <ul class="endpoint-list">
                {''.join(f'<li>{endpoint}</li>' for endpoint in endpoints)}
            </ul>
        </div>
        ''' for journey, endpoints in journey_coverage.items())}
    </div>

    <div class="section">
        <h2>✅ Tested Endpoints ({len(tested)})</h2>
        <ul class="endpoint-list">
            {''.join(f'<li>{endpoint}</li>' for endpoint in sorted(tested))}
        </ul>
    </div>

    <div class="section">
        <h2>❌ Untested Endpoints ({len(untested)})</h2>
        <ul class="endpoint-list">
            {''.join(f'<li class="untested">{endpoint}</li>' for endpoint in sorted(untested))}
        </ul>
    </div>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_markdown_summary(coverage_pct: float, tested: List[str], untested: List[str],
                              journey_coverage: Dict[str, List[str]], output_file: Path):
    """Generate Markdown coverage summary."""
    badge_color = 'brightgreen' if coverage_pct >= 70 else 'orange' if coverage_pct >= 50 else 'red'

    md = f"""# 🧪 E2E Test Coverage Report

![Coverage](<https://img.shields.io/badge/coverage-{coverage_pct:.0f}%25-{badge_color}>)

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 Summary

| Metric | Value |
|--------|-------|
| **Total Endpoints** | {len(ALL_ENDPOINTS)} |
| **Tested Endpoints** | {len(tested)} |
| **Untested Endpoints** | {len(untested)} |
| **Coverage** | **{coverage_pct:.1f}%** |
| **User Journeys** | {len(journey_coverage)} |

## 🎯 Coverage Status

{'✅ **PASSED**: Coverage >= 70%' if coverage_pct >= 70 else '⚠️ **WARNING**: Coverage < 70%' if coverage_pct >= 50 else '❌ **FAILED**: Coverage < 50%'}

## 🧭 User Journey Coverage

"""

    for journey, endpoints in journey_coverage.items():
        md += f"\n### {journey}\n"
        md += f"- **Endpoints Tested:** {len(endpoints)}\n"
        for endpoint in endpoints:
            md += f"  - `{endpoint}`\n"

    md += "\n## ✅ Tested Endpoints\n\n"
    for endpoint in sorted(tested)[:20]:  # Limit to first 20
        md += f"- `{endpoint}`\n"

    if len(tested) > 20:
        md += f"\n_...and {len(tested) - 20} more_\n"

    md += "\n## ❌ Untested Endpoints\n\n"
    if untested:
        for endpoint in sorted(untested):
            md += f"- `{endpoint}`\n"
    else:
        md += "_All endpoints are tested! 🎉_\n"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md)


def main():
    """Main execution."""
    print("🔍 Analyzing E2E test coverage...")

    # Analyze test files
    journey_coverage = analyze_test_files()
    print(f"✅ Found {len(journey_coverage)} user journeys")

    # Extract tested endpoints (from logs if available)
    tested_endpoints = set()

    # For now, infer from journey coverage
    for endpoints in journey_coverage.values():
        for endpoint in endpoints:
            # Try to match with known endpoints
            for known_endpoint, method in ALL_ENDPOINTS.items():
                if endpoint in known_endpoint or known_endpoint.replace('{id}', '') in endpoint:
                    tested_endpoints.add((known_endpoint, method))

    # Calculate coverage
    coverage_pct, tested_list, untested_list = calculate_coverage(tested_endpoints)
    print(f"📊 Coverage: {coverage_pct:.1f}%")
    print(f"   - Tested: {len(tested_list)}")
    print(f"   - Untested: {len(untested_list)}")

    # Generate reports
    output_dir = Path(__file__).parent.parent / 'test-results'
    output_dir.mkdir(parents=True, exist_ok=True)

    html_report = output_dir / 'e2e-coverage-report.html'
    md_summary = output_dir / 'coverage-summary.md'

    generate_html_report(coverage_pct, tested_list, untested_list, journey_coverage, html_report)
    print(f"✅ HTML report: {html_report}")

    generate_markdown_summary(coverage_pct, tested_list, untested_list, journey_coverage, md_summary)
    print(f"✅ Markdown summary: {md_summary}")

    # Exit code based on coverage
    if coverage_pct >= 70:
        print("✅ Coverage target achieved (≥70%)")
        return 0
    else:
        print(f"⚠️  Coverage below target: {coverage_pct:.1f}% < 70%")
        return 1


if __name__ == '__main__':
    exit(main())
