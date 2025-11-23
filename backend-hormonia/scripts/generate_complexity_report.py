#!/usr/bin/env python3
"""
Generate comprehensive complexity report
Combines radon complexity metrics with maintainability index
Usage: python scripts/generate_complexity_report.py > docs/code-quality/COMPLEXITY_REPORT.md
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json

# Colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def run_command(cmd: list) -> str:
    """Run command and return output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout
    except Exception as e:
        print(f"{RED}Error running {' '.join(cmd)}: {e}{RESET}", file=sys.stderr)
        return ""


def get_cyclomatic_complexity() -> str:
    """Get cyclomatic complexity metrics."""
    print(f"{BLUE}Calculating cyclomatic complexity...{RESET}", file=sys.stderr)
    return run_command(['radon', 'cc', 'app/', '-a', '-s', '--total-average'])


def get_maintainability_index() -> str:
    """Get maintainability index."""
    print(f"{BLUE}Calculating maintainability index...{RESET}", file=sys.stderr)
    return run_command(['radon', 'mi', 'app/', '-s'])


def get_raw_metrics() -> str:
    """Get raw metrics (LOC, LLOC, etc)."""
    print(f"{BLUE}Calculating raw metrics...{RESET}", file=sys.stderr)
    return run_command(['radon', 'raw', 'app/', '-s'])


def get_halstead_metrics() -> str:
    """Get Halstead complexity metrics."""
    print(f"{BLUE}Calculating Halstead metrics...{RESET}", file=sys.stderr)
    return run_command(['radon', 'hal', 'app/'])


def count_files_by_complexity() -> dict:
    """Count files by complexity grade."""
    output = run_command(['radon', 'cc', 'app/', '-a', '--json'])

    if not output:
        return {}

    try:
        data = json.loads(output)
        grades = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0, 'F': 0}

        for file_path, metrics in data.items():
            if isinstance(metrics, list):
                for metric in metrics:
                    if 'complexity' in metric:
                        complexity = metric['complexity']
                        if complexity <= 5:
                            grades['A'] += 1
                        elif complexity <= 10:
                            grades['B'] += 1
                        elif complexity <= 20:
                            grades['C'] += 1
                        elif complexity <= 30:
                            grades['D'] += 1
                        elif complexity <= 40:
                            grades['E'] += 1
                        else:
                            grades['F'] += 1

        return grades
    except json.JSONDecodeError:
        return {}


