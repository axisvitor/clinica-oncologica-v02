#!/usr/bin/env python3
"""
CORS Security Verification Script

Validates that CORS configuration follows security best practices and
prevents credential leakage vulnerabilities.

Usage:
    python scripts/verify_cors_security.py

Exit codes:
    0 - All checks passed
    1 - Security issues found
"""

import sys
import re
from pathlib import Path
from typing import List, Tuple


class CORSSecurityChecker:
    """Checks CORS configuration for security issues."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[Tuple[str, str]] = []
        self.warnings: List[Tuple[str, str]] = []

    def check_file(self, file_path: Path) -> None:
        """Check a single file for CORS security issues."""
        try:
            content = file_path.read_text(encoding='utf-8')

            # Remove comments and docstrings to avoid false positives
            lines = content.split('\n')
            code_lines = []
            in_docstring = False
            docstring_char = None

            for line in lines:
                stripped = line.strip()

                # Handle docstrings
                if '"""' in stripped or "'''" in stripped:
                    if not in_docstring:
                        in_docstring = True
                        docstring_char = '"""' if '"""' in stripped else "'''"
                        if stripped.count(docstring_char) == 2:
                            # Single line docstring
                            in_docstring = False
                        continue
                    elif docstring_char in stripped:
                        in_docstring = False
                        continue

                # Skip comments and lines inside docstrings
                if in_docstring or stripped.startswith('#'):
                    continue

                # Remove inline comments
                if '#' in line:
                    line = line[:line.index('#')]

                code_lines.append(line)

            code_content = '\n'.join(code_lines)

            # Check for wildcard headers in actual code (not comments)
            if re.search(r'allow_headers\s*=\s*\[\s*["\']?\*["\']?\s*\]', code_content):
                self.issues.append((
                    str(file_path),
                    "Wildcard headers [\"*\"] found in code - CRITICAL security issue"
                ))

            # Check for wildcard headers with credentials in actual code
            if re.search(r'allow_credentials\s*=\s*True', code_content):
                # Check if there's a wildcard in headers nearby in code
                for i, line in enumerate(code_lines):
                    if 'allow_credentials' in line and 'True' in line:
                        # Check surrounding lines for wildcard headers
                        context = '\n'.join(code_lines[max(0, i-10):min(len(code_lines), i+10)])
                        if re.search(r'allow_headers\s*=\s*\[\s*["\']?\*["\']?\s*\]', context):
                            self.issues.append((
                                str(file_path),
                                f"Line {i+1}: Wildcard headers with credentials=True in code - "
                                "CRITICAL credential leakage vulnerability"
                            ))

            # Check for lowercase header names (should be proper case) in code
            header_pattern = r'allow_headers\s*=\s*\[(.*?)\]'
            matches = re.finditer(header_pattern, code_content, re.DOTALL)
            for match in matches:
                headers_str = match.group(1)
                if re.search(r'["\']authorization["\']', headers_str.lower()):
                    if not re.search(r'["\']Authorization["\']', headers_str):
                        self.warnings.append((
                            str(file_path),
                            "Headers should use proper case (e.g., 'Authorization' not 'authorization')"
                        ))

            # Check for missing security headers in code
            if 'allow_headers' in code_content and 'Authorization' in code_content:
                required_headers = ['Content-Type', 'Authorization', 'X-CSRF-Token']
                for header in required_headers:
                    if header not in code_content:
                        self.warnings.append((
                            str(file_path),
                            f"Missing recommended header: {header}"
                        ))

            # Check for wildcard origins with credentials in code
            if re.search(r'allow_origins\s*=\s*\[\s*["\']?\*["\']?\s*\]', code_content):
                if re.search(r'allow_credentials\s*=\s*True', code_content):
                    self.issues.append((
                        str(file_path),
                        "Wildcard origins [\"*\"] with credentials=True in code - CRITICAL security issue"
                    ))

        except Exception as e:
            self.warnings.append((str(file_path), f"Error reading file: {e}"))

    def check_all_files(self) -> None:
        """Check all relevant Python files for CORS configuration."""
        patterns = [
            'app/core/middleware_setup.py',
            'app/middleware/cors.py',
            'app/core/security_config.py',
        ]

        for pattern in patterns:
            file_path = self.project_root / pattern
            if file_path.exists():
                print(f"Checking {pattern}...")
                self.check_file(file_path)
            else:
                self.warnings.append((pattern, "File not found"))

    def print_results(self) -> int:
        """Print results and return exit code."""
        print("\n" + "="*80)
        print("CORS SECURITY VERIFICATION RESULTS")
        print("="*80 + "\n")

        if self.issues:
            print("❌ CRITICAL SECURITY ISSUES FOUND:")
            print("-" * 80)
            for file_path, issue in self.issues:
                print(f"\n  File: {file_path}")
                print(f"  Issue: {issue}")
            print()

        if self.warnings:
            print("⚠️  WARNINGS:")
            print("-" * 80)
            for file_path, warning in self.warnings:
                print(f"\n  File: {file_path}")
                print(f"  Warning: {warning}")
            print()

        if not self.issues and not self.warnings:
            print("✅ ALL CHECKS PASSED")
            print("\nCORS configuration follows security best practices:")
            print("  ✓ No wildcard headers with credentials")
            print("  ✓ No wildcard origins with credentials")
            print("  ✓ Explicit header whitelists used")
            print("  ✓ Proper header case conventions")
            print()
            return 0

        if self.issues:
            print("\n" + "="*80)
            print("SECURITY FIX REQUIRED")
            print("="*80)
            print("\nAction required:")
            print("1. Fix all CRITICAL issues immediately")
            print("2. Review and address warnings")
            print("3. Re-run this script to verify fixes")
            print()
            return 1

        if self.warnings:
            print("\n" + "="*80)
            print("WARNINGS FOUND - REVIEW RECOMMENDED")
            print("="*80)
            print()
            return 0

        return 0


def main():
    """Main entry point."""
    print("="*80)
    print("CORS SECURITY VERIFICATION TOOL")
    print("="*80)
    print("\nThis tool checks for CORS misconfigurations that could lead to")
    print("credential leakage and other security vulnerabilities.\n")

    # Find project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    print(f"Project root: {project_root}\n")

    # Run checks
    checker = CORSSecurityChecker(project_root)
    checker.check_all_files()

    # Print results and exit
    exit_code = checker.print_results()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
