"""Add AI audit logs table

Revision ID: 006_add_ai_audit_logs
Revises: 005_add_other_text_to_quiz_responses
Create Date: 2025-09-24 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '012_ai_audit_logs'
down_revision = '011_other_text'
branch_labels = None
depends_on = None


def upgrade():
    """Create AI audit logs table with HIPAA-compliant structure."""

    # Note: audit_logs table already exists, but we'll add indexes for AI-specific queries
    # and ensure all necessary columns are present

    # Add indexes for AI audit queries
    op.create_index(
        'ix_audit_logs_event_type_timestamp',
        'audit_logs',
        ['event_type', 'timestamp'],
        postgresql_where=sa.text("event_type LIKE 'ai_%'")
    )

    op.create_index(
        'ix_audit_logs_actor_subject',
        'audit_logs',
        ['actor_id', 'subject_id'],
        postgresql_where=sa.text("event_type LIKE 'ai_%'")
    )

    op.create_index(
        'ix_audit_logs_data_subject_timestamp',
        'audit_logs',
        ['data_subject_id', 'timestamp'],
        postgresql_where=sa.text("event_type LIKE 'ai_%'")
    )

    # Create materialized view for AI performance metrics (optional, for faster reporting)
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ai_performance_metrics AS
        SELECT
            DATE_TRUNC('hour', timestamp) as hour,
            event_type,
            COUNT(*) as request_count,
            AVG(CAST(event_data->>'response_time_ms' AS FLOAT)) as avg_response_time,
            SUM(CASE WHEN event_data->>'cache_hit' = 'true' THEN 1 ELSE 0 END) as cache_hits,
            SUM(CASE WHEN result = 'failure' THEN 1 ELSE 0 END) as error_count
        FROM audit_logs
        WHERE event_type LIKE 'ai_%'
        GROUP BY DATE_TRUNC('hour', timestamp), event_type;

        CREATE INDEX IF NOT EXISTS ix_ai_perf_metrics_hour ON ai_performance_metrics(hour);
    """)

    # Create function to refresh metrics view (can be called by scheduler)
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_ai_metrics()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY ai_performance_metrics;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    """Remove AI audit log enhancements."""

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS refresh_ai_metrics();")

    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ai_performance_metrics;")

    # Drop indexes
    op.drop_index('ix_audit_logs_data_subject_timestamp', 'audit_logs')
    op.drop_index('ix_audit_logs_actor_subject', 'audit_logs')
    op.drop_index('ix_audit_logs_event_type_timestamp', 'audit_logs')