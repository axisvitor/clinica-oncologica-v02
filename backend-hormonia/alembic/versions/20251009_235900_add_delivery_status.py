"""Add delivery status tracking to messages

Revision ID: 20251009_235900
Revises: 20251009_235500
Create Date: 2025-10-09 23:59:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251009_235900'
down_revision = '20251009_235500'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add delivery_status field and retry tracking to messages table.
    This enables proper flow state management when WhatsApp delivery fails.
    """
    # Add delivery_status enum type
    delivery_status_enum = postgresql.ENUM(
        'scheduled', 'queued', 'sending', 'sent', 'delivered',
        'read', 'failed', 'cancelled',
        name='deliverystatus',
        create_type=True
    )
    delivery_status_enum.create(op.get_bind(), checkfirst=True)

    # Add delivery_status column to messages table
    op.add_column(
        'messages',
        sa.Column(
            'delivery_status',
            postgresql.ENUM(
                'scheduled', 'queued', 'sending', 'sent', 'delivered',
                'read', 'failed', 'cancelled',
                name='deliverystatus'
            ),
            nullable=True,
            comment='Current delivery status for tracking message lifecycle'
        )
    )

    # Add retry tracking columns
    op.add_column(
        'messages',
        sa.Column(
            'retry_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Number of delivery retry attempts'
        )
    )

    op.add_column(
        'messages',
        sa.Column(
            'last_retry_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp of last retry attempt'
        )
    )

    op.add_column(
        'messages',
        sa.Column(
            'failure_reason',
            sa.Text(),
            nullable=True,
            comment='Reason for delivery failure'
        )
    )

    op.add_column(
        'messages',
        sa.Column(
            'next_retry_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Scheduled time for next retry attempt'
        )
    )

    # Add index for efficient retry query
    op.create_index(
        'ix_messages_next_retry_at',
        'messages',
        ['next_retry_at'],
        postgresql_where=sa.text("delivery_status = 'failed' AND retry_count < 3")
    )

    # Add index for delivery status queries
    op.create_index(
        'ix_messages_delivery_status',
        'messages',
        ['delivery_status', 'patient_id']
    )

    # Backfill delivery_status from existing status field
    op.execute("""
        UPDATE messages
        SET delivery_status = CASE
            WHEN status = 'scheduled' THEN 'scheduled'::deliverystatus
            WHEN status = 'pending' THEN 'queued'::deliverystatus
            WHEN status = 'sending' THEN 'sending'::deliverystatus
            WHEN status = 'sent' THEN 'sent'::deliverystatus
            WHEN status = 'delivered' THEN 'delivered'::deliverystatus
            WHEN status = 'read' THEN 'read'::deliverystatus
            WHEN status = 'failed' THEN 'failed'::deliverystatus
            WHEN status = 'cancelled' THEN 'cancelled'::deliverystatus
            ELSE 'queued'::deliverystatus
        END
        WHERE delivery_status IS NULL
    """)


def downgrade() -> None:
    """
    Remove delivery status tracking fields.
    """
    # Drop indexes
    op.drop_index('ix_messages_delivery_status', table_name='messages')
    op.drop_index('ix_messages_next_retry_at', table_name='messages')

    # Drop columns
    op.drop_column('messages', 'next_retry_at')
    op.drop_column('messages', 'failure_reason')
    op.drop_column('messages', 'last_retry_at')
    op.drop_column('messages', 'retry_count')
    op.drop_column('messages', 'delivery_status')

    # Drop enum type
    delivery_status_enum = postgresql.ENUM(
        'scheduled', 'queued', 'sending', 'sent', 'delivered',
        'read', 'failed', 'cancelled',
        name='deliverystatus'
    )
    delivery_status_enum.drop(op.get_bind(), checkfirst=True)
