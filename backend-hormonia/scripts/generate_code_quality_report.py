#!/usr/bin/env python3
"""
Generate comprehensive code quality report.

This script aggregates results from all code quality tools and generates
a comprehensive report with metrics and recommendations.
"""
import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def run_command(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess:
    """
    Run command and return result.

    Args:
        cmd: Command to run
        check: Raise exception on error

    Returns:
        CompletedProcess instance
    """
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check
    )


def count_unused_imports(directories: List[str] = None) -> int:
    """
    Count unused imports using ruff.

    Args:
        directories: Directories to check

    Returns:
        Number of unused imports
    """
    if directories is None:
        directories = ['app/', 'tests/']

    result = run_command(
        ['ruff', 'check'] + directories + ['--select', 'F401', '--output-format', 'text']
    )

    # Count lines in output (each line is one issue)
    if result.stdout:
        return len([l for l in result.stdout.split('\n') if l.strip()])
    return 0


def count_dead_code(directories: List[str] = None, min_confidence: int = 80) -> Dict:
    """
    Count dead code using vulture.

    Args:
        directories: Directories to check
        min_confidence: Minimum confidence level

    Returns:
        Dictionary with dead code stats
    """
    if directories is None:
        directories = ['app/']

    result = run_command(
        ['vulture'] + directories + [f'--min-confidence={min_confidence}']
    )

    items = [l for l in result.stdout.split('\n') if l.strip() and not l.startswith('#')]

    return {
        'total': len(items),
        'confidence': min_confidence
    }


def count_commented_code(directories: List[str] = None) -> int:
    """
    Count commented code lines using eradicate.

    Args:
        directories: Directories to check

    Returns:
        Number of commented code lines
    """
    if directories is None:
        directories = ['app/', 'tests/']

    count = 0
    for directory in directories:
        for py_file in Path(directory).rglob('*.py'):
            result = run_command(['eradicate', '--check', str(py_file)])
            if result.stdout:
                count += len([l for l in result.stdout.split('\n') if l.strip()])

    return count


def get_docstring_coverage(directories: List[str] = None) -> Dict:
    """
    Get docstring coverage using interrogate.

    Args:
        directories: Directories to check

    Returns:
        Dictionary with coverage stats
    """
    if directories is None:
        directories = ['app/']

    result = run_command(
        ['interrogate', '-vv', '--quiet'] + directories
    )

    # Parse coverage from output
    import re
    coverage = 0.0
    for line in result.stdout.split('\n'):
        match = re.search(r'(\d+\.?\d*)%', line)
        if match:
            coverage = float(match.group(1))
            break

    return {
        'coverage': coverage,
        'target': 95.0
    }


def count_regex_patterns(directories: List[str] = None) -> int:
    """
    Count hardcoded regex patterns.

    Args:
        directories: Directories to check

    Returns:
        Number of hardcoded regex patterns
    """
    if directories is None:
        directories = ['app/']

    # Run audit script if it exists
    audit_script = Path('scripts/audit_regex_patterns.py')
    if audit_script.exists():
        result = run_command([
            sys.executable,
            str(audit_script),
            '--directory', directories[0],
            '--json'
        ])

        # Try to parse JSON output
        try:
            report_file = Path('regex_audit_report.json')
            if report_file.exists():
                with open(report_file) as f:
                    data = json.load(f)
                    return data.get('total_patterns', 0)
        except Exception:
            pass

    return 0


def calculate_complexity(directories: List[str] = None) -> Dict:
    """
    Calculate code complexity using radon.

    Args:
        directories: Directories to check

    Returns:
        Dictionary with complexity stats
    """
    if directories is None:
        directories = ['app/']

    try:
        result = run_command(
            ['radon', 'cc'] + directories + ['-a', '-s']
        )

        # Parse average complexity
        import re
        avg_complexity = 0.0
        for line in result.stdout.split('\n'):
            if 'Average complexity' in line:
                match = re.search(r'(\d+\.?\d*)', line)
                if match:
                    avg_complexity = float(match.group(1))
                    break

        return {
            'average': avg_complexity,
            'grade': get_complexity_grade(avg_complexity)
        }
    except FileNotFoundError:
        return {'average': 0.0, 'grade': 'Unknown'}


