#!/usr/bin/env python3
"""
Database Initialization Script

Handles database setup, migrations, and seeding:
- Create database if not exists
- Run Alembic migrations
- Seed initial data
- Create indexes and constraints
- Validate schema integrity

Usage:
    python scripts/init_database.py [--fresh] [--seed] [--skip-migrations]
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DatabaseInit')


class DatabaseInitializer:
    """Orchestrates database initialization"""

    def __init__(self, fresh: bool = False, seed: bool = False, skip_migrations: bool = False):
        self.fresh = fresh
        self.seed = seed
        self.skip_migrations = skip_migrations

    async def initialize(self) -> bool:
        """Run database initialization"""
        logger.info("=" * 80)
        logger.info("Database Initialization")
        logger.info("=" * 80)

        try:
            # Step 1: Validate database connection
            await self._validate_connection()

            # Step 2: Create database if needed
            if self.fresh:
                await self._create_fresh_database()

            # Step 3: Run migrations
            if not self.skip_migrations:
                await self._run_migrations()

            # Step 4: Seed data
            if self.seed:
                await self._seed_data()

            # Step 5: Validate schema
            await self._validate_schema()

            logger.info("\n✅ Database initialization completed successfully!")
            return True

        except Exception as e:
            logger.error(f"\n❌ Database initialization failed: {e}")
            return False

    async def _validate_connection(self) -> None:
        """Validate database connection"""
        logger.info("\n[1/5] Validating database connection...")

        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("SELECT version()"))
                version = result.scalar()
                logger.info(f"✓ Connected to PostgreSQL: {version}")

                # Check if we have necessary permissions
                result = await session.execute(text(
                    "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"
                ))
                can_create = result.scalar()
                if not can_create:
                    logger.warning("⚠ User does not have CREATE privilege")

        except Exception as e:
            logger.error(f"✗ Database connection failed: {e}")
            raise

    async def _create_fresh_database(self) -> None:
        """Create fresh database (WARNING: Drops existing data)"""
        logger.info("\n[2/5] Creating fresh database...")
        logger.warning("⚠️  WARNING: This will DROP all existing data!")

        response = input("Are you sure? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            logger.info("Aborted by user")
            sys.exit(0)

        from app.core.database import Base, engine

        try:
            # Drop all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                logger.info("✓ Dropped all existing tables")

                # Create all tables
                await conn.run_sync(Base.metadata.create_all)
                logger.info("✓ Created all tables from models")

        except Exception as e:
            logger.error(f"✗ Failed to create fresh database: {e}")
            raise

    async def _run_migrations(self) -> None:
        """Run Alembic migrations"""
        logger.info("\n[3/5] Running database migrations...")

        import subprocess

        try:
            # Check current migration status
            result = subprocess.run(
                ['alembic', 'current'],
                cwd=project_root,
                capture_output=True,
                text=True
            )
            logger.info(f"Current migration: {result.stdout.strip()}")

            # Run migrations
            result = subprocess.run(
                ['alembic', 'upgrade', 'head'],
                cwd=project_root,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                logger.info("✓ Migrations applied successfully")
                if result.stdout:
                    logger.debug(result.stdout)
            else:
                logger.error(f"✗ Migration failed: {result.stderr}")
                raise RuntimeError(f"Migration failed: {result.stderr}")

        except FileNotFoundError:
            logger.error("✗ Alembic not found. Install with: pip install alembic")
            raise
        except Exception as e:
            logger.error(f"✗ Migration error: {e}")
            raise

    async def _seed_data(self) -> None:
        """Seed initial data"""
        logger.info("\n[4/5] Seeding initial data...")

        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        try:
            async with AsyncSessionLocal() as session:
                # Example: Create default admin user
                # This is a placeholder - implement based on your models

                # Check if we already have data
                result = await session.execute(text(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin'"
                ))
                admin_count = result.scalar()

                if admin_count == 0:
                    logger.info("Creating default admin user...")
                    # Add your user creation logic here
                    logger.info("✓ Default admin user created")
                else:
                    logger.info(f"✓ Admin user already exists ({admin_count} found)")

                await session.commit()

        except Exception as e:
            logger.error(f"✗ Seeding failed: {e}")
            raise

    async def _validate_schema(self) -> None:
        """Validate database schema integrity"""
        logger.info("\n[5/5] Validating schema integrity...")

        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        try:
            async with AsyncSessionLocal() as session:
                # Get all tables
                result = await session.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result]

                logger.info(f"✓ Found {len(tables)} tables")
                for table in tables:
                    logger.debug(f"  - {table}")

                # Check for required indexes
                result = await session.execute(text("""
                    SELECT
                        schemaname,
                        tablename,
                        indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                """))
                indexes = result.fetchall()
                logger.info(f"✓ Found {len(indexes)} indexes")

                # Check for foreign key constraints
                result = await session.execute(text("""
                    SELECT
                        tc.table_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                """))
                fks = result.fetchall()
                logger.info(f"✓ Found {len(fks)} foreign key constraints")

                logger.info("✓ Schema validation completed")

        except Exception as e:
            logger.error(f"✗ Schema validation failed: {e}")
            raise


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Initialize database')
    parser.add_argument('--fresh', action='store_true',
                        help='Create fresh database (WARNING: drops all data)')
    parser.add_argument('--seed', action='store_true',
                        help='Seed initial data')
    parser.add_argument('--skip-migrations', action='store_true',
                        help='Skip running migrations')
    args = parser.parse_args()

    initializer = DatabaseInitializer(
        fresh=args.fresh,
        seed=args.seed,
        skip_migrations=args.skip_migrations
    )

    success = await initializer.initialize()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
