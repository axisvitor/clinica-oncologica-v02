"""Baseline production schema matching AWS RDS

This migration creates ALL tables that exist in the production database.
It serves as the definitive baseline for the database schema.

Revision ID: 20251010_010000
Revises: None
Create Date: 2025-10-10 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251010_010000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all production tables."""

    # Create ENUMs first
    op.execute("CREATE TYPE user_role AS ENUM ('admin', 'doctor')")
    op.execute("CREATE TYPE auth_provider AS ENUM ('local', 'firebase')")
    op.execute("CREATE TYPE flow_state AS ENUM ('onboarding', 'active', 'paused', 'completed', 'inactive')")
    op.execute("CREATE TYPE messagedirection AS ENUM ('inbound', 'outbound')")
    op.execute("CREATE TYPE messagetype AS ENUM ('text', 'button', 'list', 'media', 'location', 'quiz_intro', 'quiz_question', 'quiz_encouragement', 'quiz_completion', 'monthly_quiz_link', 'monthly_quiz_reminder', 'monthly_quiz_expired', 'monthly_quiz_completed')")
    op.execute("CREATE TYPE messagestatus AS ENUM ('pending', 'scheduled', 'sending', 'sent', 'delivered', 'read', 'failed', 'cancelled')")
    op.execute("CREATE TYPE deliverystatus AS ENUM ('scheduled', 'queued', 'sending', 'sent', 'delivered', 'read', 'failed', 'cancelled')")
    op.execute("CREATE TYPE alertseverity AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute("CREATE TYPE alertstatus AS ENUM ('pending', 'active', 'acknowledged', 'resolved', 'dismissed')")
    op.execute("CREATE TYPE audit_event_type AS ENUM ('login_success', 'login_failure', 'logout', 'session_created', 'session_expired', 'session_invalidated', 'token_refresh', 'access_denied', 'permission_changed', 'role_changed', 'password_changed', 'password_reset_requested', 'password_reset_completed', 'account_locked', 'account_unlocked', 'account_disabled', 'account_enabled', 'profile_updated', 'email_changed', 'suspicious_activity', 'rate_limit_exceeded', 'invalid_token', 'csrf_violation')")
    op.execute("CREATE TYPE experimentstatus AS ENUM ('draft', 'active', 'paused', 'completed', 'terminated')")
    op.execute("CREATE TYPE varianttype AS ENUM ('control', 'treatment')")
    op.execute("CREATE TYPE patientsafetylevel AS ENUM ('safe', 'restricted', 'excluded')")
    op.execute("CREATE TYPE treatmentstatus AS ENUM ('planned', 'active', 'completed', 'suspended', 'cancelled')")
    op.execute("CREATE TYPE treatmenttype AS ENUM ('quimioterapia', 'radioterapia', 'hormonioterapia', 'imunoterapia', 'cirurgia', 'outros')")
    op.execute("CREATE TYPE appointmentstatus AS ENUM ('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show')")
    op.execute("CREATE TYPE appointmenttype AS ENUM ('consultation', 'followup', 'treatment', 'exam', 'emergency', 'telemedicine')")
    op.execute("CREATE TYPE notificationtype AS ENUM ('info', 'warning', 'error', 'success', 'alert', 'reminder')")
    op.execute("CREATE TYPE notificationpriority AS ENUM ('low', 'medium', 'high', 'urgent')")
    op.execute("CREATE TYPE consenttype AS ENUM ('treatment', 'data_sharing', 'research', 'communication', 'telemedicine', 'photography', 'general')")
    op.execute("CREATE TYPE consentstatus AS ENUM ('pending', 'granted', 'denied', 'revoked', 'expired')")
    op.execute("CREATE TYPE failurereason AS ENUM ('max_retries_exceeded', 'network_error', 'api_error', 'invalid_phone', 'blocked_number', 'rate_limit', 'timeout', 'unknown')")
    op.execute("CREATE TYPE dlqstatus AS ENUM ('pending_review', 'under_review', 'approved_for_retry', 'requeued', 'permanently_failed', 'resolved')")

    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', postgresql.ENUM('admin', 'doctor', name='user_role'), nullable=False, server_default='doctor'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('firebase_uid', sa.String(255), unique=True, nullable=True, index=True),
        sa.Column('auth_provider', postgresql.ENUM('local', 'firebase', name='auth_provider'), nullable=False, server_default='local'),
        sa.Column('firebase_last_sign_in', sa.DateTime(timezone=True), nullable=True),
        sa.Column('firebase_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('firebase_email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('firebase_display_name', sa.String(255), nullable=True),
        sa.Column('firebase_photo_url', sa.String(500), nullable=True),
        sa.Column('firebase_custom_claims', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('last_firebase_sync', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 2. patients table
    op.create_table(
        'patients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('phone', sa.String(), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('treatment_type', sa.String(), nullable=True),
        sa.Column('treatment_start_date', sa.Date(), nullable=True),
        sa.Column('flow_state', postgresql.ENUM('onboarding', 'active', 'paused', 'completed', 'inactive', name='flow_state'), nullable=False, server_default='onboarding'),
        sa.Column('current_day', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cpf', sa.String(11), nullable=True, index=True),
        sa.Column('diagnosis', sa.String(500), nullable=True, index=True),
        sa.Column('treatment_phase', sa.String(100), nullable=True, index=True),
        sa.Column('doctor_notes', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 3. messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('direction', postgresql.ENUM('inbound', 'outbound', name='messagedirection'), nullable=False),
        sa.Column('type', postgresql.ENUM('text', 'button', 'list', 'media', 'location', 'quiz_intro', 'quiz_question', 'quiz_encouragement', 'quiz_completion', 'monthly_quiz_link', 'monthly_quiz_reminder', 'monthly_quiz_expired', 'monthly_quiz_completed', name='messagetype'), nullable=False, server_default='text'),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('whatsapp_id', sa.String(255), nullable=True, index=True),
        sa.Column('status', postgresql.ENUM('pending', 'scheduled', 'sending', 'sent', 'delivered', 'read', 'failed', 'cancelled', name='messagestatus'), nullable=False, server_default='pending'),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_status', postgresql.ENUM('scheduled', 'queued', 'sending', 'sent', 'delivered', 'read', 'failed', 'cancelled', name='deliverystatus'), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 4. flow_kinds table
    op.create_table(
        'flow_kinds',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('flow_type', sa.String(100), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 5. flow_template_versions table
    op.create_table(
        'flow_template_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kind_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('flow_kinds.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('messages', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('quiz_templates', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('alerts', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('changelog', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 6. patient_flow_states table
    op.create_table(
        'patient_flow_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('template_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('flow_template_versions.id'), nullable=False),
        sa.Column('current_step', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state_data', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 7. quiz_templates table
    op.create_table(
        'quiz_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('questions', postgresql.JSONB, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('name', 'version', name='uq_quiz_template_name_version'),
        sa.CheckConstraint('LENGTH(name) >= 1', name='ck_quiz_template_name_not_empty'),
        sa.CheckConstraint('LENGTH(version) >= 1', name='ck_quiz_template_version_not_empty'),
        sa.CheckConstraint('questions IS NOT NULL', name='ck_quiz_template_questions_not_null')
    )
    op.create_index('idx_quiz_template_name', 'quiz_templates', ['name'])
    op.create_index('idx_quiz_template_active', 'quiz_templates', ['is_active'])
    op.create_index('idx_quiz_template_name_active', 'quiz_templates', ['name', 'is_active'])

    # 8. quiz_sessions table
    op.create_table(
        'quiz_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quiz_template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_templates.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='started'),
        sa.Column('current_question', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_questions', sa.Integer(), nullable=True),
        sa.Column('answered_questions', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('score', sa.Numeric(5, 2), nullable=True),
        sa.Column('max_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('passed', sa.Boolean(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('current_question >= 0', name='ck_quiz_session_question_positive'),
        sa.CheckConstraint('score >= 0', name='ck_quiz_session_score_positive'),
        sa.CheckConstraint("status IN ('started', 'completed', 'cancelled')", name='ck_quiz_session_status_valid'),
        sa.CheckConstraint('started_at <= COALESCE(completed_at, NOW())', name='ck_quiz_session_timing_valid'),
        sa.CheckConstraint("(status = 'completed' AND completed_at IS NOT NULL) OR (status != 'completed')", name='ck_quiz_session_completed_timing')
    )
    op.create_index('idx_quiz_session_patient_id', 'quiz_sessions', ['patient_id'])
    op.create_index('idx_quiz_session_template_id', 'quiz_sessions', ['quiz_template_id'])
    op.create_index('idx_quiz_session_status', 'quiz_sessions', ['status'])
    op.create_index('idx_quiz_session_patient_status', 'quiz_sessions', ['patient_id', 'status'])
    op.create_index('idx_quiz_session_template_status', 'quiz_sessions', ['quiz_template_id', 'status'])
    op.create_index('idx_quiz_session_started_at', 'quiz_sessions', ['started_at'])
    op.create_index('idx_quiz_session_completed_at', 'quiz_sessions', ['completed_at'])
    op.create_index('idx_quiz_session_active', 'quiz_sessions', ['patient_id', 'quiz_template_id', 'status'])

    # Partial unique index for active sessions
    op.execute("""
        CREATE UNIQUE INDEX ix_quiz_session_active_unique
        ON quiz_sessions (patient_id, quiz_template_id)
        WHERE status = 'started'
    """)

    # 9. quiz_responses table
    op.create_table(
        'quiz_responses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quiz_template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_templates.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('quiz_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_sessions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('question_id', sa.String(100), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('response_type', sa.String(50), nullable=False),
        sa.Column('response_value', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('other_text', sa.Text(), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('quiz_session_id', 'question_id', name='uq_quiz_response_per_question_session'),
        sa.CheckConstraint('LENGTH(question_id) >= 1', name='ck_quiz_response_question_id_not_empty'),
        sa.CheckConstraint('LENGTH(question_text) >= 1', name='ck_quiz_response_question_text_not_empty'),
        sa.CheckConstraint('LENGTH(response_value) >= 1', name='ck_quiz_response_value_not_empty'),
        sa.CheckConstraint("response_type IN ('multiple_choice', 'open_text', 'scale', 'boolean', 'rating', 'yes_no', 'number', 'date', 'single_choice')", name='ck_quiz_response_type_valid')
    )
    op.create_index('idx_quiz_response_patient_id', 'quiz_responses', ['patient_id'])
    op.create_index('idx_quiz_response_template_id', 'quiz_responses', ['quiz_template_id'])
    op.create_index('idx_quiz_response_session_id', 'quiz_responses', ['quiz_session_id'])
    op.create_index('idx_quiz_response_question_id', 'quiz_responses', ['question_id'])
    op.create_index('idx_quiz_response_type', 'quiz_responses', ['response_type'])
    op.create_index('idx_quiz_response_responded_at', 'quiz_responses', ['responded_at'])
    op.create_index('idx_quiz_response_patient_template', 'quiz_responses', ['patient_id', 'quiz_template_id'])
    op.create_index('idx_quiz_response_session_question', 'quiz_responses', ['quiz_session_id', 'question_id'])

    # 10. alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('quiz_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('alert_type', sa.String(100), nullable=False),
        sa.Column('severity', postgresql.ENUM('low', 'medium', 'high', 'critical', name='alertseverity'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'active', 'acknowledged', 'resolved', 'dismissed', name='alertstatus'), nullable=False, server_default='pending'),
        sa.Column('data', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 11. medical_reports table
    op.create_table(
        'medical_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('generated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('insights', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('charts_data', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('alerts', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 12. message_status_events table
    op.create_table(
        'message_status_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, index=True),
        sa.Column('previous_status', sa.String(50), nullable=True),
        sa.Column('whatsapp_id', sa.String(255), nullable=True, index=True),
        sa.Column('whatsapp_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True, index=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('evolution_event_type', sa.String(100), nullable=True),
        sa.Column('evolution_payload', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True)
    )
    op.create_index('ix_msg_status_msg_created', 'message_status_events', ['message_id', 'created_at'])
    op.create_index('ix_msg_status_type_time', 'message_status_events', ['status', 'created_at'])
    op.create_index('ix_msg_status_error_time', 'message_status_events', ['error_code', 'created_at'])
    op.create_index('ix_msg_status_whatsapp', 'message_status_events', ['whatsapp_id', 'status'])

    # 13. evolution_webhook_events table (17 columns matching production webhook_events)
    op.create_table(
        'webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('source', sa.String(100), nullable=False, index=True),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_stack_trace', sa.Text(), nullable=True),
        sa.Column('related_message_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('related_patient_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('event_hash', sa.String(64), nullable=True, unique=True, index=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('original_event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True)
    )
    op.create_index('ix_webhook_type_processed', 'webhook_events', ['event_type', 'processed', 'created_at'])
    op.create_index('ix_webhook_retry_schedule', 'webhook_events', ['processed', 'next_retry_at'])
    op.create_index('ix_webhook_source_time', 'webhook_events', ['source', 'created_at'])
    op.create_index('ix_webhook_pending', 'webhook_events', ['processed', 'retry_count', 'created_at'])
    op.create_index('ix_webhook_related_msg', 'webhook_events', ['related_message_id', 'event_type'])
    op.create_index('ix_webhook_related_patient', 'webhook_events', ['related_patient_id', 'event_type'])

    # 14. webhook_idempotency table
    op.create_table(
        'webhook_idempotency',
        sa.Column('event_id', sa.String(255), primary_key=True, nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='processing'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payload', postgresql.JSONB, nullable=True),
        sa.Column('response_data', postgresql.JSONB, nullable=True)
    )
    op.create_index('idx_webhook_idempotency_provider_type', 'webhook_idempotency', ['provider', 'event_type'])
    op.create_index('idx_webhook_idempotency_expires_at', 'webhook_idempotency', ['expires_at'])
    op.create_index('idx_webhook_idempotency_received_at', 'webhook_idempotency', ['received_at'])
    op.create_index('idx_webhook_idempotency_status', 'webhook_idempotency', ['status'])

    # 15. audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_type', postgresql.ENUM('login_success', 'login_failure', 'logout', 'session_created', 'session_expired', 'session_invalidated', 'token_refresh', 'access_denied', 'permission_changed', 'role_changed', 'password_changed', 'password_reset_requested', 'password_reset_completed', 'account_locked', 'account_unlocked', 'account_disabled', 'account_enabled', 'profile_updated', 'email_changed', 'suspicious_activity', 'rate_limit_exceeded', 'invalid_token', 'csrf_violation', name='audit_event_type'), nullable=False, index=True),
        sa.Column('event_status', sa.String(50), nullable=False, server_default='success'),
        sa.Column('user_id', sa.String(255), nullable=True, index=True),
        sa.Column('user_email', sa.String(255), nullable=True, index=True),
        sa.Column('firebase_uid', sa.String(255), nullable=True, index=True),
        sa.Column('ip_address', postgresql.INET, nullable=True, index=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('resource', sa.String(255), nullable=True),
        sa.Column('action', sa.String(255), nullable=True),
        sa.Column('event_metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )
    op.create_index('idx_audit_user_event_time', 'audit_logs', ['user_id', 'event_type', 'created_at'])
    op.create_index('idx_audit_ip_time', 'audit_logs', ['ip_address', 'created_at'])
    op.create_index('idx_audit_event_status_time', 'audit_logs', ['event_type', 'event_status', 'created_at'])
    op.create_index('idx_audit_firebase_time', 'audit_logs', ['firebase_uid', 'created_at'])
    op.create_index('idx_audit_email_time', 'audit_logs', ['user_email', 'created_at'])

    # 16. user_sync_log table
    op.create_table(
        'user_sync_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firebase_uid', sa.String(255), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('operation', sa.String(50), nullable=False),
        sa.Column('sync_direction', sa.String(20), nullable=False),
        sa.Column('changes', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True)
    )

    # 17. flow_analytics table
    op.create_table(
        'flow_analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('flow_template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('total_messages_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_messages_received', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_interactions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_response_time_minutes', sa.Float(), nullable=True),
        sa.Column('completion_rate', sa.Float(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('quiz_completion_rate', sa.Float(), nullable=True),
        sa.Column('avg_quiz_score', sa.Float(), nullable=True),
        sa.Column('first_interaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('analytics_data', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('period', sa.String(50), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 18. flow_messages table
    op.create_table(
        'flow_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('flow_template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id'), nullable=True),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('message_type', sa.String(50), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, server_default='pending'),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 19. quiz_questions table
    op.create_table(
        'quiz_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('quiz_template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_templates.id'), nullable=False),
        sa.Column('question_text', sa.String(), nullable=False),
        sa.Column('question_type', sa.String(50), nullable=False),
        sa.Column('question_order', sa.Integer(), nullable=False),
        sa.Column('options', postgresql.JSONB, nullable=True),
        sa.Column('correct_answer', sa.String(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('is_required', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 20. ab_experiments table
    op.create_table(
        'ab_experiments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('message_template', sa.String(100), nullable=False, index=True),
        sa.Column('target_population', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('duration_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('traffic_split', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('primary_metric', sa.String(100), nullable=False, server_default='response_rate'),
        sa.Column('secondary_metrics', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('status', postgresql.ENUM('draft', 'active', 'paused', 'completed', 'terminated', name='experimentstatus'), nullable=False, server_default='draft', index=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('safety_checks_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('medical_keyword_check', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('manual_review_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('emergency_stop_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('statistical_config', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('encrypted_config', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=False, server_default='system'),
        sa.Column('started_by', sa.String(255), nullable=True),
        sa.Column('terminated_by', sa.String(255), nullable=True),
        sa.Column('termination_reason', sa.Text(), nullable=True),
        sa.Column('terminated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_participants', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('control_participants', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('treatment_participants', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('results', postgresql.JSONB, nullable=True),
        sa.Column('is_statistically_significant', sa.Boolean(), nullable=True),
        sa.Column('winner', sa.String(50), nullable=True),
        sa.Column('effect_size', sa.Float(), nullable=True),
        sa.Column('p_value', sa.Float(), nullable=True),
        sa.Column('confidence_interval', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 21. ab_variant_assignments table
    op.create_table(
        'ab_variant_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ab_experiments.id'), nullable=False, index=True),
        sa.Column('anonymous_patient_id', sa.String(32), nullable=False, index=True),
        sa.Column('variant', postgresql.ENUM('control', 'treatment', name='varianttype'), nullable=False, index=True),
        sa.Column('safety_level', postgresql.ENUM('safe', 'restricted', 'excluded', name='patientsafetylevel'), nullable=False, index=True),
        sa.Column('assignment_hash', sa.String(64), nullable=False, index=True),
        sa.Column('assignment_reason', sa.String(100), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )
    op.create_index('ix_ab_variant_exp_patient', 'ab_variant_assignments', ['experiment_id', 'anonymous_patient_id'], unique=True)
    op.create_index('ix_ab_variant_exp_variant', 'ab_variant_assignments', ['experiment_id', 'variant'])
    op.create_index('ix_ab_variant_safety', 'ab_variant_assignments', ['safety_level', 'variant'])

    # 22. ab_experiment_metrics table
    op.create_table(
        'ab_experiment_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ab_experiments.id'), nullable=False, index=True),
        sa.Column('message_id', sa.Integer(), nullable=True, index=True),
        sa.Column('anonymous_patient_id', sa.String(32), nullable=False, index=True),
        sa.Column('variant', postgresql.ENUM('control', 'treatment', name='varianttype'), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('response_time_seconds', sa.Float(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('event_data', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('included_in_analysis', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('exclusion_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )
    op.create_index('ix_ab_metrics_exp_variant', 'ab_experiment_metrics', ['experiment_id', 'variant'])
    op.create_index('ix_ab_metrics_event_time', 'ab_experiment_metrics', ['event_type', 'event_timestamp'])
    op.create_index('ix_ab_metrics_patient_event', 'ab_experiment_metrics', ['anonymous_patient_id', 'event_type'])
    op.create_index('ix_ab_metrics_analysis', 'ab_experiment_metrics', ['experiment_id', 'included_in_analysis', 'processed'])

    # 23. ab_experiment_results table
    op.create_table(
        'ab_experiment_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ab_experiments.id'), nullable=False, unique=True, index=True),
        sa.Column('analysis_timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('analysis_version', sa.String(50), nullable=False, server_default='1.0'),
        sa.Column('analyst_id', sa.String(255), nullable=True),
        sa.Column('control_sample_size', sa.Integer(), nullable=False),
        sa.Column('treatment_sample_size', sa.Integer(), nullable=False),
        sa.Column('total_sample_size', sa.Integer(), nullable=False),
        sa.Column('primary_metric_name', sa.String(100), nullable=False),
        sa.Column('control_primary_value', sa.Float(), nullable=False),
        sa.Column('treatment_primary_value', sa.Float(), nullable=False),
        sa.Column('primary_metric_difference', sa.Float(), nullable=False),
        sa.Column('primary_metric_relative_change', sa.Float(), nullable=False),
        sa.Column('statistical_test_type', sa.String(100), nullable=False),
        sa.Column('p_value', sa.Float(), nullable=False, index=True),
        sa.Column('alpha', sa.Float(), nullable=False, server_default='0.05'),
        sa.Column('is_statistically_significant', sa.Boolean(), nullable=False, index=True),
        sa.Column('cohens_d', sa.Float(), nullable=True),
        sa.Column('effect_size_magnitude', sa.String(50), nullable=True),
        sa.Column('confidence_level', sa.Float(), nullable=False, server_default='0.95'),
        sa.Column('ci_lower_bound', sa.Float(), nullable=True),
        sa.Column('ci_upper_bound', sa.Float(), nullable=True),
        sa.Column('ci_margin_of_error', sa.Float(), nullable=True),
        sa.Column('winner', sa.String(50), nullable=True, index=True),
        sa.Column('winner_confidence', sa.Float(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('secondary_metrics_results', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('detailed_results', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('variant_performance', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('data_quality_score', sa.Float(), nullable=True),
        sa.Column('anomalies_detected', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('quality_warnings', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('projected_impact', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('cost_benefit_analysis', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 24. ab_experiment_audit table
    op.create_table(
        'ab_experiment_audit',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ab_experiments.id'), nullable=False, index=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('actor', sa.String(255), nullable=False),
        sa.Column('actor_type', sa.String(50), nullable=False, server_default='user'),
        sa.Column('action_details', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('previous_state', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('new_state', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('hipaa_logged', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('gdpr_compliant', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 25. ab_experiment_monitoring table
    op.create_table(
        'ab_experiment_monitoring',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ab_experiments.id'), nullable=False, index=True),
        sa.Column('check_timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('check_type', sa.String(100), nullable=False, index=True),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('threshold_exceeded', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('alert_triggered', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('alert_message', sa.Text(), nullable=True),
        sa.Column('monitoring_data', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 26. treatments table
    op.create_table(
        'treatments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('treatment_type', postgresql.ENUM('quimioterapia', 'radioterapia', 'hormonioterapia', 'imunoterapia', 'cirurgia', 'outros', name='treatmenttype'), nullable=False, index=True),
        sa.Column('status', postgresql.ENUM('planned', 'active', 'completed', 'suspended', 'cancelled', name='treatmentstatus'), nullable=False, server_default='planned', index=True),
        sa.Column('start_date', sa.Date(), nullable=True, index=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('planned_sessions', sa.String(100), nullable=True),
        sa.Column('completed_sessions', sa.String(100), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('protocol', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 27. appointments table
    op.create_table(
        'appointments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('practitioner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('appointment_type', postgresql.ENUM('consultation', 'followup', 'treatment', 'exam', 'emergency', 'telemedicine', name='appointmenttype'), nullable=False, index=True),
        sa.Column('status', postgresql.ENUM('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show', name='appointmentstatus'), nullable=False, server_default='scheduled', index=True),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actual_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('reminder_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('confirmation_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 28. medications table
    op.create_table(
        'medications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('prescribed_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('treatment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('treatments.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('active_ingredient', sa.String(200), nullable=True),
        sa.Column('dosage', sa.String(100), nullable=False),
        sa.Column('frequency', sa.String(100), nullable=False),
        sa.Column('route', sa.String(50), nullable=True),
        sa.Column('prescription_date', sa.Date(), nullable=False, index=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('quantity', sa.Numeric(10, 2), nullable=True),
        sa.Column('refills_allowed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('refills_remaining', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('warnings', sa.Text(), nullable=True),
        sa.Column('side_effects', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('discontinued_date', sa.Date(), nullable=True),
        sa.Column('discontinuation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 29. notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('related_patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('notification_type', postgresql.ENUM('info', 'warning', 'error', 'success', 'alert', 'reminder', name='notificationtype'), nullable=False, index=True),
        sa.Column('priority', postgresql.ENUM('low', 'medium', 'high', 'urgent', name='notificationpriority'), nullable=False, server_default='medium', index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('action_url', sa.String(500), nullable=True),
        sa.Column('action_label', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 30. sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_token', sa.String(500), nullable=False, unique=True, index=True),
        sa.Column('refresh_token', sa.String(500), nullable=True, unique=True, index=True),
        sa.Column('device_id', sa.String(200), nullable=True, index=True),
        sa.Column('device_name', sa.String(200), nullable=True),
        sa.Column('device_type', sa.String(50), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('location', postgresql.JSONB, nullable=True),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('is_suspicious', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('risk_score', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 31. consents table
    op.create_table(
        'consents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('consented_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('consent_type', postgresql.ENUM('treatment', 'data_sharing', 'research', 'communication', 'telemedicine', 'photography', 'general', name='consenttype'), nullable=False, index=True),
        sa.Column('status', postgresql.ENUM('pending', 'granted', 'denied', 'revoked', 'expired', name='consentstatus'), nullable=False, server_default='pending', index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('legal_text', sa.Text(), nullable=True),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('version', sa.String(20), nullable=True),
        sa.Column('previous_consent_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('signature_data', postgresql.JSONB, nullable=True),
        sa.Column('witness_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 32. whatsapp_delivery_failures (DLQ/Failed Messages) table
    op.create_table(
        'whatsapp_delivery_failures',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('original_message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('whatsapp_phone', sa.String(20), nullable=False, index=True),
        sa.Column('failure_reason', postgresql.ENUM('max_retries_exceeded', 'network_error', 'api_error', 'invalid_phone', 'blocked_number', 'rate_limit', 'timeout', 'unknown', name='failurereason'), nullable=False, index=True),
        sa.Column('failure_details', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=False),
        sa.Column('dlq_status', postgresql.ENUM('pending_review', 'under_review', 'approved_for_retry', 'requeued', 'permanently_failed', 'resolved', name='dlqstatus'), nullable=False, server_default='pending_review', index=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('requeue_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_requeue_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )

    # 33. alembic_version table (Alembic creates this automatically, but including for completeness)
    # This table is managed by Alembic itself


def downgrade() -> None:
    """Drop all production tables."""

    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_table('whatsapp_delivery_failures')
    op.drop_table('consents')
    op.drop_table('sessions')
    op.drop_table('notifications')
    op.drop_table('medications')
    op.drop_table('appointments')
    op.drop_table('treatments')
    op.drop_table('ab_experiment_monitoring')
    op.drop_table('ab_experiment_audit')
    op.drop_table('ab_experiment_results')
    op.drop_table('ab_experiment_metrics')
    op.drop_table('ab_variant_assignments')
    op.drop_table('ab_experiments')
    op.drop_table('quiz_questions')
    op.drop_table('flow_messages')
    op.drop_table('flow_analytics')
    op.drop_table('user_sync_log')
    op.drop_table('audit_logs')
    op.drop_table('webhook_idempotency')
    op.drop_table('webhook_events')
    op.drop_table('message_status_events')
    op.drop_table('medical_reports')
    op.drop_table('alerts')
    op.drop_table('quiz_responses')
    op.drop_table('quiz_sessions')
    op.drop_table('quiz_templates')
    op.drop_table('patient_flow_states')
    op.drop_table('flow_template_versions')
    op.drop_table('flow_kinds')
    op.drop_table('messages')
    op.drop_table('patients')
    op.drop_table('users')

    # Drop ENUMs
    op.execute("DROP TYPE IF EXISTS dlqstatus")
    op.execute("DROP TYPE IF EXISTS failurereason")
    op.execute("DROP TYPE IF EXISTS consentstatus")
    op.execute("DROP TYPE IF EXISTS consenttype")
    op.execute("DROP TYPE IF EXISTS notificationpriority")
    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS appointmenttype")
    op.execute("DROP TYPE IF EXISTS appointmentstatus")
    op.execute("DROP TYPE IF EXISTS treatmenttype")
    op.execute("DROP TYPE IF EXISTS treatmentstatus")
    op.execute("DROP TYPE IF EXISTS patientsafetylevel")
    op.execute("DROP TYPE IF EXISTS varianttype")
    op.execute("DROP TYPE IF EXISTS experimentstatus")
    op.execute("DROP TYPE IF EXISTS audit_event_type")
    op.execute("DROP TYPE IF EXISTS alertstatus")
    op.execute("DROP TYPE IF EXISTS alertseverity")
    op.execute("DROP TYPE IF EXISTS deliverystatus")
    op.execute("DROP TYPE IF EXISTS messagestatus")
    op.execute("DROP TYPE IF EXISTS messagetype")
    op.execute("DROP TYPE IF EXISTS messagedirection")
    op.execute("DROP TYPE IF EXISTS flow_state")
    op.execute("DROP TYPE IF EXISTS auth_provider")
    op.execute("DROP TYPE IF EXISTS user_role")
