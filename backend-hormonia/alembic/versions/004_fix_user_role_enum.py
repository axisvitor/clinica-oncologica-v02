"""Fix user_role enum case sensitivity

Revision ID: 004
Revises: 003
Create Date: 2025-09-23 18:00:00.000000

This migration fixes the user_role enum to ensure lowercase values
match the Python UserRole enum exactly.

Problem: Database might have uppercase enum values but Python expects lowercase
Solution: Recreate enum with correct lowercase values
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010_user_role_enum'
down_revision = '009_quiz_constraints_v2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix user_role enum to use lowercase values consistently.
    """
    # Step 1: Convert column to VARCHAR temporarily
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE VARCHAR(20)
        USING role::text;
    """)

    # Step 2: Drop old enum type
    op.execute("DROP TYPE IF EXISTS user_role CASCADE;")

    # Step 3: Recreate enum with correct lowercase values
    op.execute("CREATE TYPE user_role AS ENUM ('doctor', 'admin');")

    # Step 4: Convert column back to enum
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE user_role
        USING role::user_role;
    """)

    # Step 5: Set default value
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role SET DEFAULT 'doctor'::user_role;
    """)

    # Step 6: Add helpful comment
    op.execute("""
        COMMENT ON TYPE user_role IS
        'User role enum with lowercase values: doctor, admin - matches Python UserRole enum';
    """)


def downgrade() -> None:
    """
    Rollback is not recommended as it could cause data inconsistency.
    The enum values should always be lowercase to match Python model.
    """
    pass