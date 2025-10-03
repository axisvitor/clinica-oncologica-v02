"""Create message_status_events table for tracking message lifecycle

Revision ID: 018_message_status_events
Revises: 3e0261295d8a
Create Date: 2025-09-29 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '018_message_status_events'
down_revision = '3e0261295d8a'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create message_status_events table to track all message status changes
    in the WhatsApp messaging system.
    """
    # Create enum for message status
    op.execute("""
        CREATE TYPE message_status_type AS ENUM (
            'queued',
            'sending',
            'sent',
            'delivered',
            'read',
            'failed',
            'rejected'
        );
    """)

    # Create message_status_events table
    op.create_table(
        'message_status_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('queued', 'sending', 'sent', 'delivered', 'read', 'failed', 'rejected', name='message_status_type'), nullable=False),
        sa.Column('previous_status', sa.Enum('queued', 'sending', 'sent', 'delivered', 'read', 'failed', 'rejected', name='message_status_type'), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('whatsapp_message_id', sa.String(255), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.CheckConstraint("status != previous_status OR previous_status IS NULL", name='check_status_changed')
    )

    # Add comment
    op.execute("""
        COMMENT ON TABLE message_status_events IS
        'Tracks all status changes for messages throughout their lifecycle';
    """)


def downgrade():
    """
    Drop message_status_events table and related enum.
    """
    op.drop_table('message_status_events')
    op.execute("DROP TYPE IF EXISTS message_status_type CASCADE;")