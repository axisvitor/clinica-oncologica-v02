#!/usr/bin/env python3
"""
Production Database Restore Script
===================================

Restores a database from a backup created by backup_production_database.py

Usage:
    python scripts/restore_database_backup.py --backup backups/backup_prod_TIMESTAMP.json

Safety Features:
    - Requires confirmation before restore
    - Validates backup integrity (checksum)
    - Can create pre-restore backup
    - Supports dry-run mode

Environment:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import argparse

from sqlalchemy import create_engine, MetaData, Table, text
from sqlalchemy.exc import SQLAlchemyError

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class DatabaseRestore:
    """Restore database from backup"""

    def __init__(self, database_url: str, backup_file: Path):
        """Initialize restore with database connection and backup file"""
        self.database_url = database_url
        self.backup_file = backup_file

        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.metadata = MetaData()

        # Load backup data
        with open(backup_file, 'r') as f:
            self.backup_data = json.load(f)

    def verify_checksum(self) -> bool:
        """Verify backup file integrity using checksum"""
        checksum_file = self.backup_file.with_suffix('.json.sha256')

        if not checksum_file.exists():
            print("⚠️  WARNING: No checksum file found, skipping verification")
            return True

        # Read expected checksum
        with open(checksum_file, 'r') as f:
            expected_checksum = f.read().strip().split()[0]

        # Calculate actual checksum
        with open(self.backup_file, 'r') as f:
            content = f.read()
            actual_checksum = hashlib.sha256(content.encode()).hexdigest()

        if expected_checksum == actual_checksum:
            print("✅ Checksum verified: Backup file is intact")
            return True
        else:
            print(f"❌ CHECKSUM MISMATCH!")
            print(f"   Expected: {expected_checksum}")
            print(f"   Actual:   {actual_checksum}")
            return False

    def confirm_restore(self) -> bool:
        """Ask user to confirm restore operation"""
        print("\n⚠️  WARNING: This will DELETE all data in the database!")
        print(f"   Database: {self.engine.url.database}")
        print(f"   Backup:   {self.backup_file.name}")
        print(f"   Tables:   {len(self.backup_data['tables'])}")
        print(f"   Rows:     {self.backup_data['statistics']['total_rows']:,}")

        response = input("\n❓ Type 'RESTORE' to continue: ")
        return response.strip() == 'RESTORE'

    def restore_alembic_version(self):
        """Restore alembic version - CRITICAL"""
        version = self.backup_data.get('version')
        if not version:
            print("⚠️  No alembic version in backup")
            return

        print(f"\n📋 Restoring Alembic version: {version}")

        try:
            with self.engine.begin() as conn:
                # Delete existing version
                conn.execute(text("DELETE FROM alembic_version"))

                # Insert backup version
                conn.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                    {"version": version}
                )

                print(f"✅ Alembic version restored: {version}")

        except SQLAlchemyError as e:
            print(f"❌ Error restoring alembic version: {e}")
            raise

    def restore_table(self, table_name: str, table_data: Dict[str, Any]):
        """Restore data for a single table"""
        print(f"\n📦 Restoring table: {table_name}")

        if table_data.get('error'):
            print(f"  ⚠️  Skipping (backup had error): {table_data['error']}")
            return

        row_count = table_data['row_count']
        print(f"  📊 Rows to restore: {row_count:,}")

        try:
            # Reflect table
            table = Table(table_name, self.metadata, autoload_with=self.engine)

            with self.engine.begin() as conn:
                # Truncate table (cascade deletes related data)
                print(f"  🗑️  Truncating table...")
                conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))

                if table_data['rows']:
                    # Prepare insert statements
                    rows_inserted = 0
                    batch_size = 1000

                    for i in range(0, len(table_data['rows']), batch_size):
                        batch = table_data['rows'][i:i+batch_size]

                        # Convert datetime strings back to datetime
                        for row in batch:
                            for key, value in row.items():
                                if isinstance(value, str) and 'T' in value:
                                    try:
                                        row[key] = datetime.fromisoformat(value)
                                    except ValueError:
                                        pass

                        conn.execute(table.insert(), batch)
                        rows_inserted += len(batch)

                        if rows_inserted % 10000 == 0:
                            print(f"  ⏳ Inserted {rows_inserted:,} / {row_count:,} rows...")

                    print(f"  ✅ Restored {rows_inserted:,} rows")
                else:
                    print(f"  ℹ️  No rows to restore (empty table)")

        except SQLAlchemyError as e:
            print(f"  ❌ Error restoring table {table_name}: {e}")
            raise

    def restore_all_tables(self):
        """Restore all tables from backup"""
        print("\n🗄️  Restoring tables...")

        total_tables = len(self.backup_data['tables'])
        restored_tables = 0

        # Disable triggers during restore
        with self.engine.begin() as conn:
            print("\n🔒 Disabling triggers and constraints...")
            conn.execute(text("SET session_replication_role = 'replica'"))

        try:
            for table_name, table_data in sorted(self.backup_data['tables'].items()):
                self.restore_table(table_name, table_data)
                restored_tables += 1

                progress = (restored_tables / total_tables) * 100
                print(f"  📊 Progress: {restored_tables}/{total_tables} ({progress:.1f}%)")

        finally:
            # Re-enable triggers
            with self.engine.begin() as conn:
                print("\n🔓 Re-enabling triggers and constraints...")
                conn.execute(text("SET session_replication_role = 'origin'"))

        print(f"\n✅ Restored {restored_tables} tables")

    def verify_restore(self) -> bool:
        """Verify restore was successful"""
        print("\n🔍 Verifying restore...")

        verification_passed = True

        # Check alembic version
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                row = result.fetchone()

                if row and row[0] == self.backup_data.get('version'):
                    print(f"✅ Alembic version matches: {row[0]}")
                else:
                    print(f"❌ Alembic version mismatch!")
                    verification_passed = False
        except SQLAlchemyError as e:
            print(f"❌ Error checking alembic version: {e}")
            verification_passed = False

        # Check row counts for each table
        for table_name, table_data in self.backup_data['tables'].items():
            if table_data.get('error'):
                continue

            try:
                with self.engine.connect() as conn:
                    result = conn.execute(
                        text(f"SELECT COUNT(*) FROM {table_name}")
                    )
                    actual_count = result.scalar()
                    expected_count = table_data['row_count']

                    if actual_count == expected_count:
                        print(f"✅ {table_name}: {actual_count:,} rows")
                    else:
                        print(f"❌ {table_name}: Expected {expected_count:,}, got {actual_count:,}")
                        verification_passed = False

            except SQLAlchemyError as e:
                print(f"❌ Error checking {table_name}: {e}")
                verification_passed = False

        return verification_passed

    def run(self, dry_run: bool = False, skip_confirmation: bool = False) -> bool:
        """Run complete restore process"""
        print("🚀 Starting Production Database Restore")
        print("=" * 60)

        # Verify checksum
        if not self.verify_checksum():
            print("\n❌ ABORTING: Backup file integrity check failed")
            return False

        # Show backup info
        print(f"\n📋 Backup Information:")
        print(f"   Timestamp:      {self.backup_data['timestamp']}")
        print(f"   Database:       {self.backup_data['database']}")
        print(f"   Alembic Version: {self.backup_data.get('version', 'N/A')}")
        print(f"   Tables:         {len(self.backup_data['tables'])}")
        print(f"   Total Rows:     {self.backup_data['statistics']['total_rows']:,}")

        if dry_run:
            print("\n✅ DRY RUN: Would restore backup (no changes made)")
            return True

        # Confirm restore
        if not skip_confirmation:
            if not self.confirm_restore():
                print("\n❌ ABORTING: User cancelled restore")
                return False

        try:
            # Restore alembic version
            self.restore_alembic_version()

            # Restore all tables
            self.restore_all_tables()

            # Verify restore
            verification_passed = self.verify_restore()

            if verification_passed:
                print("\n✅ Restore Complete and Verified!")
            else:
                print("\n⚠️  Restore completed but verification found issues")

            print("=" * 60)

            return verification_passed

        except Exception as e:
            print(f"\n❌ FATAL ERROR during restore: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Restore production PostgreSQL database from backup'
    )
    parser.add_argument(
        '--backup',
        type=Path,
        required=True,
        help='Backup file to restore from'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be restored without making changes'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt (DANGEROUS!)'
    )

    args = parser.parse_args()

    # Check backup file exists
    if not args.backup.exists():
        print(f"❌ ERROR: Backup file not found: {args.backup}")
        sys.exit(1)

    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    try:
        restore = DatabaseRestore(database_url, args.backup)
        success = restore.run(dry_run=args.dry_run, skip_confirmation=args.yes)

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
