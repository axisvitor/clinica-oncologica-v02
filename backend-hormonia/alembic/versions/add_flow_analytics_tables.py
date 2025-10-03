"""Add flow analytics and message tracking tables

Revision ID: 007_flow_analytics
Revises:
Create Date: 2025-08-12 07:18:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_flow_analytics'
down_revision = '006_audit_log'
branch_labels = None
depends_on = None


def upgrade():
    # Create flow_analytics table
    op.create_table('flow_analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('flow_type', sa.String(length=50), nullable=False),
        sa.Column('flow_day', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('response_time_seconds', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create flow_messages table
    op.create_table('flow_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('flow_state_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('flow_day', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.String(length=100), nullable=False),
        sa.Column('personalized_content', sa.Text(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['flow_state_id'], ['flow_states.id'], ),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_flow_analytics_patient_date', 'flow_analytics', ['patient_id', 'timestamp'])
    op.create_index('idx_flow_analytics_flow_type_date', 'flow_analytics', ['flow_type', 'timestamp'])
    op.create_index('idx_flow_analytics_event_type', 'flow_analytics', ['event_type'])
    op.create_index('idx_flow_analytics_flow_day', 'flow_analytics', ['flow_day'])
    
    op.create_index('idx_flow_messages_flow_state', 'flow_messages', ['flow_state_id'])
    op.create_index('idx_flow_messages_scheduled', 'flow_messages', ['scheduled_for'])
    op.create_index('idx_flow_messages_flow_day', 'flow_messages', ['flow_state_id', 'flow_day'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_flow_messages_flow_day', table_name='flow_messages')
    op.drop_index('idx_flow_messages_scheduled', table_name='flow_messages')
    op.drop_index('idx_flow_messages_flow_state', table_name='flow_messages')
    
    op.drop_index('idx_flow_analytics_flow_day', table_name='flow_analytics')
    op.drop_index('idx_flow_analytics_event_type', table_name='flow_analytics')
    op.drop_index('idx_flow_analytics_flow_type_date', table_name='flow_analytics')
    op.drop_index('idx_flow_analytics_patient_date', table_name='flow_analytics')
    
    # Drop tables
    op.drop_table('flow_messages')
    op.drop_table('flow_analytics')