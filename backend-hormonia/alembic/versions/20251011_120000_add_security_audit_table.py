"""Add security audit table for WhatsApp access monitoring

Revision ID: 20251011_120000
Revises: 20251010_010000
Create Date: 2025-10-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251011_120000'
down_revision = '20251010_010000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create security audit table and indexes."""

    # Create security audit log table
    op.create_table(
        'security_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False, index=True,
                  comment='Type of security event (unauthorized_whatsapp_access, authorized_whatsapp_access, phone_blocked, etc.)'),
        sa.Column('phone_number', sa.String(20), nullable=False, index=True,
                  comment='Phone number involved in the security event'),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=True, index=True,
                  comment='Patient ID if access was authorized'),
        sa.Column('message_content', sa.Text, nullable=True,
                  comment='Message content (truncated to 500 chars for analysis)'),
        sa.Column('source_metadata', postgresql.JSONB, nullable=True,
                  comment='Source metadata (WhatsApp ID, timestamp, etc.)'),
        sa.Column('risk_score', sa.Integer, nullable=False, default=0, index=True,
                  comment='Risk score from 0-10 based on analysis'),
        sa.Column('ip_address', sa.String(45), nullable=True, index=True,
                  comment='IP address if available'),
        sa.Column('user_agent', sa.String(500), nullable=True,
                  comment='User agent if available'),
        sa.Column('session_id', sa.String(32), nullable=True, index=True,
                  comment='Session ID for grouping related events'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP'), index=True,
                  comment='When the security event occurred'),
        sa.Column('additional_data', postgresql.JSONB, nullable=True,
                  comment='Additional context data for analysis'),
        sa.Column('alert_sent', sa.Boolean, nullable=False, default=False,
                  comment='Whether security alert was sent for this event'),
        comment='Security audit log for WhatsApp access monitoring and threat detection'
    )

    # Create composite indexes for efficient queries
    op.create_index(
        'idx_security_audit_phone_event_time',
        'security_audit_log',
        ['phone_number', 'event_type', 'created_at']
    )

    op.create_index(
        'idx_security_audit_risk_time',
        'security_audit_log',
        ['risk_score', 'created_at'],
        postgresql_where=sa.text('risk_score > 5')  # Only index high-risk events
    )

    op.create_index(
        'idx_security_audit_patient_time',
        'security_audit_log',
        ['patient_id', 'created_at'],
        postgresql_where=sa.text('patient_id IS NOT NULL')  # Only authorized accesses
    )

    op.create_index(
        'idx_security_audit_session',
        'security_audit_log',
        ['session_id', 'created_at'],
        postgresql_where=sa.text('session_id IS NOT NULL')
    )

    # Add foreign key constraint to patients table
    op.create_foreign_key(
        'fk_security_audit_patient',
        'security_audit_log', 'patients',
        ['patient_id'], ['id'],
        ondelete='SET NULL'
    )

    # Create partial index for unauthorized attempts (performance optimization)
    op.create_index(
        'idx_security_audit_unauthorized_access',
        'security_audit_log',
        ['phone_number', 'created_at'],
        postgresql_where=sa.text("event_type = 'unauthorized_whatsapp_access'")
    )

    # Create GIN index for JSON searching in metadata fields
    op.create_index(
        'idx_security_audit_source_metadata_gin',
        'security_audit_log',
        ['source_metadata'],
        postgresql_using='gin'
    )

    op.create_index(
        'idx_security_audit_additional_data_gin',
        'security_audit_log',
        ['additional_data'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    """Drop security audit table and all related indexes."""

    # Drop the table (this will automatically drop all indexes)
    op.drop_table('security_audit_log')