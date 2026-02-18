"""Add cancelled to message_status enum.

Revision ID: e2c4b1a9f7d3
Revises: d4b6c1a7e9f2
Create Date: 2026-01-24

Adds the 'cancelled' value to the message_status enum to align database
constraints with the application MessageStatus enum.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e2c4b1a9f7d3"
down_revision = "d4b6c1a7e9f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'message_status'
                  AND e.enumlabel = 'cancelled'
            ) THEN
                ALTER TYPE message_status ADD VALUE 'cancelled';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Enum value removal is not supported in PostgreSQL without recreating the type.
    # No-op downgrade to avoid destructive changes.
    pass
