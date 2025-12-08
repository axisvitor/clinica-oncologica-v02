"""Add patient_summaries table for AI-generated patient summaries.

Revision ID: 021_patient_summaries
Revises: 020_encrypt_cpf_lgpd
Create Date: 2025-01-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, BYTEA

# revision identifiers, used by Alembic.
revision = '021_patient_summaries'
down_revision = '020_encrypt_cpf_lgpd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create patient_summaries table for AI-generated doctor summaries."""
    op.create_table(
        'patient_summaries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('generated_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('content', JSONB, nullable=False, server_default='{}'),
        sa.Column('pdf_data', BYTEA, nullable=True),
        sa.Column('token_usage', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True, server_default='gemini-2.5-flash-latest'),
        sa.Column('generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Index for querying summaries by patient and date range
    op.create_index(
        'idx_patient_summaries_patient_period',
        'patient_summaries',
        ['patient_id', 'start_date', 'end_date']
    )

    # Index for recent summaries query
    op.create_index(
        'idx_patient_summaries_created_at',
        'patient_summaries',
        ['created_at']
    )

    # Index for patient_id lookups
    op.create_index(
        'idx_patient_summaries_patient_id',
        'patient_summaries',
        ['patient_id']
    )


def downgrade() -> None:
    """Remove patient_summaries table."""
    op.drop_index('idx_patient_summaries_patient_id', table_name='patient_summaries')
    op.drop_index('idx_patient_summaries_created_at', table_name='patient_summaries')
    op.drop_index('idx_patient_summaries_patient_period', table_name='patient_summaries')
    op.drop_table('patient_summaries')
