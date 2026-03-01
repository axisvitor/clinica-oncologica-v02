"""legacy drift migration intentionally neutralized.

Revision ID: ac193e8656c1
Revises: 032_add_user_security_columns
Create Date: 2025-12-05 22:28:16.020518

This revision historically attempted a full schema drift sync and re-created
many tables that already existed in the canonical chain, causing duplicate
object failures on clean bootstrap.

It is now a no-op by design. Required runtime tables are created by dedicated
migrations (or bootstrap baseline) to keep migration order deterministic.
"""

# revision identifiers, used by Alembic.
revision = "ac193e8656c1"
down_revision = "032_add_user_security_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
