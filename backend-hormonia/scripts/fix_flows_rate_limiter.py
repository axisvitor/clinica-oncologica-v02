#!/usr/bin/env python3
"""
Fix rate limiter Request parameter in all flows/ subdirectory files.
"""

import re
import os
from pathlib import Path

def fix_file(filepath):
    """Fix a single file."""
    print(f"\nProcessing {filepath}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    fixes_count = 0

    # Check if Request is imported
    has_request_import = 'from fastapi import' in content and 'Request' in content.split('from fastapi import')[1].split('\n')[0]

    # Add Request import if missing
    if not has_request_import:
        # Find the fastapi import line
        fastapi_import_match = re.search(r'from fastapi import ([^\n]+)', content)
        if fastapi_import_match:
            imports = fastapi_import_match.group(1)
            if 'Request' not in imports:
                # Add Request to imports
                new_imports = imports.rstrip() + ', Request'
                content = content.replace(
                    f'from fastapi import {imports}',
                    f'from fastapi import {new_imports}'
                )
                print(f"  ✓ Added Request to fastapi imports")

    # Pattern to find rate-limited endpoints WITHOUT request parameter
    # Matches: @limiter.limit("...") \n async def func_name( \n    (no request: Request here)
    pattern = r'(@limiter\.limit\([^)]+\))\s*\n\s*async def ([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\n((?!\s*request:\s*Request))'

    def replacement(match):
        nonlocal fixes_count
        decorator = match.group(1)
        func_name = match.group(2)
        rest = match.group(3)
        fixes_count += 1
        print(f"  ✓ Fixed {func_name}")
        return f'{decorator}\nasync def {func_name}(\n    request: Request,\n{rest}'

    content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    if content != original_content:
        # Create backup
        backup_path = f"{filepath}.backup"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)

        # Write fixed content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✅ Applied {fixes_count} fixes to {filepath}")
        print(f"  📦 Backup created: {backup_path}")
        return fixes_count
    else:
        print(f"  ✓ No fixes needed")
        return 0

def main():
    """Fix all files in flows/ directory."""
    flows_dir = Path("/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/flows")

    if not flows_dir.exists():
        print(f"❌ Directory not found: {flows_dir}")
        return

    print(f"Scanning {flows_dir} for rate-limited endpoints...")

    total_fixes = 0
    files_fixed = 0

    for py_file in flows_dir.glob("*.py"):
        if py_file.name.startswith('_'):
            continue

        fixes = fix_file(str(py_file))
        if fixes > 0:
            files_fixed += 1
            total_fixes += fixes

    print(f"\n{'='*80}")
    print(f"Total files fixed: {files_fixed}")
    print(f"Total fixes applied: {total_fixes}")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
