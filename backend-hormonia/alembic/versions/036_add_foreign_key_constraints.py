"""Add missing foreign key constraints and enhance referential integrity

Revision ID: 036_foreign_keys
Revises: 035_composite_indexes
Create Date: 2025-09-29 21:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '036_foreign_keys'
down_revision = '035_composite_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add missing foreign key constraints to ensure referential integrity.
    Uses IF NOT EXISTS pattern for safety.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Helper function to check if FK exists
    def fk_exists(table_name: str, fk_name: str) -> bool:
        foreign_keys = inspector.get_foreign_keys(table_name)
        return any(fk.get('name') == fk_name for fk in foreign_keys)

    # Flow analytics foreign keys
    if not fk_exists('flow_analytics', 'fk_flow_analytics_patient_id'):
        op.execute("""
            ALTER TABLE flow_analytics
            ADD CONSTRAINT fk_flow_analytics_patient_id
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;
        """)

    if not fk_exists('flow_analytics', 'fk_flow_analytics_flow_template_id'):
        # Check if column exists first
        columns = [c['name'] for c in inspector.get_columns('flow_analytics')]
        if 'flow_template_id' in columns:
            op.execute("""
                ALTER TABLE flow_analytics
                ADD CONSTRAINT fk_flow_analytics_flow_template_id
                FOREIGN KEY (flow_template_id) REFERENCES flow_kinds(id) ON DELETE SET NULL;
            """)

    # Flow messages foreign keys
    if not fk_exists('flow_messages', 'fk_flow_messages_flow_template_id'):
        op.execute("""
            ALTER TABLE flow_messages
            ADD CONSTRAINT fk_flow_messages_flow_template_id
            FOREIGN KEY (flow_template_id) REFERENCES flow_kinds(id) ON DELETE CASCADE;
        """)

    if not fk_exists('flow_messages', 'fk_flow_messages_patient_id'):
        op.execute("""
            ALTER TABLE flow_messages
            ADD CONSTRAINT fk_flow_messages_patient_id
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;
        """)

    if not fk_exists('flow_messages', 'fk_flow_messages_message_id'):
        op.execute("""
            ALTER TABLE flow_messages
            ADD CONSTRAINT fk_flow_messages_message_id
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL;
        """)

    # Quiz questions foreign key (if table exists)
    tables = inspector.get_table_names()
    if 'quiz_questions' in tables:
        columns = [c['name'] for c in inspector.get_columns('quiz_questions')]
        if 'quiz_template_id' in columns and not fk_exists('quiz_questions', 'fk_quiz_questions_quiz_template_id'):
            op.execute("""
                ALTER TABLE quiz_questions
                ADD CONSTRAINT fk_quiz_questions_quiz_template_id
                FOREIGN KEY (quiz_template_id) REFERENCES quiz_templates(id) ON DELETE CASCADE;
            """)

    # Add check constraints for data integrity
    op.execute("""
        DO $$
        BEGIN
            -- Ensure message status transitions are valid
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_message_status_events_status_valid'
            ) THEN
                ALTER TABLE message_status_events
                ADD CONSTRAINT ck_message_status_events_status_valid
                CHECK (status IN ('queued', 'sending', 'sent', 'delivered', 'read', 'failed', 'rejected'));
            END IF;

            -- Ensure webhook retry count is reasonable
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_webhook_events_retry_count'
            ) THEN
                ALTER TABLE webhook_events
                ADD CONSTRAINT ck_webhook_events_retry_count
                CHECK (retry_count >= 0 AND retry_count <= 10);
            END IF;

            -- Ensure A/B experiment traffic allocation is valid
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_ab_experiments_traffic_valid'
            ) THEN
                ALTER TABLE ab_experiments
                ADD CONSTRAINT ck_ab_experiments_traffic_valid
                CHECK (traffic_allocation > 0 AND traffic_allocation <= 1);
            END IF;

            -- Ensure quiz session timing is logical
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_quiz_sessions_timing'
            ) THEN
                ALTER TABLE quiz_sessions
                ADD CONSTRAINT ck_quiz_sessions_timing
                CHECK (completed_at IS NULL OR completed_at >= started_at);
            END IF;

            -- Ensure alert acknowledgment timing
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_alerts_acknowledgment_timing'
            ) THEN
                ALTER TABLE alerts
                ADD CONSTRAINT ck_alerts_acknowledgment_timing
                CHECK (acknowledged_at IS NULL OR acknowledged_at >= created_at);
            END IF;
        END $$;
    """)

    # Add table comments for documentation
    op.execute("""
        COMMENT ON CONSTRAINT fk_flow_analytics_patient_id ON flow_analytics IS
        'Ensures analytics data is deleted when patient is deleted';
    """)

    op.execute("""
        COMMENT ON CONSTRAINT fk_flow_messages_message_id ON flow_messages IS
        'Allows message deletion without breaking flow message history';
    """)


def downgrade():
    """
    Drop foreign key constraints added in upgrade.
    Note: Check constraints are not dropped in downgrade to maintain data integrity.
    """
    # Drop foreign keys
    op.execute("ALTER TABLE flow_analytics DROP CONSTRAINT IF EXISTS fk_flow_analytics_patient_id CASCADE;")
    op.execute("ALTER TABLE flow_analytics DROP CONSTRAINT IF EXISTS fk_flow_analytics_flow_template_id CASCADE;")
    op.execute("ALTER TABLE flow_messages DROP CONSTRAINT IF EXISTS fk_flow_messages_flow_template_id CASCADE;")
    op.execute("ALTER TABLE flow_messages DROP CONSTRAINT IF EXISTS fk_flow_messages_patient_id CASCADE;")
    op.execute("ALTER TABLE flow_messages DROP CONSTRAINT IF EXISTS fk_flow_messages_message_id CASCADE;")
    op.execute("ALTER TABLE quiz_questions DROP CONSTRAINT IF EXISTS fk_quiz_questions_quiz_template_id CASCADE;")

    # Note: Check constraints intentionally left in place for data integrity