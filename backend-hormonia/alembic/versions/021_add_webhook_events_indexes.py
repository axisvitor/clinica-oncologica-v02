"""Add performance indexes for webhook_events table

Revision ID: 021_webhook_events_indexes
Revises: 020_message_status_indexes
Create Date: 2025-09-29 19:33:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '021_webhook_events_indexes'
down_revision = '020_message_status_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add indexes to webhook_events for optimal processing and querying.
    """
    # Index for unprocessed events (queue processing)
    op.create_index(
        'idx_webhook_events_unprocessed',
        'webhook_events',
        ['processed', 'created_at'],
        postgresql_using='btree',
        postgresql_where=sa.text('processed = false')
    )

    # Index for event type filtering
    op.create_index(
        'idx_webhook_events_event_type',
        'webhook_events',
        ['event_type', 'created_at'],
        postgresql_using='btree'
    )

    # Index for source system filtering
    op.create_index(
        'idx_webhook_events_source',
        'webhook_events',
        ['source'],
        postgresql_using='btree'
    )

    # Index for webhook ID deduplication
    op.create_index(
        'idx_webhook_events_webhook_id',
        'webhook_events',
        ['webhook_id'],
        postgresql_using='btree',
        postgresql_where=sa.text('webhook_id IS NOT NULL')
    )

    # Index for related message lookups
    op.create_index(
        'idx_webhook_events_related_message',
        'webhook_events',
        ['related_message_id'],
        postgresql_using='btree',
        postgresql_where=sa.text('related_message_id IS NOT NULL')
    )

    # Index for error tracking and retry logic
    op.create_index(
        'idx_webhook_events_errors',
        'webhook_events',
        ['error_message', 'retry_count'],
        postgresql_using='btree',
        postgresql_where=sa.text('error_message IS NOT NULL')
    )

    # Index for timestamp range queries (audit trail)
    op.create_index(
        'idx_webhook_events_created_at',
        'webhook_events',
        ['created_at'],
        postgresql_using='btree'
    )


def downgrade():
    """
    Drop all performance indexes from webhook_events.
    """
    op.drop_index('idx_webhook_events_created_at', table_name='webhook_events')
    op.drop_index('idx_webhook_events_errors', table_name='webhook_events')
    op.drop_index('idx_webhook_events_related_message', table_name='webhook_events')
    op.drop_index('idx_webhook_events_webhook_id', table_name='webhook_events')
    op.drop_index('idx_webhook_events_source', table_name='webhook_events')
    op.drop_index('idx_webhook_events_event_type', table_name='webhook_events')
    op.drop_index('idx_webhook_events_unprocessed', table_name='webhook_events')