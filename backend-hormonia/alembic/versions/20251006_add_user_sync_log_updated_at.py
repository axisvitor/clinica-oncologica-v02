"""Add updated_at column to user_sync_log table

Revision ID: 20251006_add_user_sync_log_updated_at
Revises: add_firebase_fields
Create Date: 2025-10-06 14:55:00.000000

CRITICAL FIX:
The user_sync_log table was created without the updated_at column,
but the UserSyncLog model inherits from BaseModel which includes
updated_at. This causes INSERT failures with:
"column user_sync_log.updated_at does not exist"

This migration adds:
1. updated_at column with proper default and timezone
2. Trigger to automatically update updated_at on row modifications
3. Index on updated_at for query performance
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251006_add_user_sync_log_updated_at'
down_revision = 'add_firebase_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add updated_at column and trigger to user_sync_log table."""

    # Add updated_at column
    op.add_column(
        'user_sync_log',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('NOW()')
        )
    )

    # Create index on updated_at for performance
    op.create_index(
        'idx_user_sync_log_updated_at',
        'user_sync_log',
        ['updated_at']
    )

    # Create trigger function to automatically update updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_user_sync_log_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger
    op.execute("""
        CREATE TRIGGER trigger_user_sync_log_updated_at
        BEFORE UPDATE ON user_sync_log
        FOR EACH ROW
        EXECUTE FUNCTION update_user_sync_log_updated_at();
    """)


def downgrade():
    """Remove updated_at column and trigger from user_sync_log table."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trigger_user_sync_log_updated_at ON user_sync_log")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS update_user_sync_log_updated_at()")

    # Drop index
    op.drop_index('idx_user_sync_log_updated_at', table_name='user_sync_log')

    # Drop column
    op.drop_column('user_sync_log', 'updated_at')
