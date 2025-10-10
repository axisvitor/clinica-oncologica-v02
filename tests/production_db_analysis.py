#!/usr/bin/env python3
"""
Production Database Analysis Script
==================================

This script connects to the production PostgreSQL database and analyzes its structure,
specifically checking for Firebase fields, user_sync_log table, ENUM types, and materialized views.

Author: Database Tester Agent (Hive Mind)
Date: 2025-10-09
"""

import psycopg
import sys
import json
from datetime import datetime

# Production database connection string
DATABASE_URL = "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

def analyze_production_database():
    """Analyze the production database structure and generate a comprehensive report."""

    try:
        print("=" * 80)
        print("PRODUCTION DATABASE STRUCTURE ANALYSIS")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Database: AWS RDS PostgreSQL")
        print(f"Host: database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com")
        print("")

        # Connect to production database
        conn = psycopg.connect(DATABASE_URL)
        cursor = conn.cursor()

        print("✅ Connected successfully to production database")
        print("")

        # 1. List all tables
        print("1. ALL TABLES IN PRODUCTION:")
        print("-" * 50)
        cursor.execute("""
            SELECT schemaname, tablename,
                   CASE WHEN schemaname = 'public' THEN 'User Table'
                        ELSE 'System Table' END as table_type
            FROM pg_tables
            WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
            ORDER BY schemaname, tablename;
        """)
        tables = cursor.fetchall()

        public_tables = []
        for schema, table, table_type in tables:
            if schema == 'public':
                public_tables.append(table)
            print(f"  {schema}.{table} ({table_type})")

        print(f"\nTotal tables: {len(tables)}")
        print(f"Public schema tables: {len(public_tables)}")
        print("")

        # 2. Check users table structure for Firebase fields
        print("2. USERS TABLE STRUCTURE:")
        print("-" * 50)
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
            ORDER BY ordinal_position;
        """)
        users_columns = cursor.fetchall()

        firebase_fields = []
        for col_name, data_type, is_nullable, default, max_length in users_columns:
            firebase_indicator = ""
            if any(fb_field in col_name.lower() for fb_field in ['firebase', 'uid', 'custom_claims']):
                firebase_fields.append(col_name)
                firebase_indicator = " ⚡ FIREBASE FIELD"

            print(f"  {col_name}: {data_type}")
            if max_length:
                print(f"    Max Length: {max_length}")
            print(f"    Nullable: {is_nullable}")
            if default:
                print(f"    Default: {default}")
            print(f"    {firebase_indicator}")
            print("")

        print(f"Firebase-related fields found: {len(firebase_fields)}")
        if firebase_fields:
            print(f"Firebase fields: {', '.join(firebase_fields)}")
        print("")

        # 3. Check if user_sync_log table exists
        print("3. USER_SYNC_LOG TABLE:")
        print("-" * 50)
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'user_sync_log'
            );
        """)
        user_sync_log_exists = cursor.fetchone()[0]

        if user_sync_log_exists:
            print("✅ user_sync_log table EXISTS")

            # Get structure
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'user_sync_log'
                ORDER BY ordinal_position;
            """)
            sync_log_columns = cursor.fetchall()

            print("Structure:")
            for col_name, data_type, is_nullable, default in sync_log_columns:
                print(f"  {col_name}: {data_type} (Nullable: {is_nullable})")
                if default:
                    print(f"    Default: {default}")

            # Get row count
            cursor.execute("SELECT COUNT(*) FROM user_sync_log;")
            row_count = cursor.fetchone()[0]
            print(f"Row count: {row_count}")

        else:
            print("❌ user_sync_log table does NOT exist")
        print("")

        # 4. Check ENUM types
        print("4. ENUM TYPES IN PRODUCTION:")
        print("-" * 50)
        cursor.execute("""
            SELECT
                t.typname as enum_name,
                string_agg(e.enumlabel, ', ' ORDER BY e.enumsortorder) as enum_values
            FROM pg_type t
            INNER JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typtype = 'e'
            GROUP BY t.typname
            ORDER BY t.typname;
        """)
        enum_types = cursor.fetchall()

        if enum_types:
            for enum_name, enum_values in enum_types:
                print(f"  {enum_name}: [{enum_values}]")
        else:
            print("  No ENUM types found")

        print(f"Total ENUM types: {len(enum_types)}")
        print("")

        # 5. List materialized views
        print("5. MATERIALIZED VIEWS:")
        print("-" * 50)
        cursor.execute("""
            SELECT schemaname, matviewname, definition
            FROM pg_matviews
            WHERE schemaname = 'public'
            ORDER BY matviewname;
        """)
        materialized_views = cursor.fetchall()

        if materialized_views:
            for schema, view_name, definition in materialized_views:
                print(f"  {schema}.{view_name}")
                print(f"    Definition (truncated): {definition[:100]}...")
                print("")
        else:
            print("  No materialized views found")

        print(f"Total materialized views: {len(materialized_views)}")
        print("")

        # 6. Check for specific migration indicators
        print("6. MIGRATION STATUS INDICATORS:")
        print("-" * 50)

        # Check alembic version table
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'alembic_version'
            );
        """)
        alembic_exists = cursor.fetchone()[0]

        if alembic_exists:
            cursor.execute("SELECT version_num FROM alembic_version;")
            current_version = cursor.fetchone()
            if current_version:
                print(f"✅ Alembic version table exists - Current version: {current_version[0]}")
            else:
                print("⚠️  Alembic version table exists but no version recorded")
        else:
            print("❌ Alembic version table does NOT exist")

        # Check for recent Firebase migration indicators
        firebase_migration_indicators = [
            "firebase_uid", "firebase_custom_claims", "firebase_metadata",
            "last_firebase_sync", "firebase_sync_status"
        ]

        firebase_found = []
        for field in firebase_migration_indicators:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'users'
                    AND column_name = %s
                );
            """, (field,))
            if cursor.fetchone()[0]:
                firebase_found.append(field)

        if firebase_found:
            print(f"✅ Firebase fields detected: {', '.join(firebase_found)}")
        else:
            print("❌ No Firebase fields detected in users table")

        print("")

        # 7. Generate summary report
        print("7. PRODUCTION DATABASE SUMMARY:")
        print("-" * 50)
        print(f"Total tables: {len(public_tables)}")
        print(f"Firebase integration: {'Yes' if firebase_found else 'No'}")
        print(f"User sync logging: {'Enabled' if user_sync_log_exists else 'Disabled'}")
        print(f"ENUM types: {len(enum_types)}")
        print(f"Materialized views: {len(materialized_views)}")
        print(f"Migration system: {'Alembic' if alembic_exists else 'Unknown'}")

        # Close connection
        cursor.close()
        conn.close()

        print("")
        print("=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)

        return {
            "timestamp": datetime.now().isoformat(),
            "tables": public_tables,
            "firebase_fields": firebase_fields,
            "user_sync_log_exists": user_sync_log_exists,
            "enum_types": dict(enum_types) if enum_types else {},
            "materialized_views": [view[1] for view in materialized_views],
            "alembic_version": current_version[0] if alembic_exists and current_version else None
        }

    except Exception as e:
        print(f"❌ Error analyzing database: {e}")
        return None

if __name__ == "__main__":
    result = analyze_production_database()
    if result:
        # Save detailed report
        with open("production_db_analysis_report.json", "w") as f:
            json.dump(result, f, indent=2)
        print(f"📄 Detailed report saved to: production_db_analysis_report.json")