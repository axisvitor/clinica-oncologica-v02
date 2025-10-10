"""
Database migration script to create audit_log table.

This script creates the audit_logs table with appropriate indexes
for security event tracking.

Usage:
    python scripts/migrations/add_audit_log_table.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import engine, get_scoped_session
from app.models.audit_log import AuditLog, Base
from app.utils.logging import get_logger

logger = get_logger(__name__)


def create_audit_log_table():
    """Create audit_log table if it doesn't exist."""
    try:
        logger.info("Creating audit_logs table...")

        # Create all tables defined in Base metadata
        # This will create audit_logs table along with its indexes
        Base.metadata.create_all(bind=engine, checkfirst=True)

        logger.info("✅ audit_logs table created successfully")

        # Verify table creation
        with get_scoped_session() as session:
            result = session.execute(
                text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'audit_logs'
                """)
            )
            if result.fetchone():
                logger.info("✅ Table verified in database schema")

                # Check indexes
                indexes_result = session.execute(
                    text("""
                        SELECT indexname
                        FROM pg_indexes
                        WHERE tablename = 'audit_logs'
                    """)
                )
                indexes = [row[0] for row in indexes_result]
                logger.info(f"✅ Created indexes: {', '.join(indexes)}")
            else:
                logger.error("❌ Table not found after creation")
                return False

        return True

    except Exception as e:
        logger.error(f"❌ Failed to create audit_logs table: {e}", exc_info=True)
        return False


def verify_audit_log_enums():
    """Verify audit event type enum is created."""
    try:
        with get_scoped_session() as session:
            result = session.execute(
                text("""
                    SELECT typname
                    FROM pg_type
                    WHERE typname = 'audit_event_type'
                """)
            )
            if result.fetchone():
                logger.info("✅ audit_event_type enum verified")

                # Get enum values
                values_result = session.execute(
                    text("""
                        SELECT enumlabel
                        FROM pg_enum e
                        JOIN pg_type t ON e.enumtypid = t.oid
                        WHERE t.typname = 'audit_event_type'
                    """)
                )
                values = [row[0] for row in values_result]
                logger.info(f"✅ Enum values: {', '.join(values)}")
                return True
            else:
                logger.warning("⚠️  audit_event_type enum not found")
                return False

    except Exception as e:
        logger.error(f"❌ Failed to verify enum: {e}", exc_info=True)
        return False


def rollback_migration():
    """Rollback migration by dropping audit_logs table."""
    try:
        logger.warning("⚠️  Rolling back migration: dropping audit_logs table...")

        with get_scoped_session() as session:
            session.execute(text("DROP TABLE IF EXISTS audit_logs CASCADE"))
            session.execute(text("DROP TYPE IF EXISTS audit_event_type CASCADE"))
            session.commit()

        logger.info("✅ Rollback completed successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage audit_log table migration")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (drop table)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify table exists without creating"
    )

    args = parser.parse_args()

    if args.rollback:
        if rollback_migration():
            logger.info("Migration rollback completed")
            sys.exit(0)
        else:
            logger.error("Migration rollback failed")
            sys.exit(1)

    if args.verify_only:
        with get_scoped_session() as session:
            result = session.execute(
                text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'audit_logs'
                """)
            )
            if result.fetchone():
                logger.info("✅ audit_logs table exists")
                verify_audit_log_enums()
                sys.exit(0)
            else:
                logger.error("❌ audit_logs table does not exist")
                sys.exit(1)

    # Create table
    if create_audit_log_table():
        verify_audit_log_enums()
        logger.info("✅ Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed")
        sys.exit(1)
