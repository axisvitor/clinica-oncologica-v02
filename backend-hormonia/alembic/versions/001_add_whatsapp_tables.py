"""Add WhatsApp integration tables

Revision ID: 001_whatsapp_tables
Revises:
Create Date: 2025-09-17 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_whatsapp'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create WhatsApp integration tables."""

    # WhatsApp Instances table
    op.create_table(
        'whatsapp_instances',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True, default='disconnected'),
        sa.Column('qr_code', sa.Text(), nullable=True),
        sa.Column('webhook_url', sa.String(), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('profile_name', sa.String(), nullable=True),
        sa.Column('profile_picture_url', sa.String(), nullable=True),
        sa.Column('is_connected', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_activity', sa.DateTime(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create indexes for instances
    op.create_index('ix_whatsapp_instances_name', 'whatsapp_instances', ['name'])
    op.create_index('ix_whatsapp_instances_status', 'whatsapp_instances', ['status'])
    op.create_index('ix_whatsapp_instances_is_connected', 'whatsapp_instances', ['is_connected'])

    # WhatsApp Contacts table
    op.create_table(
        'whatsapp_contacts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('instance_name', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('formatted_number', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('profile_picture_url', sa.String(), nullable=True),
        sa.Column('is_whatsapp_user', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('contact_data', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for contacts
    op.create_index('ix_whatsapp_contacts_instance_name', 'whatsapp_contacts', ['instance_name'])
    op.create_index('ix_whatsapp_contacts_phone_number', 'whatsapp_contacts', ['phone_number'])
    op.create_index('ix_whatsapp_contacts_formatted_number', 'whatsapp_contacts', ['formatted_number'])
    op.create_index('ix_whatsapp_contacts_name', 'whatsapp_contacts', ['name'])

    # WhatsApp Messages table
    op.create_table(
        'whatsapp_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('instance_name', sa.String(), nullable=False),
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('sender_id', sa.String(), nullable=False),
        sa.Column('recipient_id', sa.String(), nullable=False),
        sa.Column('message_type', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(), nullable=True),
        sa.Column('media_caption', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, default='pending'),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('message_data', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for messages
    op.create_index('ix_whatsapp_messages_instance_name', 'whatsapp_messages', ['instance_name'])
    op.create_index('ix_whatsapp_messages_chat_id', 'whatsapp_messages', ['chat_id'])
    op.create_index('ix_whatsapp_messages_sender_id', 'whatsapp_messages', ['sender_id'])
    op.create_index('ix_whatsapp_messages_recipient_id', 'whatsapp_messages', ['recipient_id'])
    op.create_index('ix_whatsapp_messages_status', 'whatsapp_messages', ['status'])
    op.create_index('ix_whatsapp_messages_external_id', 'whatsapp_messages', ['external_id'], unique=True)
    op.create_index('ix_whatsapp_messages_created_at', 'whatsapp_messages', ['created_at'])
    op.create_index('ix_whatsapp_messages_message_type', 'whatsapp_messages', ['message_type'])

    # Create composite indexes for common queries
    op.create_index(
        'ix_whatsapp_messages_instance_chat',
        'whatsapp_messages',
        ['instance_name', 'chat_id']
    )
    op.create_index(
        'ix_whatsapp_messages_status_created',
        'whatsapp_messages',
        ['status', 'created_at']
    )


def downgrade() -> None:
    """Drop WhatsApp integration tables."""

    # Drop indexes first
    op.drop_index('ix_whatsapp_messages_status_created', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_instance_chat', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_message_type', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_created_at', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_external_id', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_status', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_recipient_id', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_sender_id', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_chat_id', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_instance_name', table_name='whatsapp_messages')

    op.drop_index('ix_whatsapp_contacts_name', table_name='whatsapp_contacts')
    op.drop_index('ix_whatsapp_contacts_formatted_number', table_name='whatsapp_contacts')
    op.drop_index('ix_whatsapp_contacts_phone_number', table_name='whatsapp_contacts')
    op.drop_index('ix_whatsapp_contacts_instance_name', table_name='whatsapp_contacts')

    op.drop_index('ix_whatsapp_instances_is_connected', table_name='whatsapp_instances')
    op.drop_index('ix_whatsapp_instances_status', table_name='whatsapp_instances')
    op.drop_index('ix_whatsapp_instances_name', table_name='whatsapp_instances')

    # Drop tables
    op.drop_table('whatsapp_messages')
    op.drop_table('whatsapp_contacts')
    op.drop_table('whatsapp_instances')