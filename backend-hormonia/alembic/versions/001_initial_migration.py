"""Initial migration - sync with Supabase

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE user_role AS ENUM ('doctor', 'admin')")
    op.execute("CREATE TYPE flow_state AS ENUM ('onboarding', 'active', 'paused', 'completed', 'inactive')")
    op.execute("CREATE TYPE message_direction AS ENUM ('inbound', 'outbound')")
    op.execute("CREATE TYPE message_type AS ENUM ('text', 'button', 'list', 'media', 'location')")
    op.execute("CREATE TYPE message_status AS ENUM ('pending', 'sent', 'delivered', 'read', 'failed')")
    op.execute("CREATE TYPE alert_severity AS ENUM ('low', 'medium', 'high', 'critical')")
    
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', postgresql.ENUM('doctor', 'nurse', 'admin', name='user_role'), nullable=False, server_default='doctor'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Create patients table
    op.create_table('patients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('treatment_type', sa.String(100), nullable=True),
        sa.Column('treatment_start_date', sa.Date(), nullable=True),
        sa.Column('flow_state', postgresql.ENUM('onboarding', 'active', 'paused', 'completed', 'inactive', name='flow_state'), nullable=False, server_default='onboarding'),
        sa.Column('current_day', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('patient_metadata', postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Create messages table
    op.create_table('messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('direction', postgresql.ENUM('inbound', 'outbound', name='message_direction'), nullable=False),
        sa.Column('type', postgresql.ENUM('text', 'button', 'list', 'media', 'location', name='message_type'), nullable=False, server_default='text'),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('message_metadata', postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column('whatsapp_id', sa.String(255), nullable=True, index=True),
        sa.Column('status', postgresql.ENUM('pending', 'sent', 'delivered', 'read', 'failed', name='message_status'), nullable=False, server_default='pending'),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Create flow_states table
    op.create_table('flow_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('flow_type', sa.String(50), nullable=False),
        sa.Column('current_step', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state_data', postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Create quiz_templates table
    op.create_table('quiz_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('questions', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Create quiz_responses table
    op.create_table('quiz_responses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('quiz_template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_templates.id'), nullable=False),
        sa.Column('question_id', sa.String(100), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('response_type', sa.String(50), nullable=False),
        sa.Column('response_value', sa.Text(), nullable=False),
        sa.Column('response_metadata', postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Create medical_reports table
    op.create_table('medical_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('generated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('insights', postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column('charts_data', postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column('alerts', postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Create alerts table
    op.create_table('alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('severity', postgresql.ENUM('low', 'medium', 'high', 'critical', name='alert_severity'), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Create indexes
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])
    
    op.create_index('idx_patients_doctor_id', 'patients', ['doctor_id'])
    op.create_index('idx_patients_flow_state', 'patients', ['flow_state'])
    op.create_index('idx_patients_treatment_type', 'patients', ['treatment_type'])
    
    op.create_index('idx_messages_patient_id', 'messages', ['patient_id'])
    op.create_index('idx_messages_status', 'messages', ['status'])
    op.create_index('idx_messages_direction', 'messages', ['direction'])
    op.create_index('idx_messages_scheduled_for', 'messages', ['scheduled_for'])
    
    op.create_index('idx_flow_states_patient_id', 'flow_states', ['patient_id'])
    op.create_index('idx_flow_states_flow_type', 'flow_states', ['flow_type'])
    
    op.create_index('idx_quiz_templates_is_active', 'quiz_templates', ['is_active'])
    
    op.create_index('idx_quiz_responses_patient_id', 'quiz_responses', ['patient_id'])
    op.create_index('idx_quiz_responses_quiz_template_id', 'quiz_responses', ['quiz_template_id'])
    op.create_index('idx_quiz_responses_responded_at', 'quiz_responses', ['responded_at'])
    
    op.create_index('idx_medical_reports_patient_id', 'medical_reports', ['patient_id'])
    op.create_index('idx_medical_reports_generated_by', 'medical_reports', ['generated_by'])
    op.create_index('idx_medical_reports_period', 'medical_reports', ['period_start', 'period_end'])
    
    op.create_index('idx_alerts_patient_id', 'alerts', ['patient_id'])
    op.create_index('idx_alerts_severity', 'alerts', ['severity'])
    op.create_index('idx_alerts_acknowledged', 'alerts', ['acknowledged'])
    op.create_index('idx_alerts_type', 'alerts', ['type'])
    
    # Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Create triggers for updated_at columns
    op.execute("CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    op.execute("CREATE TRIGGER update_patients_updated_at BEFORE UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    op.execute("CREATE TRIGGER update_messages_updated_at BEFORE UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    op.execute("CREATE TRIGGER update_flow_states_updated_at BEFORE UPDATE ON flow_states FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    op.execute("CREATE TRIGGER update_quiz_templates_updated_at BEFORE UPDATE ON quiz_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    op.execute("CREATE TRIGGER update_quiz_responses_updated_at BEFORE UPDATE ON quiz_responses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    op.execute("CREATE TRIGGER update_medical_reports_updated_at BEFORE UPDATE ON medical_reports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    op.execute("CREATE TRIGGER update_alerts_updated_at BEFORE UPDATE ON alerts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")


def downgrade() -> None:
    # Drop all tables in reverse order of dependencies
    op.drop_table('alerts')
    op.drop_table('medical_reports')
    op.drop_table('quiz_responses')
    op.drop_table('quiz_templates')
    op.drop_table('flow_states')
    op.drop_table('messages')
    op.drop_table('patients')
    op.drop_table('users')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS alert_severity CASCADE')
    op.execute('DROP TYPE IF EXISTS message_status CASCADE')
    op.execute('DROP TYPE IF EXISTS message_type CASCADE')
    op.execute('DROP TYPE IF EXISTS message_direction CASCADE')
    op.execute('DROP TYPE IF EXISTS flow_state CASCADE')
    op.execute('DROP TYPE IF EXISTS user_role CASCADE')