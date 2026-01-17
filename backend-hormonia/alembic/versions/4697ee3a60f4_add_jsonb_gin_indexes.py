"""Add JSONB GIN indexes for operational tables.

Revision ID: 4697ee3a60f4
Revises: 21f306d5c4b8
Create Date: 2026-01-09

Adds GIN indexes on JSONB columns used in messages, sagas, and flow states.

WHY:
- Not recorded (legacy migration).

WHAT:
- Not recorded (legacy migration).

IMPACT:
- Not recorded (legacy migration).

BENCHMARK:
- Not recorded (legacy migration).

ROLLBACK:
- Not recorded (legacy migration).

RELATED:
- Not recorded (legacy migration).

MIGRATION TYPE:
- Not recorded (legacy migration).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4697ee3a60f4"
down_revision = "21f306d5c4b8"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _create_gin_index_if_missing(
    bind, table_name: str, column_name: str, index_name: str
) -> None:
    if not _table_exists(bind, table_name):
        return
    if not _column_exists(bind, table_name, column_name):
        return
    if _index_exists(bind, table_name, index_name):
        return
    op.create_index(
        index_name,
        table_name,
        [column_name],
        postgresql_using="gin",
    )


def upgrade() -> None:
    bind = op.get_bind()

    targets = [
        ("messages", "message_metadata", "idx_messages_message_metadata_gin"),
        ("patient_onboarding_saga", "execution_log", "idx_patient_onboarding_saga_execution_log_gin"),
        ("patient_onboarding_saga", "step_data", "idx_patient_onboarding_saga_step_data_gin"),
        ("patient_onboarding_saga", "patient_data", "idx_patient_onboarding_saga_patient_data_gin"),
        ("patient_flow_states", "flow_metadata", "idx_patient_flow_states_flow_metadata_gin"),
        ("patient_flow_states", "step_data", "idx_patient_flow_states_step_data_gin"),
        ("flow_states", "state_data", "idx_flow_states_state_data_gin"),
    ]

    for table_name, column_name, index_name in targets:
        _create_gin_index_if_missing(bind, table_name, column_name, index_name)


def downgrade() -> None:
    bind = op.get_bind()

    for table_name, index_name in [
        ("messages", "idx_messages_message_metadata_gin"),
        ("patient_onboarding_saga", "idx_patient_onboarding_saga_execution_log_gin"),
        ("patient_onboarding_saga", "idx_patient_onboarding_saga_step_data_gin"),
        ("patient_onboarding_saga", "idx_patient_onboarding_saga_patient_data_gin"),
        ("patient_flow_states", "idx_patient_flow_states_flow_metadata_gin"),
        ("patient_flow_states", "idx_patient_flow_states_step_data_gin"),
        ("flow_states", "idx_flow_states_state_data_gin"),
    ]:
        if _table_exists(bind, table_name) and _index_exists(bind, table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
