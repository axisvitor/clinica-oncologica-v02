"""Add webhook idempotency tracking table

Revision ID: 20251009_235500
Revises: 20251009_230000
Create Date: 2025-10-09 23:55:00.000000

IMPORTANT: Renamed table from 'webhook_events' to 'webhook_idempotency'
to avoid conflict with existing webhook_events table (created in migration 019)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251009_235500'
down_revision = '20251009_230000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create webhook_idempotency table for idempotency tracking.

    This table prevents duplicate webhook processing by storing event IDs
    and detecting replays within a 24-hour window.

    Note: Table renamed from webhook_events to webhook_idempotency to avoid
    conflict with the existing webhook_events table (migration 019).
    """
    # Create webhook_idempotency table
    op.create_table(
        'webhook_idempotency',
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
        'idx_webhook_idempotency_provider_type',
        'webhook_idempotency',
        ['provider', 'event_type']
    )

    op.create_index(
        'idx_webhook_idempotency_expires_at',
        'webhook_idempotency',
        ['expires_at']
    )

    op.create_index(
        'idx_webhook_idempotency_received_at',
        'webhook_idempotency',
        ['received_at']
    )

    op.create_index(
        'idx_webhook_idempotency_status',
        'webhook_idempotency',
        ['status']
    )

    # Create partial index for active events (optimization)
    op.execute("""
        CREATE INDEX idx_webhook_idempotency_active
        ON webhook_idempotency (event_id, status)
        WHERE status = 'processing' OR status = 'completed'
    """)

    # Add comment to table
    op.execute("""
        COMMENT ON TABLE webhook_idempotency IS
        'Tracks webhook events for idempotent processing.
        Prevents duplicate webhook processing within 24-hour window.
        Separate from webhook_events table which stores full event history.'
    """)


def downgrade() -> None:
    """Drop webhook_idempotency table and related indexes."""
    # Drop indexes
    op.drop_index('idx_webhook_idempotency_active', table_name='webhook_idempotency')
    op.drop_index('idx_webhook_idempotency_status', table_name='webhook_idempotency')
    op.drop_index('idx_webhook_idempotency_received_at', table_name='webhook_idempotency')
    op.drop_index('idx_webhook_idempotency_expires_at', table_name='webhook_idempotency')
    op.drop_index('idx_webhook_idempotency_provider_type', table_name='webhook_idempotency')

    # Drop table
    op.drop_table('webhook_idempotency')
