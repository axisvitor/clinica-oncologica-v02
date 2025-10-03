"""Add composite index on audit_log_entries for user activity queries

Revision ID: 033_audit_user_timestamp_idx
Revises: 032_messages_whatsapp_idx
Create Date: 2025-09-29 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '033_audit_user_timestamp_idx'
down_revision = '032_messages_whatsapp_idx'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add composite indexes on audit_log_entries for common query patterns:
    - User activity timeline
    - Action type filtering
    - Entity tracking
    """
    # Composite index for user activity queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_entries_user_timestamp
        ON audit_log_entries(user_id, timestamp DESC)
        WHERE user_id IS NOT NULL;
    """)

    # Composite index for action filtering with timestamps
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_entries_action_timestamp
        ON audit_log_entries(action, timestamp DESC);
    """)

    # Composite index for entity tracking
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_entries_entity_type_id
        ON audit_log_entries(entity_type, entity_id, timestamp DESC);
    """)

    # Index for IP address tracking (security audits)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_entries_ip_address
        ON audit_log_entries(ip_address, timestamp DESC)
        WHERE ip_address IS NOT NULL;
    """)


def downgrade():
    """
    Drop the audit log composite indexes.
    """
    op.drop_index('idx_audit_log_entries_ip_address', table_name='audit_log_entries', if_exists=True)
    op.drop_index('idx_audit_log_entries_entity_type_id', table_name='audit_log_entries', if_exists=True)
    op.drop_index('idx_audit_log_entries_action_timestamp', table_name='audit_log_entries', if_exists=True)
    op.drop_index('idx_audit_log_entries_user_timestamp', table_name='audit_log_entries', if_exists=True)