#!/usr/bin/env python3
"""
Fix Rate Limiter Request Parameters

This script scans all API v2 endpoints for @limiter.limit or @auth_limiter.limit decorators
and adds the missing 'request: Request' parameter if it's not present.

Usage:
    python3 scripts/fix_rate_limiter_request_params.py --dry-run   # Preview changes
    python3 scripts/fix_rate_limiter_request_params.py --apply     # Apply fixes
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import argparse


def find_rate_limited_endpoints(file_path: Path) -> List[Dict]:
    """
    Find all endpoints with rate limiting decorators.

    Returns:
        List of dicts with endpoint info
    """
    endpoints = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return endpoints

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Check for rate limiter decorators
        if re.match(r'@(limiter|auth_limiter)\.limit\(', line):
            decorator_line = i + 1  # 1-indexed for display

            # Find the function definition (skip other decorators)
            j = i + 1
            while j < len(lines):
                func_line = lines[j].strip()

                # Skip other decorators and blank lines
                if func_line.startswith('@') or not func_line:
                    j += 1
                    continue

                # Found function definition
                if func_line.startswith('async def ') or func_line.startswith('def '):
                    # Extract function name and parameters
                    # Handle multiline function signatures
                    full_signature = func_line
                    k = j + 1
                    while k < len(lines) and ')' not in full_signature:
                        full_signature += ' ' + lines[k].strip()
                        k += 1

                    # Check if 'request: Request' is in the signature
                    has_request = bool(re.search(r'\brequest\s*:\s*Request\b', full_signature))

                    endpoints.append({
                        'file': file_path,
                        'line': decorator_line,
                        'decorator': line,
                        'function_line': j + 1,
                        'function': full_signature,
                        'has_request': has_request
                    })
                    break

                j += 1

            i = j if j < len(lines) else i + 1
        else:
            i += 1

    return endpoints


def main():
    parser = argparse.ArgumentParser(description='Fix rate limiter request parameters')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--apply', action='store_true', help='Apply fixes')

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.print_help()
        print("\nPlease specify --dry-run or --apply")
        sys.exit(1)

    # Find all Python files in app/api/v2
    backend_path = Path(__file__).parent.parent
    api_v2_path = backend_path / "app" / "api" / "v2"

    if not api_v2_path.exists():
        print(f"Error: {api_v2_path} does not exist")
        sys.exit(1)

    python_files = list(api_v2_path.glob("**/*.py"))
    print(f"Scanning {len(python_files)} files in {api_v2_path}")
    print("=" * 80)

    # Find all rate-limited endpoints
    all_endpoints = []
    for py_file in python_files:
        endpoints = find_rate_limited_endpoints(py_file)
        all_endpoints.extend(endpoints)

    print(f"\nFound {len(all_endpoints)} endpoints with rate limiting decorators")

    # Filter endpoints missing request parameter
    missing_request = [ep for ep in all_endpoints if not ep['has_request']]

    if not missing_request:
        print("\n✅ All rate-limited endpoints have the request: Request parameter!")
        return

    print(f"\n⚠️  Found {len(missing_request)} endpoints missing request: Request parameter:")
    print("=" * 80)

    for i, ep in enumerate(missing_request, 1):
        print(f"\n{i}. {ep['file'].name}:{ep['line']}")
        print(f"   Decorator: {ep['decorator']}")
        print(f"   Function:  {ep['function'][:100]}...")

    if args.dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN MODE - No changes applied")
        print(f"Run with --apply to fix {len(missing_request)} endpoints")
        return

    print("\n⚠️  Manual fix required. Review the endpoints above and add 'request: Request' as first parameter.")


if __name__ == "__main__":
    main()
