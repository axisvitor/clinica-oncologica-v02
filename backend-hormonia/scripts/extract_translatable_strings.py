#!/usr/bin/env python3
"""
Translation String Extraction Script

Extracts hardcoded error messages from Python source files to identify
strings that should be added to translation files.

Usage:
    python scripts/extract_translatable_strings.py

This will:
1. Scan all Python files in app/ directory
2. Extract strings from HTTPException, raise statements
3. Generate a report of untranslated strings
4. Create a template JSON file for new translations
"""

import ast
import json
from pathlib import Path
from typing import Set, Dict, List
from collections import defaultdict
import argparse


class StringExtractor(ast.NodeVisitor):
    """AST visitor to extract string literals from source code."""

    def __init__(self):
        self.error_messages: Set[str] = set()
        self.success_messages: Set[str] = set()
        self.http_exceptions: List[Dict] = []

    def visit_Raise(self, node):
        """Extract strings from raise statements."""
        if isinstance(node.exc, ast.Call):
            # Extract exception message
            for arg in node.exc.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    self.error_messages.add(arg.value)

            # Extract keyword arguments (e.g., detail="message")
            for keyword in node.exc.keywords:
                if keyword.arg == 'detail' and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str):
                        self.error_messages.add(keyword.value.value)

        self.generic_visit(node)

    def visit_Call(self, node):
        """Extract strings from HTTPException calls."""
        if isinstance(node.func, ast.Name) and node.func.id == 'HTTPException':
            exception_info = {
                'status_code': None,
                'detail': None
            }

            for keyword in node.keywords:
                if keyword.arg == 'status_code':
                    if isinstance(keyword.value, ast.Constant):
                        exception_info['status_code'] = keyword.value.value
                elif keyword.arg == 'detail':
                    if isinstance(keyword.value, ast.Constant):
                        exception_info['detail'] = keyword.value.value
                        self.error_messages.add(keyword.value.value)

            if exception_info['detail']:
                self.http_exceptions.append(exception_info)

        self.generic_visit(node)


def extract_from_file(filepath: Path) -> StringExtractor:
    """
    Extract translatable strings from a Python file.

    Args:
        filepath: Path to Python file

    Returns:
        StringExtractor with extracted strings
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source, filename=str(filepath))
        extractor = StringExtractor()
        extractor.visit(tree)

        return extractor
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return StringExtractor()


def categorize_message(message: str) -> str:
    """
    Categorize error message by type.

    Args:
        message: Error message string

    Returns:
        Category name
    """
    message_lower = message.lower()

    if 'patient' in message_lower or 'paciente' in message_lower:
        return 'patient'
    elif 'auth' in message_lower or 'login' in message_lower or 'token' in message_lower:
        return 'auth'
    elif 'quiz' in message_lower or 'question' in message_lower:
        return 'quiz'
    elif 'webhook' in message_lower:
        return 'webhook'
    elif 'saga' in message_lower:
        return 'saga'
    elif 'flow' in message_lower:
        return 'flow'
    elif 'validation' in message_lower or 'invalid' in message_lower or 'required' in message_lower:
        return 'validation'
    elif 'server' in message_lower or 'internal' in message_lower or 'database' in message_lower:
        return 'server'
    else:
        return 'other'


def main():
    """Main extraction function."""
    parser = argparse.ArgumentParser(description='Extract translatable strings from source code')
    parser.add_argument(
        '--directory',
        default='app',
        help='Directory to scan for Python files (default: app)'
    )
    parser.add_argument(
        '--output',
        default='docs/translations/missing_translations.json',
        help='Output file for translation template'
    )
    parser.add_argument(
        '--report',
        default='docs/translations/extraction_report.txt',
        help='Output file for extraction report'
    )

    args = parser.parse_args()

    # Find all Python files
    app_dir = Path(args.directory)
    python_files = list(app_dir.rglob('*.py'))

    print(f"Scanning {len(python_files)} Python files in {app_dir}...")

    # Extract strings from all files
    all_error_messages: Set[str] = set()
    all_http_exceptions: List[Dict] = []

    for filepath in python_files:
        extractor = extract_from_file(filepath)
        all_error_messages.update(extractor.error_messages)
        all_http_exceptions.extend(extractor.http_exceptions)

    print(f"Found {len(all_error_messages)} unique error messages")
    print(f"Found {len(all_http_exceptions)} HTTPException instances")

    # Categorize messages
    categorized = defaultdict(list)
    for message in all_error_messages:
        category = categorize_message(message)
        categorized[category].append(message)

    # Generate translation template
    translation_template = {
        "errors": {}
    }

    for category, messages in sorted(categorized.items()):
        translation_template["errors"][category] = {
            "todo": sorted(messages)
        }

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write translation template
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(translation_template, f, indent=2, ensure_ascii=False)

    print(f"\nTranslation template written to: {output_path}")

    # Generate report
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("TRANSLATION STRING EXTRACTION REPORT\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total Python files scanned: {len(python_files)}\n")
        f.write(f"Total unique error messages: {len(all_error_messages)}\n")
        f.write(f"Total HTTPException instances: {len(all_http_exceptions)}\n\n")

        f.write("=" * 80 + "\n")
        f.write("ERROR MESSAGES BY CATEGORY\n")
        f.write("=" * 80 + "\n\n")

        for category, messages in sorted(categorized.items()):
            f.write(f"\n{category.upper()} ({len(messages)} messages):\n")
            f.write("-" * 40 + "\n")
            for msg in sorted(messages):
                f.write(f"  - {msg}\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("HTTP EXCEPTIONS ANALYSIS\n")
        f.write("=" * 80 + "\n\n")

        # Group by status code
        by_status = defaultdict(list)
        for exc in all_http_exceptions:
            status = exc.get('status_code', 'unknown')
            by_status[status].append(exc['detail'])

        for status, details in sorted(by_status.items()):
            f.write(f"\nStatus {status} ({len(details)} occurrences):\n")
            f.write("-" * 40 + "\n")
            for detail in sorted(set(details)):
                f.write(f"  - {detail}\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("RECOMMENDATIONS\n")
        f.write("=" * 80 + "\n\n")

        f.write("1. Review the generated translation template at:\n")
        f.write(f"   {output_path}\n\n")

        f.write("2. Add translations to:\n")
        f.write("   - backend-hormonia/app/locales/pt-BR.json\n")
        f.write("   - backend-hormonia/app/locales/en-US.json\n\n")

        f.write("3. Replace hardcoded strings with i18n exceptions:\n")
        f.write("   Before: raise HTTPException(404, 'Patient not found')\n")
        f.write("   After:  raise PatientNotFoundException()\n\n")

        f.write("4. Use translation keys for dynamic messages:\n")
        f.write("   from app.config.i18n import t\n")
        f.write("   message = t('errors.patient.not_found')\n\n")

    print(f"Extraction report written to: {report_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for category, messages in sorted(categorized.items()):
        print(f"{category:15s}: {len(messages):3d} messages")

    print("\n" + "=" * 80)
    print(f"Next steps:")
    print(f"1. Review: {output_path}")
    print(f"2. Review: {report_path}")
    print(f"3. Add translations to locales/pt-BR.json and locales/en-US.json")
    print("=" * 80)


if __name__ == '__main__':
    main()
