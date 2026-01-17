"""add_message_archives_table

Revision ID: a1b2c3d4e5f6
Revises: e8c29fcb2be8
Create Date: 2026-01-25 10:00:00.000000


WHY:
- Not recorded (legacy migration).

WHAT:
- Not recorded (legacy migration).

IMPACT:
- Not recorded (legacy migration).

BENCHMARK:
- Not recorded (legacy migration).

ROLLBACK:
- Not recorded (legacy migration).

RELATED:
- Not recorded (legacy migration).

MIGRATION TYPE:
- Not recorded (legacy migration).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e8c29fcb2be8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('message_archives',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('original_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('direction', sa.Enum('INBOUND', 'OUTBOUND', name='message_direction'), nullable=False),
        sa.Column('type', sa.Enum('TEXT', 'IMAGE', 'AUDIO', 'VIDEO', 'DOCUMENT', 'BUTTON', 'LIST', 'MEDIA', 'LOCATION', 'QUIZ_INTRO', 'QUIZ_QUESTION', 'QUIZ_ENCOURAGEMENT', 'QUIZ_COMPLETION', 'MONTHLY_QUIZ_LINK', 'MONTHLY_QUIZ_REMINDER', 'MONTHLY_QUIZ_EXPIRED', 'MONTHLY_QUIZ_COMPLETED', name='messagetype'), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('message_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('priority', sa.Enum('CRITICAL', 'HIGH', 'NORMAL', 'LOW', name='message_priority'), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('whatsapp_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED', 'SCHEDULED', 'SENDING', 'CANCELLED', name='message_status'), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_status', sa.Enum('SCHEDULED', 'QUEUED', 'SENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED', 'CANCELLED', name='message_delivery_status'), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_message_archives_id'), 'message_archives', ['id'], unique=False)
    op.create_index(op.f('ix_message_archives_original_id'), 'message_archives', ['original_id'], unique=False)
    op.create_index(op.f('ix_message_archives_patient_id'), 'message_archives', ['patient_id'], unique=False)
    op.create_index(op.f('ix_message_archives_whatsapp_id'), 'message_archives', ['whatsapp_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_message_archives_whatsapp_id'), table_name='message_archives')
    op.drop_index(op.f('ix_message_archives_patient_id'), table_name='message_archives')
    op.drop_index(op.f('ix_message_archives_original_id'), table_name='message_archives')
    op.drop_index(op.f('ix_message_archives_id'), table_name='message_archives')
    op.drop_table('message_archives')
