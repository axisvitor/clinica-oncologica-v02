"""Create quiz_questions table for storing quiz question templates

Revision ID: 029_quiz_questions
Revises: 028_ab_testing_indexes
Create Date: 2025-09-29 19:41:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '029_quiz_questions'
down_revision = '028_ab_testing_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create quiz_questions table to store reusable quiz question templates
    that can be referenced by quiz sessions.
    """
    # Create enum for question types
    op.execute("""
        CREATE TYPE quiz_question_type AS ENUM (
            'multiple_choice',
            'single_choice',
            'text',
            'numeric',
            'yes_no',
            'rating',
            'date'
        );
    """)

    # Create quiz_questions table
    op.create_table(
        'quiz_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('question_key', sa.String(100), nullable=False, unique=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.Enum('multiple_choice', 'single_choice', 'text', 'numeric', 'yes_no', 'rating', 'date', name='quiz_question_type'), nullable=False),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('is_required', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('help_text', sa.Text(), nullable=True),
        sa.Column('placeholder_text', sa.String(255), nullable=True),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('display_order >= 0', name='check_display_order')
    )

    # Create indexes
    op.create_index(
        'idx_quiz_questions_type',
        'quiz_questions',
        ['question_type'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_quiz_questions_category',
        'quiz_questions',
        ['category'],
        postgresql_using='btree',
        postgresql_where=sa.text('category IS NOT NULL')
    )

    op.create_index(
        'idx_quiz_questions_active',
        'quiz_questions',
        ['is_active', 'display_order'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_quiz_questions_tags',
        'quiz_questions',
        ['tags'],
        postgresql_using='gin',
        postgresql_where=sa.text('tags IS NOT NULL')
    )

    # Add comments
    op.execute("""
        COMMENT ON TABLE quiz_questions IS
        'Reusable quiz question templates for patient assessments';
    """)

    op.execute("""
        COMMENT ON COLUMN quiz_questions.question_key IS
        'Unique identifier for the question (e.g., symptom_severity, pain_level)';
    """)

    op.execute("""
        COMMENT ON COLUMN quiz_questions.validation_rules IS
        'JSON object containing validation rules (regex patterns, min/max length, etc.)';
    """)


def downgrade():
    """
    Drop quiz_questions table and related types.
    """
    op.drop_index('idx_quiz_questions_tags', table_name='quiz_questions')
    op.drop_index('idx_quiz_questions_active', table_name='quiz_questions')
    op.drop_index('idx_quiz_questions_category', table_name='quiz_questions')
    op.drop_index('idx_quiz_questions_type', table_name='quiz_questions')
    op.drop_table('quiz_questions')
    op.execute("DROP TYPE IF EXISTS quiz_question_type CASCADE;")