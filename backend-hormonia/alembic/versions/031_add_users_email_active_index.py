"""Add composite index on users.email and users.is_active for login performance

Revision ID: 031_users_email_active_idx
Revises: 030_fix_audit_naming
Create Date: 2025-09-29 19:43:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '031_users_email_active_idx'
down_revision = '030_fix_audit_naming'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add composite index on users table for email + is_active
    to optimize authentication queries.
    """
    # Check if index already exists before creating
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_email_active
        ON users(email, is_active)
        WHERE is_active = true;
    """)

    # Add index for email lookups (if not already exists)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_email_lower
        ON users(LOWER(email));
    """)


def downgrade():
    """
    Drop the composite index on users.email and users.is_active.
    """
    op.drop_index('idx_users_email_lower', table_name='users', if_exists=True)
    op.drop_index('idx_users_email_active', table_name='users', if_exists=True)