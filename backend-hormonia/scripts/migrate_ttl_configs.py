"""
Migration script to replace hardcoded TTL values with centralized configuration.

This script automatically updates Python files to use the centralized cache configuration
instead of hardcoded TTL values.

Usage:
    python scripts/migrate_ttl_configs.py --dry-run  # Preview changes
    python scripts/migrate_ttl_configs.py            # Apply changes
    python scripts/migrate_ttl_configs.py --file app/services/patient.py  # Migrate specific file
"""

import re
import os
import argparse
import json
from typing import List, Dict, Tuple, Optional
from pathlib import Path


# TTL value to configuration key mapping
TTL_MAPPING = {
    # Flow & Templates
    3600: 'FLOW_TEMPLATE_TTL',

    # User & Auth
    1800: 'USER_SESSION_TTL',
    86400: 'AUTH_TOKEN_TTL',
    604800: 'REFRESH_TOKEN_TTL',

    # Patient Data
    900: 'PATIENT_CACHE_TTL',
    300: 'PATIENT_LIST_TTL',
    600: 'PATIENT_DETAIL_TTL',

    # Quiz
    7200: 'QUIZ_SESSION_TTL',

    # Messages
    # 3600: 'MESSAGE_CACHE_TTL',  # Conflicts with FLOW_TEMPLATE_TTL

    # Webhooks
    # 3600: 'WEBHOOK_IDEMPOTENCY_TTL',  # Conflicts
    # 300: 'WEBHOOK_CACHE_TTL',  # Conflicts

    # Rate Limiting
    60: 'RATE_LIMIT_WINDOW_TTL',

    # Reports & Analytics
    # 1800: 'REPORT_CACHE_TTL',  # Conflicts
    # 300: 'ANALYTICS_CACHE_TTL',  # Conflicts

    # AI
    # 7200: 'AI_RESPONSES_TTL',  # Conflicts

    # Distributed
    30: 'DISTRIBUTED_LOCK_TTL',
    # 3600: 'SAGA_STATE_TTL',  # Conflicts

    # Monitoring
    # 60: 'SYSTEM_METRICS_TTL',  # Conflicts
    # 300: 'RESOURCE_MONITOR_TTL',  # Conflicts
}


def smart_ttl_mapping(ttl_value: int, file_path: str, context: str) -> str:
    """
    Intelligently map TTL value to configuration key based on context.

    Args:
        ttl_value: TTL value in seconds
        file_path: Path of the file being processed
        context: Code context around the TTL

    Returns:
        Configuration key name
    """
    file_lower = file_path.lower()
    context_lower = context.lower()

    # Exact matches first (no conflicts)
    if ttl_value in [900, 600, 7200, 604800, 86400, 30]:
        return TTL_MAPPING.get(ttl_value, f'TTL_{ttl_value}')

    # For conflicting values, use context
    if ttl_value == 3600:  # 1 hour - most conflicts
        if 'flow' in file_lower or 'template' in file_lower or 'flow' in context_lower:
            return 'FLOW_TEMPLATE_TTL'
        elif 'message' in file_lower or 'whatsapp' in context_lower:
            return 'MESSAGE_CACHE_TTL'
        elif 'webhook' in file_lower or 'idempotency' in context_lower:
            return 'WEBHOOK_IDEMPOTENCY_TTL'
        elif 'saga' in file_lower or 'saga' in context_lower:
            return 'SAGA_STATE_TTL'
        elif 'ai' in file_lower or 'openai' in context_lower:
            return 'AI_CONTEXT_TTL'
        else:
            return 'MEDIUM_CACHE_TTL'

    if ttl_value == 1800:  # 30 minutes
        if 'user' in file_lower or 'session' in context_lower:
            return 'USER_SESSION_TTL'
        elif 'patient' in file_lower:
            return 'DOCTOR_CACHE_TTL'
        elif 'report' in file_lower or 'report' in context_lower:
            return 'REPORT_CACHE_TTL'
        elif 'quiz' in file_lower:
            return 'QUIZ_CACHE_TTL'
        else:
            return 'MEDIUM_CACHE_TTL'

    if ttl_value == 300:  # 5 minutes
        if 'patient' in file_lower and 'list' in context_lower:
            return 'PATIENT_LIST_TTL'
        elif 'webhook' in file_lower:
            return 'WEBHOOK_CACHE_TTL'
        elif 'analytics' in file_lower or 'dashboard' in context_lower:
            return 'ANALYTICS_CACHE_TTL'
        elif 'message' in file_lower and 'stats' in context_lower:
            return 'MESSAGE_STATS_TTL'
        elif 'monitor' in file_lower or 'resource' in context_lower:
            return 'RESOURCE_MONITOR_TTL'
        elif 'qrcode' in file_lower or 'qr' in context_lower:
            return 'QRCODE_TTL'
        else:
            return 'SHORT_CACHE_TTL'

    if ttl_value == 60:  # 1 minute
        if 'rate' in file_lower or 'limit' in context_lower:
            return 'RATE_LIMIT_WINDOW_TTL'
        elif 'metric' in file_lower or 'system' in context_lower:
            return 'SYSTEM_METRICS_TTL'
        else:
            return 'RATE_LIMIT_WINDOW_TTL'

    # Default fallback
    return f'TTL_{ttl_value}'


