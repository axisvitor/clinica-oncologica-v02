"""add patient idempotency key

Revision ID: 025
Revises: 024
Create Date: 2025-11-26

QW-004: Add idempotency_key column to patients table for duplicate request prevention

This migration adds database-level idempotency support to prevent duplicate patient
creation from retried API requests. The idempotency key is stored with a unique
constraint to ensure atomicity at the database level.

Changes:
- Add idempotency_key column (VARCHAR(64), nullable, unique)
- Add unique index on idempotency_key (partial index where NOT NULL)
- Backward compatible - existing records will have NULL idempotency_key

Performance Impact:
- Minimal - single column addition with partial index
- Index only applies to rows with non-NULL idempotency_key
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024_drop_plaintext_cpf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add idempotency_key column to patients table.

    QW-004: Database-level idempotency support
    """
    # Add idempotency_key column
    op.add_column(
        'patients',
        sa.Column('idempotency_key', sa.String(64), nullable=True)
    )

    # Create unique partial index (only for non-NULL values)
    # Using partial index to allow multiple NULL values while enforcing uniqueness
    # for non-NULL values (supports optional idempotency)
    op.create_index(
        'ix_patients_idempotency_key',
        'patients',
        ['idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL')
    )


def downgrade() -> None:
    """
    Remove idempotency_key column and index.
    """
    # Drop index first
    op.drop_index('ix_patients_idempotency_key', table_name='patients')

    # Drop column
    op.drop_column('patients', 'idempotency_key')
