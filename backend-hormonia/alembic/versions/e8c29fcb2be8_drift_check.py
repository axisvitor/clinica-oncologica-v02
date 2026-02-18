"""legacy drift-check migration intentionally neutralized.

Revision ID: e8c29fcb2be8
Revises: b7c2f9a1d3e4
Create Date: 2026-01-17 16:17:14.365367

The historical drift-check migration attempted broad schema rewrites and enum
casts that are not deterministic across clean/bootstrap environments.

This revision is now a no-op; concrete schema changes are kept in dedicated,
scoped migrations.
"""

# revision identifiers, used by Alembic.
revision = "e8c29fcb2be8"
down_revision = "b7c2f9a1d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
