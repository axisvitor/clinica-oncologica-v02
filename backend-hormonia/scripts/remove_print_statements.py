#!/usr/bin/env python3
"""Remove all print() statements from production code.

This script scans Python files in the app/ directory and removes
debug print() statements, replacing them with comments for audit trail.

Usage:
    python scripts/remove_print_statements.py [--dry-run]

Arguments:
    --dry-run: Show what would be removed without making changes
"""

import re
import sys
from pathlib import Path
from typing import Tuple
import argparse


def remove_prints_from_file(file_path: Path, dry_run: bool = False) -> Tuple[int, int]:
    """Remove print statements from a Python file.

    Args:
        file_path: Path to the Python file
        dry_run: If True, don't modify the file

    Returns:
        Tuple of (removed_count, total_lines)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return 0, 0

    original_content = content
    lines = content.split('\n')
    new_lines = []
    removed_count = 0

    # Pattern to match print() calls (standalone statements)
    # Matches: print(...), print(f"..."), print("..."), etc.
    # But not inside strings or comments
    print_pattern = re.compile(r'^\s*print\s*\([^)]*\)\s*$')

    for i, line in enumerate(lines, 1):
        # Skip if line is already a comment
        if line.strip().startswith('#'):
            new_lines.append(line)
            continue

        # Check if line contains a print statement
        if print_pattern.match(line):
            removed_count += 1
            indent = len(line) - len(line.lstrip())
            comment_line = ' ' * indent + f"# REMOVED print() statement (line {i}): {line.strip()}"
            new_lines.append(comment_line)

            if not dry_run:
                print(f"  📝 Line {i}: {line.strip()}")
        else:
            new_lines.append(line)

    new_content = '\n'.join(new_lines)

    if new_content != original_content and not dry_run:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

    return removed_count, len(lines)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Remove print() statements from production code'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be removed without making changes'
    )
    args = parser.parse_args()

    print("🔍 Scanning for print() statements in production code...")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'ACTIVE REMOVAL'}\n")

    app_dir = Path(__file__).parent.parent / 'app'

    if not app_dir.exists():
        print(f"❌ ERROR: app/ directory not found at {app_dir}")
        sys.exit(1)

    total_removed = 0
    total_files = 0
    total_lines = 0
    files_modified = []

    # Scan all Python files in app/ directory
    for py_file in sorted(app_dir.rglob('*.py')):
        # Skip __pycache__ and test files
        if '__pycache__' in str(py_file) or 'test_' in py_file.name:
            continue

        removed, lines = remove_prints_from_file(py_file, dry_run=args.dry_run)

        if removed > 0:
            total_removed += removed
            total_files += 1
            files_modified.append(py_file)

            rel_path = py_file.relative_to(app_dir.parent)
            print(f"{'🔍' if args.dry_run else '✅'} {rel_path}: "
                  f"Removed {removed} print() statement{'s' if removed != 1 else ''}")

        total_lines += lines

    # Summary
    print("\n" + "="*80)
    if args.dry_run:
        print("📊 DRY RUN SUMMARY")
    else:
        print("📊 REMOVAL SUMMARY")
    print("="*80)
    print(f"Total files scanned: {len(list(app_dir.rglob('*.py')))}")
    print(f"Files with print() statements: {total_files}")
    print(f"Total print() statements {'found' if args.dry_run else 'removed'}: {total_removed}")
    print(f"Total lines of code: {total_lines:,}")

    if files_modified:
        print("\nModified files:")
        for file_path in files_modified:
            print(f"  - {file_path.relative_to(app_dir.parent)}")

    if args.dry_run and total_removed > 0:
        print("\n💡 Run without --dry-run to apply changes")
    elif total_removed > 0:
        print("\n✅ COMPLETE: All print() statements removed successfully!")
        print("\n📝 Next steps:")
        print("  1. Review changes with: git diff")
        print("  2. Run tests: pytest")
        print("  3. Install pre-commit hook: pre-commit install")
    else:
        print("\n✅ COMPLETE: No print() statements found!")

    return 0 if total_removed == 0 else (1 if args.dry_run else 0)


if __name__ == '__main__':
    sys.exit(main())
