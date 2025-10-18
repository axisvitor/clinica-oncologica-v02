#!/usr/bin/env python3
"""
Legacy Endpoint Files Removal Script

This script safely removes legacy endpoint files after the consolidation period.
It performs checks before removal to ensure no active imports remain.

Usage:
    python scripts/remove_legacy_endpoints.py --dry-run  # Preview changes
    python scripts/remove_legacy_endpoints.py --execute  # Actually remove files
    python scripts/remove_legacy_endpoints.py --backup   # Create backup before removal

Safety Features:
- Dry-run mode by default
- Checks for active imports
- Creates backups before deletion
- Logs all operations
- Rollback capability

Sprint: 3 (Future Enhancement)
Status: Ready for Sprint 4
"""

import os
import sys
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("legacy_removal.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# Legacy files to be removed (after migration period)
LEGACY_FILES = [
    # Health checks (consolidated into monitoring/health.py)
    "app/api/v1/health_consolidated.py",
    "app/api/v1/health_rls.py",
    "app/api/v1/database_health.py",
    "app/api/v1/production_health.py",
    "app/api/v1/railway_health.py",
    "app/api/v1/worker_health.py",
    # Enhanced versions (consolidated)
    "app/api/v1/enhanced_health.py",
    "app/api/v1/enhanced_monitoring.py",
    "app/api/v1/enhanced_messages.py",
    "app/api/v1/enhanced_analytics.py",
    "app/api/v1/enhanced_reports.py",
    "app/api/v1/enhanced_quiz.py",
    # Deprecated/duplicate files
    "app/api/v1/patients_simple.py",
    "app/api/v1/monthly_quiz_public.py.backup",
    # Files moved to new structure (keep originals for now)
    # These will be removed in Phase 2
]

# Files to keep (core functionality, not yet migrated)
KEEP_FILES = [
    "app/api/v1/__init__.py",
    "app/api/v1/auth.py",
    "app/api/v1/flows.py",
    "app/api/v1/alerts.py",
    "app/api/v1/ai.py",
    "app/api/v1/dashboard.py",
    "app/api/v1/docs.py",
    "app/api/v1/localization.py",
    "app/api/v1/medico.py",
    "app/api/v1/physician.py",
    "app/api/v1/platform_sync.py",
    "app/api/v1/system.py",
    "app/api/v1/tasks.py",
    "app/api/v1/upload.py",
    "app/api/v1/debug.py",
    "app/api/v1/config.py",
    "app/api/v1/ab_testing.py",
]


class LegacyFileRemover:
    """Handles safe removal of legacy endpoint files."""

    def __init__(self, root_dir: str, dry_run: bool = True, create_backup: bool = True):
        self.root_dir = Path(root_dir)
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.backup_dir = (
            self.root_dir
            / "backups"
            / f"legacy_removal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self.removed_files: List[Path] = []
        self.failed_files: List[tuple] = []

    def check_imports(self, file_path: Path) -> Set[str]:
        """Find all files that import from the given file."""
        importers = set()
        file_name = file_path.stem

        # Search patterns
        patterns = [
            rf"from\s+app\.api\.v1\.{file_name}\s+import",
            rf"import\s+app\.api\.v1\.{file_name}",
        ]

        # Search all Python files
        for py_file in self.root_dir.rglob("*.py"):
            if py_file == file_path:
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                for pattern in patterns:
                    if re.search(pattern, content):
                        importers.add(str(py_file.relative_to(self.root_dir)))
            except Exception as e:
                logger.warning(f"Could not read {py_file}: {e}")

        return importers

    def create_backup_copy(self, file_path: Path) -> bool:
        """Create backup of file before deletion."""
        try:
            if not self.backup_dir.exists():
                self.backup_dir.mkdir(parents=True, exist_ok=True)

            backup_path = self.backup_dir / file_path.relative_to(self.root_dir)
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(file_path, backup_path)
            logger.info(f"✅ Backed up: {file_path.name} → {backup_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to backup {file_path}: {e}")
            return False

    def remove_file(self, file_path: Path) -> bool:
        """Remove a single legacy file."""
        try:
            full_path = self.root_dir / file_path

            if not full_path.exists():
                logger.warning(f"⚠️  File not found: {file_path}")
                return False

            # Check for active imports
            importers = self.check_imports(full_path)
            if importers:
                logger.warning(f"⚠️  File {file_path.name} is still imported by:")
                for importer in importers:
                    logger.warning(f"     - {importer}")
                logger.warning(f"⚠️  Skipping removal of {file_path.name}")
                self.failed_files.append((file_path, "Active imports found"))
                return False

            if self.dry_run:
                logger.info(f"🔍 [DRY RUN] Would remove: {file_path}")
                return True

            # Create backup if requested
            if self.create_backup:
                if not self.create_backup_copy(full_path):
                    return False

            # Remove the file
            full_path.unlink()
            logger.info(f"✅ Removed: {file_path}")
            self.removed_files.append(file_path)
            return True

        except Exception as e:
            logger.error(f"❌ Failed to remove {file_path}: {e}")
            self.failed_files.append((file_path, str(e)))
            return False

    def remove_all_legacy_files(self) -> Dict[str, int]:
        """Remove all legacy files."""
        logger.info("=" * 80)
        logger.info("Legacy File Removal Process")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'EXECUTE'}")
        logger.info(f"Backup: {'Enabled' if self.create_backup else 'Disabled'}")
        logger.info(f"Root Directory: {self.root_dir}")
        logger.info("")

        stats = {
            "total": len(LEGACY_FILES),
            "removed": 0,
            "skipped": 0,
            "failed": 0,
        }

        for legacy_file in LEGACY_FILES:
            logger.info(f"Processing: {legacy_file}")
            if self.remove_file(Path(legacy_file)):
                stats["removed"] += 1
            else:
                stats["skipped"] += 1

        stats["failed"] = len(self.failed_files)

        return stats

    def generate_report(self, stats: Dict[str, int]):
        """Generate summary report."""
        logger.info("")
        logger.info("=" * 80)
        logger.info("REMOVAL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total files processed: {stats['total']}")
        logger.info(f"Successfully removed: {stats['removed']}")
        logger.info(f"Skipped (has imports): {stats['skipped']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info("")

        if self.removed_files:
            logger.info("Removed files:")
            for file in self.removed_files:
                logger.info(f"  ✅ {file}")
            logger.info("")

        if self.failed_files:
            logger.info("Failed/Skipped files:")
            for file, reason in self.failed_files:
                logger.info(f"  ❌ {file}: {reason}")
            logger.info("")

        if self.create_backup and not self.dry_run and self.removed_files:
            logger.info(f"Backup location: {self.backup_dir}")
            logger.info("")

        logger.info("=" * 80)

    def rollback(self):
        """Rollback: restore files from backup."""
        if not self.backup_dir.exists():
            logger.error("❌ No backup found to rollback from")
            return False

        logger.info("=" * 80)
        logger.info("ROLLBACK: Restoring files from backup")
        logger.info("=" * 80)

        restored = 0
        failed = 0

        for backup_file in self.backup_dir.rglob("*.py"):
            try:
                # Calculate original path
                relative_path = backup_file.relative_to(self.backup_dir)
                original_path = self.root_dir / relative_path

                # Restore file
                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, original_path)

                logger.info(f"✅ Restored: {relative_path}")
                restored += 1
            except Exception as e:
                logger.error(f"❌ Failed to restore {backup_file}: {e}")
                failed += 1

        logger.info("")
        logger.info(f"Restored: {restored} files")
        logger.info(f"Failed: {failed} files")
        logger.info("=" * 80)

        return failed == 0


def main():
    parser = argparse.ArgumentParser(
        description="Remove legacy endpoint files after consolidation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would be removed (safe)
  python scripts/remove_legacy_endpoints.py --dry-run

  # Actually remove files with backup
  python scripts/remove_legacy_endpoints.py --execute --backup

  # Remove without backup (not recommended)
  python scripts/remove_legacy_endpoints.py --execute --no-backup

  # Rollback (restore from backup)
  python scripts/remove_legacy_endpoints.py --rollback --backup-dir backups/legacy_removal_20250115_120000
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without actually removing files (default)",
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually remove files (disables dry-run)",
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup before removal (default)",
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create backup (not recommended)",
    )

    parser.add_argument(
        "--rollback", action="store_true", help="Rollback: restore files from backup"
    )

    parser.add_argument("--backup-dir", type=str, help="Backup directory for rollback")

    parser.add_argument(
        "--root-dir",
        type=str,
        default=".",
        help="Root directory of the project (default: current directory)",
    )

    args = parser.parse_args()

    # Determine dry-run mode
    dry_run = not args.execute
    create_backup = not args.no_backup

    # Get root directory
    root_dir = Path(args.root_dir).resolve()
    if not root_dir.exists():
        logger.error(f"❌ Root directory not found: {root_dir}")
        sys.exit(1)

    # Create remover instance
    remover = LegacyFileRemover(
        root_dir=str(root_dir), dry_run=dry_run, create_backup=create_backup
    )

    # Handle rollback
    if args.rollback:
        if args.backup_dir:
            remover.backup_dir = Path(args.backup_dir)
        success = remover.rollback()
        sys.exit(0 if success else 1)

    # Remove legacy files
    stats = remover.remove_all_legacy_files()
    remover.generate_report(stats)

    # Exit code
    if stats["failed"] > 0:
        sys.exit(1)

    if dry_run:
        logger.info("✅ Dry-run complete. Use --execute to actually remove files.")
        sys.exit(0)

    logger.info("✅ Legacy file removal complete!")
    sys.exit(0)


if __name__ == "__main__":
    main()
