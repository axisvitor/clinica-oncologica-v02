"""
Database Analysis Script
Comprehensive analysis of Supabase PostgreSQL database schema, relationships, and security.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, MetaData, text
from sqlalchemy.engine import reflection
from app.database import engine
from app.config import settings
import json
from datetime import datetime


def analyze_database():
    """Perform comprehensive database analysis."""
    print("=" * 80)
    print("SUPABASE DATABASE ANALYSIS REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {settings.DATABASE_URL.split('@')[1].split('/')[0] if '@' in settings.DATABASE_URL else 'Unknown'}")
    print("=" * 80)
    print()

    # Create inspector
    inspector = inspect(engine)

    # Get all table names
    tables = inspector.get_table_names(schema='public')

    print(f"📊 TOTAL TABLES FOUND: {len(tables)}")
    print()

    # Analyze each table
    table_analysis = {}

    for table_name in sorted(tables):
        print(f"\n{'='*80}")
        print(f"📋 TABLE: {table_name}")
        print(f"{'='*80}")

        analysis = {
            'columns': [],
            'primary_keys': [],
            'foreign_keys': [],
            'indexes': [],
            'constraints': []
        }

        # Get columns
        columns = inspector.get_columns(table_name, schema='public')
        print(f"\n  📌 COLUMNS ({len(columns)}):")
        for col in columns:
            col_info = {
                'name': col['name'],
                'type': str(col['type']),
                'nullable': col['nullable'],
                'default': str(col.get('default', 'None'))
            }
            analysis['columns'].append(col_info)
            nullable_str = "NULL" if col['nullable'] else "NOT NULL"
            default_str = f" DEFAULT {col.get('default')}" if col.get('default') else ""
            print(f"    - {col['name']:<30} {str(col['type']):<20} {nullable_str}{default_str}")

        # Get primary keys
        pk_constraint = inspector.get_pk_constraint(table_name, schema='public')
        if pk_constraint and pk_constraint['constrained_columns']:
            analysis['primary_keys'] = pk_constraint['constrained_columns']
            print(f"\n  🔑 PRIMARY KEY: {', '.join(pk_constraint['constrained_columns'])}")

        # Get foreign keys
        foreign_keys = inspector.get_foreign_keys(table_name, schema='public')
        if foreign_keys:
            print(f"\n  🔗 FOREIGN KEYS ({len(foreign_keys)}):")
            for fk in foreign_keys:
                fk_info = {
                    'name': fk.get('name'),
                    'columns': fk['constrained_columns'],
                    'referred_table': fk['referred_table'],
                    'referred_columns': fk['referred_columns']
                }
                analysis['foreign_keys'].append(fk_info)
                print(f"    - {fk.get('name', 'unnamed')}")
                print(f"      {', '.join(fk['constrained_columns'])} -> {fk['referred_table']}({', '.join(fk['referred_columns'])})")

        # Get indexes
        indexes = inspector.get_indexes(table_name, schema='public')
        if indexes:
            print(f"\n  📇 INDEXES ({len(indexes)}):")
            for idx in indexes:
                idx_info = {
                    'name': idx['name'],
                    'columns': idx['column_names'],
                    'unique': idx.get('unique', False)
                }
                analysis['indexes'].append(idx_info)
                unique_str = " (UNIQUE)" if idx.get('unique') else ""
                print(f"    - {idx['name']}{unique_str}")
                print(f"      Columns: {', '.join(idx['column_names'])}")

        # Get check constraints
        try:
            check_constraints = inspector.get_check_constraints(table_name, schema='public')
            if check_constraints:
                print(f"\n  ✓ CHECK CONSTRAINTS ({len(check_constraints)}):")
                for chk in check_constraints:
                    analysis['constraints'].append({
                        'name': chk.get('name'),
                        'sqltext': chk.get('sqltext', '')
                    })
                    print(f"    - {chk.get('name', 'unnamed')}: {chk.get('sqltext', 'N/A')}")
        except Exception as e:
            print(f"\n  ⚠️  Could not retrieve check constraints: {e}")

        table_analysis[table_name] = analysis

    # Analyze RLS policies
    print(f"\n\n{'='*80}")
    print("🔒 ROW LEVEL SECURITY (RLS) ANALYSIS")
    print(f"{'='*80}")

    with engine.connect() as conn:
        # Check if RLS is enabled on tables
        rls_query = text("""
            SELECT
                schemaname,
                tablename,
                rowsecurity as rls_enabled
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)

        try:
            result = conn.execute(rls_query)
            rls_tables = result.fetchall()

            print(f"\n  Tables with RLS:")
            for row in rls_tables:
                status = "✓ ENABLED" if row[2] else "✗ DISABLED"
                print(f"    {row[1]:<30} {status}")

            # Get RLS policies
            policies_query = text("""
                SELECT
                    schemaname,
                    tablename,
                    policyname,
                    permissive,
                    roles,
                    cmd,
                    qual
                FROM pg_policies
                WHERE schemaname = 'public'
                ORDER BY tablename, policyname;
            """)

            result = conn.execute(policies_query)
            policies = result.fetchall()

            if policies:
                print(f"\n  RLS Policies ({len(policies)}):")
                current_table = None
                for policy in policies:
                    if current_table != policy[1]:
                        current_table = policy[1]
                        print(f"\n    📋 {current_table}:")
                    print(f"      - {policy[2]}")
                    print(f"        Command: {policy[5]}")
                    print(f"        Roles: {policy[4]}")
            else:
                print("\n  ⚠️  No RLS policies found!")

        except Exception as e:
            print(f"\n  ⚠️  Could not query RLS information: {e}")

    # Database statistics
    print(f"\n\n{'='*80}")
    print("📈 DATABASE STATISTICS")
    print(f"{'='*80}")

    with engine.connect() as conn:
        try:
            # Table sizes
            size_query = text("""
                SELECT
                    table_name,
                    pg_size_pretty(pg_total_relation_size(quote_ident(table_name)::regclass)) as total_size,
                    pg_size_pretty(pg_relation_size(quote_ident(table_name)::regclass)) as table_size,
                    pg_size_pretty(pg_indexes_size(quote_ident(table_name)::regclass)) as indexes_size
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY pg_total_relation_size(quote_ident(table_name)::regclass) DESC;
            """)

            result = conn.execute(size_query)
            sizes = result.fetchall()

            if sizes:
                print(f"\n  Table Sizes:")
                print(f"  {'Table Name':<30} {'Total Size':<15} {'Data':<15} {'Indexes':<15}")
                print(f"  {'-'*75}")
                for row in sizes:
                    print(f"  {row[0]:<30} {row[1]:<15} {row[2]:<15} {row[3]:<15}")

        except Exception as e:
            print(f"\n  ⚠️  Could not query table sizes: {e}")

    # Recommendations
    print(f"\n\n{'='*80}")
    print("💡 RECOMMENDATIONS")
    print(f"{'='*80}")

    recommendations = []

    # Check for tables without indexes
    for table_name, analysis in table_analysis.items():
        if len(analysis['foreign_keys']) > 0 and len(analysis['indexes']) <= 1:  # <= 1 because PK is usually an index
            recommendations.append(f"⚠️  Table '{table_name}' has foreign keys but few indexes. Consider adding indexes on FK columns.")

    # Check for tables without primary keys
    for table_name, analysis in table_analysis.items():
        if not analysis['primary_keys']:
            recommendations.append(f"❌ Table '{table_name}' has NO PRIMARY KEY! This is critical.")

    if recommendations:
        print("\n  Issues found:")
        for i, rec in enumerate(recommendations, 1):
            print(f"\n  {i}. {rec}")
    else:
        print("\n  ✓ No major issues detected!")

    print(f"\n\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}\n")

    # Save detailed JSON report
    report = {
        'generated_at': datetime.now().isoformat(),
        'database': settings.DATABASE_URL.split('@')[1].split('/')[0] if '@' in settings.DATABASE_URL else 'Unknown',
        'total_tables': len(tables),
        'tables': table_analysis,
        'recommendations': recommendations
    }

    report_path = Path(__file__).parent / 'database_analysis_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"📄 Detailed JSON report saved to: {report_path}\n")


if __name__ == "__main__":
    try:
        analyze_database()
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
