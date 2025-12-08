#!/usr/bin/env python3
"""
Audit hardcoded regex patterns in the codebase.

This script scans all Python files to find hardcoded regex patterns
that should be extracted to centralized constants.
"""
import re
import json
from pathlib import Path
from typing import List, Dict
from collections import defaultdict


def find_regex_patterns(directory: str) -> List[Dict]:
    """
    Find all regex patterns in code.

    Args:
        directory: Root directory to scan

    Returns:
        List of dictionaries containing pattern information
    """
    patterns = []

    # Pattern to find regex compile or raw strings that look like regex
    regex_compile = r're\.compile\([rf]?["\'](.+?)["\']\)'
    raw_string = r'[rf]["\'](.+?)["\']'

    for py_file in Path(directory).rglob('*.py'):
        # Skip our own regex patterns file
        if 'regex_patterns.py' in str(py_file):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

                # Find re.compile patterns
                for match in re.finditer(regex_compile, content):
                    pattern = match.group(1)
                    line_num = content[:match.start()].count('\n') + 1

                    # Skip simple patterns
                    if len(pattern) > 10 and any(c in pattern for c in r'\d\w\s[]{}+*?|()'):
                        patterns.append({
                            'file': str(py_file.relative_to(directory)),
                            'line': line_num,
                            'pattern': pattern,
                            'type': 're.compile',
                            'context': lines[line_num - 1].strip() if line_num - 1 < len(lines) else ''
                        })
        except Exception as e:
            print(f"Error processing {py_file}: {e}")

    return patterns


def categorize_patterns(patterns: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Categorize patterns by type.

    Args:
        patterns: List of pattern dictionaries

    Returns:
        Dictionary of categorized patterns
    """
    categories = defaultdict(list)

    for pattern in patterns:
        p = pattern['pattern']

        # Categorize by pattern type
        if 'cpf' in pattern['context'].lower() or r'\d{3}\.\d{3}\.\d{3}' in p:
            categories['CPF'].append(pattern)
        elif 'phone' in pattern['context'].lower() or 'telefone' in pattern['context'].lower():
            categories['Phone'].append(pattern)
        elif 'email' in pattern['context'].lower() or '@' in p:
            categories['Email'].append(pattern)
        elif 'date' in pattern['context'].lower() or 'data' in pattern['context'].lower():
            categories['Date'].append(pattern)
        elif 'url' in pattern['context'].lower() or 'http' in p:
            categories['URL'].append(pattern)
        elif 'password' in pattern['context'].lower() or 'senha' in pattern['context'].lower():
            categories['Password'].append(pattern)
        elif 'crm' in pattern['context'].lower() or 'cid' in pattern['context'].lower():
            categories['Medical'].append(pattern)
        else:
            categories['Other'].append(pattern)

    return dict(categories)


def generate_report(patterns: List[Dict], output_file: str = 'regex_audit_report.txt'):
    """
    Generate audit report.

    Args:
        patterns: List of pattern dictionaries
        output_file: Output file path
    """
    categorized = categorize_patterns(patterns)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Regex Patterns Audit Report\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total patterns found: {len(patterns)}\n")
        f.write(f"Categories: {len(categorized)}\n\n")

        for category, items in sorted(categorized.items()):
            f.write(f"\n## {category} ({len(items)} patterns)\n")
            f.write("-" * 80 + "\n")

            for item in items:
                f.write(f"\nFile: {item['file']}:{item['line']}\n")
                f.write(f"Pattern: {item['pattern']}\n")
                f.write(f"Context: {item['context']}\n")

    print(f"Report generated: {output_file}")
    print(f"Total patterns found: {len(patterns)}")
    print(f"Categories: {', '.join(categorized.keys())}")


def generate_json_report(patterns: List[Dict], output_file: str = 'regex_audit_report.json'):
    """
    Generate JSON report for programmatic processing.

    Args:
        patterns: List of pattern dictionaries
        output_file: Output file path
    """
    categorized = categorize_patterns(patterns)

    report = {
        'total_patterns': len(patterns),
        'categories': {k: len(v) for k, v in categorized.items()},
        'patterns_by_category': categorized,
        'all_patterns': patterns
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"JSON report generated: {output_file}")


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Audit regex patterns in codebase')
    parser.add_argument(
        '--directory',
        default='app/',
        help='Directory to scan (default: app/)'
    )
    parser.add_argument(
        '--output',
        default='regex_audit_report.txt',
        help='Output file path (default: regex_audit_report.txt)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Generate JSON report'
    )

    args = parser.parse_args()

    print(f"Scanning directory: {args.directory}")
    patterns = find_regex_patterns(args.directory)

    if not patterns:
        print("No hardcoded regex patterns found!")
        return

    generate_report(patterns, args.output)

    if args.json:
        json_output = args.output.replace('.txt', '.json')
        generate_json_report(patterns, json_output)


if __name__ == '__main__':
    main()
