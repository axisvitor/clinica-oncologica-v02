"""Add GIN indexes on JSONB columns for fast metadata searches

Revision ID: 038_jsonb_indexes
Revises: 037_triggers
Create Date: 2025-09-29 21:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '038_jsonb_indexes'
down_revision = '037_triggers'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add GIN (Generalized Inverted Index) indexes on JSONB columns
    to enable fast containment queries and metadata searches.

    GIN indexes are essential for:
    - @> (contains) operator
    - ? (key exists) operator
    - ?| (any key exists) operator
    - ?& (all keys exist) operator
    """

    # Patient metadata GIN index for flexible querying
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_metadata_gin
        ON patients USING GIN (metadata jsonb_path_ops);
    """)

    # Message metadata GIN index for button data, media URLs, etc.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_metadata_gin
        ON messages USING GIN (message_metadata jsonb_path_ops);
    """)

    # Patient flow state data GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patient_flow_states_state_data_gin
        ON patient_flow_states USING GIN (state_data jsonb_path_ops);
    """)

    # Quiz template questions GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_quiz_templates_questions_gin
        ON quiz_templates USING GIN (questions jsonb_path_ops);
    """)

    # Quiz response metadata GIN index (for sentiment analysis, entities)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_quiz_responses_metadata_gin
        ON quiz_responses USING GIN (response_metadata jsonb_path_ops);
    """)

    # Quiz session metadata GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_quiz_sessions_metadata_gin
        ON quiz_sessions USING GIN (session_metadata jsonb_path_ops);
    """)

    # Flow analytics event data GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_flow_analytics_analytics_data_gin
        ON flow_analytics USING GIN (analytics_data jsonb_path_ops);
    """)

    # Flow template version data GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_flow_template_versions_data_gin
        ON flow_template_versions USING GIN (template_data jsonb_path_ops);
    """)

    # Alert data GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_data_gin
        ON alerts USING GIN (data jsonb_path_ops);
    """)

    # Medical report insights and charts GIN indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_medical_reports_insights_gin
        ON medical_reports USING GIN (insights jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_medical_reports_charts_gin
        ON medical_reports USING GIN (charts_data jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_medical_reports_alerts_gin
        ON medical_reports USING GIN (alerts jsonb_path_ops);
    """)

    # A/B testing JSONB GIN indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiments_target_population_gin
        ON ab_experiments USING GIN (target_population jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiments_statistical_config_gin
        ON ab_experiments USING GIN (statistical_config jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiments_results_gin
        ON ab_experiments USING GIN (results jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiment_metrics_event_data_gin
        ON ab_experiment_metrics USING GIN (event_data jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiment_results_secondary_gin
        ON ab_experiment_results USING GIN (secondary_metrics_results jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiment_results_detailed_gin
        ON ab_experiment_results USING GIN (detailed_results jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiment_audit_action_details_gin
        ON ab_experiment_audit USING GIN (action_details jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_experiment_monitoring_data_gin
        ON ab_experiment_monitoring USING GIN (monitoring_data jsonb_path_ops);
    """)

    # Webhook event payload GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_webhook_events_payload_gin
        ON webhook_events USING GIN (payload jsonb_path_ops);
    """)

    # Message status event metadata GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_message_status_events_metadata_gin
        ON message_status_events USING GIN (metadata jsonb_path_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_message_status_events_evolution_payload_gin
        ON message_status_events USING GIN (evolution_payload jsonb_path_ops);
    """)

    # Add documentation comments
    op.execute("""
        COMMENT ON INDEX idx_patients_metadata_gin IS
        'GIN index for fast containment queries on patient metadata (diagnosis, treatment_phase, etc.)';
    """)

    op.execute("""
        COMMENT ON INDEX idx_ab_experiment_results_detailed_gin IS
        'Enables fast queries on A/B test results by metric names and values';
    """)

    op.execute("""
        COMMENT ON INDEX idx_webhook_events_payload_gin IS
        'Enables fast searches for specific webhook event types and content';
    """)

    # Create helper view for common JSONB queries
    op.execute("""
        CREATE OR REPLACE VIEW v_patients_with_diagnosis AS
        SELECT
            p.id,
            p.name,
            p.phone,
            p.diagnosis,
            p.treatment_phase,
            p.metadata->>'diagnosis' as metadata_diagnosis,
            p.metadata->>'treatment_phase' as metadata_treatment_phase
        FROM patients p
        WHERE p.diagnosis IS NOT NULL OR p.metadata ? 'diagnosis';

        COMMENT ON VIEW v_patients_with_diagnosis IS
        'Combines dedicated diagnosis column with metadata fallback for backward compatibility';
    """)


def downgrade():
    """
    Drop all GIN indexes and helper views created in upgrade.
    """
    # Drop helper view
    op.execute("DROP VIEW IF EXISTS v_patients_with_diagnosis;")

    # Drop GIN indexes
    op.execute("DROP INDEX IF EXISTS idx_message_status_events_evolution_payload_gin;")
    op.execute("DROP INDEX IF EXISTS idx_message_status_events_metadata_gin;")
    op.execute("DROP INDEX IF EXISTS idx_webhook_events_payload_gin;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiment_monitoring_data_gin;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiment_audit_action_details_gin;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiment_results_detailed_gin;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiment_results_secondary_gin;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiment_metrics_event_data_gin;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiments_results_gin;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiments_statistical_config_gin;")
    op.execute("DROP INDEX IF EXISTS idx_ab_experiments_target_population_gin;")
    op.execute("DROP INDEX IF EXISTS idx_medical_reports_alerts_gin;")
    op.execute("DROP INDEX IF EXISTS idx_medical_reports_charts_gin;")
    op.execute("DROP INDEX IF EXISTS idx_medical_reports_insights_gin;")
    op.execute("DROP INDEX IF EXISTS idx_alerts_data_gin;")
    op.execute("DROP INDEX IF EXISTS idx_flow_template_versions_data_gin;")
    op.execute("DROP INDEX IF EXISTS idx_flow_analytics_analytics_data_gin;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_sessions_metadata_gin;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_responses_metadata_gin;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_templates_questions_gin;")
    op.execute("DROP INDEX IF EXISTS idx_patient_flow_states_state_data_gin;")
    op.execute("DROP INDEX IF EXISTS idx_messages_metadata_gin;")
    op.execute("DROP INDEX IF EXISTS idx_patients_metadata_gin;")