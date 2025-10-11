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
    """Create security audit table and indexes with error handling."""

    # Create security audit log table
    op.create_table(
        'security_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_type', sa.String(100), nullable=False,
                  comment='Type of security event (unauthorized_whatsapp_access, authorized_whatsapp_access, phone_blocked, etc.)'),
        sa.Column('phone_number', sa.String(20), nullable=False,
                  comment='Phone number involved in the security event'),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='Patient ID if access was authorized'),
        sa.Column('message_content', sa.Text, nullable=True,
                  comment='Message content (truncated to 500 chars for analysis)'),
        sa.Column('source_metadata', postgresql.JSONB, nullable=True,
                  comment='Source metadata (WhatsApp ID, timestamp, etc.)'),
        sa.Column('risk_score', sa.Integer, nullable=False, server_default=sa.text('0'),
                  comment='Risk score from 0-10 based on analysis'),
        sa.Column('ip_address', sa.String(45), nullable=True,
                  comment='IP address if available'),
        sa.Column('user_agent', sa.String(500), nullable=True,
                  comment='User agent if available'),
        sa.Column('session_id', sa.String(32), nullable=True,
                  comment='Session ID for grouping related events'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP'),
                  comment='When the security event occurred'),
        sa.Column('additional_data', postgresql.JSONB, nullable=True,
                  comment='Additional context data for analysis'),
        sa.Column('alert_sent', sa.Boolean, nullable=False, server_default=sa.text('false'),
                  comment='Whether security alert was sent for this event'),
        comment='Security audit log for WhatsApp access monitoring and threat detection'
    )

    # Create basic indexes first
    op.create_index('idx_security_audit_event_type', 'security_audit_log', ['event_type'])
    op.create_index('idx_security_audit_phone_number', 'security_audit_log', ['phone_number'])
    op.create_index('idx_security_audit_patient_id', 'security_audit_log', ['patient_id'])
    op.create_index('idx_security_audit_risk_score', 'security_audit_log', ['risk_score'])
    op.create_index('idx_security_audit_created_at', 'security_audit_log', ['created_at'])
    op.create_index('idx_security_audit_session_id', 'security_audit_log', ['session_id'])
    op.create_index('idx_security_audit_ip_address', 'security_audit_log', ['ip_address'])

    # Create composite indexes
    op.create_index(
        'idx_security_audit_phone_event_time',
        'security_audit_log',
        ['phone_number', 'event_type', 'created_at']
    )

    op.create_index(
        'idx_security_audit_risk_time',
        'security_audit_log',
        ['risk_score', 'created_at']
    )

    # Try to add foreign key constraint if patients table exists
    connection = op.get_bind()
    try:
        # Check if patients table exists
        result = connection.execute(sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'patients'
            );
        """))
        
        if result.scalar():
            op.create_foreign_key(
                'fk_security_audit_patient',
                'security_audit_log', 'patients',
                ['patient_id'], ['id'],
                ondelete='SET NULL'
            )
            print("✅ Foreign key constraint to patients table created successfully")
        else:
            print("⚠️ Patients table not found, skipping foreign key constraint")
    except Exception as e:
        print(f"⚠️ Could not create foreign key constraint: {e}")

    # Create GIN indexes for JSONB columns
    try:
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
        print("✅ GIN indexes for JSONB columns created successfully")
    except Exception as e:
        print(f"⚠️ Could not create GIN indexes: {e}")

    print("✅ Security audit table migration completed successfully")


def downgrade() -> None:
    """Drop security audit table and all related indexes."""
    
    # Drop the table (this will automatically drop all indexes and constraints)
    op.drop_table('security_audit_log')
    print("✅ Security audit table dropped successfully")