"""Add message status events indexes

Revision ID: 20250929_200005
Revises: 20250929_200004
Create Date: 2025-09-29

Performance optimization for message tracking queries.
Multiple indexes for comprehensive message status event tracking.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250929_200005'
down_revision = '20250929_200004'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create multiple indexes on message_status_events table.

    Query patterns:
    1. Message status history by message_id
    2. Status-based event filtering
    3. WhatsApp ID lookups for webhook processing

    Benefits:
    - Comprehensive message tracking optimization
    - Efficient webhook event processing
    - Status-based analytics support
    - Fast message history retrieval
    """

    # Index 1: Message status history lookup
    # SELECT * FROM message_status_events WHERE message_id = ? ORDER BY created_at DESC
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_message_status_events_message_id
        ON message_status_events (message_id, created_at DESC)
    """)

    # Index 2: Status-based filtering for analytics
    # SELECT * FROM message_status_events WHERE status = ? ORDER BY created_at DESC
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_message_status_events_status
        ON message_status_events (status, created_at DESC)
    """)

    # Index 3: WhatsApp ID lookup for webhook processing
    # SELECT * FROM message_status_events WHERE whatsapp_id = ?
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_message_status_events_whatsapp_id
        ON message_status_events (whatsapp_id)
    """)

    # Add comments for performance tracking
    op.execute("""
        COMMENT ON INDEX idx_message_status_events_message_id IS
        'Optimizes message status history queries'
    """)

    op.execute("""
        COMMENT ON INDEX idx_message_status_events_status IS
        'Optimizes status-based event filtering and analytics'
    """)

    op.execute("""
        COMMENT ON INDEX idx_message_status_events_whatsapp_id IS
        'Optimizes webhook processing lookups'
    """)


def downgrade():
    """Remove message status events indexes"""
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_message_status_events_whatsapp_id")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_message_status_events_status")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_message_status_events_message_id")