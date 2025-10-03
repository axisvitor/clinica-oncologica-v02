"""add other_text to quiz_responses

Revision ID: 005_add_other_text
Revises: 004_fix_user_role_enum
Create Date: 2025-09-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_other_text'
down_revision = '010_user_role_enum'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add other_text column to quiz_responses table."""
    # Add other_text column to quiz_responses table
    op.add_column(
        'quiz_responses',
        sa.Column('other_text', sa.Text(), nullable=True)
    )

    # Add comment to explain the column
    op.execute(
        """
        COMMENT ON COLUMN quiz_responses.other_text IS
        'Custom text for "other" option when user selects an option that allows custom input'
        """
    )


def downgrade() -> None:
    """Remove other_text column from quiz_responses table."""
    # Remove the column
    op.drop_column('quiz_responses', 'other_text')