def get_complexity_grade(complexity: float) -> str:
    """
    Get complexity grade.

    Args:
        complexity: Complexity score

    Returns:
        Grade (A-F)
    """
    if complexity <= 5:
        return 'A'
    elif complexity <= 10:
        return 'B'
    elif complexity <= 20:
        return 'C'
    elif complexity <= 30:
        return 'D'
    else:
        return 'F'


def calculate_maintainability(directories: List[str] = None) -> Dict:
    """
    Calculate maintainability index using radon.

    Args:
        directories: Directories to check

    Returns:
        Dictionary with maintainability stats
    """
    if directories is None:
        directories = ['app/']

    try:
        result = run_command(
            ['radon', 'mi'] + directories + ['-s']
        )

        # Parse average MI
        import re
        avg_mi = 0.0
        for line in result.stdout.split('\n'):
            if 'Average MI' in line or 'Average' in line:
                match = re.search(r'(\d+\.?\d*)', line)
                if match:
                    avg_mi = float(match.group(1))
                    break

        return {
            'index': avg_mi,
            'rank': get_maintainability_rank(avg_mi)
        }
    except FileNotFoundError:
        return {'index': 0.0, 'rank': 'Unknown'}


def get_maintainability_rank(mi: float) -> str:
    """
    Get maintainability rank.

    Args:
        mi: Maintainability index

    Returns:
        Rank (A-C)
    """
    if mi >= 20:
        return 'A (High)'
    elif mi >= 10:
        return 'B (Medium)'
    else:
        return 'C (Low)'


