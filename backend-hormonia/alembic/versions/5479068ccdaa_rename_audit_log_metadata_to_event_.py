"""rename_audit_log_metadata_to_event_metadata

Revision ID: 5479068ccdaa
Revises: 3d3c49dd21c2
Create Date: 2025-10-09 12:32:08.452811

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5479068ccdaa'
down_revision = '3d3c49dd21c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename metadata column to event_metadata in audit_logs table.

    This fixes a conflict with SQLAlchemy's reserved 'metadata' attribute.
    """
    # Rename column from metadata to event_metadata
    op.alter_column(
        'audit_logs',
        'metadata',
        new_column_name='event_metadata',
        existing_type=sa.dialects.postgresql.JSONB(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
        comment="Additional event metadata (device info, session ID, etc.)"
    )


def downgrade() -> None:
    """Revert event_metadata column back to metadata."""
    # Rename column back from event_metadata to metadata
    op.alter_column(
        'audit_logs',
        'event_metadata',
        new_column_name='metadata',
        existing_type=sa.dialects.postgresql.JSONB(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
        comment="Additional event metadata (device info, session ID, etc.)"
    )