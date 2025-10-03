"""Add index on messages.whatsapp_message_id for webhook correlation

Revision ID: 032_messages_whatsapp_idx
Revises: 031_users_email_active_idx
Create Date: 2025-09-29 19:44:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '032_messages_whatsapp_idx'
down_revision = '031_users_email_active_idx'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add index on messages.whatsapp_message_id for fast webhook
    status update lookups.
    """
    # Index for WhatsApp message ID lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_whatsapp_message_id
        ON messages(whatsapp_message_id)
        WHERE whatsapp_message_id IS NOT NULL;
    """)

    # Composite index for patient + timestamp queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_patient_timestamp
        ON messages(patient_id, created_at DESC);
    """)

    # Index for status filtering
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_status_created
        ON messages(status, created_at DESC);
    """)


def downgrade():
    """
    Drop the WhatsApp message ID indexes.
    """
    op.drop_index('idx_messages_status_created', table_name='messages', if_exists=True)
    op.drop_index('idx_messages_patient_timestamp', table_name='messages', if_exists=True)
    op.drop_index('idx_messages_whatsapp_message_id', table_name='messages', if_exists=True)