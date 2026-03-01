"""add_user_permissions

Add permissions JSONB field to users table for granular RBAC.
Stores array of permission strings like ["patients:read", "patients:write"].

Revision ID: 023_add_user_permissions
Revises: 022_add_cursor_pagination_indexes
Create Date: 2025-11-26

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
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '023_add_user_permissions'
down_revision = '022_add_cursor_pagination_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add permissions column to users table."""
    op.add_column(
        'users',
        sa.Column(
            'permissions',
            JSONB,
            nullable=False,
            server_default='[]'
        )
    )

    # Add GIN index for efficient permission lookups
    op.create_index(
        'ix_users_permissions_gin',
        'users',
        ['permissions'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    """Remove permissions column from users table."""
    op.drop_index('ix_users_permissions_gin', table_name='users')
    op.drop_column('users', 'permissions')
