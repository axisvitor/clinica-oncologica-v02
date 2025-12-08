#!/usr/bin/env python3
"""
Detect and remove commented-out code.

This script uses eradicate to find and optionally remove commented code blocks.
"""
import subprocess
import sys
import re
from pathlib import Path
from typing import List, Dict, Set


def check_eradicate_installed() -> bool:
    """
    Check if eradicate is installed.

    Returns:
        True if installed, False otherwise
    """
    try:
        subprocess.run(
            ['eradicate', '--version'],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_eradicate():
    """Install eradicate."""
    print("Installing eradicate...")
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', 'eradicate'],
        check=True
    )


def load_allowlist(allowlist_file: str = '.eradicaterc') -> Set[str]:
    """
    Load allowlist patterns from config file.

    Args:
        allowlist_file: Path to allowlist config

    Returns:
        Set of allowed patterns
    """
    allowlist = {
        'TODO',
        'FIXME',
        'NOTE',
        'Example:',
        'HACK',
        'XXX',
        'BUG',
        'WARNING',
    }

    if Path(allowlist_file).exists():
        with open(allowlist_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if line.startswith('--whitelist='):
                        pattern = line.split('=', 1)[1]
                        allowlist.add(pattern)

    return allowlist


def is_allowed_comment(line: str, allowlist: Set[str]) -> bool:
    """
    Check if comment is in allowlist.

    Args:
        line: Comment line to check
        allowlist: Set of allowed patterns

    Returns:
        True if comment is allowed, False otherwise
    """
    for pattern in allowlist:
        if pattern in line:
            return True
    return False


def find_commented_code(
    directories: List[str],
    allowlist: Set[str] = None
) -> List[Dict]:
    """
    Find commented-out code.

    Args:
        directories: Directories to scan
        allowlist: Set of allowed comment patterns

    Returns:
        List of files with commented code
    """
    if allowlist is None:
        allowlist = load_allowlist()

    files_with_comments = []

    for directory in directories:
        for py_file in Path(directory).rglob('*.py'):
            args = ['eradicate', '--check', str(py_file)]

            result = subprocess.run(
                args,
                capture_output=True,
                text=True
            )

            if result.returncode != 0 or result.stdout.strip():
                # Parse eradicate output
                lines_to_remove = []

                with open(py_file) as f:
                    content = f.read()
                    lines = content.split('\n')

                # Find commented code lines
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith('#') and not is_allowed_comment(stripped, allowlist):
                        # Check if it looks like code
                        comment_text = stripped[1:].strip()
                        if looks_like_code(comment_text):
                            lines_to_remove.append(i)

                if lines_to_remove:
                    files_with_comments.append({
                        'file': str(py_file),
                        'lines': lines_to_remove,
                        'count': len(lines_to_remove)
                    })

    return files_with_comments


def looks_like_code(text: str) -> bool:
    """
    Heuristic to determine if comment looks like code.

    Args:
        text: Comment text (without #)

    Returns:
        True if it looks like code, False otherwise
    """
    # Skip empty or very short comments
    if len(text.strip()) < 5:
        return False

    # Code indicators
    code_patterns = [
        r'^\s*(def|class|if|for|while|try|except|import|from)\s+',  # Keywords
        r'=\s*["\'\d\[]',  # Assignments
        r'\(.*\)',  # Function calls
        r'^\s*return\s+',  # Return statements
        r'^\s*print\(',  # Print statements
        r'^\s*\w+\.\w+',  # Method calls
    ]

    for pattern in code_patterns:
        if re.search(pattern, text):
            return True

    return False


def remove_commented_code(
    file_path: str,
    dry_run: bool = False
) -> bool:
    """
    Remove commented code from a file.

    Args:
        file_path: Path to file
        dry_run: If True, only show what would be removed

    Returns:
        True if changes were made, False otherwise
    """
    args = ['eradicate', str(file_path)]

    if not dry_run:
        args.append('--in-place')

    result = subprocess.run(
        args,
        capture_output=True,
        text=True
    )

    if result.stdout:
        print(f"\n{file_path}:")
        print(result.stdout)
        return True

    return False


def generate_report(
    files_with_comments: List[Dict],
    output_file: str = 'commented_code_report.txt'
):
    """
    Generate report of commented code.

    Args:
        files_with_comments: List of files with commented code
        output_file: Output file path
    """
    total_lines = sum(item['count'] for item in files_with_comments)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Commented Code Detection Report\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Files with commented code: {len(files_with_comments)}\n")
        f.write(f"Total commented code lines: {total_lines}\n\n")

        # Sort by number of lines (descending)
        for item in sorted(files_with_comments, key=lambda x: x['count'], reverse=True):
            f.write(f"\n{item['file']} ({item['count']} lines)\n")
            f.write(f"  Lines: {', '.join(map(str, item['lines']))}\n")

    print(f"Report generated: {output_file}")
    print(f"Files with commented code: {len(files_with_comments)}")
    print(f"Total lines: {total_lines}")


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Detect and remove commented code')
    parser.add_argument(
        '--directories',
        nargs='+',
        default=['app/', 'tests/'],
        help='Directories to scan (default: app/ tests/)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be removed without making changes'
    )
    parser.add_argument(
        '--output',
        default='commented_code_report.txt',
        help='Output file path'
    )
    parser.add_argument(
        '--remove',
        action='store_true',
        help='Remove commented code'
    )
    parser.add_argument(
        '--skip-install',
        action='store_true',
        help='Skip installing eradicate'
    )
    parser.add_argument(
        '--allowlist-file',
        default='.eradicaterc',
        help='Allowlist config file'
    )

    args = parser.parse_args()

    # Check if eradicate is installed
    if not check_eradicate_installed():
        if args.skip_install:
            print("Error: eradicate is not installed")
            print("Install with: pip install eradicate")
            sys.exit(1)
        else:
            install_eradicate()

    print("\n" + "=" * 80)
    print("DETECTING COMMENTED CODE")
    print("=" * 80 + "\n")

    # Load allowlist
    allowlist = load_allowlist(args.allowlist_file)
    print(f"Allowlist patterns: {', '.join(sorted(allowlist))}\n")

    # Find commented code
    files_with_comments = find_commented_code(args.directories, allowlist)

    if not files_with_comments:
        print("✅ No commented code found!")
        return

    # Generate report
    generate_report(files_with_comments, args.output)

    # Remove if requested
    if args.remove:
        print("\n" + "=" * 80)
        print("REMOVING COMMENTED CODE")
        print("=" * 80 + "\n")

        if args.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made\n")

        changes_made = 0
        for item in files_with_comments:
            if remove_commented_code(item['file'], dry_run=args.dry_run):
                changes_made += 1

        if changes_made > 0:
            print(f"\n✅ Modified {changes_made} files")
        else:
            print("\n✅ No changes needed")


if __name__ == '__main__':
    main()