def generate_report():
    """Generate the complete complexity report."""
    # Header
    print("# Code Complexity Report")
    print()
    print(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"**Project:** Clínica Oncológica - Backend")
    print(f"**Status:** Agent 17 - Code Quality Audit")
    print()
    print("---")
    print()

    # Executive Summary
    print("## Executive Summary")
    print()
    print("This report provides comprehensive code complexity metrics for the backend application.")
    print("The analysis includes:")
    print()
    print("- **Cyclomatic Complexity:** Measures the number of linearly independent paths")
    print("- **Maintainability Index:** Overall maintainability score (0-100, higher is better)")
    print("- **Raw Metrics:** Lines of code, logical lines, comments, etc.")
    print("- **Halstead Metrics:** Computational complexity measurements")
    print()
    print("### Complexity Grades")
    print()
    print("| Grade | Complexity | Risk | Description |")
    print("|-------|------------|------|-------------|")
    print("| A | 1-5 | Low | Simple, well-structured code |")
    print("| B | 6-10 | Low | Slightly complex code |")
    print("| C | 11-20 | Moderate | Complex code, needs review |")
    print("| D | 21-30 | High | Very complex, refactor recommended |")
    print("| E | 31-40 | Very High | Extremely complex, refactor required |")
    print("| F | 41+ | Extreme | Unmaintainable, immediate refactoring needed |")
    print()

    # Complexity distribution
    grades = count_files_by_complexity()
    if grades:
        print("### Complexity Distribution")
        print()
        print("| Grade | Count | Percentage |")
        print("|-------|-------|------------|")
        total = sum(grades.values())
        for grade in ['A', 'B', 'C', 'D', 'E', 'F']:
            count = grades.get(grade, 0)
            pct = (count / total * 100) if total > 0 else 0
            print(f"| {grade} | {count} | {pct:.1f}% |")
        print()

    # Cyclomatic Complexity
    print("---")
    print()
    print("## Cyclomatic Complexity")
    print()
    print("Measures the number of linearly independent paths through the code.")
    print("Lower values indicate simpler, more maintainable code.")
    print()
    print("```")
    cc_output = get_cyclomatic_complexity()
    print(cc_output if cc_output else "No data available")
    print("```")
    print()

    # Maintainability Index
    print("---")
    print()
    print("## Maintainability Index")
    print()
    print("A composite metric ranging from 0 to 100:")
    print("- **85-100:** Good maintainability")
    print("- **65-84:** Moderate maintainability")
    print("- **0-64:** Difficult to maintain")
    print()
    print("```")
    mi_output = get_maintainability_index()
    print(mi_output if mi_output else "No data available")
    print("```")
    print()

    # Raw Metrics
    print("---")
    print()
    print("## Raw Metrics")
    print()
    print("Physical lines of code, logical lines, comments, etc.")
    print()
    print("```")
    raw_output = get_raw_metrics()
    print(raw_output if raw_output else "No data available")
    print("```")
    print()

    # Halstead Metrics
    print("---")
    print()
    print("## Halstead Metrics")
    print()
    print("Computational complexity based on operators and operands:")
    print("- **Volume:** Size of the implementation")
    print("- **Difficulty:** How difficult the code is to write or understand")
    print("- **Effort:** Mental effort required to understand/maintain")
    print()
    print("```")
    hal_output = get_halstead_metrics()
    if hal_output:
        # Limit Halstead output (it can be very long)
        lines = hal_output.split('\n')
        print('\n'.join(lines[:50]))
        if len(lines) > 50:
            print(f"\n... ({len(lines) - 50} more lines omitted)")
    else:
        print("No data available")
    print("```")
    print()

    # Recommendations
    print("---")
    print()
    print("## Recommendations")
    print()
    print("### Priority Actions")
    print()
    print("1. **Refactor F-grade functions** (complexity > 40)")
    print("   - Break into smaller functions")
    print("   - Extract complex logic into helper methods")
    print("   - Apply Single Responsibility Principle")
    print()
    print("2. **Review D/E-grade functions** (complexity 21-40)")
    print("   - Simplify conditional logic")
    print("   - Reduce nesting levels")
    print("   - Consider design patterns (Strategy, Factory, etc.)")
    print()
    print("3. **Maintain A/B-grade functions** (complexity ≤ 10)")
    print("   - Keep functions simple and focused")
    print("   - Limit to 50 lines per function")
    print("   - Write comprehensive tests")
    print()
    print("### Best Practices")
    print()
    print("- **Target Cyclomatic Complexity:** ≤ 10 per function")
    print("- **Target Maintainability Index:** ≥ 85")
    print("- **Max Function Length:** 50 lines")
    print("- **Max Class Length:** 300 lines")
    print()
    print("### Tools")
    print()
    print("```bash")
    print("# Check specific file complexity")
    print("radon cc app/services/patient.py -s")
    print()
    print("# Check maintainability")
    print("radon mi app/services/patient.py -s")
    print()
    print("# Check all metrics")
    print("radon cc app/ -a -s --total-average")
    print("```")
    print()
    print("---")
    print()
    print(f"**Report End** | Generated by Agent 17 - Code Quality Audit")


def main():
    """Main execution."""
    root_dir = Path.cwd() / "app"
    if not root_dir.exists():
        print(f"{RED}Error: app/ directory not found. Run from backend-hormonia root.{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        generate_report()
    except Exception as e:
        print(f"{RED}Error generating report: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
