#!/usr/bin/env python3
"""
Remove unused imports from Python files.

This script uses autoflake and ruff to detect and remove unused imports
and variables from the codebase.
"""
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def check_tools_installed() -> Tuple[bool, List[str]]:
    """
    Check if required tools are installed.

    Returns:
        Tuple of (all_installed, missing_tools)
    """
    tools = ['autoflake', 'ruff']
    missing = []

    for tool in tools:
        try:
            subprocess.run(
                [tool, '--version'],
                capture_output=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(tool)

    return len(missing) == 0, missing


def install_missing_tools(tools: List[str]):
    """
    Install missing tools.

    Args:
        tools: List of tool names to install
    """
    print(f"Installing missing tools: {', '.join(tools)}")
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install'] + tools,
        check=True
    )


def remove_unused_imports_autoflake(directories: List[str], dry_run: bool = False):
    """
    Use autoflake to remove unused imports.

    Args:
        directories: List of directories to process
        dry_run: If True, only show what would be changed
    """
    args = [
        'autoflake',
        '--remove-all-unused-imports',
        '--remove-unused-variables',
        '--recursive',
        '--exclude', '__init__.py,__pycache__',
    ]

    if not dry_run:
        args.append('--in-place')

    args.extend(directories)

    print(f"Running autoflake on: {', '.join(directories)}")
    result = subprocess.run(args, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0


def verify_with_ruff(directories: List[str]) -> bool:
    """
    Verify with ruff linter.

    Args:
        directories: List of directories to check

    Returns:
        True if no unused imports found, False otherwise
    """
    print(f"Verifying with ruff: {', '.join(directories)}")

    result = subprocess.run(
        ['ruff', 'check'] + directories + ['--select', 'F401'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("\n⚠️  Unused imports found:")
        print(result.stdout)
        return False

    print("✅ No unused imports found!")
    return True


def fix_with_ruff(directories: List[str]) -> bool:
    """
    Fix issues with ruff.

    Args:
        directories: List of directories to fix

    Returns:
        True if successful, False otherwise
    """
    print(f"Fixing with ruff: {', '.join(directories)}")

    result = subprocess.run(
        ['ruff', 'check'] + directories + ['--select', 'F401', '--fix'],
        capture_output=True,
        text=True
    )

    if result.stdout:
        print(result.stdout)

    return result.returncode == 0


def generate_report(directories: List[str], output_file: str = 'unused_imports_report.txt'):
    """
    Generate report of unused imports.

    Args:
        directories: List of directories to check
        output_file: Output file path
    """
    result = subprocess.run(
        ['ruff', 'check'] + directories + ['--select', 'F401', '--output-format', 'text'],
        capture_output=True,
        text=True
    )

    with open(output_file, 'w') as f:
        f.write("# Unused Imports Report\n")
        f.write("=" * 80 + "\n\n")

        if result.returncode == 0:
            f.write("✅ No unused imports found!\n")
        else:
            f.write(result.stdout)

    print(f"Report generated: {output_file}")


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Remove unused imports')
    parser.add_argument(
        '--directories',
        nargs='+',
        default=['app/', 'tests/'],
        help='Directories to process (default: app/ tests/)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making changes'
    )
    parser.add_argument(
        '--skip-install',
        action='store_true',
        help='Skip installing missing tools'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate report only'
    )

    args = parser.parse_args()

    # Check tools
    all_installed, missing = check_tools_installed()

    if not all_installed:
        if args.skip_install:
            print(f"Error: Missing tools: {', '.join(missing)}")
            print("Install with: pip install " + " ".join(missing))
            sys.exit(1)
        else:
            install_missing_tools(missing)

    # Generate report if requested
    if args.report:
        generate_report(args.directories)
        return

    # Remove unused imports
    print("\n" + "=" * 80)
    print("REMOVING UNUSED IMPORTS")
    print("=" * 80 + "\n")

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")

    # Step 1: Use autoflake
    print("Step 1: Running autoflake...")
    remove_unused_imports_autoflake(args.directories, dry_run=args.dry_run)

    if not args.dry_run:
        # Step 2: Use ruff to fix remaining issues
        print("\nStep 2: Running ruff fix...")
        fix_with_ruff(args.directories)

    # Step 3: Verify
    print("\nStep 3: Verifying results...")
    verify_with_ruff(args.directories)

    print("\n✅ Cleanup complete!")


if __name__ == '__main__':
    main()
