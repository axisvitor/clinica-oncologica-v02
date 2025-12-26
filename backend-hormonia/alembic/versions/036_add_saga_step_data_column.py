"""Add step_data column to patient_onboarding_saga

Revision ID: 036_add_saga_step_data_column
Revises: 035_add_saga_status_enum_values
Create Date: 2025-12-26

This migration adds the step_data JSONB column to the patient_onboarding_saga table.
The column is used for compensation tracking data and idempotency support (FIX P1-008).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '036_add_saga_step_data_column'
down_revision = '035_add_saga_status_enum_values'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add step_data column with default empty JSON object
    op.add_column(
        'patient_onboarding_saga',
        sa.Column('step_data', JSONB, nullable=True, server_default='{}')
    )

    # Add comment for documentation
    op.execute("""
        COMMENT ON COLUMN patient_onboarding_saga.step_data IS
        'Stores compensation tracking data for idempotency (FIX P1-008)'
    """)


def downgrade() -> None:
    op.drop_column('patient_onboarding_saga', 'step_data')
