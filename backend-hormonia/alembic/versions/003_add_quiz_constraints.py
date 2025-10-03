"""Add quiz database constraints and indexes

Revision ID: 003_quiz_constraints
Revises: 20240831_quiz_metadata
Create Date: 2024-09-13 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '009_quiz_constraints_v2'
down_revision = '008_quiz_constraints_v1'
branch_labels = None
depends_on = None


def upgrade():
    """Add constraints and indexes to quiz tables for better data integrity and performance."""

    # ===== QuizTemplate constraints and indexes =====

    # Add unique constraint for template name and version
    op.create_unique_constraint(
        'uq_quiz_template_name_version',
        'quiz_templates',
        ['name', 'version']
    )

    # Add check constraints for quiz templates
    op.create_check_constraint(
        'ck_quiz_template_name_not_empty',
        'quiz_templates',
        'LENGTH(name) >= 1'
    )

    op.create_check_constraint(
        'ck_quiz_template_version_not_empty',
        'quiz_templates',
        'LENGTH(version) >= 1'
    )

    op.create_check_constraint(
        'ck_quiz_template_questions_not_null',
        'quiz_templates',
        'questions IS NOT NULL'
    )

    # Add indexes for quiz templates
    op.create_index('idx_quiz_template_name', 'quiz_templates', ['name'])
    op.create_index('idx_quiz_template_active', 'quiz_templates', ['is_active'])
    op.create_index('idx_quiz_template_name_active', 'quiz_templates', ['name', 'is_active'])

    # ===== QuizSession constraints and indexes =====

    # Add foreign key constraints with proper cascade options
    op.drop_constraint('quiz_sessions_patient_id_fkey', 'quiz_sessions', type_='foreignkey')
    op.drop_constraint('quiz_sessions_quiz_template_id_fkey', 'quiz_sessions', type_='foreignkey')

    op.create_foreign_key(
        'quiz_sessions_patient_id_fkey',
        'quiz_sessions', 'patients',
        ['patient_id'], ['id'],
        ondelete='CASCADE'
    )

    op.create_foreign_key(
        'quiz_sessions_quiz_template_id_fkey',
        'quiz_sessions', 'quiz_templates',
        ['quiz_template_id'], ['id'],
        ondelete='RESTRICT'
    )

    # Add unique constraint for active sessions (only one active session per patient per template)
    op.execute("""
        CREATE UNIQUE INDEX uq_active_quiz_session_per_patient
        ON quiz_sessions (patient_id, quiz_template_id)
        WHERE status = 'in_progress'
    """)

    # Add check constraints for quiz sessions
    op.create_check_constraint(
        'ck_quiz_session_question_index_positive',
        'quiz_sessions',
        'current_question_index >= 0'
    )

    op.create_check_constraint(
        'ck_quiz_session_score_positive',
        'quiz_sessions',
        'total_score >= 0'
    )

    op.create_check_constraint(
        'ck_quiz_session_status_valid',
        'quiz_sessions',
        "status IN ('in_progress', 'completed', 'cancelled')"
    )

    op.create_check_constraint(
        'ck_quiz_session_timing_valid',
        'quiz_sessions',
        'started_at <= COALESCE(completed_at, NOW())'
    )

    op.create_check_constraint(
        'ck_quiz_session_completed_timing',
        'quiz_sessions',
        "(status = 'completed' AND completed_at IS NOT NULL) OR (status != 'completed')"
    )

    # Add additional indexes for quiz sessions (some already exist, check before creating)
    indexes_to_create = [
        ('idx_quiz_session_status', ['status']),
        ('idx_quiz_session_patient_status', ['patient_id', 'status']),
        ('idx_quiz_session_template_status', ['quiz_template_id', 'status']),
        ('idx_quiz_session_started_at', ['started_at']),
        ('idx_quiz_session_completed_at', ['completed_at']),
        ('idx_quiz_session_active', ['patient_id', 'quiz_template_id', 'status']),
    ]

    for idx_name, columns in indexes_to_create:
        try:
            op.create_index(idx_name, 'quiz_sessions', columns)
        except Exception:
            # Index might already exist, skip
            pass

    # ===== QuizResponse constraints and indexes =====

    # Add foreign key constraints with proper cascade options
    op.drop_constraint('quiz_responses_patient_id_fkey', 'quiz_responses', type_='foreignkey')
    op.drop_constraint('quiz_responses_quiz_template_id_fkey', 'quiz_responses', type_='foreignkey')

    # Drop and recreate quiz_session_id foreign key if exists
    try:
        op.drop_constraint('quiz_responses_quiz_session_id_fkey', 'quiz_responses', type_='foreignkey')
    except Exception:
        pass

    op.create_foreign_key(
        'quiz_responses_patient_id_fkey',
        'quiz_responses', 'patients',
        ['patient_id'], ['id'],
        ondelete='CASCADE'
    )

    op.create_foreign_key(
        'quiz_responses_quiz_template_id_fkey',
        'quiz_responses', 'quiz_templates',
        ['quiz_template_id'], ['id'],
        ondelete='RESTRICT'
    )

    op.create_foreign_key(
        'quiz_responses_quiz_session_id_fkey',
        'quiz_responses', 'quiz_sessions',
        ['quiz_session_id'], ['id'],
        ondelete='CASCADE'
    )

    # Add unique constraint for responses (one response per question per session)
    op.create_unique_constraint(
        'uq_quiz_response_per_question_session',
        'quiz_responses',
        ['quiz_session_id', 'question_id']
    )

    # Add check constraints for quiz responses
    op.create_check_constraint(
        'ck_quiz_response_question_id_not_empty',
        'quiz_responses',
        'LENGTH(question_id) >= 1'
    )

    op.create_check_constraint(
        'ck_quiz_response_question_text_not_empty',
        'quiz_responses',
        'LENGTH(question_text) >= 1'
    )

    op.create_check_constraint(
        'ck_quiz_response_value_not_empty',
        'quiz_responses',
        'LENGTH(response_value) >= 1'
    )

    op.create_check_constraint(
        'ck_quiz_response_type_valid',
        'quiz_responses',
        "response_type IN ('multiple_choice', 'open_text', 'scale', 'boolean', 'rating')"
    )

    # Add indexes for quiz responses
    response_indexes = [
        ('idx_quiz_response_question_id', ['question_id']),
        ('idx_quiz_response_type', ['response_type']),
        ('idx_quiz_response_responded_at', ['responded_at']),
        ('idx_quiz_response_patient_template', ['patient_id', 'quiz_template_id']),
        ('idx_quiz_response_session_question', ['quiz_session_id', 'question_id']),
    ]

    for idx_name, columns in response_indexes:
        try:
            op.create_index(idx_name, 'quiz_responses', columns)
        except Exception:
            # Index might already exist, skip
            pass


def downgrade():
    """Remove constraints and indexes added in upgrade."""

    # ===== Remove QuizResponse constraints and indexes =====

    # Drop indexes
    response_indexes = [
        'idx_quiz_response_question_id',
        'idx_quiz_response_type',
        'idx_quiz_response_responded_at',
        'idx_quiz_response_patient_template',
        'idx_quiz_response_session_question'
    ]

    for idx_name in response_indexes:
        try:
            op.drop_index(idx_name, 'quiz_responses')
        except Exception:
            pass

    # Drop check constraints
    response_check_constraints = [
        'ck_quiz_response_question_id_not_empty',
        'ck_quiz_response_question_text_not_empty',
        'ck_quiz_response_value_not_empty',
        'ck_quiz_response_type_valid'
    ]

    for constraint_name in response_check_constraints:
        try:
            op.drop_constraint(constraint_name, 'quiz_responses', type_='check')
        except Exception:
            pass

    # Drop unique constraint
    try:
        op.drop_constraint('uq_quiz_response_per_question_session', 'quiz_responses', type_='unique')
    except Exception:
        pass

    # Restore original foreign key constraints (without CASCADE options)
    try:
        op.drop_constraint('quiz_responses_patient_id_fkey', 'quiz_responses', type_='foreignkey')
        op.drop_constraint('quiz_responses_quiz_template_id_fkey', 'quiz_responses', type_='foreignkey')
        op.drop_constraint('quiz_responses_quiz_session_id_fkey', 'quiz_responses', type_='foreignkey')

        op.create_foreign_key(None, 'quiz_responses', 'patients', ['patient_id'], ['id'])
        op.create_foreign_key(None, 'quiz_responses', 'quiz_templates', ['quiz_template_id'], ['id'])
        op.create_foreign_key(None, 'quiz_responses', 'quiz_sessions', ['quiz_session_id'], ['id'])
    except Exception:
        pass

    # ===== Remove QuizSession constraints and indexes =====

    # Drop indexes
    session_indexes = [
        'idx_quiz_session_status',
        'idx_quiz_session_patient_status',
        'idx_quiz_session_template_status',
        'idx_quiz_session_started_at',
        'idx_quiz_session_completed_at',
        'idx_quiz_session_active'
    ]

    for idx_name in session_indexes:
        try:
            op.drop_index(idx_name, 'quiz_sessions')
        except Exception:
            pass

    # Drop unique partial index
    try:
        op.drop_index('uq_active_quiz_session_per_patient', 'quiz_sessions')
    except Exception:
        pass

    # Drop check constraints
    session_check_constraints = [
        'ck_quiz_session_question_index_positive',
        'ck_quiz_session_score_positive',
        'ck_quiz_session_status_valid',
        'ck_quiz_session_timing_valid',
        'ck_quiz_session_completed_timing'
    ]

    for constraint_name in session_check_constraints:
        try:
            op.drop_constraint(constraint_name, 'quiz_sessions', type_='check')
        except Exception:
            pass

    # Restore original foreign key constraints
    try:
        op.drop_constraint('quiz_sessions_patient_id_fkey', 'quiz_sessions', type_='foreignkey')
        op.drop_constraint('quiz_sessions_quiz_template_id_fkey', 'quiz_sessions', type_='foreignkey')

        op.create_foreign_key(None, 'quiz_sessions', 'patients', ['patient_id'], ['id'])
        op.create_foreign_key(None, 'quiz_sessions', 'quiz_templates', ['quiz_template_id'], ['id'])
    except Exception:
        pass

    # ===== Remove QuizTemplate constraints and indexes =====

    # Drop indexes
    template_indexes = [
        'idx_quiz_template_name',
        'idx_quiz_template_active',
        'idx_quiz_template_name_active'
    ]

    for idx_name in template_indexes:
        try:
            op.drop_index(idx_name, 'quiz_templates')
        except Exception:
            pass

    # Drop check constraints
    template_check_constraints = [
        'ck_quiz_template_name_not_empty',
        'ck_quiz_template_version_not_empty',
        'ck_quiz_template_questions_not_null'
    ]

    for constraint_name in template_check_constraints:
        try:
            op.drop_constraint(constraint_name, 'quiz_templates', type_='check')
        except Exception:
            pass

    # Drop unique constraint
    try:
        op.drop_constraint('uq_quiz_template_name_version', 'quiz_templates', type_='unique')
    except Exception:
        pass