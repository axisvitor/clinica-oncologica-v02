#!/usr/bin/env python3
"""
Apply Retroactive Migrations 011 and 012

These migrations were skipped during the initial migration run (007-018)
but need to be applied for HIPAA compliance and JSONB functionality.

This script applies them directly to the database without using Alembic's
version tracking, since the current version (018) is already past these migrations.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from alembic import op
from alembic.runtime.migration import MigrationContext
from alembic.operations import Operations
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def apply_migration_011():
    """Apply migration 011_hipaa_audit_trail_enhancement.py"""

    logger.info("=" * 80)
    logger.info("APPLYING MIGRATION 011: HIPAA Audit Trail Enhancement")
    logger.info("=" * 80)

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not set in environment")

    engine = create_engine(DATABASE_URL)

    with engine.begin() as conn:
        # Setup Alembic context for op commands
        ctx = MigrationContext.configure(conn)
        op_obj = Operations(ctx)

        # Make op available globally for the migration code
        import alembic
        alembic.op = op_obj

        try:
            logger.info("Step 1: Adding new columns to audit_logs...")

            # Import migration dynamically
            import importlib.util
            migration_path = project_root / "alembic" / "versions" / "011_hipaa_audit_trail_enhancement.py"
            spec = importlib.util.spec_from_file_location("migration_011", migration_path)
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)

            # Execute upgrade
            logger.info("Executing migration 011 upgrade()...")
            migration_module.upgrade()

            logger.info("✅ Migration 011 applied successfully!")

            # Verify some key columns were added
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'audit_logs'
                AND column_name IN ('checksum', 'session_id', 'event_category')
            """))
            new_cols = [row[0] for row in result]
            logger.info(f"✅ Verified new columns: {new_cols}")

        except Exception as e:
            logger.error(f"❌ Migration 011 failed: {e}")
            raise


def apply_migration_012():
    """Apply migration 012_migrate_quiz_response_value_to_jsonb.py"""

    logger.info("=" * 80)
    logger.info("APPLYING MIGRATION 012: Quiz Response JSONB Migration")
    logger.info("=" * 80)

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not set in environment")

    engine = create_engine(DATABASE_URL)

    with engine.begin() as conn:
        # Setup Alembic context
        ctx = MigrationContext.configure(conn)
        op_obj = Operations(ctx)

        import alembic
        alembic.op = op_obj

        try:
            logger.info("Step 1: Creating temporary JSONB column...")

            # Import migration
            import importlib.util
            migration_path = project_root / "alembic" / "versions" / "012_migrate_quiz_response_value_to_jsonb.py"
            spec = importlib.util.spec_from_file_location("migration_012", migration_path)
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)

            # Execute upgrade
            logger.info("Executing migration 012 upgrade()...")
            migration_module.upgrade()

            logger.info("✅ Migration 012 applied successfully!")

            # Verify column type changed
            result = conn.execute(text("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'quiz_responses'
                AND column_name = 'response_value'
            """))
            data_type = result.scalar()
            logger.info(f"✅ Verified response_value type: {data_type}")

            if data_type != 'jsonb':
                raise ValueError(f"Expected jsonb, got {data_type}")

        except Exception as e:
            logger.error(f"❌ Migration 012 failed: {e}")
            raise


def main():
    """Apply both retroactive migrations"""

    logger.info("\n" + "=" * 80)
    logger.info("RETROACTIVE MIGRATION APPLICATION")
    logger.info("Applying skipped migrations 011 and 012")
    logger.info("=" * 80 + "\n")

    try:
        # Apply migration 011
        apply_migration_011()

        logger.info("\n")

        # Apply migration 012
        apply_migration_012()

        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL RETROACTIVE MIGRATIONS APPLIED SUCCESSFULLY!")
        logger.info("=" * 80)

        logger.info("\nSummary:")
        logger.info("  - Migration 011: HIPAA Audit Trail Enhancement ✅")
        logger.info("  - Migration 012: Quiz Response JSONB Migration ✅")
        logger.info("\nNote: alembic_version table was NOT updated (stays at 018)")
        logger.info("      These migrations were applied retroactively.")

        return 0

    except Exception as e:
        logger.error(f"\n❌ MIGRATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
