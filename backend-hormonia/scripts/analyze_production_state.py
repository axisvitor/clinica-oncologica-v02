#!/usr/bin/env python3
"""
Analyze production database state and map to migrations.
Run from backend-hormonia directory.
"""
import asyncio
import asyncpg
import sys

DATABASE_URL = "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

async def get_production_tables():
    """Get all tables in production database."""
    url = DATABASE_URL.replace("?sslmode=require", "")

    try:
        conn = await asyncpg.connect(url, ssl='require')

        # Get all tables
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)

        # Get alembic version
        version = await conn.fetchval("""
            SELECT version_num FROM alembic_version
        """)

        # Get detailed info for key tables
        webhook_events_columns = None
        if any(t['table_name'] == 'webhook_events' for t in tables):
            webhook_events_columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'webhook_events'
                ORDER BY ordinal_position
            """)

        await conn.close()

        return {
            'version': version,
            'tables': [t['table_name'] for t in tables],
            'webhook_events_columns': webhook_events_columns
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

async def main():
    print("Analyzing Production Database State...")
    print("=" * 80)

    result = await get_production_tables()

    if not result:
        print("Failed to connect to database")
        sys.exit(1)

    print(f"\nAlembic Version: {result['version']}")
    print(f"Total Tables: {len(result['tables'])}")
    print("\nTables in Production:")
    for i, table in enumerate(result['tables'], 1):
        print(f"  {i:2d}. {table}")

    if result['webhook_events_columns']:
        print("\nwebhook_events table structure:")
        for col in result['webhook_events_columns']:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  - {col['column_name']}: {col['data_type']} {nullable}")

    # Check for specific tables
    print("\n" + "=" * 80)
    print("KEY TABLE CHECK")
    print("=" * 80)

    checks = {
        'webhook_idempotency': 'New table (migration 20251009_235500)',
        'whatsapp_delivery_failures': 'New table (migration 20251009_230000)',
        'quiz_questions': 'New table (migration 029)',
        'ab_experiments': 'New table (migration 022)',
        'message_status_events': 'New table (migration 018)',
        'webhook_events': 'Existing table (migration 019)',
        'flow_kinds': 'New table (migration 015)',
        'flow_template_versions': 'New table (migration 015)',
        'audit_log_entries': 'Existing table',
    }

    for table, description in checks.items():
        exists = table in result['tables']
        status = "✓ EXISTS" if exists else "✗ MISSING"
        print(f"  {status:12s} {table:30s} - {description}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(1)
