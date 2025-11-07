#!/usr/bin/env python3
"""
Script to safely remove legacy/backup files from the codebase.
Creates a backup before removal for safety.
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

# Patterns to identify legacy files
LEGACY_PATTERNS = [
    "_ORIGINAL_BACKUP.py",
    "_old.py",
    "_backup.py",
    ".backup",
    "_DEPRECATED.py",
]

def find_legacy_files(root_dir):
    """Find all legacy files matching patterns."""
    legacy_files = []
    root_path = Path(root_dir).resolve()  # Convert to absolute path
    for pattern in LEGACY_PATTERNS:
        for path in root_path.rglob(f"*{pattern}"):
            if path.is_file():
                legacy_files.append(path.resolve())  # Store as absolute path
    return sorted(legacy_files)

def create_backup(files, backup_dir):
    """Create backup of files before removal."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    cwd = Path.cwd().resolve()

    backup_list = backup_dir / "removed_files_manifest.txt"
    with open(backup_list, 'w') as f:
        f.write(f"Backup created: {datetime.now()}\n")
        f.write(f"Total files: {len(files)}\n\n")

        for file_path in files:
            # Copy to backup maintaining structure
            relative_path = file_path.relative_to(cwd)
            backup_path = backup_dir / relative_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(file_path, backup_path)
            f.write(f"{relative_path}\n")
            print(f"Backed up: {relative_path}")
    
    print(f"\n✅ Backup complete: {backup_dir}")
    print(f"📄 Manifest: {backup_list}")

def remove_files(files, dry_run=False):
    """Remove legacy files."""
    removed_count = 0
    cwd = Path.cwd().resolve()
    for file_path in files:
        relative_path = file_path.relative_to(cwd)
        if dry_run:
            print(f"[DRY RUN] Would remove: {relative_path}")
        else:
            try:
                file_path.unlink()
                print(f"Removed: {relative_path}")
                removed_count += 1
            except Exception as e:
                print(f"Error removing {relative_path}: {e}")

    return removed_count

def main():
    # Find legacy files in backend and frontend
    roots = ["backend-hormonia", "frontend-hormonia"]
    all_legacy_files = []
    
    for root in roots:
        if os.path.exists(root):
            files = find_legacy_files(root)
            all_legacy_files.extend(files)
            print(f"\nFound {len(files)} legacy files in {root}/")
    
    if not all_legacy_files:
        print("✅ No legacy files found!")
        return
    
    print(f"\n📊 Total legacy files found: {len(all_legacy_files)}")
    print("\nLegacy files:")
    cwd = Path.cwd().resolve()
    for f in all_legacy_files[:10]:
        print(f"  - {f.relative_to(cwd)}")
    if len(all_legacy_files) > 10:
        print(f"  ... and {len(all_legacy_files) - 10} more")
    
    # Create backup
    backup_dir = f"docs/backups/legacy_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n🗂️  Creating backup in {backup_dir}...")
    create_backup(all_legacy_files, backup_dir)
    
    # Remove files
    print("\n🗑️  Removing legacy files...")
    removed = remove_files(all_legacy_files, dry_run=False)
    
    print(f"\n✅ Phase complete!")
    print(f"📦 Backup: {backup_dir}")
    print(f"🗑️  Removed: {removed} files")
    print(f"💾 Files backed up safely before removal")

if __name__ == "__main__":
    main()