def generate_markdown_report(metrics: Dict, output_file: str):
    """
    Generate markdown report.

    Args:
        metrics: Metrics dictionary
        output_file: Output file path
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Code Quality Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Overall status
        f.write("## Overall Status\n\n")

        overall_score = calculate_overall_score(metrics)
        f.write(f"**Overall Score:** {overall_score:.1f}/100\n\n")

        if overall_score >= 90:
            f.write("🟢 **Status:** Excellent\n\n")
        elif overall_score >= 75:
            f.write("🟡 **Status:** Good\n\n")
        elif overall_score >= 60:
            f.write("🟠 **Status:** Needs Improvement\n\n")
        else:
            f.write("🔴 **Status:** Poor\n\n")

        # Metrics
        f.write("## Metrics\n\n")
        f.write("| Metric | Value | Target | Status |\n")
        f.write("|--------|-------|--------|--------|\n")

        # Unused imports
        unused_status = "✅" if metrics['unused_imports'] == 0 else "❌"
        f.write(f"| Unused Imports | {metrics['unused_imports']} | 0 | {unused_status} |\n")

        # Dead code
        dead_status = "✅" if metrics['dead_code']['total'] == 0 else "❌"
        f.write(f"| Dead Code Items | {metrics['dead_code']['total']} | 0 | {dead_status} |\n")

        # Commented code
        commented_status = "✅" if metrics['commented_code_lines'] == 0 else "❌"
        f.write(f"| Commented Code Lines | {metrics['commented_code_lines']} | 0 | {commented_status} |\n")

        # Docstring coverage
        doc_coverage = metrics['docstring_coverage']['coverage']
        doc_target = metrics['docstring_coverage']['target']
        doc_status = "✅" if doc_coverage >= doc_target else "❌"
        f.write(f"| Docstring Coverage | {doc_coverage:.1f}% | {doc_target}% | {doc_status} |\n")

        # Hardcoded regex
        regex_status = "✅" if metrics['hardcoded_regex'] == 0 else "⚠️"
        f.write(f"| Hardcoded Regex | {metrics['hardcoded_regex']} | 0 | {regex_status} |\n")

        # Code complexity
        complexity = metrics['code_complexity']['average']
        f.write(f"| Code Complexity | {complexity:.1f} (Grade {metrics['code_complexity']['grade']}) | ≤5 (A) | - |\n")

        # Maintainability
        mi = metrics['maintainability_index']['index']
        f.write(f"| Maintainability Index | {mi:.1f} ({metrics['maintainability_index']['rank']}) | ≥20 (A) | - |\n")

        # Recommendations
        f.write("\n## Recommendations\n\n")

        recommendations = generate_recommendations(metrics)
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                f.write(f"{i}. {rec}\n")
        else:
            f.write("✅ No recommendations - code quality is excellent!\n")

        # Next steps
        f.write("\n## Next Steps\n\n")
        f.write("1. Review and address all recommendations\n")
        f.write("2. Run automated fixes where possible\n")
        f.write("3. Add missing docstrings\n")
        f.write("4. Remove dead code\n")
        f.write("5. Re-run quality checks\n")


def calculate_overall_score(metrics: Dict) -> float:
    """
    Calculate overall quality score (0-100).

    Args:
        metrics: Metrics dictionary

    Returns:
        Score between 0-100
    """
    score = 100.0

    # Deduct for unused imports (max 10 points)
    score -= min(metrics['unused_imports'] * 0.5, 10)

    # Deduct for dead code (max 15 points)
    score -= min(metrics['dead_code']['total'] * 0.3, 15)

    # Deduct for commented code (max 10 points)
    score -= min(metrics['commented_code_lines'] * 0.2, 10)

    # Deduct for low docstring coverage (max 20 points)
    doc_shortfall = metrics['docstring_coverage']['target'] - metrics['docstring_coverage']['coverage']
    score -= max(doc_shortfall * 0.5, 0)

    # Deduct for hardcoded regex (max 5 points)
    score -= min(metrics['hardcoded_regex'] * 0.5, 5)

    return max(score, 0)


def generate_recommendations(metrics: Dict) -> List[str]:
    """
    Generate recommendations based on metrics.

    Args:
        metrics: Metrics dictionary

    Returns:
        List of recommendation strings
    """
    recommendations = []

    if metrics['unused_imports'] > 0:
        recommendations.append(
            f"Remove {metrics['unused_imports']} unused imports using `python scripts/remove_unused_imports.py`"
        )

    if metrics['dead_code']['total'] > 0:
        recommendations.append(
            f"Remove {metrics['dead_code']['total']} dead code items (see dead_code_report.txt)"
        )

    if metrics['commented_code_lines'] > 0:
        recommendations.append(
            f"Remove {metrics['commented_code_lines']} commented code lines using `python scripts/detect_commented_code.py --remove`"
        )

    doc_coverage = metrics['docstring_coverage']['coverage']
    doc_target = metrics['docstring_coverage']['target']
    if doc_coverage < doc_target:
        recommendations.append(
            f"Improve docstring coverage from {doc_coverage:.1f}% to {doc_target}% (see missing_docstrings_report.txt)"
        )

    if metrics['hardcoded_regex'] > 0:
        recommendations.append(
            f"Extract {metrics['hardcoded_regex']} hardcoded regex patterns to app/utils/regex_patterns.py"
        )

    if metrics['code_complexity']['average'] > 10:
        recommendations.append(
            "Refactor high-complexity functions to reduce cyclomatic complexity"
        )

    if metrics['maintainability_index']['index'] < 20:
        recommendations.append(
            "Improve code maintainability by simplifying complex functions"
        )

    return recommendations


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate comprehensive code quality report'
    )
    parser.add_argument(
        '--output',
        default='docs/code-quality/FINAL_REPORT.md',
        help='Output file path'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Also generate JSON report'
    )

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("GENERATING CODE QUALITY REPORT")
    print("=" * 80 + "\n")

    # Collect metrics
    print("Collecting metrics...")

    metrics = {
        'unused_imports': count_unused_imports(),
        'dead_code': count_dead_code(),
        'commented_code_lines': count_commented_code(),
        'docstring_coverage': get_docstring_coverage(),
        'hardcoded_regex': count_regex_patterns(),
        'code_complexity': calculate_complexity(),
        'maintainability_index': calculate_maintainability()
    }

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate markdown report
    generate_markdown_report(metrics, args.output)
    print(f"\n✅ Report generated: {args.output}")

    # Generate JSON report if requested
    if args.json:
        json_output = str(output_path).replace('.md', '.json')
        with open(json_output, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"✅ JSON report generated: {json_output}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Overall Score: {calculate_overall_score(metrics):.1f}/100")
    print(f"Unused Imports: {metrics['unused_imports']}")
    print(f"Dead Code: {metrics['dead_code']['total']}")
    print(f"Commented Code: {metrics['commented_code_lines']}")
    print(f"Docstring Coverage: {metrics['docstring_coverage']['coverage']:.1f}%")
    print(f"Hardcoded Regex: {metrics['hardcoded_regex']}")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
