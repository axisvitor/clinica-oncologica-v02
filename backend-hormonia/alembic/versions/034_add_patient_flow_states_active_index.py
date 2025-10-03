"""Add indexes on patient_flow_states for active flow queries

Revision ID: 034_flow_states_active_idx
Revises: 033_audit_user_timestamp_idx
Create Date: 2025-09-29 19:46:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '034_flow_states_active_idx'
down_revision = '033_audit_user_timestamp_idx'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add indexes on patient_flow_states (or flow_states) table
    for optimizing active flow queries and scheduling.
    """
    # Determine the correct table name
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    table_name = None
    if 'patient_flow_states' in tables:
        table_name = 'patient_flow_states'
    elif 'flow_states' in tables:
        table_name = 'flow_states'

    if table_name:
        # Index for active flows by patient
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_patient_active
            ON {table_name}(patient_id, is_active)
            WHERE is_active = true;
        """)

        # Index for flow type and status
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_type_status
            ON {table_name}(flow_type, current_status);
        """)

        # Index for scheduling queries (next action date)
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_next_action
            ON {table_name}(next_scheduled_action)
            WHERE next_scheduled_action IS NOT NULL AND is_active = true;
        """)

        # Index for current day in flow (progress tracking)
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_current_day
            ON {table_name}(patient_id, current_day)
            WHERE is_active = true;
        """)


def downgrade():
    """
    Drop the patient_flow_states indexes.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    table_name = None
    if 'patient_flow_states' in tables:
        table_name = 'patient_flow_states'
    elif 'flow_states' in tables:
        table_name = 'flow_states'

    if table_name:
        op.execute(f"DROP INDEX IF EXISTS idx_{table_name}_current_day;")
        op.execute(f"DROP INDEX IF EXISTS idx_{table_name}_next_action;")
        op.execute(f"DROP INDEX IF EXISTS idx_{table_name}_type_status;")
        op.execute(f"DROP INDEX IF EXISTS idx_{table_name}_patient_active;")