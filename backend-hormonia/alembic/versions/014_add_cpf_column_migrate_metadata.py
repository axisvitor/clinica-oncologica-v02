"""Add CPF column and migrate metadata to dedicated columns

Revision ID: 014_add_cpf_migrate_metadata
Revises: 013_fix_quiz_response_type_constraint
Create Date: 2025-09-27

This migration adds a dedicated CPF column to the patients table and migrates
critical metadata fields to dedicated columns for better performance and querying.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import table, column
import json

# revision identifiers, used by Alembic.
revision = '014_add_cpf_migrate_metadata'
down_revision = '013_fix_quiz_response_type_constraint'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add dedicated columns for CPF and diagnosis, migrating data from metadata JSONB.
    This improves query performance and data integrity.
    """

    # Step 1: Add new columns (nullable initially for migration)
    op.add_column('patients', sa.Column('cpf', sa.String(11), nullable=True))
    op.add_column('patients', sa.Column('diagnosis', sa.String(500), nullable=True))
    op.add_column('patients', sa.Column('treatment_phase', sa.String(100), nullable=True))
    op.add_column('patients', sa.Column('doctor_notes', sa.Text, nullable=True))

    # Step 2: Add indexes for better query performance
    op.create_index('idx_patients_cpf', 'patients', ['cpf'], unique=True, postgresql_where=sa.text("cpf IS NOT NULL"))
    op.create_index('idx_patients_diagnosis', 'patients', ['diagnosis'])
    op.create_index('idx_patients_treatment_phase', 'patients', ['treatment_phase'])

    # Step 3: Migrate data from metadata JSONB to new columns
    # Using direct SQL for better performance
    op.execute("""
        UPDATE patients
        SET
            cpf = CASE
                WHEN metadata->>'cpf' IS NOT NULL AND metadata->>'cpf' != ''
                THEN metadata->>'cpf'
                ELSE NULL
            END,
            diagnosis = CASE
                WHEN metadata->>'diagnosis' IS NOT NULL AND metadata->>'diagnosis' != ''
                THEN metadata->>'diagnosis'
                ELSE NULL
            END,
            treatment_phase = CASE
                WHEN metadata->>'treatment_phase' IS NOT NULL AND metadata->>'treatment_phase' != ''
                THEN metadata->>'treatment_phase'
                ELSE NULL
            END,
            doctor_notes = CASE
                WHEN metadata->>'doctor_notes' IS NOT NULL AND metadata->>'doctor_notes' != ''
                THEN metadata->>'doctor_notes'
                ELSE NULL
            END
        WHERE metadata IS NOT NULL;
    """)

    # Step 4: Clean up migrated fields from metadata to reduce storage
    # Keep other metadata fields that might exist
    op.execute("""
        UPDATE patients
        SET metadata =
            CASE
                WHEN metadata IS NOT NULL THEN
                    (metadata - 'cpf' - 'diagnosis' - 'treatment_phase' - 'doctor_notes')
                ELSE metadata
            END
        WHERE metadata IS NOT NULL;
    """)

    # Step 5: Add check constraint for CPF format (11 digits)
    op.create_check_constraint(
        'check_cpf_format',
        'patients',
        sa.text("cpf ~ '^[0-9]{11}$' OR cpf IS NULL")
    )

    # Step 6: Add check constraint for treatment_phase values
    op.create_check_constraint(
        'check_treatment_phase_values',
        'patients',
        sa.text("""
            treatment_phase IN (
                'initial', 'adjustment', 'maintenance',
                'monitoring', 'followup', 'completed'
            ) OR treatment_phase IS NULL
        """)
    )

    # Step 7: Create a function to validate CPF check digit (Brazilian CPF validation)
    op.execute("""
        CREATE OR REPLACE FUNCTION validate_cpf(cpf_input text)
        RETURNS boolean AS $$
        DECLARE
            cpf_clean text;
            sum1 integer := 0;
            sum2 integer := 0;
            digit1 integer;
            digit2 integer;
            i integer;
        BEGIN
            -- Clean CPF (remove non-digits)
            cpf_clean := regexp_replace(cpf_input, '[^0-9]', '', 'g');

            -- Check length
            IF length(cpf_clean) != 11 THEN
                RETURN false;
            END IF;

            -- Check for known invalid patterns
            IF cpf_clean IN ('00000000000', '11111111111', '22222222222',
                             '33333333333', '44444444444', '55555555555',
                             '66666666666', '77777777777', '88888888888',
                             '99999999999') THEN
                RETURN false;
            END IF;

            -- Calculate first check digit
            FOR i IN 1..9 LOOP
                sum1 := sum1 + (substr(cpf_clean, i, 1)::integer * (11 - i));
            END LOOP;

            digit1 := 11 - (sum1 % 11);
            IF digit1 >= 10 THEN
                digit1 := 0;
            END IF;

            -- Calculate second check digit
            FOR i IN 1..10 LOOP
                sum2 := sum2 + (substr(cpf_clean, i, 1)::integer * (12 - i));
            END LOOP;

            digit2 := 11 - (sum2 % 11);
            IF digit2 >= 10 THEN
                digit2 := 0;
            END IF;

            -- Validate check digits
            RETURN substr(cpf_clean, 10, 1)::integer = digit1 AND
                   substr(cpf_clean, 11, 1)::integer = digit2;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    # Step 8: Add trigger to validate CPF on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION trigger_validate_cpf()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.cpf IS NOT NULL AND NOT validate_cpf(NEW.cpf) THEN
                RAISE EXCEPTION 'Invalid CPF: %', NEW.cpf;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER validate_cpf_trigger
        BEFORE INSERT OR UPDATE OF cpf ON patients
        FOR EACH ROW
        EXECUTE FUNCTION trigger_validate_cpf();
    """)


def downgrade():
    """
    Revert changes by moving data back to metadata and removing new columns.
    """

    # Step 1: Move data back to metadata JSONB
    op.execute("""
        UPDATE patients
        SET metadata =
            CASE
                WHEN metadata IS NULL THEN
                    jsonb_build_object(
                        'cpf', cpf,
                        'diagnosis', diagnosis,
                        'treatment_phase', treatment_phase,
                        'doctor_notes', doctor_notes
                    )
                ELSE
                    metadata ||
                    jsonb_build_object(
                        'cpf', cpf,
                        'diagnosis', diagnosis,
                        'treatment_phase', treatment_phase,
                        'doctor_notes', doctor_notes
                    )
            END
        WHERE cpf IS NOT NULL
           OR diagnosis IS NOT NULL
           OR treatment_phase IS NOT NULL
           OR doctor_notes IS NOT NULL;
    """)

    # Step 2: Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS validate_cpf_trigger ON patients;")
    op.execute("DROP FUNCTION IF EXISTS trigger_validate_cpf();")
    op.execute("DROP FUNCTION IF EXISTS validate_cpf(text);")

    # Step 3: Drop constraints
    op.drop_constraint('check_treatment_phase_values', 'patients', type_='check')
    op.drop_constraint('check_cpf_format', 'patients', type_='check')

    # Step 4: Drop indexes
    op.drop_index('idx_patients_treatment_phase', table_name='patients')
    op.drop_index('idx_patients_diagnosis', table_name='patients')
    op.drop_index('idx_patients_cpf', table_name='patients')

    # Step 5: Drop columns
    op.drop_column('patients', 'doctor_notes')
    op.drop_column('patients', 'treatment_phase')
    op.drop_column('patients', 'diagnosis')
    op.drop_column('patients', 'cpf')