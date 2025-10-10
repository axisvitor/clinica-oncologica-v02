#!/usr/bin/env python3
"""
Script to check production database state and compare with migrations.
"""
import os
import sys
from pathlib import Path
import asyncio
import asyncpg

# Database connection from .env
DATABASE_URL = "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

async def check_alembic_version():
    """Check which migrations are applied in production."""
    print("=" * 80)
    print("CONNECTING TO PRODUCTION DATABASE (AWS RDS)")
    print("=" * 80)

    try:
        # Parse connection URL
        url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        url = url.replace("?sslmode=require", "")

        conn = await asyncpg.connect(url, ssl='require')

        print("\nConnected successfully!\n")

        # Check if alembic_version table exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'alembic_version'
            )
        """)

        if not exists:
            print("WARNING: alembic_version table does NOT exist!")
            print("   This means NO migrations have been applied yet.")
            print("   Database is empty or manually created.\n")
            await conn.close()
            return None

        # Get current migration version
        version = await conn.fetchval("SELECT version_num FROM alembic_version")

        print(f"Current Alembic Version: {version}\n")

        # Get all tables in database
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)

        print(f"Total Tables in Production: {len(tables)}\n")
        print("Tables:")
        for i, row in enumerate(tables, 1):
            print(f"  {i:2d}. {row['table_name']}")

        print("\n" + "=" * 80)
        print("CHECKING FOR SPECIFIC TABLES")
        print("=" * 80 + "\n")

        # Check for webhook_events table
        webhook_events_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'webhook_events'
            )
        """)

        print(f"webhook_events table exists: {'YES' if webhook_events_exists else 'NO'}")

        if webhook_events_exists:
            # Check structure
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'webhook_events'
                ORDER BY ordinal_position
            """)
            print(f"  Columns ({len(columns)}):")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"    - {col['column_name']}: {col['data_type']} {nullable}")

        # Check for webhook_idempotency table
        webhook_idempotency_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'webhook_idempotency'
            )
        """)

        print(f"\nwebhook_idempotency table exists: {'YES' if webhook_idempotency_exists else 'NO'}")

        # Check for whatsapp_delivery_failures table
        whatsapp_failures_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'whatsapp_delivery_failures'
            )
        """)

        print(f"whatsapp_delivery_failures table exists: {'YES' if whatsapp_failures_exists else 'NO'}")

        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80 + "\n")

        print(f"Current migration version: {version}")
        print(f"Latest migration in code: 20251010_000000")

        if version and version < '20251010_000000':
            print("\nWARNING: Production is BEHIND code migrations!")
            print(f"   Production: {version}")
            print(f"   Code:       20251010_000000")
            print("\n   Action: Run 'alembic upgrade head' to apply pending migrations")
        elif version == '20251010_000000':
            print("\nProduction is UP TO DATE with latest migration!")
        elif version and version > '20251010_000000':
            print("\nWARNING: Production is AHEAD of code?!")
            print("   This shouldn't happen. Check migration files.")

        await conn.close()
        return version

    except Exception as e:
        print(f"\nError connecting to database:")
        print(f"   {type(e).__name__}: {str(e)}\n")
        return None

async def get_migration_history():
    """Get full migration history from alembic_version."""
    url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    url = url.replace("?sslmode=require", "")

    try:
        conn = await asyncpg.connect(url, ssl='require')

        # Check if there's a history table (some setups keep history)
        # Usually Alembic only keeps current version
        history = await conn.fetch("""
            SELECT version_num, applied_at
            FROM alembic_version
            ORDER BY version_num
        """)

        if len(history) > 1:
            print("\n" + "=" * 80)
            print("MIGRATION HISTORY")
            print("=" * 80 + "\n")
            for row in history:
                applied = row.get('applied_at', 'unknown')
                print(f"  {row['version_num']} - applied: {applied}")

        await conn.close()
    except Exception as e:
        print(f"Could not fetch history: {e}")

if __name__ == "__main__":
    print("\nProduction Database Inspector")
    print("Checking AWS RDS database state...\n")

    try:
        version = asyncio.run(check_alembic_version())
        if version:
            asyncio.run(get_migration_history())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)
