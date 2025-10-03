"""add_missing_user_roles

Revision ID: 3e0261295d8a
Revises: 54ab19a5b23f
Create Date: 2025-09-29 17:29:14.596405

This migration adds the missing user roles to the user_role enum:
- super_admin: System administrator with full access
- nurse: Healthcare provider with patient care permissions
- patient: End user receiving care
- researcher: Data analysis and research permissions
- coordinator: Care coordination and scheduling
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '3e0261295d8a'
down_revision = '54ab19a5b23f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add missing user roles to the user_role enum.
    Updates: super_admin, nurse, patient, researcher, coordinator
    Changes default role from 'doctor' to 'patient'
    """
    # Step 1: Convert column to VARCHAR temporarily
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE VARCHAR(20)
        USING role::text;
    """)

    # Step 2: Drop old enum type
    op.execute("DROP TYPE IF EXISTS user_role CASCADE;")

    # Step 3: Recreate enum with all 7 roles
    op.execute("""
        CREATE TYPE user_role AS ENUM (
            'super_admin',
            'admin',
            'doctor',
            'nurse',
            'patient',
            'researcher',
            'coordinator'
        );
    """)

    # Step 4: Convert column back to enum
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE user_role
        USING role::user_role;
    """)

    # Step 5: Set default value to patient
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role SET DEFAULT 'patient'::user_role;
    """)

    # Step 6: Add helpful comment
    op.execute("""
        COMMENT ON TYPE user_role IS
        'User role enum: super_admin, admin, doctor, nurse, patient, researcher, coordinator - expanded roles in migration 3e0261295d8a';
    """)

    # Step 7: Create indexes for better query performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_role
        ON users(role);
    """)


def downgrade() -> None:
    """
    Rollback to original two roles: doctor and admin.
    WARNING: This will convert all users with new roles to 'doctor'.
    """
    # Step 1: Convert all new roles to doctor (fallback)
    op.execute("""
        UPDATE users
        SET role = 'doctor'
        WHERE role IN ('super_admin', 'nurse', 'patient', 'researcher', 'coordinator');
    """)

    # Step 2: Drop index
    op.execute("DROP INDEX IF EXISTS idx_users_role;")

    # Step 3: Convert column to VARCHAR temporarily
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE VARCHAR(20)
        USING role::text;
    """)

    # Step 4: Drop current enum type
    op.execute("DROP TYPE IF EXISTS user_role CASCADE;")

    # Step 5: Recreate enum with only original roles
    op.execute("CREATE TYPE user_role AS ENUM ('doctor', 'admin');")

    # Step 6: Convert column back to enum
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE user_role
        USING role::user_role;
    """)

    # Step 7: Set default value back to doctor
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role SET DEFAULT 'doctor'::user_role;
    """)

    # Step 8: Add comment
    op.execute("""
        COMMENT ON TYPE user_role IS
        'User role enum: doctor, admin - roles reverted from migration 3e0261295d8a';
    """)