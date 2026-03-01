"""Add user security columns for account lockout

Revision ID: 032_add_user_security_columns
Revises: 031_add_performance_indexes
Create Date: 2025-12-05 00:00:00.000000

This migration adds security columns to the users table:
- failed_login_attempts: Track failed login attempts
- is_locked: Account lockout flag
- locked_until: Timestamp when lockout expires
- force_change_password: Require password change on next login
- last_password_change: Track password changes for security policies

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


# revision identifiers, used by Alembic.
revision = '032_add_user_security_columns'
down_revision = '031_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add security columns to users table"""

    # Add failed_login_attempts column
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'failed_login_attempts'
            ) THEN
                ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0;
            END IF;
        END $$;
    """)

    # Add is_locked column
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'is_locked'
            ) THEN
                ALTER TABLE users ADD COLUMN is_locked BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END $$;
    """)

    # Add locked_until column
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'locked_until'
            ) THEN
                ALTER TABLE users ADD COLUMN locked_until TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)

    # Add force_change_password column
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'force_change_password'
            ) THEN
                ALTER TABLE users ADD COLUMN force_change_password BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END $$;
    """)

    # Add last_password_change column
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'last_password_change'
            ) THEN
                ALTER TABLE users ADD COLUMN last_password_change TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)

    # Add permissions column (JSONB array for RBAC)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'permissions'
            ) THEN
                ALTER TABLE users ADD COLUMN permissions JSONB NOT NULL DEFAULT '[]'::jsonb;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove security columns from users table"""

    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS permissions")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS last_password_change")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS force_change_password")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS locked_until")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_locked")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS failed_login_attempts")
