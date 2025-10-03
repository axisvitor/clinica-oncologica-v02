"""Add quiz_sessions table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_quiz_sessions'
down_revision = '004_duplicate_detection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create quiz_sessions table
    op.create_table('quiz_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('quiz_template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_templates.id'), nullable=False),
        sa.Column('current_question_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Add quiz_session_id column to quiz_responses table
    op.add_column('quiz_responses', sa.Column('quiz_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_sessions.id'), nullable=True))
    
    # Create indexes
    op.create_index('idx_quiz_sessions_patient_id', 'quiz_sessions', ['patient_id'])
    op.create_index('idx_quiz_sessions_quiz_template_id', 'quiz_sessions', ['quiz_template_id'])
    op.create_index('idx_quiz_sessions_is_completed', 'quiz_sessions', ['is_completed'])
    op.create_index('idx_quiz_responses_quiz_session_id', 'quiz_responses', ['quiz_session_id'])
    
    # Create trigger for updated_at column
    op.execute("CREATE TRIGGER update_quiz_sessions_updated_at BEFORE UPDATE ON quiz_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")


def downgrade() -> None:
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_quiz_sessions_updated_at ON quiz_sessions")
    
    # Drop indexes
    op.drop_index('idx_quiz_responses_quiz_session_id', 'quiz_responses')
    op.drop_index('idx_quiz_sessions_is_completed', 'quiz_sessions')
    op.drop_index('idx_quiz_sessions_quiz_template_id', 'quiz_sessions')
    op.drop_index('idx_quiz_sessions_patient_id', 'quiz_sessions')
    
    # Remove quiz_session_id column from quiz_responses
    op.drop_column('quiz_responses', 'quiz_session_id')
    
    # Drop quiz_sessions table
    op.drop_table('quiz_sessions')