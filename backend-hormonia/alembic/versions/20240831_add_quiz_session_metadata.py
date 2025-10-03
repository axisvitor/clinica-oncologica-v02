"""Add session_metadata and status to quiz_sessions table

Revision ID: 20240831_quiz_metadata
Revises: latest
Create Date: 2024-08-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '002_quiz_metadata'
down_revision = '001_whatsapp'
branch_labels = None
depends_on = None


def upgrade():
    """Add new columns to quiz_sessions table."""
    
    # Add status column with default value
    op.add_column('quiz_sessions', 
        sa.Column('status', sa.String(50), nullable=False, server_default='in_progress')
    )
    
    # Add total_score column
    op.add_column('quiz_sessions',
        sa.Column('total_score', sa.Integer(), nullable=True, default=0)
    )
    
    # Add session_metadata JSONB column
    op.add_column('quiz_sessions',
        sa.Column('session_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}')
    )
    
    # Remove server defaults after adding columns
    op.alter_column('quiz_sessions', 'status', server_default=None)
    op.alter_column('quiz_sessions', 'session_metadata', server_default=None)


def downgrade():
    """Remove added columns from quiz_sessions table."""
    
    op.drop_column('quiz_sessions', 'session_metadata')
    op.drop_column('quiz_sessions', 'total_score')
    op.drop_column('quiz_sessions', 'status')