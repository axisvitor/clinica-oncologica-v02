"""Remove nurse role from user_role enum

Revision ID: 011
Revises: 010_user_role_enum
Create Date: 2025-09-26 19:00:00.000000

This migration removes the 'nurse' role from the user_role enum,
converting any existing nurse users to doctor role as a fallback.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_remove_nurse_role'
down_revision = '010_user_role_enum'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove nurse role from user_role enum.
    """
    # Step 1: Convert any existing nurse users to doctor role
    op.execute("""
        UPDATE users
        SET role = 'doctor'
        WHERE role = 'nurse';
    """)

    # Step 2: Convert column to VARCHAR temporarily
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE VARCHAR(20)
        USING role::text;
    """)

    # Step 3: Drop old enum type
    op.execute("DROP TYPE IF EXISTS user_role CASCADE;")

    # Step 4: Recreate enum without nurse role
    op.execute("CREATE TYPE user_role AS ENUM ('doctor', 'admin');")

    # Step 5: Convert column back to enum
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE user_role
        USING role::user_role;
    """)

    # Step 6: Set default value
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role SET DEFAULT 'doctor'::user_role;
    """)

    # Step 7: Add helpful comment
    op.execute("""
        COMMENT ON TYPE user_role IS
        'User role enum: doctor, admin - nurse role removed in migration 011';
    """)


def downgrade() -> None:
    """
    Rollback to include nurse role.
    Note: This will not restore users who were converted from nurse to doctor.
    """
    # Step 1: Convert column to VARCHAR temporarily
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE VARCHAR(20)
        USING role::text;
    """)

    # Step 2: Drop current enum type
    op.execute("DROP TYPE IF EXISTS user_role CASCADE;")

    # Step 3: Recreate enum with nurse role
    op.execute("CREATE TYPE user_role AS ENUM ('doctor', 'nurse', 'admin');")

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

    # Step 6: Add comment
    op.execute("""
        COMMENT ON TYPE user_role IS
        'User role enum: doctor, nurse, admin - nurse role restored';
    """)