#!/usr/bin/env python3
"""
Script to remove deprecated cache service files after successful migration.
Only run this after verifying the migration was successful.
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

# Deprecated cache files to remove
DEPRECATED_CACHE_FILES = [
    "app/services/ai/cache_layer.py",
    "app/services/analytics_cache.py",
    "app/services/cache.py",
    "app/services/cache/specialized/analytics_cache.py",
    "app/services/cache/specialized/jwt_cache.py",
    "app/services/cache/specialized/query_cache.py",
    "app/services/cache/specialized/template_cache.py",
    "app/services/cache_invalidation.py",
    "app/services/cache_service.py",
    "app/services/jwt_cache_service.py",
    "app/services/template_cache.py",
]

def create_final_backup(root_dir: Path):
    """Create final backup before removal."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(f"docs/backups/cache_removal_{timestamp}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    manifest_file = backup_dir / "removed_files.txt"
    with open(manifest_file, 'w') as f:
        f.write(f"Deprecated Cache Files Removal\n")
        f.write(f"Date: {datetime.now()}\n")
        f.write(f"Files removed: {len(DEPRECATED_CACHE_FILES)}\n\n")

        for cache_file in DEPRECATED_CACHE_FILES:
            file_path = root_dir / cache_file
            if file_path.exists():
                # Backup file
                relative_path = Path(cache_file)
                backup_path = backup_dir / relative_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_path)
                f.write(f"{cache_file}\n")

    return backup_dir

def remove_deprecated_files(root_dir: Path, dry_run: bool = True):
    """Remove deprecated cache files."""
    results = {
        'removed': [],
        'not_found': [],
        'errors': [],
    }

    for cache_file in DEPRECATED_CACHE_FILES:
        file_path = root_dir / cache_file

        if not file_path.exists():
            results['not_found'].append(cache_file)
            continue

        try:
            if not dry_run:
                file_path.unlink()
                print(f"✅ Removed: {cache_file}")
            else:
                print(f"[DRY RUN] Would remove: {cache_file}")

            results['removed'].append(cache_file)

        except Exception as e:
            error_msg = f"Error removing {cache_file}: {e}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")

    return results

def cleanup_empty_directories(root_dir: Path):
    """Remove empty cache directories after file removal."""
    cache_dirs = [
        root_dir / "app/services/cache/specialized",
        root_dir / "app/services/cache",
    ]

    for cache_dir in cache_dirs:
        if cache_dir.exists() and not any(cache_dir.iterdir()):
            print(f"🗑️  Removing empty directory: {cache_dir.relative_to(root_dir)}")
            cache_dir.rmdir()

def main():
    root_dir = Path(__file__).parent.parent / "backend-hormonia"

    print("="*80)
    print("DEPRECATED CACHE FILES REMOVAL")
    print("="*80)
    print()

    print(f"📁 Working directory: {root_dir}")
    print(f"📄 Files to remove: {len(DEPRECATED_CACHE_FILES)}")
    print()

    # List files
    print("Files to remove:")
    existing_count = 0
    for cache_file in DEPRECATED_CACHE_FILES:
        file_path = root_dir / cache_file
        status = "✅ EXISTS" if file_path.exists() else "⚠️  NOT FOUND"
        print(f"  {status}: {cache_file}")
        if file_path.exists():
            existing_count += 1

    print()
    print(f"📊 Summary: {existing_count}/{len(DEPRECATED_CACHE_FILES)} files exist")
    print()

    if existing_count == 0:
        print("✅ No files to remove (already cleaned up)")
        return

    # Dry run
    print("🔍 Running DRY RUN...")
    dry_results = remove_deprecated_files(root_dir, dry_run=True)
    print(f"  Would remove: {len(dry_results['removed'])} files")
    print(f"  Not found: {len(dry_results['not_found'])} files")
    if dry_results['errors']:
        print(f"  ⚠️  Errors: {len(dry_results['errors'])}")
    print()

    # Confirm
    print("⚠️  WARNING: This will permanently delete deprecated cache files!")
    print("⚠️  Make sure migration was successful and tests pass.")
    print()
    response = input("Proceed with removal? (yes/no): ")

    if response.lower() != 'yes':
        print("❌ Removal cancelled")
        return

    # Create backup
    print()
    print("📦 Creating final backup...")
    backup_dir = create_final_backup(root_dir)
    print(f"✅ Backup created: {backup_dir}")
    print()

    # Remove files
    print("🗑️  Removing deprecated files...")
    results = remove_deprecated_files(root_dir, dry_run=False)
    print()

    # Cleanup empty directories
    print("🧹 Cleaning up empty directories...")
    cleanup_empty_directories(root_dir)
    print()

    # Summary
    print("="*80)
    print("REMOVAL COMPLETE")
    print("="*80)
    print(f"✅ Files removed: {len(results['removed'])}")
    print(f"⚠️  Files not found: {len(results['not_found'])}")
    print(f"📦 Backup location: {backup_dir}")

    if results['errors']:
        print()
        print(f"❌ Errors: {len(results['errors'])}")
        for error in results['errors']:
            print(f"  - {error}")

    print()
    print("Next steps:")
    print("1. Run tests: pytest tests/ -v")
    print("2. Update __init__.py exports if needed")
    print("3. Commit changes")
    print()

if __name__ == "__main__":
    main()
