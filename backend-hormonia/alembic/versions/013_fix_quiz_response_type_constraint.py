"""Fix quiz response type constraint

Revision ID: 013_fix_quiz_response_type_constraint
Revises: 012_ai_audit_logs
Create Date: 2025-09-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013_fix_quiz_response_type_constraint'
down_revision = '012_ai_audit_logs'
branch_labels = None
depends_on = None


def upgrade():
    """Add new response types to quiz_responses response_type constraint."""
    # Drop the existing constraint
    op.drop_constraint('ck_quiz_response_type_valid', 'quiz_responses', type_='check')

    # Create the new constraint with additional response types
    op.create_check_constraint(
        'ck_quiz_response_type_valid',
        'quiz_responses',
        "response_type IN ('multiple_choice', 'open_text', 'scale', 'boolean', 'rating', 'yes_no', 'number', 'date', 'single_choice')"
    )


def downgrade():
    """Revert to original response types constraint."""
    # Drop the expanded constraint
    op.drop_constraint('ck_quiz_response_type_valid', 'quiz_responses', type_='check')

    # Restore the original constraint
    op.create_check_constraint(
        'ck_quiz_response_type_valid',
        'quiz_responses',
        "response_type IN ('multiple_choice', 'open_text', 'scale', 'boolean', 'rating')"
    )