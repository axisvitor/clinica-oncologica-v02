"""Add composite indexes for query performance optimization

Revision ID: 035_composite_indexes
Revises: 034_flow_states_active_idx
Create Date: 2025-09-29 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '035_composite_indexes'
down_revision = '034_flow_states_active_idx'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add composite indexes for frequently joined queries and
    complex WHERE clauses to improve query performance.
    """

    # Message-Patient composite indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_patient_direction_status
        ON messages(patient_id, direction, status)
        WHERE status != 'failed';
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_patient_created
        ON messages(patient_id, created_at DESC);
    """)

    # Quiz session-patient composite indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_quiz_sessions_patient_completed
        ON quiz_sessions(patient_id, is_completed, created_at DESC);
    """)

    # Quiz response analytics index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_quiz_responses_patient_template_date
        ON quiz_responses(patient_id, quiz_template_id, responded_at DESC);
    """)

    # Alert management indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_patient_severity_status
        ON alerts(patient_id, severity, status)
        WHERE status IN ('pending', 'active');
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_status_created
        ON alerts(status, created_at DESC)
        WHERE status != 'resolved';
    """)

    # Flow state tracking indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patient_flow_states_template_patient
        ON patient_flow_states(template_version_id, patient_id, started_at DESC);
    """)

    # Medical reports indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_medical_reports_patient_period
        ON medical_reports(patient_id, period_start, period_end);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_medical_reports_doctor_created
        ON medical_reports(generated_by, created_at DESC);
    """)

    # A/B testing composite indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiments_status_dates
        ON ab_experiments(status, start_date, end_date)
        WHERE status IN ('active', 'paused');
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_variant_assignments_exp_variant_assigned
        ON ab_variant_assignments(experiment_id, variant, assigned_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_metrics_exp_variant_event
        ON ab_experiment_metrics(experiment_id, variant, event_type, event_timestamp)
        WHERE included_in_analysis = true;
    """)

    # Webhook event processing indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_webhook_events_processed_retry
        ON webhook_events(processed, retry_count, next_retry_at)
        WHERE processed = false AND retry_count < max_retries;
    """)

    # Message status event tracking
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_msg_status_events_msg_status_time
        ON message_status_events(message_id, status, created_at DESC);
    """)

    # Flow analytics composite indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_flow_analytics_patient_type_time
        ON flow_analytics(patient_id, flow_type, timestamp DESC);
    """)

    # Add table comments for documentation
    op.execute("""
        COMMENT ON INDEX idx_messages_patient_direction_status IS
        'Optimizes message history queries filtered by direction and status';
    """)

    op.execute("""
        COMMENT ON INDEX idx_alerts_patient_severity_status IS
        'Optimizes active alert queries for patient dashboard';
    """)


def downgrade():
    """
    Drop all composite indexes created in upgrade.
    """
    op.execute("DROP INDEX IF EXISTS idx_flow_analytics_patient_type_time;")
    op.execute("DROP INDEX IF EXISTS idx_msg_status_events_msg_status_time;")
    op.execute("DROP INDEX IF EXISTS idx_webhook_events_processed_retry;")
    op.execute("DROP INDEX IF EXISTS idx_ab_metrics_exp_variant_event;")
    op.execute("DROP INDEX IF EXISTS idx_ab_variant_assignments_exp_variant_assigned;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiments_status_dates;")
    op.execute("DROP INDEX IF EXISTS idx_medical_reports_doctor_created;")
    op.execute("DROP INDEX IF EXISTS idx_medical_reports_patient_period;")
    op.execute("DROP INDEX IF EXISTS idx_patient_flow_states_template_patient;")
    op.execute("DROP INDEX IF EXISTS idx_alerts_status_created;")
    op.execute("DROP INDEX IF EXISTS idx_alerts_patient_severity_status;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_responses_patient_template_date;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_sessions_patient_completed;")
    op.execute("DROP INDEX IF EXISTS idx_messages_patient_created;")
    op.execute("DROP INDEX IF EXISTS idx_messages_patient_direction_status;")