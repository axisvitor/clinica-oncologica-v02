"""Create webhook_events table for tracking incoming webhook deliveries

Revision ID: 019_webhook_events
Revises: 018_message_status_events
Create Date: 2025-09-29 19:31:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '019_webhook_events'
down_revision = '018_message_status_events'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create webhook_events table to track all incoming webhook deliveries
    from WhatsApp and other external services.
    """
    # Create enum for webhook event types
    op.execute("""
        CREATE TYPE webhook_event_type AS ENUM (
            'message_received',
            'message_status',
            'message_delivered',
            'message_read',
            'message_failed',
            'system_notification',
            'unknown'
        );
    """)

    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_type', sa.Enum('message_received', 'message_status', 'message_delivered', 'message_read', 'message_failed', 'system_notification', 'unknown', name='webhook_event_type'), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('webhook_id', sa.String(255), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('processed', sa.Boolean(), default=False, nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0, nullable=False),
        sa.Column('related_message_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['related_message_id'], ['messages.id'], ondelete='SET NULL')
    )

    # Add comments
    op.execute("""
        COMMENT ON TABLE webhook_events IS
        'Stores all incoming webhook events for audit trail and debugging';
    """)

    op.execute("""
        COMMENT ON COLUMN webhook_events.source IS
        'Source system (e.g., whatsapp, twilio, custom)';
    """)


def downgrade():
    """
    Drop webhook_events table and related enum.
    """
    op.drop_table('webhook_events')
    op.execute("DROP TYPE IF EXISTS webhook_event_type CASCADE;")