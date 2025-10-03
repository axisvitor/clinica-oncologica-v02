"""Add database triggers for automated timestamp updates and data validation

Revision ID: 037_triggers
Revises: 036_foreign_keys
Create Date: 2025-09-29 21:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '037_triggers'
down_revision = '036_foreign_keys'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create database triggers for:
    1. Auto-updating updated_at timestamps
    2. Validating data transitions
    3. Maintaining denormalized counts
    4. Audit trail automation
    """

    # Create reusable trigger function for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Apply updated_at trigger to all tables with updated_at column
    tables_with_updated_at = [
        'users', 'patients', 'messages', 'patient_flow_states',
        'flow_kinds', 'flow_template_versions', 'flow_analytics', 'flow_messages',
        'quiz_templates', 'quiz_sessions', 'quiz_responses',
        'medical_reports', 'alerts', 'webhook_events',
        'ab_experiments'
    ]

    for table in tables_with_updated_at:
        op.execute(f"""
            DROP TRIGGER IF EXISTS trigger_update_{table}_updated_at ON {table};

            CREATE TRIGGER trigger_update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)

    # Trigger to automatically complete quiz sessions when all questions answered
    op.execute("""
        CREATE OR REPLACE FUNCTION auto_complete_quiz_session()
        RETURNS TRIGGER AS $$
        DECLARE
            total_questions INTEGER;
            answered_questions INTEGER;
        BEGIN
            -- Get total questions in template
            SELECT jsonb_array_length(questions) INTO total_questions
            FROM quiz_templates
            WHERE id = NEW.quiz_template_id;

            -- Count answered questions in this session
            SELECT COUNT(*) INTO answered_questions
            FROM quiz_responses
            WHERE quiz_session_id = NEW.quiz_session_id;

            -- If all questions answered, mark session complete
            IF answered_questions >= total_questions THEN
                UPDATE quiz_sessions
                SET
                    is_completed = true,
                    status = 'completed',
                    completed_at = NOW()
                WHERE id = NEW.quiz_session_id AND is_completed = false;
            END IF;

            RETURN NEW;
        END;
        $$ language 'plpgsql';

        DROP TRIGGER IF EXISTS trigger_auto_complete_quiz ON quiz_responses;

        CREATE TRIGGER trigger_auto_complete_quiz
        AFTER INSERT ON quiz_responses
        FOR EACH ROW
        EXECUTE FUNCTION auto_complete_quiz_session();
    """)

    # Trigger to update A/B experiment participant counts
    op.execute("""
        CREATE OR REPLACE FUNCTION update_ab_experiment_counts()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE ab_experiments
                SET
                    total_participants = total_participants + 1,
                    control_participants = control_participants +
                        CASE WHEN NEW.variant = 'control' THEN 1 ELSE 0 END,
                    treatment_participants = treatment_participants +
                        CASE WHEN NEW.variant = 'treatment' THEN 1 ELSE 0 END
                WHERE id = NEW.experiment_id;
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE ab_experiments
                SET
                    total_participants = total_participants - 1,
                    control_participants = control_participants -
                        CASE WHEN OLD.variant = 'control' THEN 1 ELSE 0 END,
                    treatment_participants = treatment_participants -
                        CASE WHEN OLD.variant = 'treatment' THEN 1 ELSE 0 END
                WHERE id = OLD.experiment_id;
            END IF;

            RETURN COALESCE(NEW, OLD);
        END;
        $$ language 'plpgsql';

        DROP TRIGGER IF EXISTS trigger_update_ab_counts ON ab_variant_assignments;

        CREATE TRIGGER trigger_update_ab_counts
        AFTER INSERT OR DELETE ON ab_variant_assignments
        FOR EACH ROW
        EXECUTE FUNCTION update_ab_experiment_counts();
    """)

    # Trigger to create message status event on message status change
    op.execute("""
        CREATE OR REPLACE FUNCTION log_message_status_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' OR (OLD.status IS DISTINCT FROM NEW.status) THEN
                INSERT INTO message_status_events (
                    message_id,
                    status,
                    previous_status,
                    whatsapp_id,
                    created_at
                ) VALUES (
                    NEW.id,
                    NEW.status,
                    CASE WHEN TG_OP = 'UPDATE' THEN OLD.status ELSE NULL END,
                    NEW.whatsapp_id,
                    NOW()
                );
            END IF;

            RETURN NEW;
        END;
        $$ language 'plpgsql';

        DROP TRIGGER IF EXISTS trigger_log_message_status ON messages;

        CREATE TRIGGER trigger_log_message_status
        AFTER INSERT OR UPDATE OF status ON messages
        FOR EACH ROW
        EXECUTE FUNCTION log_message_status_change();
    """)

    # Trigger to prevent deletion of active A/B experiments
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_active_experiment_deletion()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status = 'active' THEN
                RAISE EXCEPTION 'Cannot delete active A/B experiment. Pause or complete it first.';
            END IF;

            RETURN OLD;
        END;
        $$ language 'plpgsql';

        DROP TRIGGER IF EXISTS trigger_prevent_active_ab_deletion ON ab_experiments;

        CREATE TRIGGER trigger_prevent_active_ab_deletion
        BEFORE DELETE ON ab_experiments
        FOR EACH ROW
        EXECUTE FUNCTION prevent_active_experiment_deletion();
    """)

    # Trigger to validate alert status transitions
    op.execute("""
        CREATE OR REPLACE FUNCTION validate_alert_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Can't go from resolved back to pending
            IF OLD.status = 'resolved' AND NEW.status IN ('pending', 'active') THEN
                RAISE EXCEPTION 'Cannot reopen resolved alert. Create a new alert instead.';
            END IF;

            -- Set resolved_at timestamp when resolving
            IF NEW.status = 'resolved' AND OLD.status != 'resolved' THEN
                NEW.resolved_at = NOW();
            END IF;

            RETURN NEW;
        END;
        $$ language 'plpgsql';

        DROP TRIGGER IF EXISTS trigger_validate_alert_transition ON alerts;

        CREATE TRIGGER trigger_validate_alert_transition
        BEFORE UPDATE OF status ON alerts
        FOR EACH ROW
        EXECUTE FUNCTION validate_alert_status_transition();
    """)

    # Add comments
    op.execute("""
        COMMENT ON FUNCTION update_updated_at_column() IS
        'Automatically updates updated_at column on row modification';
    """)

    op.execute("""
        COMMENT ON FUNCTION auto_complete_quiz_session() IS
        'Automatically marks quiz session as complete when all questions answered';
    """)

    op.execute("""
        COMMENT ON FUNCTION update_ab_experiment_counts() IS
        'Maintains denormalized participant counts in ab_experiments table';
    """)


