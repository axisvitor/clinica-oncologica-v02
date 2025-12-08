#!/usr/bin/env python3
"""
Database Schema Validation Script
Pre-Migration Health Check and Snapshot Generator

This script performs comprehensive schema validation before applying migrations:
1. Table and row count analysis
2. Foreign key relationship validation
3. Index health checks
4. Constraint verification
5. Orphaned record detection
6. Migration readiness assessment
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Any
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text, MetaData, Table
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


class SchemaValidator:
    """Comprehensive database schema validation and analysis"""

    def __init__(self, database_url: str):
        """Initialize with database connection"""
        self.engine = create_engine(database_url)
        self.inspector = inspect(self.engine)
        self.metadata = MetaData()
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'database_url': database_url.split('@')[1] if '@' in database_url else 'redacted',
            'tables': {},
            'foreign_keys': {},
            'indexes': {},
            'constraints': {},
            'orphaned_records': {},
            'warnings': [],
            'errors': [],
            'summary': {}
        }

    def validate_all(self) -> Dict:
        """Run all validation checks"""
        print("🔍 Starting comprehensive schema validation...\n")

        try:
            self._check_table_stats()
            self._check_foreign_key_indexes()
            self._validate_foreign_key_relationships()
            self._check_constraint_violations()
            self._check_index_health()
            self._check_migration_specific_requirements()
            self._generate_summary()

            print("\n✅ Schema validation complete!")
            return self.results

        except Exception as e:
            self.results['errors'].append(f"Fatal error during validation: {str(e)}")
            print(f"\n❌ Validation failed: {str(e)}")
            return self.results

    def _check_table_stats(self):
        """Check all tables and their row counts"""
        print("📊 Analyzing table statistics...")

        tables = self.inspector.get_table_names()

        for table_name in sorted(tables):
            try:
                # Get row count
                with self.engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    row_count = result.scalar()

                    # Get disk usage
                    result = conn.execute(text(f"""
                        SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))
                    """))
                    table_size = result.scalar()

                # Get columns
                columns = self.inspector.get_columns(table_name)

                self.results['tables'][table_name] = {
                    'row_count': row_count,
                    'size': table_size,
                    'column_count': len(columns),
                    'columns': [col['name'] for col in columns]
                }

                print(f"  ✓ {table_name}: {row_count:,} rows, {table_size}")

            except Exception as e:
                self.results['errors'].append(f"Error checking table {table_name}: {str(e)}")
                print(f"  ✗ {table_name}: Error - {str(e)}")

    def _check_foreign_key_indexes(self):
        """Check if all foreign keys have corresponding indexes"""
        print("\n🔗 Checking foreign key indexes...")

        tables = self.inspector.get_table_names()
        missing_indexes = []

        for table_name in tables:
            try:
                # Get foreign keys
                fks = self.inspector.get_foreign_keys(table_name)

                # Get existing indexes
                indexes = self.inspector.get_indexes(table_name)
                indexed_columns = set()
                for idx in indexes:
                    # Handle composite indexes by creating tuples
                    if len(idx['column_names']) == 1:
                        indexed_columns.add(idx['column_names'][0])
                    else:
                        indexed_columns.add(tuple(idx['column_names']))

                # Check each FK
                for fk in fks:
                    fk_columns = fk['constrained_columns']

                    # Check single column FK
                    if len(fk_columns) == 1:
                        if fk_columns[0] not in indexed_columns:
                            missing_indexes.append({
                                'table': table_name,
                                'column': fk_columns[0],
                                'references': f"{fk['referred_table']}.{fk['referred_columns']}"
                            })
                    # Check composite FK
                    else:
                        if tuple(fk_columns) not in indexed_columns:
                            missing_indexes.append({
                                'table': table_name,
                                'columns': fk_columns,
                                'references': f"{fk['referred_table']}.{fk['referred_columns']}"
                            })

            except Exception as e:
                self.results['errors'].append(f"Error checking FK indexes for {table_name}: {str(e)}")

        self.results['foreign_keys']['missing_indexes'] = missing_indexes

        if missing_indexes:
            print(f"  ⚠️  Found {len(missing_indexes)} foreign keys without indexes:")
            for mi in missing_indexes:
                if 'column' in mi:
                    print(f"     - {mi['table']}.{mi['column']} → {mi['references']}")
                else:
                    print(f"     - {mi['table']}.({','.join(mi['columns'])}) → {mi['references']}")
            self.results['warnings'].append(f"{len(missing_indexes)} foreign keys without indexes")
        else:
            print("  ✓ All foreign keys have indexes")

    def _validate_foreign_key_relationships(self):
        """Validate all foreign key relationships for orphaned records"""
        print("\n🔎 Validating foreign key relationships...")

        tables = self.inspector.get_table_names()
        orphaned = []

        for table_name in tables:
            try:
                fks = self.inspector.get_foreign_keys(table_name)

                for fk in fks:
                    # Skip self-referential FKs
                    if fk['referred_table'] == table_name:
                        continue

                    # Build query to find orphaned records
                    fk_col = fk['constrained_columns'][0]
                    ref_table = fk['referred_table']
                    ref_col = fk['referred_columns'][0]

                    query = text(f"""
                        SELECT COUNT(*)
                        FROM {table_name} t
                        WHERE t.{fk_col} IS NOT NULL
                        AND NOT EXISTS (
                            SELECT 1 FROM {ref_table} r
                            WHERE r.{ref_col} = t.{fk_col}
                        )
                    """)

                    with self.engine.connect() as conn:
                        result = conn.execute(query)
                        orphan_count = result.scalar()

                        if orphan_count > 0:
                            orphaned.append({
                                'table': table_name,
                                'column': fk_col,
                                'references': f"{ref_table}.{ref_col}",
                                'orphan_count': orphan_count
                            })
                            print(f"  ⚠️  {table_name}.{fk_col}: {orphan_count} orphaned records")

            except Exception as e:
                # Some queries might fail for various reasons, log but continue
                self.results['warnings'].append(f"Could not validate FK for {table_name}: {str(e)}")

        self.results['orphaned_records'] = orphaned

        if not orphaned:
            print("  ✓ No orphaned records found")
        else:
            self.results['warnings'].append(f"Found {len(orphaned)} tables with orphaned records")

    def _check_constraint_violations(self):
        """Check for constraint violations"""
        print("\n🔒 Checking constraint violations...")

        tables = self.inspector.get_table_names()
        violations = []

        for table_name in tables:
            try:
                # Get NOT NULL columns
                columns = self.inspector.get_columns(table_name)

                for col in columns:
                    if not col['nullable'] and col['name'] != 'id':
                        # Check for NULL values in NOT NULL columns
                        query = text(f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE {col['name']} IS NULL
                        """)

                        with self.engine.connect() as conn:
                            result = conn.execute(query)
                            null_count = result.scalar()

                            if null_count > 0:
                                violations.append({
                                    'table': table_name,
                                    'column': col['name'],
                                    'type': 'NOT NULL violation',
                                    'count': null_count
                                })
                                print(f"  ⚠️  {table_name}.{col['name']}: {null_count} NULL values in NOT NULL column")

            except Exception as e:
                self.results['warnings'].append(f"Could not check constraints for {table_name}: {str(e)}")

        self.results['constraints']['violations'] = violations

        if not violations:
            print("  ✓ No constraint violations found")
        else:
            self.results['errors'].append(f"Found {len(violations)} constraint violations")

    def _check_index_health(self):
        """Check index health and usage"""
        print("\n📇 Analyzing index health...")

        try:
            # Get index statistics
            query = text("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_stat_user_indexes
                ORDER BY idx_scan ASC
                LIMIT 20
            """)

            with self.engine.connect() as conn:
                result = conn.execute(query)
                unused_indexes = []

                for row in result:
                    if row.idx_scan == 0:
                        unused_indexes.append({
                            'table': row.tablename,
                            'index': row.indexname,
                            'size': row.index_size,
                            'scans': row.idx_scan
                        })

                self.results['indexes']['unused'] = unused_indexes

                if unused_indexes:
                    print(f"  ℹ️  Found {len(unused_indexes)} potentially unused indexes")
                    for idx in unused_indexes[:5]:  # Show first 5
                        print(f"     - {idx['table']}.{idx['index']} ({idx['size']})")
                else:
                    print("  ✓ All indexes are being used")

        except Exception as e:
            self.results['warnings'].append(f"Could not check index health: {str(e)}")

    def _check_migration_specific_requirements(self):
        """Check requirements specific to pending migrations"""
        print("\n🔧 Checking migration-specific requirements...")

        # Check for patient_flow_states table (migration 003)
        tables = self.inspector.get_table_names()

        if 'patient_flow_states' in tables:
            print("  ✓ patient_flow_states table exists")

            # Check structure
            columns = self.inspector.get_columns('patient_flow_states')
            column_names = [col['name'] for col in columns]

            expected_columns = ['id', 'patient_id', 'flow_id', 'state', 'data', 'created_at', 'updated_at']
            missing_columns = [col for col in expected_columns if col not in column_names]

            if missing_columns:
                self.results['warnings'].append(f"patient_flow_states missing columns: {missing_columns}")
                print(f"  ⚠️  Missing columns: {missing_columns}")
            else:
                print("  ✓ patient_flow_states has expected structure")
        else:
            print("  ℹ️  patient_flow_states table does not exist (will be created by migration)")

    def _generate_summary(self):
        """Generate validation summary"""
        self.results['summary'] = {
            'total_tables': len(self.results['tables']),
            'total_rows': sum(t['row_count'] for t in self.results['tables'].values()),
            'missing_fk_indexes': len(self.results['foreign_keys'].get('missing_indexes', [])),
            'orphaned_record_tables': len(self.results['orphaned_records']),
            'constraint_violations': len(self.results['constraints'].get('violations', [])),
            'unused_indexes': len(self.results['indexes'].get('unused', [])),
            'total_warnings': len(self.results['warnings']),
            'total_errors': len(self.results['errors']),
            'migration_ready': len(self.results['errors']) == 0
        }

    def print_summary(self):
        """Print formatted summary"""
        s = self.results['summary']

        print("\n" + "="*60)
        print("SCHEMA VALIDATION SUMMARY")
        print("="*60)
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Database: {self.results['database_url']}")
        print(f"\nTables: {s['total_tables']}")
        print(f"Total Rows: {s['total_rows']:,}")
        print(f"\nIssues:")
        print(f"  - Missing FK Indexes: {s['missing_fk_indexes']}")
        print(f"  - Orphaned Record Tables: {s['orphaned_record_tables']}")
        print(f"  - Constraint Violations: {s['constraint_violations']}")
        print(f"  - Unused Indexes: {s['unused_indexes']}")
        print(f"\nStatus:")
        print(f"  - Warnings: {s['total_warnings']}")
        print(f"  - Errors: {s['total_errors']}")
        print(f"  - Migration Ready: {'✅ YES' if s['migration_ready'] else '❌ NO'}")
        print("="*60)


def generate_markdown_report(results: Dict, output_path: str):
    """Generate markdown report from validation results"""

    with open(output_path, 'w') as f:
        f.write("# Database Schema Pre-Migration Snapshot\n\n")
        f.write(f"**Generated:** {results['timestamp']}\n\n")
        f.write(f"**Database:** {results['database_url']}\n\n")

        # Summary
        s = results['summary']
        f.write("## Executive Summary\n\n")
        f.write(f"- **Total Tables:** {s['total_tables']}\n")
        f.write(f"- **Total Rows:** {s['total_rows']:,}\n")
        f.write(f"- **Migration Ready:** {'✅ YES' if s['migration_ready'] else '❌ NO'}\n\n")

        if s['total_errors'] > 0:
            f.write(f"### ⚠️ Critical Issues ({s['total_errors']})\n\n")
            for error in results['errors']:
                f.write(f"- {error}\n")
            f.write("\n")

        if s['total_warnings'] > 0:
            f.write(f"### ℹ️ Warnings ({s['total_warnings']})\n\n")
            for warning in results['warnings']:
                f.write(f"- {warning}\n")
            f.write("\n")

        # Table Statistics
        f.write("## Table Statistics\n\n")
        f.write("| Table | Rows | Size | Columns |\n")
        f.write("|-------|------|------|----------|\n")

        for table_name, stats in sorted(results['tables'].items()):
            f.write(f"| {table_name} | {stats['row_count']:,} | {stats['size']} | {stats['column_count']} |\n")

        f.write("\n")

        # Foreign Key Analysis
        missing_fk_indexes = results['foreign_keys'].get('missing_indexes', [])
        if missing_fk_indexes:
            f.write("## Foreign Keys Without Indexes\n\n")
            f.write("| Table | Column(s) | References |\n")
            f.write("|-------|-----------|------------|\n")

            for mi in missing_fk_indexes:
                if 'column' in mi:
                    f.write(f"| {mi['table']} | {mi['column']} | {mi['references']} |\n")
                else:
                    f.write(f"| {mi['table']} | {', '.join(mi['columns'])} | {mi['references']} |\n")

            f.write("\n")

        # Orphaned Records
        if results['orphaned_records']:
            f.write("## Orphaned Records\n\n")
            f.write("| Table | Column | References | Count |\n")
            f.write("|-------|--------|------------|-------|\n")

            for orphan in results['orphaned_records']:
                f.write(f"| {orphan['table']} | {orphan['column']} | {orphan['references']} | {orphan['orphan_count']} |\n")

            f.write("\n")

        # Constraint Violations
        violations = results['constraints'].get('violations', [])
        if violations:
            f.write("## Constraint Violations\n\n")
            f.write("| Table | Column | Type | Count |\n")
            f.write("|-------|--------|------|-------|\n")

            for v in violations:
                f.write(f"| {v['table']} | {v['column']} | {v['type']} | {v['count']} |\n")

            f.write("\n")

        # Unused Indexes
        unused = results['indexes'].get('unused', [])
        if unused:
            f.write("## Potentially Unused Indexes\n\n")
            f.write("| Table | Index | Size | Scans |\n")
            f.write("|-------|-------|------|-------|\n")

            for idx in unused:
                f.write(f"| {idx['table']} | {idx['index']} | {idx['size']} | {idx['scans']} |\n")

            f.write("\n")

        f.write("## Recommendation\n\n")

        if s['migration_ready']:
            f.write("✅ **Database is ready for migration.**\n\n")
            f.write("All critical checks passed. You may proceed with applying migrations.\n")
        else:
            f.write("❌ **Database requires fixes before migration.**\n\n")
            f.write("Please address the errors listed above before proceeding.\n")


def main():
    """Main execution"""
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("❌ Error: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Create validator
    validator = SchemaValidator(database_url)

    # Run validation
    results = validator.validate_all()

    # Print summary
    validator.print_summary()

    # Generate report
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'database')
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'PRE_MIGRATION_SNAPSHOT.md')
    generate_markdown_report(results, output_path)

    print(f"\n📄 Full report saved to: {output_path}")

    # Exit with appropriate code
    if results['summary']['migration_ready']:
        print("\n✅ Database is ready for migration!")
        sys.exit(0)
    else:
        print("\n❌ Database requires fixes before migration!")
        sys.exit(1)


if __name__ == '__main__':
    main()
