"""Add whatsapp_delivery_failures table for tracking failed message deliveries

Revision ID: 20251009_230000
Revises: 20251009_210800
Create Date: 2025-10-09 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251009_230000'
down_revision: Union[str, None] = '20251009_210800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create whatsapp_delivery_failures table for tracking failed WhatsApp message deliveries.

    This table stores information about WhatsApp messages that failed to send,
    enabling retry mechanisms and failure analysis.
    """
    op.create_table(
        'whatsapp_delivery_failures',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('phone_number', sa.String(20), nullable=False),
        sa.Column('message_type', sa.String(50), nullable=False, comment='Type of message (welcome, reminder, quiz, etc.)'),
        sa.Column('message_content', sa.Text, nullable=True, comment='Content of the failed message'),
        sa.Column('error_message', sa.Text, nullable=False, comment='Error message from WhatsApp API'),
        sa.Column('error_code', sa.String(50), nullable=True, comment='Error code from WhatsApp API'),
        sa.Column('retry_count', sa.Integer, nullable=False, default=0),
        sa.Column('max_retries', sa.Integer, nullable=False, default=3),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True, comment='Scheduled time for next retry'),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending', comment='Status: pending, retrying, failed, resolved'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, default={}, comment='Additional failure context'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        comment='Tracks failed WhatsApp message deliveries for retry and analysis'
    )

    # Create indexes for efficient querying
    op.create_index(
        'idx_whatsapp_failures_status',
        'whatsapp_delivery_failures',
        ['status'],
        postgresql_where=sa.text("status IN ('pending', 'retrying')")
    )

    op.create_index(
        'idx_whatsapp_failures_next_retry',
        'whatsapp_delivery_failures',
        ['next_retry_at'],
        postgresql_where=sa.text("next_retry_at IS NOT NULL AND status = 'pending'")
    )

    op.create_index(
        'idx_whatsapp_failures_created_at',
        'whatsapp_delivery_failures',
        ['created_at']
    )

    # Create updated_at trigger
    op.execute("""
        CREATE TRIGGER update_whatsapp_delivery_failures_updated_at
        BEFORE UPDATE ON whatsapp_delivery_failures
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Remove whatsapp_delivery_failures table."""
    op.drop_table('whatsapp_delivery_failures')
