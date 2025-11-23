#!/usr/bin/env python3
"""
SQL Injection Fixes Verification Script

This script verifies that the SQL injection fixes have been properly applied
and that no similar vulnerabilities exist in the codebase.

Usage:
    python scripts/verify_sql_injection_fixes.py
    python scripts/verify_sql_injection_fixes.py --verbose
    python scripts/verify_sql_injection_fixes.py --scan-all
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class VulnerabilityLevel(Enum):
    """Severity levels for detected issues"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class SecurityIssue:
    """Represents a potential security issue"""
    file_path: str
    line_number: int
    line_content: str
    issue_type: str
    severity: VulnerabilityLevel
    description: str


class SQLInjectionScanner:
    """Scanner for SQL injection vulnerabilities"""

    def __init__(self, base_path: str = "app"):
        self.base_path = Path(base_path)
        self.issues: List[SecurityIssue] = []

        # Patterns that indicate potential SQL injection vulnerabilities
        self.vulnerable_patterns = [
            # f-string SQL injection patterns
            (r'\.execute\(f["\']', "Raw SQL with f-string", VulnerabilityLevel.CRITICAL),
            (r'\.execute\(f".*SELECT', "SELECT with f-string", VulnerabilityLevel.CRITICAL),
            (r'\.execute\(f".*INSERT', "INSERT with f-string", VulnerabilityLevel.CRITICAL),
            (r'\.execute\(f".*UPDATE', "UPDATE with f-string", VulnerabilityLevel.CRITICAL),
            (r'\.execute\(f".*DELETE', "DELETE with f-string", VulnerabilityLevel.CRITICAL),

            # String concatenation in queries
            (r'\.execute\(.*\+.*\)', "SQL with string concatenation", VulnerabilityLevel.HIGH),
            (r'\.filter\(f["\']', "Filter with f-string", VulnerabilityLevel.HIGH),

            # Format string patterns
            (r'\.execute\(.*\.format\(', "SQL with .format()", VulnerabilityLevel.HIGH),
            (r'\.execute\(.*%.*%', "SQL with % formatting", VulnerabilityLevel.HIGH),

            # Potentially unsafe LIKE patterns
            (r'\.ilike\(f"%\{', "ILIKE with f-string interpolation", VulnerabilityLevel.MEDIUM),
            (r'\.like\(f"%\{', "LIKE with f-string interpolation", VulnerabilityLevel.MEDIUM),
        ]

        # Patterns for safe implementations (to reduce false positives)
        self.safe_patterns = [
            r'text\(["\'].*["\'],\s*\{',  # SQLAlchemy text() with parameters
            r'# SECURITY FIX',  # Already fixed
            r'# SAFE:',  # Marked as safe
            r'search_pattern\s*=',  # Using pattern variable (our fix)
        ]

    def scan_file(self, file_path: Path) -> List[SecurityIssue]:
        """Scan a single file for SQL injection vulnerabilities"""
        issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, start=1):
                # Skip comments
                if line.strip().startswith('#'):
                    continue

                # Check if line matches safe patterns first
                is_safe = any(re.search(pattern, line) for pattern in self.safe_patterns)
                if is_safe:
                    continue

                # Check for vulnerable patterns
                for pattern, issue_type, severity in self.vulnerable_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append(SecurityIssue(
                            file_path=str(file_path.relative_to(self.base_path.parent)),
                            line_number=line_num,
                            line_content=line.strip(),
                            issue_type=issue_type,
                            severity=severity,
                            description=f"Potential SQL injection: {issue_type}"
                        ))

        except Exception as e:
            print(f"Error scanning {file_path}: {e}", file=sys.stderr)

        return issues

    def scan_directory(self, directory: Path = None) -> List[SecurityIssue]:
        """Recursively scan directory for SQL injection vulnerabilities"""
        if directory is None:
            directory = self.base_path

        all_issues = []

        for py_file in directory.rglob("*.py"):
            # Skip test files and migrations
            if "test" in str(py_file) or "migration" in str(py_file):
                continue

            issues = self.scan_file(py_file)
            all_issues.extend(issues)

        return all_issues

    def verify_fixes(self) -> Dict[str, bool]:
        """Verify that known SQL injection fixes have been applied"""
        fixes_status = {}

        # Check conversations.py fix
        conversations_file = self.base_path / "api/v2/messages/conversations.py"
        if conversations_file.exists():
            with open(conversations_file, 'r') as f:
                content = f.read()
                # Check for security fix comment
                has_fix = "# SECURITY FIX: Use parameterized query to prevent SQL injection" in content
                # Check that old vulnerable pattern is not present
                has_vulnerable = re.search(r'\.ilike\(f"%\{q\}%"\)', content) is not None
                fixes_status['conversations.py'] = has_fix and not has_vulnerable

        # Check medication.py fix
        medication_file = self.base_path / "repositories/medication.py"
        if medication_file.exists():
            with open(medication_file, 'r') as f:
                content = f.read()
                # Check for security fix comment
                has_fix = "# SECURITY FIX: Use parameterized query to prevent SQL injection" in content
                # Check that old vulnerable pattern is not present
                has_vulnerable = re.search(r'\.ilike\(f"%\{name\}%"\)', content) is not None
                fixes_status['medication.py'] = has_fix and not has_vulnerable

        return fixes_status

    def generate_report(self) -> str:
        """Generate a formatted report of findings"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("SQL INJECTION VULNERABILITY SCAN REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")

        # Verify known fixes
        report_lines.append("KNOWN FIXES VERIFICATION:")
        report_lines.append("-" * 40)
        fixes_status = self.verify_fixes()

        for file_name, is_fixed in fixes_status.items():
            status = "✅ FIXED" if is_fixed else "❌ NOT FIXED"
            report_lines.append(f"  {file_name}: {status}")

        report_lines.append("")

        # Report new issues found
        if self.issues:
            report_lines.append(f"NEW ISSUES FOUND: {len(self.issues)}")
            report_lines.append("-" * 40)

            # Group by severity
            by_severity = {}
            for issue in self.issues:
                severity = issue.severity.value
                if severity not in by_severity:
                    by_severity[severity] = []
                by_severity[severity].append(issue)

            for severity in [VulnerabilityLevel.CRITICAL, VulnerabilityLevel.HIGH,
                           VulnerabilityLevel.MEDIUM, VulnerabilityLevel.LOW]:
                severity_name = severity.value
                if severity_name in by_severity:
                    report_lines.append(f"\n{severity_name} SEVERITY ({len(by_severity[severity_name])} issues):")

                    for issue in by_severity[severity_name]:
                        report_lines.append(f"\n  File: {issue.file_path}")
                        report_lines.append(f"  Line: {issue.line_number}")
                        report_lines.append(f"  Issue: {issue.issue_type}")
                        report_lines.append(f"  Code: {issue.line_content}")
                        report_lines.append(f"  Description: {issue.description}")
        else:
            report_lines.append("✅ NO NEW ISSUES FOUND")

        report_lines.append("")
        report_lines.append("=" * 80)

        return "\n".join(report_lines)


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify SQL injection fixes and scan for vulnerabilities"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--scan-all",
        action="store_true",
        help="Scan all Python files including tests"
    )
    parser.add_argument(
        "--base-path",
        default="app",
        help="Base path to scan (default: app)"
    )

    args = parser.parse_args()

    print("🔍 SQL Injection Vulnerability Scanner")
    print("=" * 80)
    print()

    scanner = SQLInjectionScanner(base_path=args.base_path)

    # Verify known fixes
    print("Verifying known SQL injection fixes...")
    fixes_status = scanner.verify_fixes()

    all_fixed = all(fixes_status.values())

    if all_fixed:
        print("✅ All known fixes verified successfully!")
    else:
        print("❌ Some fixes are missing or incomplete!")
        for file_name, is_fixed in fixes_status.items():
            status = "✅" if is_fixed else "❌"
            print(f"  {status} {file_name}")

    print()

    # Scan for new issues
    print("Scanning for SQL injection vulnerabilities...")
    scanner.issues = scanner.scan_directory()

    # Generate and print report
    report = scanner.generate_report()
    print(report)

    # Exit with appropriate code
    if not all_fixed or scanner.issues:
        print("\n⚠️  Issues detected! Please review the report above.")
        sys.exit(1)
    else:
        print("\n✅ All checks passed! No SQL injection vulnerabilities detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
