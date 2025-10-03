"""Add messages patient status index

Revision ID: 20250929_200008
Revises: 20250929_200007
Create Date: 2025-09-29

Performance optimization for patient message history with status filtering.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250929_200008'
down_revision = '20250929_200007'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create composite index on messages table for patient_id, status, and created_at.

    Query pattern: Patient message history with status filtering
    SELECT * FROM messages
    WHERE patient_id = ? AND status = ?
    ORDER BY created_at DESC

    Benefits:
    - Optimizes patient message history queries with status filtering
    - Supports delivery status monitoring per patient
    - Enables efficient message analytics per patient
    - Critical for patient communication tracking
    """
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_status_created
        ON messages (patient_id, status, created_at DESC)
    """)

    # Add comment for performance tracking
    op.execute("""
        COMMENT ON INDEX idx_messages_patient_status_created IS
        'Optimizes patient message history with status filtering'
    """)


def downgrade():
    """Remove messages patient status index"""
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_messages_patient_status_created")