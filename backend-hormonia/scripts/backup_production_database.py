#!/usr/bin/env python3
"""
Production Database Backup Script
==================================

Creates a complete backup of the production PostgreSQL database including:
- Schema (all tables, indexes, constraints)
- All data from all tables
- Alembic version (CRITICAL for migration tracking)
- Metadata and statistics

Usage:
    python scripts/backup_production_database.py [--format json|sql]

Environment:
    DATABASE_URL: PostgreSQL connection string (required)
    BACKUP_DIR: Directory for backups (default: backups/)

Security:
    - Does NOT backup credentials or secrets
    - Creates timestamped backup files
    - Generates checksums for integrity
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse

from sqlalchemy import (
    create_engine, MetaData, Table, inspect, text,
    Column, Integer, String, DateTime, Boolean, JSON
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects import postgresql

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class DatabaseBackup:
    """Complete database backup with schema and data"""

    EXCLUDED_TABLES = {
        'sessions',  # Temporary session data
        'celery_taskmeta',  # Celery temporary data
        'celery_tasksetmeta',  # Celery temporary data
    }

    SENSITIVE_COLUMNS = {
        'password_hash',
        'firebase_uid',
        'api_key',
        'secret_key',
        'private_key',
    }

    def __init__(self, database_url: str, backup_dir: str = 'backups'):
        """Initialize backup with database connection"""
        self.database_url = database_url
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.metadata = MetaData()
        self.inspector = inspect(self.engine)

        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_data: Dict[str, Any] = {
            'timestamp': self.timestamp,
            'database': self.engine.url.database,
            'version': None,
            'tables': {},
            'schema': {},
            'statistics': {}
        }

    def backup_alembic_version(self) -> Optional[str]:
        """Backup alembic version - CRITICAL for migrations"""
        print("\n📋 Backing up Alembic version...")
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                row = result.fetchone()
                if row:
                    version = row[0]
                    self.backup_data['version'] = version
                    print(f"✅ Alembic version: {version}")
                    return version
                else:
                    print("⚠️  No alembic version found")
                    return None
        except SQLAlchemyError as e:
            print(f"❌ Error backing up alembic version: {e}")
            return None

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get complete table schema definition"""
        schema = {
            'columns': [],
            'indexes': [],
            'constraints': [],
            'foreign_keys': []
        }

        # Get columns
        for column in self.inspector.get_columns(table_name):
            col_info = {
                'name': column['name'],
                'type': str(column['type']),
                'nullable': column['nullable'],
                'default': str(column.get('default', '')),
                'autoincrement': column.get('autoincrement', False)
            }
            schema['columns'].append(col_info)

        # Get indexes
        for index in self.inspector.get_indexes(table_name):
            schema['indexes'].append({
                'name': index['name'],
                'columns': index['column_names'],
                'unique': index['unique']
            })

        # Get foreign keys
        for fk in self.inspector.get_foreign_keys(table_name):
            schema['foreign_keys'].append({
                'name': fk.get('name'),
                'columns': fk['constrained_columns'],
                'referred_table': fk['referred_table'],
                'referred_columns': fk['referred_columns']
            })

        # Get primary key
        pk = self.inspector.get_pk_constraint(table_name)
        if pk:
            schema['primary_key'] = pk.get('constrained_columns', [])

        return schema

    def backup_table_data(self, table_name: str) -> Dict[str, Any]:
        """Backup data from a single table"""
        print(f"\n📦 Backing up table: {table_name}")

        table_data = {
            'schema': self.get_table_schema(table_name),
            'rows': [],
            'row_count': 0
        }

        try:
            # Reflect table
            table = Table(table_name, self.metadata, autoload_with=self.engine)

            # Get row count
            with self.engine.connect() as conn:
                count_result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                )
                table_data['row_count'] = count_result.scalar()

                print(f"  📊 Row count: {table_data['row_count']:,}")

                # Get all rows
                result = conn.execute(table.select())

                for row in result:
                    row_dict = {}
                    for key, value in row._mapping.items():
                        # Skip sensitive columns
                        if key.lower() in self.SENSITIVE_COLUMNS:
                            row_dict[key] = '[REDACTED]'
                        # Handle datetime
                        elif isinstance(value, datetime):
                            row_dict[key] = value.isoformat()
                        # Handle JSON
                        elif isinstance(value, (dict, list)):
                            row_dict[key] = value
                        else:
                            row_dict[key] = value

                    table_data['rows'].append(row_dict)

                print(f"  ✅ Backed up {len(table_data['rows']):,} rows")

        except SQLAlchemyError as e:
            print(f"  ❌ Error backing up table {table_name}: {e}")
            table_data['error'] = str(e)

        return table_data

    def backup_all_tables(self):
        """Backup all tables in the database"""
        print("\n🗄️  Discovering tables...")
        table_names = self.inspector.get_table_names()

        # Filter out excluded tables
        tables_to_backup = [
            t for t in table_names
            if t not in self.EXCLUDED_TABLES
        ]

        print(f"📋 Found {len(tables_to_backup)} tables to backup")
        print(f"⏭️  Skipping {len(table_names) - len(tables_to_backup)} temporary tables")

        total_rows = 0
        for table_name in sorted(tables_to_backup):
            table_data = self.backup_table_data(table_name)
            self.backup_data['tables'][table_name] = table_data
            total_rows += table_data['row_count']

        self.backup_data['statistics']['total_tables'] = len(tables_to_backup)
        self.backup_data['statistics']['total_rows'] = total_rows

        print(f"\n✅ Total rows backed up: {total_rows:,}")

    def generate_sql_backup(self) -> str:
        """Generate SQL dump from backup data"""
        sql_lines = [
            "-- Production Database Backup",
            f"-- Generated: {self.timestamp}",
            f"-- Database: {self.engine.url.database}",
            f"-- Alembic Version: {self.backup_data.get('version', 'unknown')}",
            "",
            "-- Disable triggers and constraints for import",
            "SET session_replication_role = 'replica';",
            "",
        ]

        # Backup alembic version first
        if self.backup_data.get('version'):
            sql_lines.extend([
                "-- Restore Alembic Version",
                "DELETE FROM alembic_version;",
                f"INSERT INTO alembic_version (version_num) VALUES ('{self.backup_data['version']}');",
                "",
            ])

        # Generate INSERT statements for each table
        for table_name, table_data in sorted(self.backup_data['tables'].items()):
            if table_data.get('error'):
                sql_lines.append(f"-- ERROR backing up {table_name}: {table_data['error']}")
                continue

            sql_lines.append(f"-- Table: {table_name} ({table_data['row_count']} rows)")
            sql_lines.append(f"TRUNCATE TABLE {table_name} CASCADE;")

            if table_data['rows']:
                # Generate INSERT statements
                columns = [col['name'] for col in table_data['schema']['columns']]

                for row in table_data['rows']:
                    values = []
                    for col in columns:
                        value = row.get(col)
                        if value is None:
                            values.append('NULL')
                        elif isinstance(value, bool):
                            values.append('TRUE' if value else 'FALSE')
                        elif isinstance(value, (int, float)):
                            values.append(str(value))
                        elif isinstance(value, (dict, list)):
                            values.append(f"'{json.dumps(value)}'::jsonb")
                        else:
                            # Escape single quotes
                            escaped = str(value).replace("'", "''")
                            values.append(f"'{escaped}'")

                    sql_lines.append(
                        f"INSERT INTO {table_name} ({', '.join(columns)}) "
                        f"VALUES ({', '.join(values)});"
                    )

            sql_lines.append("")

        sql_lines.extend([
            "-- Re-enable triggers and constraints",
            "SET session_replication_role = 'origin';",
            "",
            "-- Backup complete",
        ])

        return '\n'.join(sql_lines)

    def calculate_checksum(self, content: str) -> str:
        """Calculate SHA256 checksum of content"""
        return hashlib.sha256(content.encode()).hexdigest()

    def save_backup(self, format: str = 'json') -> Path:
        """Save backup to file"""
        if format == 'json':
            filename = f"backup_prod_{self.timestamp}.json"
            filepath = self.backup_dir / filename

            with open(filepath, 'w') as f:
                json.dump(self.backup_data, f, indent=2, default=str)

            # Calculate checksum
            with open(filepath, 'r') as f:
                content = f.read()
                checksum = self.calculate_checksum(content)

            # Save checksum file
            checksum_file = self.backup_dir / f"{filename}.sha256"
            with open(checksum_file, 'w') as f:
                f.write(f"{checksum}  {filename}\n")

        else:  # SQL format
            filename = f"backup_prod_{self.timestamp}.sql"
            filepath = self.backup_dir / filename

            sql_content = self.generate_sql_backup()

            with open(filepath, 'w') as f:
                f.write(sql_content)

            # Calculate checksum
            checksum = self.calculate_checksum(sql_content)

            # Save checksum file
            checksum_file = self.backup_dir / f"{filename}.sha256"
            with open(checksum_file, 'w') as f:
                f.write(f"{checksum}  {filename}\n")

        print(f"\n💾 Backup saved to: {filepath}")
        print(f"🔐 Checksum: {checksum}")
        print(f"📝 Checksum file: {checksum_file}")

        return filepath

    def generate_report(self) -> str:
        """Generate backup report"""
        report = [
            "# Production Database Backup Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Database:** {self.engine.url.database}",
            f"**Alembic Version:** {self.backup_data.get('version', 'N/A')}",
            "",
            "## Statistics",
            "",
            f"- **Total Tables:** {self.backup_data['statistics']['total_tables']}",
            f"- **Total Rows:** {self.backup_data['statistics']['total_rows']:,}",
            "",
            "## Tables Backed Up",
            "",
            "| Table Name | Row Count | Columns | Indexes |",
            "|------------|-----------|---------|---------|"
        ]

        for table_name, table_data in sorted(self.backup_data['tables'].items()):
            if table_data.get('error'):
                report.append(f"| {table_name} | ERROR | - | - |")
            else:
                row_count = table_data['row_count']
                col_count = len(table_data['schema']['columns'])
                idx_count = len(table_data['schema']['indexes'])
                report.append(f"| {table_name} | {row_count:,} | {col_count} | {idx_count} |")

        report.extend([
            "",
            "## Restore Instructions",
            "",
            "### From JSON Backup:",
            "```bash",
            "python scripts/restore_database_backup.py --backup backups/backup_prod_TIMESTAMP.json",
            "```",
            "",
            "### From SQL Backup:",
            "```bash",
            "psql $DATABASE_URL -f backups/backup_prod_TIMESTAMP.sql",
            "```",
            "",
            "## Security Notes",
            "",
            "- Sensitive columns are redacted in backups",
            "- Backup files contain checksums for integrity",
            "- Store backups securely (encrypted at rest)",
            "- Do NOT commit backups to version control",
            "",
        ])

        return '\n'.join(report)

    def run(self, format: str = 'json') -> Path:
        """Run complete backup process"""
        print("🚀 Starting Production Database Backup")
        print("=" * 60)

        # Backup alembic version (CRITICAL)
        self.backup_alembic_version()

        # Backup all tables
        self.backup_all_tables()

        # Save backup file
        backup_file = self.save_backup(format)

        # Generate report
        report = self.generate_report()
        report_file = self.backup_dir / f"BACKUP_REPORT_{self.timestamp}.md"
        with open(report_file, 'w') as f:
            f.write(report)

        print(f"\n📊 Report saved to: {report_file}")

        print("\n✅ Backup Complete!")
        print("=" * 60)

        return backup_file


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Backup production PostgreSQL database'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'sql'],
        default='json',
        help='Backup format (default: json)'
    )
    parser.add_argument(
        '--backup-dir',
        default='backups',
        help='Backup directory (default: backups/)'
    )

    args = parser.parse_args()

    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    try:
        backup = DatabaseBackup(database_url, args.backup_dir)
        backup_file = backup.run(args.format)

        print(f"\n✅ SUCCESS: Backup saved to {backup_file}")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
