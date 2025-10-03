"""Add performance indexes for message_status_events table

Revision ID: 020_message_status_indexes
Revises: 019_webhook_events
Create Date: 2025-09-29 19:32:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '020_message_status_indexes'
down_revision = '019_webhook_events'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add indexes to message_status_events for optimal query performance.
    """
    # Index for message_id lookups (most common query)
    op.create_index(
        'idx_message_status_events_message_id',
        'message_status_events',
        ['message_id'],
        postgresql_using='btree'
    )

    # Composite index for message_id + timestamp (timeline queries)
    op.create_index(
        'idx_message_status_events_message_timestamp',
        'message_status_events',
        ['message_id', 'timestamp'],
        postgresql_using='btree'
    )

    # Index for status filtering
    op.create_index(
        'idx_message_status_events_status',
        'message_status_events',
        ['status'],
        postgresql_using='btree'
    )

    # Index for timestamp range queries (monitoring)
    op.create_index(
        'idx_message_status_events_timestamp',
        'message_status_events',
        ['timestamp'],
        postgresql_using='btree'
    )

    # Index for WhatsApp message ID lookups (webhook correlation)
    op.create_index(
        'idx_message_status_events_whatsapp_id',
        'message_status_events',
        ['whatsapp_message_id'],
        postgresql_using='btree',
        postgresql_where=sa.text('whatsapp_message_id IS NOT NULL')
    )

    # Index for error tracking (failed messages)
    op.create_index(
        'idx_message_status_events_errors',
        'message_status_events',
        ['status', 'timestamp'],
        postgresql_using='btree',
        postgresql_where=sa.text("status IN ('failed', 'rejected')")
    )


def downgrade():
    """
    Drop all performance indexes from message_status_events.
    """
    op.drop_index('idx_message_status_events_errors', table_name='message_status_events')
    op.drop_index('idx_message_status_events_whatsapp_id', table_name='message_status_events')
    op.drop_index('idx_message_status_events_timestamp', table_name='message_status_events')
    op.drop_index('idx_message_status_events_status', table_name='message_status_events')
    op.drop_index('idx_message_status_events_message_timestamp', table_name='message_status_events')
    op.drop_index('idx_message_status_events_message_id', table_name='message_status_events')