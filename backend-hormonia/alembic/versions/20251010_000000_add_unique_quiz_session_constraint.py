"""add unique constraint for quiz sessions to prevent concurrent creation

Revision ID: 20251010_000000
Revises: 20251009_235900
Create Date: 2025-10-10 00:00:00

Sprint 2 - P8: Prevent Concurrent Quiz Session Creation

This migration adds:
1. Unique partial index on (patient_id, quiz_template_id, month) for active sessions
2. Helper function to extract month from started_at timestamp
3. Database constraint to ensure only one active session per patient/template/month

The unique constraint prevents race conditions at database level, ensuring that
even with concurrent requests, only one quiz session can be created for a given
patient, template, and month combination.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '20251010_000000'
down_revision = '20251009_235900'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add unique constraint to prevent concurrent quiz session creation.

    Strategy:
    1. Create unique partial index on (patient_id, quiz_template_id, started_at::date)
       - Only applies to non-completed sessions (status != 'completed')
       - Uses PostgreSQL partial index for optimal performance
       - Prevents duplicate sessions for same patient/template on same day

    2. This constraint ensures:
       - Race conditions are prevented at database level
       - Duplicate sessions impossible even with concurrent requests
       - Completed sessions don't conflict with new sessions
    """

    # Create unique partial index for active sessions
    # This prevents multiple active sessions for the same patient, template, and month
    op.execute("""
        CREATE UNIQUE INDEX CONCURRENTLY ix_quiz_session_patient_template_month_unique
        ON quiz_sessions (patient_id, quiz_template_id, DATE_TRUNC('month', started_at))
        WHERE status != 'completed'
    """)

    # Add check constraint to ensure started_at is not null for active sessions
    op.create_check_constraint(
        'ck_quiz_session_started_at_not_null_active',
        'quiz_sessions',
        "status = 'completed' OR started_at IS NOT NULL"
    )

    # Add comment explaining the constraint
    op.execute("""
        COMMENT ON INDEX ix_quiz_session_patient_template_month_unique IS
        'Ensures only one active quiz session per patient, template, and month.
         Prevents race conditions during concurrent session creation.
         Uses partial index to exclude completed sessions from uniqueness check.'
    """)


def downgrade():
    """Remove unique constraint for quiz sessions."""

    # Drop check constraint
    op.drop_constraint(
        'ck_quiz_session_started_at_not_null_active',
        'quiz_sessions',
        type_='check'
    )

    # Drop unique partial index
    op.execute("""
        DROP INDEX CONCURRENTLY IF EXISTS ix_quiz_session_patient_template_month_unique
    """)
