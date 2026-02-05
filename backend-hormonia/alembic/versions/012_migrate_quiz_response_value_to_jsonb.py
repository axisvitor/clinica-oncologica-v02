"""Migrate quiz.response_value from Text to JSONB

Revision ID: 012_migrate_quiz_response_value_to_jsonb
Revises: 011_hipaa_audit
Create Date: 2025-01-14 00:00:00.000000

This migration converts the quiz_responses.response_value column from Text to JSONB
to support structured data storage for complex response types including:
- Multiple choice selections (arrays)
- Multi-select responses (arrays)
- Scale responses with metadata
- Structured open-text responses with sentiment analysis

Migration Strategy:
1. Create new temporary JSONB column
2. Safely migrate existing Text data to JSONB with validation
3. Handle all edge cases (NULL, empty strings, JSON strings, plain text)
4. Drop old column and rename new column
5. Add JSONB-specific indexes and constraints
6. Provide rollback path

Priority: P1 (High) - Issue HIGH-003
Effort: 5 hours

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
from sqlalchemy.dialects import postgresql
import json


# revision identifiers, used by Alembic
revision = '012_migrate_quiz_response_value_to_jsonb'
down_revision = '011_hipaa_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Migrate response_value from Text to JSONB with safe data conversion.

    This upgrade handles multiple data formats:
    - Plain text responses → {"text": "value"}
    - JSON strings → parsed JSON objects
    - Arrays → preserved as arrays
    - NULL values → preserved as NULL
    """

    # ========================================
    # STEP 1: Create temporary JSONB column
    # ========================================
    print("Step 1: Creating temporary JSONB column...")

    op.add_column(
        'quiz_responses',
        sa.Column('response_value_jsonb', postgresql.JSONB(), nullable=True)
    )

    # ========================================
    # STEP 2: Migrate data with validation and error handling
    # ========================================
    print("Step 2: Migrating existing data to JSONB...")

    # Create a safe migration function
    op.execute("""
        CREATE OR REPLACE FUNCTION migrate_response_value_to_jsonb()
        RETURNS TABLE(
            id UUID,
            original_value TEXT,
            converted_value JSONB,
            conversion_status TEXT,
            error_message TEXT
        ) AS $$
        DECLARE
            rec RECORD;
            parsed_json JSONB;
            conversion_result TEXT;
            error_msg TEXT;
        BEGIN
            FOR rec IN
                SELECT
                    qr.id,
                    qr.response_value,
                    qr.response_type
                FROM quiz_responses qr
                ORDER BY qr.responded_at DESC
            LOOP
                -- Reset variables
                parsed_json := NULL;
                conversion_result := 'SUCCESS';
                error_msg := NULL;

                BEGIN
                    -- Handle NULL values
                    IF rec.response_value IS NULL THEN
                        parsed_json := NULL;
                        conversion_result := 'NULL_PRESERVED';

                    -- Handle empty strings
                    ELSIF rec.response_value = '' THEN
                        parsed_json := to_jsonb(''::text);
                        conversion_result := 'EMPTY_STRING';

                    -- Try to parse as JSON first (handles JSON strings and arrays)
                    ELSIF rec.response_value ~ '^[\\[\\{]' THEN
                        BEGIN
                            parsed_json := rec.response_value::jsonb;
                            conversion_result := 'JSON_PARSED';
                        EXCEPTION WHEN OTHERS THEN
                            -- If JSON parsing fails, treat as plain text
                            parsed_json := to_jsonb(rec.response_value::text);
                            conversion_result := 'JSON_PARSE_FAILED_AS_TEXT';
                            error_msg := SQLERRM;
                        END;

                    -- Handle comma-separated values (multi-select responses)
                    ELSIF rec.response_type = 'multiple_choice' AND rec.response_value ~ ',' THEN
                        -- Convert "A,B,C" to ["A", "B", "C"]
                        parsed_json := to_jsonb(
                            string_to_array(
                                regexp_replace(rec.response_value, '\\s*,\\s*', ',', 'g'),
                                ','
                            )
                        );
                        conversion_result := 'MULTI_SELECT_CONVERTED';

                    -- Handle scale responses (1-10 format)
                    ELSIF rec.response_type = 'scale' AND rec.response_value ~ '^\\d+$' THEN
                        parsed_json := jsonb_build_object(
                            'value', rec.response_value::integer,
                            'type', 'scale'
                        );
                        conversion_result := 'SCALE_CONVERTED';

                    -- Handle boolean-like responses
                    ELSIF rec.response_value ~ '^(true|false|yes|no|sim|não)$' THEN
                        parsed_json := jsonb_build_object(
                            'text', rec.response_value,
                            'boolean', CASE
                                WHEN rec.response_value IN ('true', 'yes', 'sim') THEN true
                                WHEN rec.response_value IN ('false', 'no', 'não') THEN false
                                ELSE NULL
                            END
                        );
                        conversion_result := 'BOOLEAN_CONVERTED';

                    -- Default: treat as plain text
                    ELSE
                        parsed_json := to_jsonb(rec.response_value::text);
                        conversion_result := 'PLAIN_TEXT';
                    END IF;

                EXCEPTION WHEN OTHERS THEN
                    -- Fallback: wrap in error object with original value
                    parsed_json := jsonb_build_object(
                        'text', rec.response_value,
                        'conversion_error', SQLERRM
                    );
                    conversion_result := 'ERROR_FALLBACK';
                    error_msg := SQLERRM;
                END;

                -- Return migration record for logging
                RETURN QUERY SELECT
                    rec.id,
                    rec.response_value,
                    parsed_json,
                    conversion_result,
                    error_msg;

            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Execute migration and update the new column
    op.execute("""
        UPDATE quiz_responses qr
        SET response_value_jsonb = migration.converted_value
        FROM migrate_response_value_to_jsonb() AS migration
        WHERE qr.id = migration.id;
    """)

    # ========================================
    # STEP 3: Create migration audit log
    # ========================================
    print("Step 3: Creating migration audit log...")

    op.execute("""
        CREATE TABLE IF NOT EXISTS quiz_response_migration_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            quiz_response_id UUID NOT NULL,
            original_value TEXT,
            converted_value JSONB,
            conversion_status TEXT NOT NULL,
            error_message TEXT,
            migrated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Log all migrations
    op.execute("""
        INSERT INTO quiz_response_migration_log (
            quiz_response_id,
            original_value,
            converted_value,
            conversion_status,
            error_message
        )
        SELECT
            id,
            original_value,
            converted_value,
            conversion_status,
            error_message
        FROM migrate_response_value_to_jsonb();
    """)

    # Create index on migration log
    op.execute("""
        CREATE INDEX idx_migration_log_status
        ON quiz_response_migration_log(conversion_status);

        CREATE INDEX idx_migration_log_errors
        ON quiz_response_migration_log(quiz_response_id)
        WHERE error_message IS NOT NULL;
    """)

    # ========================================
    # STEP 4: Validate migration results
    # ========================================
    print("Step 4: Validating migration results...")

    op.execute("""
        CREATE OR REPLACE FUNCTION validate_response_value_migration()
        RETURNS TABLE(
            total_responses BIGINT,
            successfully_migrated BIGINT,
            null_values BIGINT,
            errors BIGINT,
            error_rate NUMERIC(5,2)
        ) AS $$
        DECLARE
            total BIGINT;
            success BIGINT;
            nulls BIGINT;
            errs BIGINT;
        BEGIN
            -- Count total responses
            SELECT COUNT(*) INTO total FROM quiz_responses;

            -- Count successful migrations (non-null JSONB)
            SELECT COUNT(*) INTO success
            FROM quiz_responses
            WHERE response_value_jsonb IS NOT NULL;

            -- Count NULL values (should match original NULLs)
            SELECT COUNT(*) INTO nulls
            FROM quiz_responses
            WHERE response_value IS NULL AND response_value_jsonb IS NULL;

            -- Count errors from migration log
            SELECT COUNT(*) INTO errs
            FROM quiz_response_migration_log
            WHERE conversion_status = 'ERROR_FALLBACK';

            RETURN QUERY SELECT
                total,
                success,
                nulls,
                errs,
                CASE WHEN total > 0 THEN (errs::NUMERIC / total::NUMERIC) * 100 ELSE 0 END;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Log validation results
    print("Migration validation:")
    op.execute("""
        DO $$
        DECLARE
            validation RECORD;
        BEGIN
            SELECT * INTO validation FROM validate_response_value_migration();

            RAISE NOTICE 'Migration Validation Results:';
            RAISE NOTICE '  Total responses: %', validation.total_responses;
            RAISE NOTICE '  Successfully migrated: %', validation.successfully_migrated;
            RAISE NOTICE '  NULL values preserved: %', validation.null_values;
            RAISE NOTICE '  Errors: %', validation.errors;
            RAISE NOTICE '  Error rate: %%%', validation.error_rate;

            IF validation.error_rate > 5 THEN
                RAISE WARNING 'Error rate exceeds 5%%. Manual review recommended.';
            END IF;
        END $$;
    """)

    # ========================================
    # STEP 5: Backup old column and swap
    # ========================================
    print("Step 5: Backing up old column and performing swap...")

    # Rename old column to backup
    op.alter_column(
        'quiz_responses',
        'response_value',
        new_column_name='response_value_text_backup',
        existing_type=sa.Text(),
        existing_nullable=False
    )

    # Rename new column to official name
    op.alter_column(
        'quiz_responses',
        'response_value_jsonb',
        new_column_name='response_value',
        existing_type=postgresql.JSONB(),
        existing_nullable=True  # Allow NULL for optional responses
    )

    # Make response_value NOT NULL where response_type requires it
    # We'll handle this at the application level initially to avoid breaking existing data

    # ========================================
    # STEP 6: Add JSONB-specific indexes
    # ========================================
    print("Step 6: Adding JSONB-specific indexes...")

    # GIN index for general JSONB queries
    op.create_index(
        'idx_quiz_response_value_gin',
        'quiz_responses',
        ['response_value'],
        unique=False,
        postgresql_using='gin'
    )

    # Specific indexes for common query patterns
    op.execute("""
        -- Index for text responses
        CREATE INDEX idx_quiz_response_text_value
        ON quiz_responses ((response_value->>'text'))
        WHERE response_value ? 'text';

        -- Index for array responses (multiple choice)
        CREATE INDEX idx_quiz_response_array_value
        ON quiz_responses USING gin (response_value)
        WHERE jsonb_typeof(response_value) = 'array';

        -- Index for scale responses
        CREATE INDEX idx_quiz_response_scale_value
        ON quiz_responses ((response_value->'value'))
        WHERE response_value ? 'value';

        -- Index for boolean responses
        CREATE INDEX idx_quiz_response_boolean_value
        ON quiz_responses ((response_value->'boolean'))
        WHERE response_value ? 'boolean';
    """)

    # ========================================
    # STEP 7: Add check constraint for JSONB validity
    # ========================================
    print("Step 7: Adding validation constraints...")

    # Ensure response_value is valid JSONB (PostgreSQL handles this automatically)
    # Add application-level validation hints as comments
    op.execute("""
        COMMENT ON COLUMN quiz_responses.response_value IS
        'JSONB column storing structured quiz responses.
        Formats:
        - Plain text: "response text" or {"text": "response text"}
        - Multiple choice: ["option1", "option2"] or {"selections": ["A", "B"]}
        - Scale: {"value": 7, "type": "scale"}
        - Boolean: {"text": "yes", "boolean": true}
        Migration completed: 2025-01-14';
    """)

    # ========================================
    # STEP 8: Create helper functions for JSONB operations
    # ========================================
    print("Step 8: Creating helper functions...")

    op.execute("""
        -- Function to extract response as text regardless of JSONB structure
        CREATE OR REPLACE FUNCTION get_quiz_response_text(response_value JSONB)
        RETURNS TEXT AS $$
        BEGIN
            IF response_value IS NULL THEN
                RETURN NULL;
            ELSIF jsonb_typeof(response_value) = 'string' THEN
                RETURN response_value #>> '{}';  -- Extract string value
            ELSIF jsonb_typeof(response_value) = 'array' THEN
                RETURN array_to_string(
                    ARRAY(SELECT jsonb_array_elements_text(response_value)),
                    ', '
                );
            ELSIF jsonb_typeof(response_value) = 'object' THEN
                RETURN COALESCE(
                    response_value->>'text',
                    response_value->>'value',
                    response_value::text
                );
            ELSE
                RETURN response_value::text;
            END IF;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;

        -- Function to extract response as array (for multi-select)
        CREATE OR REPLACE FUNCTION get_quiz_response_array(response_value JSONB)
        RETURNS TEXT[] AS $$
        BEGIN
            IF response_value IS NULL THEN
                RETURN NULL;
            ELSIF jsonb_typeof(response_value) = 'array' THEN
                RETURN ARRAY(SELECT jsonb_array_elements_text(response_value));
            ELSIF jsonb_typeof(response_value) = 'string' THEN
                RETURN ARRAY[response_value #>> '{}'];
            ELSIF jsonb_typeof(response_value) = 'object' AND response_value ? 'selections' THEN
                RETURN ARRAY(SELECT jsonb_array_elements_text(response_value->'selections'));
            ELSE
                RETURN ARRAY[response_value::text];
            END IF;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;

        -- Function to get numeric value (for scales)
        CREATE OR REPLACE FUNCTION get_quiz_response_numeric(response_value JSONB)
        RETURNS NUMERIC AS $$
        BEGIN
            IF response_value IS NULL THEN
                RETURN NULL;
            ELSIF jsonb_typeof(response_value) = 'number' THEN
                RETURN (response_value #>> '{}')::numeric;
            ELSIF jsonb_typeof(response_value) = 'object' AND response_value ? 'value' THEN
                RETURN (response_value->>'value')::numeric;
            ELSIF jsonb_typeof(response_value) = 'string' AND
                  response_value #>> '{}' ~ '^[0-9]+\\.?[0-9]*$' THEN
                RETURN (response_value #>> '{}')::numeric;
            ELSE
                RETURN NULL;
            END IF;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    # ========================================
    # STEP 9: Create view for backward compatibility
    # ========================================
    print("Step 9: Creating backward compatibility view...")

    op.execute("""
        CREATE OR REPLACE VIEW quiz_responses_with_text AS
        SELECT
            qr.*,
            get_quiz_response_text(qr.response_value) AS response_value_text,
            get_quiz_response_array(qr.response_value) AS response_value_array,
            get_quiz_response_numeric(qr.response_value) AS response_value_numeric
        FROM quiz_responses qr;

        COMMENT ON VIEW quiz_responses_with_text IS
        'Backward compatibility view providing text, array, and numeric representations of JSONB response_value';
    """)

    # ========================================
    # STEP 10: Clean up migration function
    # ========================================
    print("Step 10: Cleaning up temporary functions...")

    op.execute("DROP FUNCTION IF EXISTS migrate_response_value_to_jsonb();")

    print("Migration completed successfully!")
    print("Note: Old text column preserved as 'response_value_text_backup' for safety.")
    print("      Review migration log at 'quiz_response_migration_log' table.")
    print("      After validation, backup column can be dropped manually if needed.")


def downgrade() -> None:
    """
    Rollback JSONB migration - convert back to Text.

    WARNING: This may result in data loss for complex JSONB structures.
    Only use in development/testing or emergency rollback scenarios.
    """

    print("WARNING: Rolling back JSONB migration to Text format...")
    print("         Complex JSONB structures will be serialized as JSON strings.")

    # ========================================
    # STEP 1: Create temporary text column
    # ========================================
    print("Step 1: Creating temporary text column...")

    op.add_column(
        'quiz_responses',
        sa.Column('response_value_text', sa.Text(), nullable=True)
    )

    # ========================================
    # STEP 2: Convert JSONB back to text
    # ========================================
    print("Step 2: Converting JSONB back to text...")

    op.execute("""
        UPDATE quiz_responses
        SET response_value_text = CASE
            -- NULL values
            WHEN response_value IS NULL THEN NULL

            -- String values: extract directly
            WHEN jsonb_typeof(response_value) = 'string' THEN
                response_value #>> '{}'

            -- Array values: serialize as JSON
            WHEN jsonb_typeof(response_value) = 'array' THEN
                response_value::text

            -- Object values: try to extract text field, otherwise serialize
            WHEN jsonb_typeof(response_value) = 'object' THEN
                COALESCE(
                    response_value->>'text',
                    response_value::text
                )

            -- Other types: serialize as text
            ELSE
                response_value::text
        END;
    """)

    # ========================================
    # STEP 3: Drop JSONB column and restore text column
    # ========================================
    print("Step 3: Swapping columns...")

    # Drop helper functions
    op.execute("DROP FUNCTION IF EXISTS get_quiz_response_numeric(JSONB);")
    op.execute("DROP FUNCTION IF EXISTS get_quiz_response_array(JSONB);")
    op.execute("DROP FUNCTION IF EXISTS get_quiz_response_text(JSONB);")

    # Drop validation function
    op.execute("DROP FUNCTION IF EXISTS validate_response_value_migration();")

    # Drop view
    op.execute("DROP VIEW IF EXISTS quiz_responses_with_text;")

    # Drop JSONB-specific indexes
    op.execute("DROP INDEX IF EXISTS idx_quiz_response_boolean_value;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_response_scale_value;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_response_array_value;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_response_text_value;")
    op.drop_index('idx_quiz_response_value_gin', table_name='quiz_responses')

    # Drop current JSONB column
    op.drop_column('quiz_responses', 'response_value')

    # Rename text column to official name
    op.alter_column(
        'quiz_responses',
        'response_value_text',
        new_column_name='response_value',
        existing_type=sa.Text(),
        nullable=False  # Restore NOT NULL constraint
    )

    # Restore backup column if it exists
    try:
        op.alter_column(
            'quiz_responses',
            'response_value_text_backup',
            new_column_name='response_value_backup',
            existing_type=sa.Text()
        )
    except Exception:
        # Backup column doesn't exist, skip
        pass

    # Drop migration log table
    op.execute("DROP TABLE IF EXISTS quiz_response_migration_log;")

    print("Rollback completed.")
    print("Note: Complex JSONB structures have been serialized as JSON strings.")
    print("      Manual data cleanup may be required.")
