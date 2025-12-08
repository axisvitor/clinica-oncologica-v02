"""Placeholder migration - reserved number.

Revision ID: 026_placeholder_reserved
Revises: 025
Create Date: 2024-11-30

Note: This migration number was skipped during development.
This placeholder maintains migration chain integrity.
"""
from alembic import op

revision = '026_placeholder_reserved'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op migration for sequence continuity."""
    pass


def downgrade() -> None:
    """No-op migration for sequence continuity."""
    pass
