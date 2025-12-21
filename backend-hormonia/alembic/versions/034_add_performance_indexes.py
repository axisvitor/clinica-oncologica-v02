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

All indexes use CREATE INDEX IF NOT EXISTS for idempotency.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '034_add_performance_indexes'
down_revision = '033_fix_user_sync_log_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing performance indexes for frequently filtered columns."""

    # Patients table indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_doctor_id
        ON patients(doctor_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_flow_state
        ON patients(flow_state)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_treatment_type
        ON patients(treatment_type)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_treatment_start_date
        ON patients(treatment_start_date)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_created_at
        ON patients(created_at)
    """)

    # Quiz sessions indexes
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'quiz_sessions') THEN
                CREATE INDEX IF NOT EXISTS idx_quiz_sessions_patient_id
                ON quiz_sessions(patient_id);
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'quiz_sessions') THEN
                CREATE INDEX IF NOT EXISTS idx_quiz_sessions_created_at
                ON quiz_sessions(created_at);
            END IF;
        END $$;
    """)

    # Messages table indexes
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'messages') THEN
                CREATE INDEX IF NOT EXISTS idx_messages_patient_id
                ON messages(patient_id);
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'messages') THEN
                CREATE INDEX IF NOT EXISTS idx_messages_created_at
                ON messages(created_at);
            END IF;
        END $$;
    """)

    # Appointments table indexes (if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'appointments') THEN
                CREATE INDEX IF NOT EXISTS idx_appointments_patient_id
                ON appointments(patient_id);
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'appointments') THEN
                CREATE INDEX IF NOT EXISTS idx_appointments_scheduled_at
                ON appointments(scheduled_at);
            END IF;
        END $$;
    """)


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
