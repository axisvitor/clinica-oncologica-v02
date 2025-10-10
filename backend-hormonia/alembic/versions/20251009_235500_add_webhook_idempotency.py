"""Add webhook idempotency tracking table

Revision ID: 20251009_235500
Revises: 20251009_230000
Create Date: 2025-10-09 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251009_235500'
down_revision: Union[str, None] = '20251009_230000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create webhook_events table for idempotency tracking.

    This table prevents duplicate webhook processing by storing event IDs
    and detecting replays within a 24-hour window.
    """
    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column(
            'event_id',
            sa.String(length=255),
            nullable=False,
            primary_key=True,
            comment='Unique event ID from webhook provider'
        ),
        sa.Column(
            'provider',
            sa.String(length=50),
            nullable=False,
            comment='Webhook provider (e.g., whatsapp, twilio)'
        ),
        sa.Column(
            'event_type',
            sa.String(length=100),
            nullable=False,
            comment='Type of webhook event (e.g., message.received)'
        ),
        sa.Column(
            'received_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
            comment='When webhook was first received'
        ),
        sa.Column(
            'processed_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='When webhook processing completed'
        ),
        sa.Column(
            'expires_at',
            sa.DateTime(timezone=True),
            nullable=False,
            comment='When idempotency record expires (24h from received_at)'
        ),
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            server_default='processing',
            comment='Processing status: processing, completed, failed'
        ),
        sa.Column(
            'retry_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Number of duplicate webhook attempts detected'
        ),
        sa.Column(
            'payload',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Original webhook payload (for debugging)'
        ),
        sa.Column(
            'response_data',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Processing result or error details'
        ),
        sa.PrimaryKeyConstraint('event_id')
    )

    # Create indexes for efficient queries
    op.create_index(
        'idx_webhook_events_provider_type',
        'webhook_events',
        ['provider', 'event_type']
    )

    op.create_index(
        'idx_webhook_events_expires_at',
        'webhook_events',
        ['expires_at']
    )

    op.create_index(
        'idx_webhook_events_received_at',
        'webhook_events',
        ['received_at']
    )

    op.create_index(
        'idx_webhook_events_status',
        'webhook_events',
        ['status']
    )

    # Create partial index for active events (optimization)
    op.execute("""
        CREATE INDEX idx_webhook_events_active
        ON webhook_events (event_id, status)
        WHERE status = 'processing' OR status = 'completed'
    """)

    # Add comment to table
    op.execute("""
        COMMENT ON TABLE webhook_events IS
        'Tracks webhook events for idempotent processing.
        Prevents duplicate webhook processing within 24-hour window.'
    """)


def downgrade() -> None:
    """Drop webhook_events table and related indexes."""
    # Drop indexes
    op.drop_index('idx_webhook_events_active', table_name='webhook_events')
    op.drop_index('idx_webhook_events_status', table_name='webhook_events')
    op.drop_index('idx_webhook_events_received_at', table_name='webhook_events')
    op.drop_index('idx_webhook_events_expires_at', table_name='webhook_events')
    op.drop_index('idx_webhook_events_provider_type', table_name='webhook_events')

    # Drop table
    op.drop_table('webhook_events')
