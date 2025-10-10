"""add quiz_session_id to alerts table

Revision ID: 20251009_225600
Revises: 20251009_210800
Create Date: 2025-10-09 22:56:00

Sprint 2 - Week 1, Task 3: Automatic Alert Evaluation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '20251009_225600'
down_revision = '20251009_210800'
branch_labels = None
depends_on = None


def upgrade():
    """Add quiz_session_id foreign key to alerts table."""
    # Add quiz_session_id column as nullable initially
    op.add_column(
        'alerts',
        sa.Column('quiz_session_id', UUID(as_uuid=True), nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_alerts_quiz_session_id',
        'alerts',
        'quiz_sessions',
        ['quiz_session_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add index for performance
    op.create_index(
        'idx_alerts_quiz_session_id',
        'alerts',
        ['quiz_session_id']
    )

    # Add composite index for patient + quiz session
    op.create_index(
        'idx_alerts_patient_quiz_session',
        'alerts',
        ['patient_id', 'quiz_session_id']
    )


def downgrade():
    """Remove quiz_session_id from alerts table."""
    # Drop indexes
    op.drop_index('idx_alerts_patient_quiz_session', table_name='alerts')
    op.drop_index('idx_alerts_quiz_session_id', table_name='alerts')

    # Drop foreign key constraint
    op.drop_constraint('fk_alerts_quiz_session_id', 'alerts', type_='foreignkey')

    # Drop column
    op.drop_column('alerts', 'quiz_session_id')
