"""Add quiz responses patient index

Revision ID: 20250929_200010
Revises: 20250929_200009
Create Date: 2025-09-29

Performance optimization for patient quiz history queries.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250929_200010'
down_revision = '20250929_200009'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create composite index on quiz_responses table for patient_id, quiz_id, and created_at.

    Query pattern: Patient quiz history retrieval
    SELECT * FROM quiz_responses
    WHERE patient_id = ? AND quiz_id = ?
    ORDER BY created_at DESC

    Benefits:
    - Optimizes patient quiz history queries
    - Supports quiz progress tracking per patient
    - Enables efficient quiz analytics per patient
    - Critical for patient assessment workflows

    Note: This complements the existing idx_quiz_responses_patient_template index
    but uses quiz_id instead of quiz_template_id for different query patterns.
    """
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quiz_responses_patient_quiz
        ON quiz_responses (patient_id, quiz_id, created_at DESC)
    """)

    # Add comment for performance tracking
    op.execute("""
        COMMENT ON INDEX idx_quiz_responses_patient_quiz IS
        'Optimizes patient quiz history queries by quiz_id'
    """)


def downgrade():
    """Remove quiz responses patient index"""
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_quiz_responses_patient_quiz")