"""Add dedicated columns for CPF, diagnosis, treatment_phase, and doctor_notes to patients table

Revision ID: add_dedicated_patient_columns
Revises: 014_add_cpf_migrate_metadata
Create Date: 2025-09-27

This migration adds dedicated columns for CPF, diagnosis, treatment_phase, and doctor_notes
to the patients table if they don't exist, migrates existing data from the metadata JSONB field,
creates proper indexes for performance, and maintains backward compatibility.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import table, column
from sqlalchemy import text
import json

# revision identifiers, used by Alembic.
revision = 'add_dedicated_patient_columns'
down_revision = '014_add_cpf_migrate_metadata'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in the table."""
    connection = op.get_bind()
    result = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
        );
    """), {"table_name": table_name, "column_name": column_name})
    return result.scalar()


def index_exists(index_name: str) -> bool:
    """Check if an index exists."""
    connection = op.get_bind()
    result = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE indexname = :index_name
        );
    """), {"index_name": index_name})
    return result.scalar()


def constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Check if a constraint exists."""
    connection = op.get_bind()
    result = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name = :table_name AND constraint_name = :constraint_name
        );
    """), {"table_name": table_name, "constraint_name": constraint_name})
    return result.scalar()


def upgrade():
    """
    Add dedicated columns for CPF, diagnosis, treatment_phase, and doctor_notes,
    migrating data from metadata JSONB. This improves query performance and data integrity.
    """

    # Step 1: Add new columns if they don't exist (nullable initially for migration)
    if not column_exists('patients', 'cpf'):
        op.add_column('patients', sa.Column('cpf', sa.String(11), nullable=True))

    if not column_exists('patients', 'diagnosis'):
        op.add_column('patients', sa.Column('diagnosis', sa.String(500), nullable=True))

    if not column_exists('patients', 'treatment_phase'):
        op.add_column('patients', sa.Column('treatment_phase', sa.String(100), nullable=True))

    if not column_exists('patients', 'doctor_notes'):
        # Use String instead of Text for consistency with model
        op.add_column('patients', sa.Column('doctor_notes', sa.String, nullable=True))

    # Step 2: Add indexes for better query performance (if they don't exist)
    if not index_exists('idx_patients_cpf'):
        op.create_index(
            'idx_patients_cpf',
            'patients',
            ['cpf'],
            unique=True,
            postgresql_where=text("cpf IS NOT NULL")
        )

    if not index_exists('idx_patients_diagnosis'):
        op.create_index('idx_patients_diagnosis', 'patients', ['diagnosis'])

    if not index_exists('idx_patients_treatment_phase'):
        op.create_index('idx_patients_treatment_phase', 'patients', ['treatment_phase'])

    # Step 3: Migrate data from metadata JSONB to new columns
    # Only migrate if there's data in metadata that's not already in dedicated columns
    op.execute("""
        UPDATE patients
        SET
            cpf = CASE
                WHEN cpf IS NULL AND metadata->>'cpf' IS NOT NULL AND metadata->>'cpf' != ''
                THEN metadata->>'cpf'
                ELSE cpf
            END,
            diagnosis = CASE
                WHEN diagnosis IS NULL AND metadata->>'diagnosis' IS NOT NULL AND metadata->>'diagnosis' != ''
                THEN metadata->>'diagnosis'
                ELSE diagnosis
            END,
            treatment_phase = CASE
                WHEN treatment_phase IS NULL AND metadata->>'treatment_phase' IS NOT NULL AND metadata->>'treatment_phase' != ''
                THEN metadata->>'treatment_phase'
                ELSE treatment_phase
            END,
            doctor_notes = CASE
                WHEN doctor_notes IS NULL AND metadata->>'doctor_notes' IS NOT NULL AND metadata->>'doctor_notes' != ''
                THEN metadata->>'doctor_notes'
                ELSE doctor_notes
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
        WHERE metadata IS NOT NULL
        AND (
            metadata ? 'cpf' OR
            metadata ? 'diagnosis' OR
            metadata ? 'treatment_phase' OR
            metadata ? 'doctor_notes'
        );
    """)

    # Step 5: Add check constraint for CPF format (11 digits) if not exists
    if not constraint_exists('patients', 'check_cpf_format'):
        op.create_check_constraint(
            'check_cpf_format',
            'patients',
            text("cpf ~ '^[0-9]{11}$' OR cpf IS NULL")
        )

    # Step 6: Add check constraint for treatment_phase values if not exists
    if not constraint_exists('patients', 'check_treatment_phase_values'):
        op.create_check_constraint(
            'check_treatment_phase_values',
            'patients',
            text("""
                treatment_phase IN (
                    'initial', 'adjustment', 'maintenance',
                    'monitoring', 'followup', 'completed'
                ) OR treatment_phase IS NULL
            """)
        )

    # Step 7: Create CPF validation function if it doesn't exist
    connection = op.get_bind()
    function_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public' AND p.proname = 'validate_cpf'
        );
    """)).scalar()

    if not function_exists:
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

    # Step 8: Add trigger to validate CPF on insert/update if it doesn't exist
    trigger_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.triggers
            WHERE trigger_name = 'validate_cpf_trigger'
            AND event_object_table = 'patients'
        );
    """)).scalar()

    if not trigger_exists:
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
    This ensures proper rollback functionality.
    """

    # Step 1: Move data back to metadata JSONB
    # Only move data that exists in dedicated columns
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

    # Step 2: Drop trigger and function (if they exist)
    connection = op.get_bind()

    trigger_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.triggers
            WHERE trigger_name = 'validate_cpf_trigger'
        );
    """)).scalar()

    if trigger_exists:
        op.execute("DROP TRIGGER IF EXISTS validate_cpf_trigger ON patients;")

    op.execute("DROP FUNCTION IF EXISTS trigger_validate_cpf();")
    op.execute("DROP FUNCTION IF EXISTS validate_cpf(text);")

    # Step 3: Drop constraints (if they exist)
    if constraint_exists('patients', 'check_treatment_phase_values'):
        op.drop_constraint('check_treatment_phase_values', 'patients', type_='check')

    if constraint_exists('patients', 'check_cpf_format'):
        op.drop_constraint('check_cpf_format', 'patients', type_='check')

    # Step 4: Drop indexes (if they exist)
    if index_exists('idx_patients_treatment_phase'):
        op.drop_index('idx_patients_treatment_phase', table_name='patients')

    if index_exists('idx_patients_diagnosis'):
        op.drop_index('idx_patients_diagnosis', table_name='patients')

    if index_exists('idx_patients_cpf'):
        op.drop_index('idx_patients_cpf', table_name='patients')

    # Step 5: Drop columns (if they exist)
    if column_exists('patients', 'doctor_notes'):
        op.drop_column('patients', 'doctor_notes')

    if column_exists('patients', 'treatment_phase'):
        op.drop_column('patients', 'treatment_phase')

    if column_exists('patients', 'diagnosis'):
        op.drop_column('patients', 'diagnosis')

    if column_exists('patients', 'cpf'):
        op.drop_column('patients', 'cpf')