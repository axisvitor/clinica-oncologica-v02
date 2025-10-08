#!/usr/bin/env python3
"""
Extract complete production database schema from AWS RDS PostgreSQL.
Generates detailed schema report for SCHEMA_MASTER_COMPLETO.sql update.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import sys

# Database connection parameters
DB_CONFIG = {
    'host': 'database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com',
    'port': 5432,
    'database': 'postgres',
    'user': 'neoplasias',
    'password': 'imdA4mXfM0IxZuVj778E',
    'sslmode': 'require'
}

def connect_db():
    """Establish connection to PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("[OK] Successfully connected to production database")
        return conn
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        sys.exit(1)

def extract_extensions(conn):
    """Extract installed PostgreSQL extensions."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                extname AS name,
                extversion AS version,
                nspname AS schema
            FROM pg_extension e
            JOIN pg_namespace n ON e.extnamespace = n.oid
            WHERE nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY extname;
        """)
        return cur.fetchall()

def extract_enums(conn):
    """Extract custom ENUM types."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                t.typname AS enum_name,
                array_agg(e.enumlabel ORDER BY e.enumsortorder) AS enum_values
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = 'public'
            GROUP BY t.typname
            ORDER BY t.typname;
        """)
        return cur.fetchall()

def extract_tables(conn):
    """Extract all tables with detailed information."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                table_name,
                pg_size_pretty(pg_total_relation_size(quote_ident(table_name)::regclass)) AS total_size,
                (SELECT obj_description(quote_ident(table_name)::regclass)) AS table_comment
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        return cur.fetchall()

def extract_columns(conn, table_name):
    """Extract column details for a specific table."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                column_name,
                data_type,
                udt_name,
                character_maximum_length,
                is_nullable,
                column_default,
                col_description((table_schema||'.'||table_name)::regclass::oid, ordinal_position) AS column_comment
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        return cur.fetchall()

def extract_constraints(conn, table_name):
    """Extract constraints for a specific table."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                conname AS constraint_name,
                contype AS constraint_type,
                pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = %s::regclass
            ORDER BY contype, conname;
        """, (table_name,))
        return cur.fetchall()

def extract_indexes(conn, table_name):
    """Extract indexes for a specific table."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                indexname AS index_name,
                indexdef AS definition
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = %s
            ORDER BY indexname;
        """, (table_name,))
        return cur.fetchall()

def extract_materialized_views(conn):
    """Extract materialized views."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                schemaname,
                matviewname AS view_name,
                definition,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) AS size
            FROM pg_matviews
            WHERE schemaname = 'public'
            ORDER BY matviewname;
        """)
        return cur.fetchall()

def extract_functions(conn):
    """Extract user-defined functions and triggers."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                p.proname AS function_name,
                pg_get_functiondef(p.oid) AS definition,
                pg_get_function_result(p.oid) AS return_type
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public'
              AND p.prokind IN ('f', 'p')
            ORDER BY p.proname;
        """)
        return cur.fetchall()

def extract_triggers(conn):
    """Extract triggers."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                tgname AS trigger_name,
                tgrelid::regclass::text AS table_name,
                pg_get_triggerdef(oid) AS definition
            FROM pg_trigger
            WHERE tgisinternal = false
            ORDER BY tgrelid::regclass::text, tgname;
        """)
        return cur.fetchall()

def extract_rls_policies(conn):
    """Extract Row Level Security policies."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                schemaname,
                tablename,
                policyname AS policy_name,
                permissive,
                roles,
                cmd AS command,
                qual AS using_expression,
                with_check AS with_check_expression
            FROM pg_policies
            WHERE schemaname = 'public'
            ORDER BY tablename, policyname;
        """)
        return cur.fetchall()

def main():
    print("=" * 80)
    print("PRODUCTION DATABASE SCHEMA EXTRACTION")
    print("=" * 80)
    print()

    conn = connect_db()

    try:
        # Extract all schema components
        print("\n1. Extracting Extensions...")
        extensions = extract_extensions(conn)
        print(f"   Found {len(extensions)} extensions")

        print("\n2. Extracting Custom ENUM Types...")
        enums = extract_enums(conn)
        print(f"   Found {len(enums)} custom ENUMs")

        print("\n3. Extracting Tables...")
        tables = extract_tables(conn)
        print(f"   Found {len(tables)} tables")

        print("\n4. Extracting Table Details (columns, constraints, indexes)...")
        table_details = {}
        for table in tables:
            table_name = table['table_name']
            table_details[table_name] = {
                'info': table,
                'columns': extract_columns(conn, table_name),
                'constraints': extract_constraints(conn, table_name),
                'indexes': extract_indexes(conn, table_name)
            }
            print(f"   [OK] {table_name}: {len(table_details[table_name]['columns'])} columns, "
                  f"{len(table_details[table_name]['constraints'])} constraints, "
                  f"{len(table_details[table_name]['indexes'])} indexes")

        print("\n5. Extracting Materialized Views...")
        matviews = extract_materialized_views(conn)
        print(f"   Found {len(matviews)} materialized views")

        print("\n6. Extracting Functions...")
        functions = extract_functions(conn)
        print(f"   Found {len(functions)} functions")

        print("\n7. Extracting Triggers...")
        triggers = extract_triggers(conn)
        print(f"   Found {len(triggers)} triggers")

        print("\n8. Extracting RLS Policies...")
        rls_policies = extract_rls_policies(conn)
        print(f"   Found {len(rls_policies)} RLS policies")

        # Compile complete schema report
        schema_report = {
            'database_info': {
                'host': DB_CONFIG['host'],
                'database': DB_CONFIG['database'],
                'extracted_at': 'NOW()'
            },
            'extensions': extensions,
            'enums': enums,
            'tables': table_details,
            'materialized_views': matviews,
            'functions': functions,
            'triggers': triggers,
            'rls_policies': rls_policies,
            'statistics': {
                'total_tables': len(tables),
                'total_enums': len(enums),
                'total_extensions': len(extensions),
                'total_matviews': len(matviews),
                'total_functions': len(functions),
                'total_triggers': len(triggers),
                'total_rls_policies': len(rls_policies)
            }
        }

        # Save to JSON file
        output_file = 'c:\\Meu Projetos\\clinica-oncologica-v02\\scripts\\production_schema_export.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schema_report, f, indent=2, default=str, ensure_ascii=False)

        print("\n" + "=" * 80)
        print("EXTRACTION COMPLETE")
        print("=" * 80)
        print(f"\nSchema report saved to: {output_file}")
        print("\nSummary:")
        print(f"  • Extensions: {len(extensions)}")
        print(f"  • Custom ENUMs: {len(enums)}")
        print(f"  • Tables: {len(tables)}")
        print(f"  • Materialized Views: {len(matviews)}")
        print(f"  • Functions: {len(functions)}")
        print(f"  • Triggers: {len(triggers)}")
        print(f"  • RLS Policies: {len(rls_policies)}")

    finally:
        conn.close()
        print("\n[OK] Database connection closed")

if __name__ == '__main__':
    main()