def migrate_file(file_path: str, dry_run: bool = True) -> Tuple[bool, List[str]]:
    """
    Migrate a single file to use centralized TTL configuration.

    Args:
        file_path: Path to Python file
        dry_run: If True, only show what would change

    Returns:
        Tuple of (changed, list of changes)
    """
    changes = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        content = original_content
        needs_import = False

        # Patterns to replace
        patterns = [
            (r'ttl\s*=\s*(\d+)', 'ttl={config_key}'),
            (r'setex\(([^,]+),\s*(\d+)', r'setex(\1, {config_key}'),
            (r'expire\(([^,]+),\s*(\d+)', r'expire(\1, {config_key}'),
            (r'ex\s*=\s*(\d+)', 'ex={config_key}'),
        ]

        for pattern, replacement_template in patterns:
            matches = list(re.finditer(pattern, content))

            for match in reversed(matches):  # Process in reverse to maintain positions
                ttl_value = int(match.group(1) if len(match.groups()) == 1 else match.group(2))

                # Skip small values
                if ttl_value < 10:
                    continue

                # Get context for smart mapping
                line_start = content.rfind('\n', 0, match.start()) + 1
                line_end = content.find('\n', match.end())
                if line_end == -1:
                    line_end = len(content)
                line_context = content[line_start:line_end]

                # Determine config key
                config_key = smart_ttl_mapping(ttl_value, file_path, line_context)

                # Build replacement
                if '{config_key}' in replacement_template:
                    replacement = replacement_template.replace('{config_key}', f'cache_settings.{config_key}')
                else:
                    replacement = replacement_template.format(config_key=f'cache_settings.{config_key}')

                # Replace in content
                old_text = match.group(0)
                content = content[:match.start()] + replacement + content[match.end():]

                needs_import = True
                changes.append(
                    f"Line {content[:match.start()].count(chr(10)) + 1}: "
                    f"{ttl_value}s → cache_settings.{config_key}"
                )

        # Add import if needed
        if needs_import and 'from app.config.settings.cache import cache_settings' not in content:
            # Find appropriate place to add import
            import_line = 'from app.config.settings.cache import cache_settings\n'

            # Try to add after existing app.config imports
            app_config_pattern = r'(from app\.config[^\n]+\n)'
            match = re.search(app_config_pattern, content)

            if match:
                # Add after existing app.config imports
                insert_pos = match.end()
                content = content[:insert_pos] + import_line + content[insert_pos:]
            else:
                # Add after other imports
                last_import_pattern = r'((?:from |import )[^\n]+\n)(?!(?:from |import ))'
                match = re.search(last_import_pattern, content)

                if match:
                    insert_pos = match.end()
                    content = content[:insert_pos] + '\n' + import_line + content[insert_pos:]
                else:
                    # Add at the beginning after docstring/comments
                    content = import_line + '\n' + content

            changes.append("Added import: from app.config.settings.cache import cache_settings")

        # Apply changes if not dry run
        if not dry_run and content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, changes

        return content != original_content, changes

    except Exception as e:
        changes.append(f"ERROR: {str(e)}")
        return False, changes


def migrate_directory(directory: str, dry_run: bool = True) -> Dict[str, any]:
    """
    Migrate all Python files in a directory.

    Args:
        directory: Directory to scan
        dry_run: If True, only show what would change

    Returns:
        Dictionary with migration statistics
    """
    results = {
        'total_files': 0,
        'changed_files': 0,
        'total_changes': 0,
        'files': {}
    }

    for root, dirs, files in os.walk(directory):
        # Skip virtual environments and cache
        dirs[:] = [d for d in dirs if d not in ['.venv', 'venv', '__pycache__', '.pytest_cache']]

        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                results['total_files'] += 1

                changed, changes = migrate_file(file_path, dry_run)

                if changes:
                    rel_path = os.path.relpath(file_path, directory)
                    results['files'][rel_path] = changes
                    results['total_changes'] += len(changes)

                    if changed:
                        results['changed_files'] += 1

    return results


def print_results(results: Dict[str, any], dry_run: bool):
    """Print migration results."""
    print("\n" + "="*80)
    print("TTL MIGRATION REPORT")
    print("="*80)

    print(f"\nMode: {'DRY RUN (no changes applied)' if dry_run else 'APPLYING CHANGES'}")
    print(f"Total files scanned: {results['total_files']}")
    print(f"Files with changes: {results['changed_files']}")
    print(f"Total changes: {results['total_changes']}")

    if results['files']:
        print(f"\nFILES MODIFIED:")
        for file, changes in results['files'].items():
            print(f"\n  {file}:")
            for change in changes:
                print(f"    • {change}")
    else:
        print("\nNo files needed migration!")

    print("\n" + "="*80)
    if dry_run:
        print("Run without --dry-run to apply changes")
    print("="*80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate hardcoded TTL values to centralized configuration'
    )
    parser.add_argument(
        '--directory',
        default='app',
        help='Directory to migrate (default: app)'
    )
    parser.add_argument(
        '--file',
        help='Migrate specific file only'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    parser.add_argument(
        '--output',
        help='Output JSON report file path'
    )

    args = parser.parse_args()

    if args.file:
        # Migrate single file
        print(f"Migrating file: {args.file}")
        changed, changes = migrate_file(args.file, dry_run=args.dry_run)

        print("\nChanges:")
        for change in changes:
            print(f"  • {change}")

        if changed and not args.dry_run:
            print(f"\n✓ File updated successfully")
        elif changed:
            print(f"\n⚠ Run without --dry-run to apply changes")
        else:
            print(f"\n✓ No changes needed")
    else:
        # Migrate directory
        print(f"Migrating directory: {args.directory}")
        results = migrate_directory(args.directory, dry_run=args.dry_run)

        print_results(results, args.dry_run)

        # Save JSON report if requested
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            print(f"Report saved to: {args.output}")


if __name__ == '__main__':
    main()
