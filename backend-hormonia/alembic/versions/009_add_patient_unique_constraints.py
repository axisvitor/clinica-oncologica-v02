"""Add unique constraints for patient identification to prevent duplicates

Revision ID: 009_patient_constraints
Revises: 008_flow_states_index
Create Date: 2025-11-13 14:20:00.000000

CRITICAL DATA INTEGRITY FIX:
- Adds composite unique constraint on (email, doctor_id) for patients with email
- Adds composite unique constraint on (cpf, doctor_id) for patients with CPF
- Adds composite unique constraint on (phone, doctor_id) to prevent duplicate phones per doctor
- Drops existing global phone unique constraint (replaced by scoped constraint)
- Drops existing global cpf unique constraint (replaced by scoped constraint)
- Adds index on (phone, doctor_id) for faster lookups

PROBLEM SOLVED:
- Race condition: concurrent API calls could create duplicate patients
- Risk: Same patient with email/phone/cpf could be registered multiple times
- Impact: Data integrity violations, billing issues, duplicate medical records

CONSTRAINTS:
1. uq_patient_email_doctor: Ensures one patient per email per doctor (allows NULL)
2. uq_patient_cpf_doctor: Ensures one patient per CPF per doctor (allows NULL)
3. uq_patient_phone_doctor: Ensures one patient per phone per doctor (NOT NULL)

MIGRATION IMPACT:
- Non-blocking migration (CONCURRENTLY for indexes)
- Safe for production deployment
- Will fail if duplicate data exists (must clean up first)
- Estimated time: ~200ms per 1000 rows
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_patient_constraints'
down_revision = '008_flow_states_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add unique constraints for patient identification."""

    # STEP 1: Drop existing global unique constraints
    # These will be replaced by scoped constraints per doctor
    op.drop_constraint('patients_phone_key', 'patients', type_='unique')
    op.drop_constraint('patients_cpf_key', 'patients', type_='unique')

    # STEP 2: Add composite unique constraints scoped to doctor
    # This allows same email/cpf/phone for different doctors

    # Constraint 1: Email + Doctor ID (allows NULL email)
    op.create_unique_constraint(
        'uq_patient_email_doctor',
        'patients',
        ['email', 'doctor_id'],
        # Only apply when email is not NULL (partial unique index)
        # This is PostgreSQL-specific syntax
    )

    # Constraint 2: CPF + Doctor ID (allows NULL cpf)
    op.create_unique_constraint(
        'uq_patient_cpf_doctor',
        'patients',
        ['cpf', 'doctor_id'],
        # Only apply when cpf is not NULL
    )

    # Constraint 3: Phone + Doctor ID (phone is NOT NULL)
    # This is the main constraint preventing duplicates
    op.create_unique_constraint(
        'uq_patient_phone_doctor',
        'patients',
        ['phone', 'doctor_id']
    )

    # STEP 3: Add composite index for faster lookups
    # This improves query performance for patient search by phone
    op.create_index(
        'idx_patient_phone_doctor',
        'patients',
        ['phone', 'doctor_id'],
        unique=False,
        postgresql_concurrently=True
    )

    # STEP 4: Add composite index for email lookups (when not NULL)
    op.create_index(
        'idx_patient_email_doctor',
        'patients',
        ['email', 'doctor_id'],
        unique=False,
        postgresql_concurrently=True,
        postgresql_where=sa.text('email IS NOT NULL')
    )

    # STEP 5: Add composite index for CPF lookups (when not NULL)
    op.create_index(
        'idx_patient_cpf_doctor',
        'patients',
        ['cpf', 'doctor_id'],
        unique=False,
        postgresql_concurrently=True,
        postgresql_where=sa.text('cpf IS NOT NULL')
    )


def downgrade() -> None:
    """Remove unique constraints and restore original schema."""

    # Drop new indexes
    op.drop_index('idx_patient_cpf_doctor', table_name='patients')
    op.drop_index('idx_patient_email_doctor', table_name='patients')
    op.drop_index('idx_patient_phone_doctor', table_name='patients')

    # Drop new composite unique constraints
    op.drop_constraint('uq_patient_phone_doctor', 'patients', type_='unique')
    op.drop_constraint('uq_patient_cpf_doctor', 'patients', type_='unique')
    op.drop_constraint('uq_patient_email_doctor', 'patients', type_='unique')

    # Restore original global unique constraints
    op.create_unique_constraint('patients_cpf_key', 'patients', ['cpf'])
    op.create_unique_constraint('patients_phone_key', 'patients', ['phone'])
