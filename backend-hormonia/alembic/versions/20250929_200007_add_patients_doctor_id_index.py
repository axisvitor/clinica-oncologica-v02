"""Add patients doctor_id index

Revision ID: 20250929_200007
Revises: 20250929_200006
Create Date: 2025-09-29

Performance optimization for doctor's patient list queries.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250929_200007'
down_revision = '20250929_200006'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create composite index on patients table for doctor_id and created_at.

    Query pattern: Doctor's patient list retrieval
    SELECT * FROM patients WHERE doctor_id = ? ORDER BY created_at DESC

    Benefits:
    - Optimizes doctor dashboard patient list queries
    - Efficient time-ordered patient retrieval per doctor
    - Supports patient management workflows
    - Critical for multi-doctor clinic operations
    """
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_doctor_id
        ON patients (doctor_id, created_at DESC)
    """)

    # Add comment for performance tracking
    op.execute("""
        COMMENT ON INDEX idx_patients_doctor_id IS
        'Optimizes doctor patient list queries with time ordering'
    """)


def downgrade():
    """Remove patients doctor_id index"""
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_patients_doctor_id")