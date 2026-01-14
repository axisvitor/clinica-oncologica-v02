"""Add CLEANED_UP saga status

Revision ID: b7c2f9a1d3e4
Revises: f1878d0fb2fc
Create Date: 2025-12-28 12:00:00.000000

Adds CLEANED_UP to saga_status enum to support manual cleanup tracking.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b7c2f9a1d3e4"
down_revision = "f1878d0fb2fc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add CLEANED_UP to saga_status enum."""
    conn = op.get_bind()

    result = conn.execute(
        sa.text(
            """
        SELECT enumlabel FROM pg_enum
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'saga_status')
    """
        )
    )
    existing_values = {row[0] for row in result.fetchall()}

    if "CLEANED_UP" not in existing_values:
        op.execute(
            sa.text(
                """
            ALTER TYPE saga_status ADD VALUE IF NOT EXISTS 'CLEANED_UP' AFTER 'COMPENSATED'
        """
            )
        )
        print("[OK] Added CLEANED_UP to saga_status enum")
    else:
        print("[SKIP] CLEANED_UP already exists")


def downgrade() -> None:
    """
    PostgreSQL does not support removing enum values directly.
    This downgrade is intentionally left as a no-op.
    """
    print("[WARN] CLEANED_UP enum value cannot be removed without manual steps.")
