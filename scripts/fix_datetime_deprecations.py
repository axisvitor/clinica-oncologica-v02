#!/usr/bin/env python3
"""
Fix datetime.utcnow() deprecation warnings.
Replaces all occurrences with datetime.now(timezone.utc).
"""

import os
import re
from pathlib import Path

def fix_datetime_in_file(file_path):
    """Fix datetime deprecations in a single file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    modified = False

    # Step 1: Update imports
    # Pattern 1: from datetime import datetime
    if re.search(r'^from datetime import datetime(?!\s*,\s*timezone)', content, re.MULTILINE):
        # Check if timezone is already imported
        if ', timezone' not in content and 'from datetime import datetime, timezone' not in content:
            # Add timezone to the import
            content = re.sub(
                r'^from datetime import (datetime(?:,\s*\w+)*)',
                lambda m: f'from datetime import {m.group(1)}, timezone' if 'timezone' not in m.group(1) else m.group(0),
                content,
                flags=re.MULTILINE
            )
            modified = True

    # Step 2: Replace datetime.utcnow() with datetime.now(timezone.utc)
    if 'datetime.utcnow()' in content:
        content = content.replace('datetime.utcnow()', 'datetime.now(timezone.utc)')
        modified = True

    # Step 3: Replace datetime.now() without timezone argument (be careful with this)
    # Only replace in specific contexts where UTC is clearly intended
    # Look for patterns like datetime.now().date(), datetime.now().isoformat(), etc.
    patterns_to_replace = [
        (r'datetime\.now\(\)\.date\(\)', 'datetime.now(timezone.utc).date()'),
        (r'datetime\.now\(\)\.isoformat\(\)', 'datetime.now(timezone.utc).isoformat()'),
        (r'datetime\.now\(\)\.strftime\(', 'datetime.now(timezone.utc).strftime('),
        (r'datetime\.now\(\)\.timestamp\(\)', 'datetime.now(timezone.utc).timestamp()'),
    ]

    for pattern, replacement in patterns_to_replace:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            modified = True

    # Write back if modified
    if modified and content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    return False

def main():
    """Main function to process all Python files."""
    domain_path = Path('/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/domain')

    if not domain_path.exists():
        print(f"Error: {domain_path} does not exist")
        return

    python_files = list(domain_path.rglob('*.py'))
    modified_files = []

    for file_path in python_files:
        try:
            if fix_datetime_in_file(file_path):
                modified_files.append(file_path)
                print(f"✓ Fixed: {file_path.relative_to(domain_path)}")
        except Exception as e:
            print(f"✗ Error processing {file_path}: {e}")

    print(f"\n{'='*60}")
    print(f"Total files processed: {len(python_files)}")
    print(f"Files modified: {len(modified_files)}")
    print(f"{'='*60}")

    if modified_files:
        print("\nModified files:")
        for file_path in modified_files[:10]:  # Show first 10
            print(f"  - {file_path.relative_to(domain_path)}")
        if len(modified_files) > 10:
            print(f"  ... and {len(modified_files) - 10} more")

if __name__ == '__main__':
    main()