def downgrade():
    """
    Drop all triggers and trigger functions created in upgrade.
    """
    # Drop triggers
    tables_with_updated_at = [
        'users', 'patients', 'messages', 'patient_flow_states',
        'flow_kinds', 'flow_template_versions', 'flow_analytics', 'flow_messages',
        'quiz_templates', 'quiz_sessions', 'quiz_responses',
        'medical_reports', 'alerts', 'webhook_events',
        'ab_experiments'
    ]

    for table in tables_with_updated_at:
        op.execute(f"DROP TRIGGER IF EXISTS trigger_update_{table}_updated_at ON {table};")

    op.execute("DROP TRIGGER IF EXISTS trigger_auto_complete_quiz ON quiz_responses;")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_ab_counts ON ab_variant_assignments;")
    op.execute("DROP TRIGGER IF EXISTS trigger_log_message_status ON messages;")
    op.execute("DROP TRIGGER IF EXISTS trigger_prevent_active_ab_deletion ON ab_experiments;")
    op.execute("DROP TRIGGER IF EXISTS trigger_validate_alert_transition ON alerts;")

    # Drop trigger functions
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    op.execute("DROP FUNCTION IF EXISTS auto_complete_quiz_session();")
    op.execute("DROP FUNCTION IF EXISTS update_ab_experiment_counts();")
    op.execute("DROP FUNCTION IF EXISTS log_message_status_change();")
    op.execute("DROP FUNCTION IF EXISTS prevent_active_experiment_deletion();")
    op.execute("DROP FUNCTION IF EXISTS validate_alert_status_transition();")