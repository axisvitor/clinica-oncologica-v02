#!/usr/bin/env python3
"""
Script to migrate from multiple cache services to unified_cache.py
Automatically updates imports and creates backups.
"""
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Cache files to be removed (with their typical import patterns)
DEPRECATED_CACHE_IMPORTS = {
    'ai.cache_layer': ['CacheLayer', 'CacheOperation', 'CacheStrategy'],
    'analytics_cache': ['AnalyticsCacheService'],
    'cache': ['cache'],
    'cache.specialized.analytics_cache': ['AnalyticsCache'],
    'cache.specialized.jwt_cache': ['JWTCache'],
    'cache.specialized.query_cache': ['QueryCache'],
    'cache.specialized.template_cache': ['TemplateCache'],
    'cache_invalidation': ['CacheInvalidationService'],
    'cache_service': ['CacheService'],
    'jwt_cache_service': ['JWTCacheService'],
    'template_cache': ['TemplateRedisCache'],
}

# Mapping to unified_cache patterns
UNIFIED_IMPORT = "from app.services.unified_cache import UnifiedCacheService"
UNIFIED_INSTANCE = "unified_cache = UnifiedCacheService()"

def create_backup_dir():
    """Create timestamped backup directory."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(f"docs/backups/cache_migration_{timestamp}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def find_files_with_cache_imports(root_dir: Path) -> List[Path]:
    """Find all Python files that import deprecated cache services."""
    files_to_update = []

    for root, dirs, files in os.walk(root_dir):
        # Skip directories
        if any(skip in root for skip in ['node_modules', '.git', '__pycache__', 'venv', '.venv', 'tests']):
            continue

        for file in files:
            if not file.endswith('.py'):
                continue

            file_path = Path(root) / file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check if file imports any deprecated cache service
                for module_path in DEPRECATED_CACHE_IMPORTS.keys():
                    patterns = [
                        rf'from\s+app\.services\.{re.escape(module_path)}\s+import',
                        rf'from\s+\..*{re.escape(module_path.split(".")[-1])}\s+import',
                        rf'import\s+app\.services\.{re.escape(module_path)}',
                    ]

                    for pattern in patterns:
                        if re.search(pattern, content):
                            files_to_update.append(file_path)
                            break

            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")

    return list(set(files_to_update))  # Remove duplicates

def backup_file(file_path: Path, backup_dir: Path, root_dir: Path):
    """Backup a file before modification."""
    relative_path = file_path.relative_to(root_dir)
    backup_path = backup_dir / relative_path
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, backup_path)

def update_imports(content: str) -> Tuple[str, int]:
    """Update deprecated cache imports to unified_cache."""
    changes_made = 0
    original_content = content

    # Replace old imports with unified import
    for module_path, classes in DEPRECATED_CACHE_IMPORTS.items():
        # Pattern: from app.services.X import Y
        pattern = rf'from\s+app\.services\.{re.escape(module_path)}\s+import\s+([^;\n]+)'
        if re.search(pattern, content):
            # Remove the old import
            content = re.sub(pattern, '', content)
            changes_made += 1

        # Pattern: import app.services.X
        pattern = rf'import\s+app\.services\.{re.escape(module_path)}'
        if re.search(pattern, content):
            content = re.sub(pattern, '', content)
            changes_made += 1

    # Add unified import if changes were made and not already present
    if changes_made > 0 and UNIFIED_IMPORT not in content:
        # Find a good place to add the import (after other imports)
        import_section_end = 0
        for match in re.finditer(r'^(from|import)\s+', content, re.MULTILINE):
            import_section_end = max(import_section_end, match.end())

        if import_section_end > 0:
            # Find the end of the line
            next_newline = content.find('\n', import_section_end)
            if next_newline != -1:
                content = content[:next_newline+1] + UNIFIED_IMPORT + '\n' + content[next_newline+1:]
        else:
            # No imports found, add at the beginning after docstring
            docstring_end = 0
            if content.startswith('"""') or content.startswith("'''"):
                quote_type = '"""' if content.startswith('"""') else "'''"
                end_index = content.find(quote_type, 3)
                if end_index != -1:
                    docstring_end = end_index + 3

            content = content[:docstring_end] + '\n' + UNIFIED_IMPORT + '\n' + content[docstring_end:]

    return content, changes_made

