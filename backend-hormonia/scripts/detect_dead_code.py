#!/usr/bin/env python3
"""
Detect dead code in the codebase.

This script uses vulture to find unused code that can be safely removed.
"""
import subprocess
import sys
import json
from pathlib import Path
from typing import List, Dict


def check_vulture_installed() -> bool:
    """
    Check if vulture is installed.

    Returns:
        True if installed, False otherwise
    """
    try:
        subprocess.run(
            ['vulture', '--version'],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_vulture():
    """Install vulture."""
    print("Installing vulture...")
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', 'vulture'],
        check=True
    )


def find_dead_code(
    directories: List[str],
    min_confidence: int = 80,
    exclude: List[str] = None
) -> List[Dict]:
    """
    Use vulture to find dead code.

    Args:
        directories: Directories to scan
        min_confidence: Minimum confidence level (0-100)
        exclude: Patterns to exclude

    Returns:
        List of dead code items
    """
    if exclude is None:
        exclude = ['__pycache__', '*.pyc', 'migrations/', 'alembic/']

    args = [
        'vulture',
        *directories,
        f'--min-confidence={min_confidence}',
    ]

    for pattern in exclude:
        args.extend(['--exclude', pattern])

    print(f"Running vulture with min confidence: {min_confidence}%")
    result = subprocess.run(
        args,
        capture_output=True,
        text=True
    )

    # Parse output
    dead_code = []
    for line in result.stdout.split('\n'):
        if line.strip() and not line.startswith('#'):
            # Parse vulture output: file:line: message (confidence%)
            parts = line.split(':')
            if len(parts) >= 3:
                file_path = parts[0]
                line_num = parts[1]

                # Extract message and confidence
                message_part = ':'.join(parts[2:])
                if '% confidence' in message_part:
                    message, confidence_str = message_part.rsplit('(', 1)
                    confidence = int(confidence_str.replace('% confidence)', '').strip())

                    dead_code.append({
                        'file': file_path,
                        'line': int(line_num),
                        'message': message.strip(),
                        'confidence': confidence
                    })

    return dead_code


def categorize_dead_code(dead_code: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Categorize dead code by type.

    Args:
        dead_code: List of dead code items

    Returns:
        Dictionary of categorized items
    """
    categories = {
        'functions': [],
        'classes': [],
        'methods': [],
        'variables': [],
        'imports': [],
        'attributes': [],
        'properties': [],
        'other': []
    }

    for item in dead_code:
        message = item['message'].lower()

        if 'function' in message and 'method' not in message:
            categories['functions'].append(item)
        elif 'class' in message:
            categories['classes'].append(item)
        elif 'method' in message:
            categories['methods'].append(item)
        elif 'variable' in message:
            categories['variables'].append(item)
        elif 'import' in message:
            categories['imports'].append(item)
        elif 'attribute' in message:
            categories['attributes'].append(item)
        elif 'property' in message:
            categories['properties'].append(item)
        else:
            categories['other'].append(item)

    # Remove empty categories
    return {k: v for k, v in categories.items() if v}


def generate_report(
    dead_code: List[Dict],
    output_file: str = 'dead_code_report.txt'
):
    """
    Generate dead code report.

    Args:
        dead_code: List of dead code items
        output_file: Output file path
    """
    categorized = categorize_dead_code(dead_code)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Dead Code Detection Report\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total items found: {len(dead_code)}\n")
        f.write(f"Categories: {len(categorized)}\n\n")

        # Summary by category
        f.write("## Summary by Category\n")
        f.write("-" * 80 + "\n")
        for category, items in sorted(categorized.items()):
            f.write(f"  {category.title()}: {len(items)}\n")

        # Detailed breakdown
        for category, items in sorted(categorized.items()):
            f.write(f"\n## {category.title()} ({len(items)} items)\n")
            f.write("-" * 80 + "\n")

            # Sort by confidence (highest first)
            for item in sorted(items, key=lambda x: x['confidence'], reverse=True):
                f.write(f"\n{item['file']}:{item['line']}\n")
                f.write(f"  {item['message']}\n")
                f.write(f"  Confidence: {item['confidence']}%\n")

    print(f"Report generated: {output_file}")
    print(f"Total dead code items: {len(dead_code)}")


def generate_json_report(
    dead_code: List[Dict],
    output_file: str = 'dead_code_report.json'
):
    """
    Generate JSON report.

    Args:
        dead_code: List of dead code items
        output_file: Output file path
    """
    categorized = categorize_dead_code(dead_code)

    report = {
        'total_items': len(dead_code),
        'categories': {k: len(v) for k, v in categorized.items()},
        'items_by_category': categorized,
        'all_items': dead_code
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"JSON report generated: {output_file}")


def generate_removal_script(
    dead_code: List[Dict],
    output_file: str = 'remove_dead_code.sh',
    min_confidence: int = 90
):
    """
    Generate script to remove high-confidence dead code.

    Args:
        dead_code: List of dead code items
        output_file: Output file path
        min_confidence: Minimum confidence to include
    """
    high_confidence = [
        item for item in dead_code
        if item['confidence'] >= min_confidence
    ]

    with open(output_file, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Auto-generated script to remove high-confidence dead code\n")
        f.write(f"# Minimum confidence: {min_confidence}%\n\n")
        f.write("echo 'This script would remove the following:'\n\n")

        for item in high_confidence:
            f.write(f"# {item['file']}:{item['line']} - {item['message']}\n")
            f.write(f"echo '{item['file']}:{item['line']}'\n\n")

    print(f"Removal script generated: {output_file}")
    print(f"High-confidence items (>={min_confidence}%): {len(high_confidence)}")


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Detect dead code')
    parser.add_argument(
        '--directories',
        nargs='+',
        default=['app/'],
        help='Directories to scan (default: app/)'
    )
    parser.add_argument(
        '--min-confidence',
        type=int,
        default=80,
        help='Minimum confidence level (default: 80)'
    )
    parser.add_argument(
        '--exclude',
        nargs='+',
        default=['__pycache__', '*.pyc', 'migrations/', 'alembic/'],
        help='Patterns to exclude'
    )
    parser.add_argument(
        '--output',
        default='dead_code_report.txt',
        help='Output file path'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Generate JSON report'
    )
    parser.add_argument(
        '--generate-script',
        action='store_true',
        help='Generate removal script for high-confidence items'
    )
    parser.add_argument(
        '--skip-install',
        action='store_true',
        help='Skip installing vulture'
    )

    args = parser.parse_args()

    # Check if vulture is installed
    if not check_vulture_installed():
        if args.skip_install:
            print("Error: vulture is not installed")
            print("Install with: pip install vulture")
            sys.exit(1)
        else:
            install_vulture()

    print("\n" + "=" * 80)
    print("DETECTING DEAD CODE")
    print("=" * 80 + "\n")

    # Find dead code
    dead_code = find_dead_code(
        args.directories,
        min_confidence=args.min_confidence,
        exclude=args.exclude
    )

    if not dead_code:
        print("✅ No dead code found!")
        return

    # Generate reports
    generate_report(dead_code, args.output)

    if args.json:
        json_output = args.output.replace('.txt', '.json')
        generate_json_report(dead_code, json_output)

    if args.generate_script:
        script_output = 'remove_dead_code.sh'
        generate_removal_script(dead_code, script_output)


if __name__ == '__main__':
    main()
