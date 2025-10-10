"""Add quiz constraints for data integrity and performance

Revision ID: add_quiz_constraints
Revises:
Create Date: 2025-01-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008_quiz_constraints_v1'
down_revision = '007_flow_analytics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add database constraints for quiz sessions and responses."""

    # Add unique constraint for active quiz sessions per patient
    # This prevents race conditions when creating new sessions
    op.create_index(
        'ix_quiz_sessions_patient_active',
        'quiz_sessions',
        ['patient_id'],
        unique=True,
        postgresql_where=sa.text('is_completed = false')
    )

    # Add index for performance on quiz session lookups
    op.create_index(
        'ix_quiz_sessions_patient_completed',
        'quiz_sessions',
        ['patient_id', 'is_completed']
    )

    # Add index for quiz template lookups
    op.create_index(
        'ix_quiz_sessions_template',
        'quiz_sessions',
        ['quiz_template_id']
    )

    # Add composite index for session status queries
    op.create_index(
        'ix_quiz_sessions_status',
        'quiz_sessions',
        ['is_completed', 'created_at']
    )

    # Add unique constraint for quiz responses
    # Ensures one response per question per session
    op.create_unique_constraint(
        'uq_quiz_responses_session_question',
        'quiz_responses',
        ['session_id', 'question_index']
    )

    # Add index for response lookups by session
    op.create_index(
        'ix_quiz_responses_session',
        'quiz_responses',
        ['session_id']
    )

    # Add index for response timestamp queries
    op.create_index(
        'ix_quiz_responses_timestamp',
        'quiz_responses',
        ['created_at']
    )

    # Add check constraint for question index
    op.create_check_constraint(
        'ck_quiz_responses_question_index',
        'quiz_responses',
        sa.text('question_index >= 0')
    )

    # Add check constraint for quiz session dates
    op.create_check_constraint(
        'ck_quiz_sessions_dates',
        'quiz_sessions',
        sa.text('(completed_at IS NULL) OR (completed_at >= started_at)')
    )

    # Add check constraint for current question index
    op.create_check_constraint(
        'ck_quiz_sessions_question_index',
        'quiz_sessions',
        sa.text('current_question_index >= 0')
    )

    # Add foreign key constraint with CASCADE for quiz templates
    # This ensures referential integrity
    op.create_foreign_key(
        'fk_quiz_sessions_template',
        'quiz_sessions',
        'quiz_templates',
        ['quiz_template_id'],
        ['id'],
        ondelete='RESTRICT'
    )

    # Add foreign key constraint with CASCADE for patients
    op.create_foreign_key(
        'fk_quiz_sessions_patient',
        'quiz_sessions',
        'patients',
        ['patient_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Add foreign key constraint for quiz responses
    op.create_foreign_key(
        'fk_quiz_responses_session',
        'quiz_responses',
        'quiz_sessions',
        ['session_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create trigger to automatically update completed_at when is_completed changes to true
    op.execute("""
        CREATE OR REPLACE FUNCTION update_quiz_session_completed_at()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.is_completed = true AND OLD.is_completed = false THEN
                NEW.completed_at = CURRENT_TIMESTAMP;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trigger_update_quiz_session_completed_at
        BEFORE UPDATE ON quiz_sessions
        FOR EACH ROW
        WHEN (NEW.is_completed IS DISTINCT FROM OLD.is_completed)
        EXECUTE FUNCTION update_quiz_session_completed_at();
    """)

    # Create trigger to validate response data based on question type
    op.execute("""
        CREATE OR REPLACE FUNCTION validate_quiz_response()
        RETURNS TRIGGER AS $$
        DECLARE
            question_type TEXT;
            question_validation JSONB;
        BEGIN
            -- Get question type and validation from template
            SELECT
                questions->NEW.question_index->>'type',
                questions->NEW.question_index->'validation'
            INTO question_type, question_validation
            FROM quiz_templates qt
            JOIN quiz_sessions qs ON qs.quiz_template_id = qt.id
            WHERE qs.id = NEW.session_id;

            -- Validate based on question type
            CASE question_type
                WHEN 'numeric' THEN
                    -- Check if response is numeric
                    IF NOT (NEW.response_value ? 'value' AND
                            NEW.response_value->>'value' ~ '^[0-9]+(\\.[0-9]+)?$') THEN
                        RAISE EXCEPTION 'Invalid numeric response';
                    END IF;

                    -- Check min/max if specified
                    IF question_validation ? 'min' THEN
                        IF (NEW.response_value->>'value')::numeric <
                           (question_validation->>'min')::numeric THEN
                            RAISE EXCEPTION 'Response below minimum value';
                        END IF;
                    END IF;

                    IF question_validation ? 'max' THEN
                        IF (NEW.response_value->>'value')::numeric >
                           (question_validation->>'max')::numeric THEN
                            RAISE EXCEPTION 'Response above maximum value';
                        END IF;
                    END IF;

                WHEN 'boolean' THEN
                    -- Check if response is boolean
                    IF NOT (NEW.response_value ? 'value' AND
                            NEW.response_value->>'value' IN ('true', 'false')) THEN
                        RAISE EXCEPTION 'Invalid boolean response';
                    END IF;

                WHEN 'date' THEN
                    -- Check if response is valid date
                    BEGIN
                        PERFORM (NEW.response_value->>'value')::date;
                    EXCEPTION WHEN OTHERS THEN
                        RAISE EXCEPTION 'Invalid date response';
                    END;

                WHEN 'single_choice' THEN
                    -- Validate single choice selection
                    IF NOT (NEW.response_value ? 'value') THEN
                        RAISE EXCEPTION 'Single choice response required';
                    END IF;

                WHEN 'multiple_choice' THEN
                    -- Validate multiple choice is array
                    IF NOT (NEW.response_value ? 'values' AND
                            jsonb_typeof(NEW.response_value->'values') = 'array') THEN
                        RAISE EXCEPTION 'Multiple choice must be array';
                    END IF;

                ELSE
                    -- Text and other types - just ensure response exists
                    IF NOT (NEW.response_value ? 'value' OR NEW.response_value ? 'values') THEN
                        RAISE EXCEPTION 'Response value required';
                    END IF;
            END CASE;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trigger_validate_quiz_response
        BEFORE INSERT OR UPDATE ON quiz_responses
        FOR EACH ROW
        EXECUTE FUNCTION validate_quiz_response();
    """)


def downgrade() -> None:
    """Remove quiz constraints."""

    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS trigger_validate_quiz_response ON quiz_responses")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_quiz_session_completed_at ON quiz_sessions")
    op.execute("DROP FUNCTION IF EXISTS validate_quiz_response()")
    op.execute("DROP FUNCTION IF EXISTS update_quiz_session_completed_at()")

    # Drop foreign key constraints
    op.drop_constraint('fk_quiz_responses_session', 'quiz_responses', type_='foreignkey')
    op.drop_constraint('fk_quiz_sessions_patient', 'quiz_sessions', type_='foreignkey')
    op.drop_constraint('fk_quiz_sessions_template', 'quiz_sessions', type_='foreignkey')

    # Drop check constraints
    op.drop_constraint('ck_quiz_sessions_question_index', 'quiz_sessions', type_='check')
    op.drop_constraint('ck_quiz_sessions_dates', 'quiz_sessions', type_='check')
    op.drop_constraint('ck_quiz_responses_question_index', 'quiz_responses', type_='check')

    # Drop indexes
    op.drop_index('ix_quiz_responses_timestamp', table_name='quiz_responses')
    op.drop_index('ix_quiz_responses_session', table_name='quiz_responses')
    op.drop_constraint('uq_quiz_responses_session_question', 'quiz_responses', type_='unique')

    op.drop_index('ix_quiz_sessions_status', table_name='quiz_sessions')
    op.drop_index('ix_quiz_sessions_template', table_name='quiz_sessions')
    op.drop_index('ix_quiz_sessions_patient_completed', table_name='quiz_sessions')
    op.drop_index('ix_quiz_sessions_patient_active', table_name='quiz_sessions')