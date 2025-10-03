"""Add webhook events indexes

Revision ID: 20250929_200006
Revises: 20250929_200005
Create Date: 2025-09-29

Performance optimization for webhook processing and retry queries.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250929_200006'
down_revision = '20250929_200005'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create indexes on webhook_events table for processing and retry logic.

    Query patterns:
    1. Event type filtering with time ordering
    2. Unprocessed event retrieval for retry logic

    Benefits:
    - Efficient webhook event processing
    - Fast unprocessed event retrieval for retry mechanisms
    - Event type analytics support
    - Partial index reduces storage for processed events
    """

    # Index 1: Event type with timestamp ordering
    # SELECT * FROM webhook_events WHERE event_type = ? ORDER BY created_at DESC
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_events_type_created
        ON webhook_events (event_type, created_at DESC)
    """)

    # Index 2: Unprocessed events (partial index for efficiency)
    # SELECT * FROM webhook_events WHERE processed = false ORDER BY created_at DESC
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_events_processed
        ON webhook_events (processed, created_at DESC)
        WHERE processed = false
    """)

    # Add comments for performance tracking
    op.execute("""
        COMMENT ON INDEX idx_webhook_events_type_created IS
        'Optimizes event type filtering and time-ordered retrieval'
    """)

    op.execute("""
        COMMENT ON INDEX idx_webhook_events_processed IS
        'Optimizes unprocessed event queries for retry logic (partial index)'
    """)


def downgrade():
    """Remove webhook events indexes"""
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_webhook_events_processed")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_webhook_events_type_created")