def analyze_migration(root_dir: Path) -> Dict:
    """Analyze what needs to be migrated."""
    files_to_update = find_files_with_cache_imports(root_dir)

    stats = {
        'files_to_update': len(files_to_update),
        'files_list': files_to_update,
    }

    return stats

def execute_migration(root_dir: Path, backup_dir: Path, dry_run: bool = True) -> Dict:
    """Execute the cache migration."""
    files_to_update = find_files_with_cache_imports(root_dir)

    results = {
        'files_updated': 0,
        'files_backed_up': 0,
        'total_changes': 0,
        'errors': [],
    }

    manifest_file = backup_dir / 'migration_manifest.txt'
    with open(manifest_file, 'w') as manifest:
        manifest.write(f"Cache Service Migration\n")
        manifest.write(f"Date: {datetime.now()}\n")
        manifest.write(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")
        manifest.write(f"Files to update: {len(files_to_update)}\n\n")

        for file_path in files_to_update:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()

                updated_content, changes = update_imports(original_content)

                if changes > 0:
                    relative_path = file_path.relative_to(root_dir)
                    manifest.write(f"{relative_path}: {changes} changes\n")

                    if not dry_run:
                        # Backup original file
                        backup_file(file_path, backup_dir, root_dir)
                        results['files_backed_up'] += 1

                        # Write updated content
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(updated_content)

                    results['files_updated'] += 1
                    results['total_changes'] += changes

            except Exception as e:
                error_msg = f"Error processing {file_path}: {e}"
                results['errors'].append(error_msg)
                manifest.write(f"ERROR: {error_msg}\n")

    return results

def main():
    root_dir = Path(__file__).parent.parent / "backend-hormonia"

    print("="*80)
    print("CACHE SERVICES MIGRATION TOOL")
    print("="*80)
    print()

    # Analyze
    print("📊 Analyzing files...")
    stats = analyze_migration(root_dir)
    print(f"Found {stats['files_to_update']} files that need updating")
    print()

    if stats['files_to_update'] == 0:
        print("✅ No files need updating!")
        return

    print("Files to update:")
    for file_path in stats['files_list'][:10]:
        print(f"  - {file_path.relative_to(root_dir)}")
    if len(stats['files_list']) > 10:
        print(f"  ... and {len(stats['files_list']) - 10} more")
    print()

    # Create backup directory
    backup_dir = create_backup_dir()
    print(f"📦 Backup directory: {backup_dir}")
    print()

    # Dry run first
    print("🔍 Running DRY RUN...")
    dry_results = execute_migration(root_dir, backup_dir, dry_run=True)
    print(f"  Files to update: {dry_results['files_updated']}")
    print(f"  Total changes: {dry_results['total_changes']}")
    if dry_results['errors']:
        print(f"  ⚠️  Errors: {len(dry_results['errors'])}")
        for error in dry_results['errors'][:5]:
            print(f"    - {error}")
    print()

    # Ask for confirmation
    print("⚠️  This will update imports in Python files.")
    print("⚠️  Backups will be created automatically.")
    print()
    response = input("Proceed with migration? (yes/no): ")

    if response.lower() != 'yes':
        print("❌ Migration cancelled")
        return

    # Execute migration
    print()
    print("🚀 Executing migration...")
    live_results = execute_migration(root_dir, backup_dir, dry_run=False)

    print()
    print("="*80)
    print("MIGRATION COMPLETE")
    print("="*80)
    print(f"✅ Files updated: {live_results['files_updated']}")
    print(f"✅ Files backed up: {live_results['files_backed_up']}")
    print(f"✅ Total changes: {live_results['total_changes']}")
    print(f"📦 Backup location: {backup_dir}")
    print(f"📄 Manifest: {backup_dir}/migration_manifest.txt")

    if live_results['errors']:
        print()
        print(f"⚠️  Errors encountered: {len(live_results['errors'])}")
        for error in live_results['errors']:
            print(f"  - {error}")

    print()
    print("Next steps:")
    print("1. Review updated files")
    print("2. Run tests: pytest tests/")
    print("3. Check for any manual fixes needed")
    print("4. Remove deprecated cache files")
    print()

if __name__ == "__main__":
    main()
