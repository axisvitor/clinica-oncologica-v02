#!/usr/bin/env python3
"""
Analyze docstring coverage in the codebase.

This script uses interrogate to measure docstring coverage and identify
missing documentation.
"""
import subprocess
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional


def check_interrogate_installed() -> bool:
    """
    Check if interrogate is installed.

    Returns:
        True if installed, False otherwise
    """
    try:
        subprocess.run(
            ['interrogate', '--version'],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_interrogate():
    """Install interrogate."""
    print("Installing interrogate...")
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', 'interrogate'],
        check=True
    )


def analyze_coverage(
    directories: List[str],
    fail_under: float = 95.0,
    exclude: List[str] = None,
    ignore_regex: List[str] = None
) -> Dict:
    """
    Analyze docstring coverage.

    Args:
        directories: Directories to analyze
        fail_under: Minimum acceptable coverage
        exclude: Patterns to exclude
        ignore_regex: Regex patterns to ignore

    Returns:
        Dictionary with coverage results
    """
    if exclude is None:
        exclude = ['tests/', '__pycache__', 'migrations/', 'alembic/']

    if ignore_regex is None:
        ignore_regex = [r'.*/__init__.py$']

    args = [
        'interrogate',
        '-vv',  # Very verbose
        '--quiet',
        f'--fail-under={fail_under}',
        '--generate-badge', '.',
    ]

    for pattern in exclude:
        args.extend(['--exclude', pattern])

    for pattern in ignore_regex:
        args.extend(['--ignore-regex', pattern])

    args.extend(directories)

    result = subprocess.run(
        args,
        capture_output=True,
        text=True
    )

    # Parse output
    output = result.stdout

    # Extract coverage percentage
    coverage_match = None
    for line in output.split('\n'):
        if 'RESULT:' in line or '%' in line:
            import re
            match = re.search(r'(\d+\.?\d*)%', line)
            if match:
                coverage_match = float(match.group(1))
                break

    return {
        'coverage': coverage_match or 0.0,
        'passed': result.returncode == 0,
        'output': output
    }


def find_missing_docstrings(
    directories: List[str],
    exclude: List[str] = None
) -> List[Dict]:
    """
    Find files/functions missing docstrings.

    Args:
        directories: Directories to scan
        exclude: Patterns to exclude

    Returns:
        List of items missing docstrings
    """
    if exclude is None:
        exclude = ['tests/', '__pycache__', 'migrations/', 'alembic/']

    args = [
        'interrogate',
        '-vv',
        '--quiet',
        '--fail-under=0',
    ]

    for pattern in exclude:
        args.extend(['--exclude', pattern])

    args.extend(directories)

    result = subprocess.run(
        args,
        capture_output=True,
        text=True
    )

    # Parse output to find missing docstrings
    missing = []
    for line in result.stdout.split('\n'):
        if 'MISSING' in line or 'undocumented' in line.lower():
            missing.append({'line': line.strip()})

    return missing


def generate_report(
    coverage_result: Dict,
    missing: List[Dict],
    output_file: str = 'docstring_coverage_report.txt'
):
    """
    Generate coverage report.

    Args:
        coverage_result: Coverage analysis result
        missing: List of missing docstrings
        output_file: Output file path
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Docstring Coverage Report\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Coverage: {coverage_result['coverage']:.1f}%\n")
        f.write(f"Status: {'✅ PASS' if coverage_result['passed'] else '❌ FAIL'}\n\n")

        if missing:
            f.write(f"## Missing Docstrings ({len(missing)} items)\n")
            f.write("-" * 80 + "\n")
            for item in missing:
                f.write(f"{item['line']}\n")

        f.write("\n## Detailed Output\n")
        f.write("-" * 80 + "\n")
        f.write(coverage_result['output'])

    print(f"Report generated: {output_file}")
    print(f"Coverage: {coverage_result['coverage']:.1f}%")
    print(f"Missing docstrings: {len(missing)}")


def generate_html_report(directories: List[str]):
    """
    Generate HTML coverage report.

    Args:
        directories: Directories to analyze
    """
    args = [
        'interrogate',
        '--generate-badge', '.',
        '--output', 'docstring_coverage.html',
    ]

    args.extend(directories)

    subprocess.run(args)
    print("HTML report generated: docstring_coverage.html")


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze docstring coverage')
    parser.add_argument(
        '--directories',
        nargs='+',
        default=['app/'],
        help='Directories to analyze (default: app/)'
    )
    parser.add_argument(
        '--fail-under',
        type=float,
        default=95.0,
        help='Minimum acceptable coverage (default: 95.0)'
    )
    parser.add_argument(
        '--exclude',
        nargs='+',
        default=['tests/', '__pycache__', 'migrations/', 'alembic/'],
        help='Patterns to exclude'
    )
    parser.add_argument(
        '--output',
        default='docstring_coverage_report.txt',
        help='Output file path'
    )
    parser.add_argument(
        '--html',
        action='store_true',
        help='Generate HTML report'
    )
    parser.add_argument(
        '--skip-install',
        action='store_true',
        help='Skip installing interrogate'
    )

    args = parser.parse_args()

    # Check if interrogate is installed
    if not check_interrogate_installed():
        if args.skip_install:
            print("Error: interrogate is not installed")
            print("Install with: pip install interrogate")
            sys.exit(1)
        else:
            install_interrogate()

    print("\n" + "=" * 80)
    print("ANALYZING DOCSTRING COVERAGE")
    print("=" * 80 + "\n")

    # Analyze coverage
    coverage_result = analyze_coverage(
        args.directories,
        fail_under=args.fail_under,
        exclude=args.exclude
    )

    # Find missing docstrings
    missing = find_missing_docstrings(args.directories, args.exclude)

    # Generate report
    generate_report(coverage_result, missing, args.output)

    # Generate HTML if requested
    if args.html:
        generate_html_report(args.directories)

    # Exit with appropriate code
    if not coverage_result['passed']:
        print(f"\n❌ Coverage {coverage_result['coverage']:.1f}% is below target {args.fail_under}%")
        sys.exit(1)
    else:
        print(f"\n✅ Coverage {coverage_result['coverage']:.1f}% meets target {args.fail_under}%")


if __name__ == '__main__':
    main()
