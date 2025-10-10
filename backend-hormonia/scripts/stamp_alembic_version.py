#!/usr/bin/env python3
"""
Script to stamp the alembic_version table with the baseline migration.
This marks the production database as having the baseline migration applied.
"""
import asyncio
import asyncpg
import sys

# Database connection from .env
DATABASE_URL = "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

async def stamp_alembic_version():
    """Stamp the alembic_version table with baseline migration."""
    print("=" * 80)
    print("STAMPING ALEMBIC VERSION IN PRODUCTION DATABASE")
    print("=" * 80)
    print()

    try:
        # Parse connection URL
        url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        url = url.replace("?sslmode=require", "")

        print("Connecting to AWS RDS...")
        conn = await asyncpg.connect(url, ssl='require', timeout=30)
        print("Connected successfully!\n")

        # Check current version
        current_version = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"Current alembic_version: {current_version}\n")

        if current_version == '20251010_010000':
            print("Database is already stamped with baseline migration!")
            print("Nothing to do.\n")
            await conn.close()
            return

        # Clear any existing version
        if current_version:
            print(f"Clearing existing version: {current_version}")
            await conn.execute("DELETE FROM alembic_version")
            print("Cleared.\n")

        # Insert baseline version
        print("Inserting baseline migration version: 20251010_010000")
        await conn.execute(
            "INSERT INTO alembic_version (version_num) VALUES ($1)",
            '20251010_010000'
        )
        print("SUCCESS! Database stamped with baseline migration.\n")

        # Verify
        new_version = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"Verified alembic_version: {new_version}\n")

        print("=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print()
        print("1. Verify: alembic current")
        print("   Should show: 20251010_010000 (head)")
        print()
        print("2. Future migrations can now be applied:")
        print("   alembic upgrade head")
        print()
        print("3. Deploy to Railway - alembic upgrade head will work!")
        print()

        await conn.close()

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {str(e)}\n")
        sys.exit(1)

if __name__ == "__main__":
    print("\nAlembic Version Stamping Tool")
    print("Marking production database as having baseline migration applied...\n")

    try:
        asyncio.run(stamp_alembic_version())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)
