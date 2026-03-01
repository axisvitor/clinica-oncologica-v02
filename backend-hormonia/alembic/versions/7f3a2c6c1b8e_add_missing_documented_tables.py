"""legacy documented-tables migration intentionally neutralized.

Revision ID: 7f3a2c6c1b8e
Revises: c9a6d2f7b3e1
Create Date: 2026-01-19 00:00:00.000000

This migration introduced optional/legacy documented tables and enum-dependent
admin artifacts that are not required for the core runtime flow.

It is now a no-op to keep bootstrap deterministic and avoid reintroducing
legacy schema surface.
"""

# revision identifiers, used by Alembic.
revision = "7f3a2c6c1b8e"
down_revision = "c9a6d2f7b3e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
