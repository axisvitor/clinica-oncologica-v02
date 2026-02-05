"""Make doctor_id nullable in patients and sagas

Revision ID: 038_make_doctor_id_nullable
Revises: 037_fix_missing_fk_cascades
Create Date: 2025-12-31

Allows patient creation without requiring a doctor assignment.

WHY:
- Not recorded (legacy migration).

WHAT:
- Not recorded (legacy migration).

IMPACT:
- Not recorded (legacy migration).

BENCHMARK:
- Not recorded (legacy migration).

ROLLBACK:
- Not recorded (legacy migration).

RELATED:
- Not recorded (legacy migration).

MIGRATION TYPE:
- Not recorded (legacy migration).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '038_make_doctor_id_nullable'
down_revision = '037_fix_missing_fk_cascades'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make doctor_id nullable in patients table
    op.alter_column('patients', 'doctor_id',
               existing_type=sa.UUID(),
               nullable=True)
    
    # Make doctor_id nullable in patient_onboarding_saga table
    op.alter_column('patient_onboarding_saga', 'doctor_id',
               existing_type=sa.UUID(),
               nullable=True)


def downgrade() -> None:
    # Revert: Make doctor_id NOT NULL again
    # Note: This will fail if there are NULL values in the columns
    op.alter_column('patient_onboarding_saga', 'doctor_id',
               existing_type=sa.UUID(),
               nullable=False)
    op.alter_column('patients', 'doctor_id',
               existing_type=sa.UUID(),
               nullable=False)
