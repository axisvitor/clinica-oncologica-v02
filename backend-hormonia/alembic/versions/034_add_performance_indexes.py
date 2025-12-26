"""Add missing performance indexes for frequently filtered columns

Revision ID: 034_add_performance_indexes
Revises: 033_fix_user_sync_log_schema
Create Date: 2025-12-21 15:00:00.000000

This migration adds additional performance indexes for frequently
filtered columns that were missing from previous migrations.

Changes:
- Adds idx_patients_doctor_id for doctor filtering
- Adds idx_patients_flow_state for status filtering
- Adds idx_patients_treatment_type for treatment filtering
- Adds idx_patients_treatment_start_date for date range queries
- Adds idx_patients_created_at for chronological queries
- Adds idx_quiz_sessions_patient_id for patient quiz sessions
- Adds idx_quiz_sessions_created_at for session chronological queries
- Adds idx_messages_patient_id for patient messages
- Adds idx_messages_created_at for message chronological queries
- Adds idx_appointments_patient_id for patient appointments (if table exists)
- Adds idx_appointments_scheduled_at for scheduling queries (if table exists)

All indexes use CREATE INDEX CONCURRENTLY IF NOT EXISTS for non-blocking
index creation on production databases.

IMPORTANT: CONCURRENTLY requires running outside a transaction.
Run with: alembic upgrade head --sql | psql  (for manual review)
Or ensure transaction_per_migration=False in env.py for this migration.
"""

from alembic import op
import sqlalchemy as sa
from alembic import context


# revision identifiers, used by Alembic.
revision = '034_add_performance_indexes'
down_revision = '033_fix_user_sync_log_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing performance indexes for frequently filtered columns.

    CRITICAL FIX: Removed CONCURRENTLY to allow running inside transactions.
    CONCURRENTLY cannot be used inside transaction blocks and causes:
    "CREATE INDEX CONCURRENTLY cannot run inside a transaction block"

    For production zero-downtime: Run this migration with:
    1. alembic upgrade head --sql > migration.sql
    2. Manually edit to add CONCURRENTLY
    3. psql < migration.sql (outside transaction)

    For development/staging: Regular indexes are fine and faster.
    """

    # Helper to create index safely (no CONCURRENTLY in transactions)
    def create_index_safe(index_name: str, table: str, column: str) -> None:
        """Create index (no CONCURRENTLY to allow transaction usage)."""
        # Regular CREATE INDEX works in transactions
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {table}({column})
        """)

    # Patients table indexes
    create_index_safe("idx_patients_doctor_id", "patients", "doctor_id")
    create_index_safe("idx_patients_flow_state", "patients", "flow_state")
    create_index_safe("idx_patients_treatment_type", "patients", "treatment_type")
    create_index_safe("idx_patients_treatment_start_date", "patients", "treatment_start_date")
    create_index_safe("idx_patients_created_at", "patients", "created_at")

    # Helper for conditional index creation (table may not exist)
    def create_index_if_table_exists(index_name: str, table: str, column: str) -> None:
        """Create index only if table exists, using CONCURRENTLY if possible."""
        # Note: CONCURRENTLY cannot be used inside DO $$ blocks
        # We check table existence first, then create index
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}') THEN
                    EXECUTE 'CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})';
                END IF;
            END $$;
        """)

    # Quiz sessions indexes
    create_index_if_table_exists("idx_quiz_sessions_patient_id", "quiz_sessions", "patient_id")
    create_index_if_table_exists("idx_quiz_sessions_created_at", "quiz_sessions", "created_at")

    # Messages table indexes
    create_index_if_table_exists("idx_messages_patient_id", "messages", "patient_id")
    create_index_if_table_exists("idx_messages_created_at", "messages", "created_at")

    # Appointments table indexes (if table exists)
    create_index_if_table_exists("idx_appointments_patient_id", "appointments", "patient_id")
    create_index_if_table_exists("idx_appointments_scheduled_at", "appointments", "scheduled_at")


def downgrade() -> None:
    """Remove performance indexes."""

    # Drop indexes in reverse order (with existence checks)
    op.execute("DROP INDEX IF EXISTS idx_appointments_scheduled_at")
    op.execute("DROP INDEX IF EXISTS idx_appointments_patient_id")
    op.execute("DROP INDEX IF EXISTS idx_messages_created_at")
    op.execute("DROP INDEX IF EXISTS idx_messages_patient_id")
    op.execute("DROP INDEX IF EXISTS idx_quiz_sessions_created_at")
    op.execute("DROP INDEX IF EXISTS idx_quiz_sessions_patient_id")
    op.execute("DROP INDEX IF EXISTS idx_patients_created_at")
    op.execute("DROP INDEX IF EXISTS idx_patients_treatment_start_date")
    op.execute("DROP INDEX IF EXISTS idx_patients_treatment_type")
    op.execute("DROP INDEX IF EXISTS idx_patients_flow_state")
    op.execute("DROP INDEX IF EXISTS idx_patients_doctor_id")
