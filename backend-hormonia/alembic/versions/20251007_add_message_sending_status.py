"""Add SENDING status to MessageStatus enum

Revision ID: 20251007_add_sending_status
Revises: 20251006_add_risk_assessment_indexes
Create Date: 2025-10-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251007_add_sending_status'
down_revision = '20251006_add_risk_assessment_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add SENDING status to MessageStatus enum.

    This status represents messages that are currently being sent by Celery workers,
    between SCHEDULED and SENT states. This fixes P0-4 where messages were duplicated
    because the Celery task created new messages instead of updating scheduled ones.
    """
    # Add new enum value using ALTER TYPE
    op.execute("""
        ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'sending' AFTER 'scheduled';
    """)


def downgrade() -> None:
    """
    Remove SENDING status from MessageStatus enum.

    Note: PostgreSQL does not support removing enum values directly.
    This would require recreating the enum type and migrating all data.
    For safety, we'll just log a warning instead.
    """
    # PostgreSQL doesn't support removing enum values
    # We'd need to:
    # 1. Create new enum without 'sending'
    # 2. Convert all 'sending' messages to 'pending'
    # 3. Alter column to use new enum
    # 4. Drop old enum
    # This is complex and risky, so we skip downgrade
    pass
