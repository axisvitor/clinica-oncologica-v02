"""Add comprehensive performance indexes.

Revision ID: fc449418ac7b
Revises: 98ba470eed4a
Create Date: 2026-01-09

Migrates ad-hoc performance indexes into Alembic-managed changes.

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
revision = "fc449418ac7b"
down_revision = "98ba470eed4a"
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


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    where: str | None = None,
    where_columns: list[str] | None = None,
    required_columns: list[str] | None = None,
    postgresql_using: str | None = None,
    postgresql_ops: dict[str, str] | None = None,
) -> None:
    if not _table_exists(bind, table_name):
        return
    if _index_exists(bind, table_name, index_name):
        return

    existing_cols = {col["name"] for col in sa.inspect(bind).get_columns(table_name)}
    if required_columns and not all(col in existing_cols for col in required_columns):
        return

    if where and where_columns and not all(col in existing_cols for col in where_columns):
        where = None

    kwargs = {}
    if where:
        kwargs["postgresql_where"] = sa.text(where)
    if postgresql_using:
        kwargs["postgresql_using"] = postgresql_using
    if postgresql_ops:
        kwargs["postgresql_ops"] = postgresql_ops

    op.create_index(index_name, table_name, columns, **kwargs)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
    if not _table_exists(bind, table_name):
        return
    if _index_exists(bind, table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _select_first_column(
    bind, table_name: str, candidates: list[str]
) -> str | None:
    for column in candidates:
        if _column_exists(bind, table_name, column):
            return column
    return None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Quiz sessions and responses
    _create_index_if_missing(
        bind,
        "idx_quiz_sessions_patient_id_created",
        "quiz_sessions",
        ["patient_id", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["patient_id", "created_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_quiz_sessions_template_id",
        "quiz_sessions",
        ["quiz_template_id", "started_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["quiz_template_id", "started_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_quiz_sessions_status",
        "quiz_sessions",
        ["status", "started_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["status", "started_at"],
    )

    quiz_session_col = _select_first_column(
        bind, "quiz_responses", ["quiz_session_id", "session_id"]
    )
    quiz_response_time_col = _select_first_column(
        bind, "quiz_responses", ["responded_at", "created_at"]
    )
    if quiz_session_col and quiz_response_time_col:
        _create_index_if_missing(
            bind,
            "idx_quiz_responses_session_id",
            "quiz_responses",
            [quiz_session_col, quiz_response_time_col],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=[quiz_session_col, quiz_response_time_col],
        )
    if quiz_response_time_col:
        _create_index_if_missing(
            bind,
            "idx_quiz_responses_patient_id_created",
            "quiz_responses",
            ["patient_id", quiz_response_time_col],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=["patient_id", quiz_response_time_col],
        )
        _create_index_if_missing(
            bind,
            "idx_quiz_responses_template_id",
            "quiz_responses",
            ["quiz_template_id", quiz_response_time_col],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=["quiz_template_id", quiz_response_time_col],
        )

    # Flow executions and states
    flow_version_col = _select_first_column(
        bind, "patient_flow_states", ["flow_template_version_id", "template_version_id"]
    )
    if flow_version_col:
        _create_index_if_missing(
            bind,
            "idx_flow_executions_flow_id_created",
            "patient_flow_states",
            [flow_version_col, "started_at"],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=[flow_version_col, "started_at"],
        )
    _create_index_if_missing(
        bind,
        "idx_flow_states_patient_id_created",
        "patient_flow_states",
        ["patient_id", "started_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["patient_id", "started_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_flow_states_active",
        "patient_flow_states",
        ["patient_id", "started_at"],
        where="completed_at IS NULL AND deleted_at IS NULL",
        where_columns=["completed_at", "deleted_at"],
        required_columns=["patient_id", "started_at"],
    )

    flow_kind_col = _select_first_column(
        bind, "flow_template_versions", ["kind_id", "flow_kind_id"]
    )
    if flow_kind_col:
        _create_index_if_missing(
            bind,
            "idx_flow_template_versions_kind_id",
            "flow_template_versions",
            [flow_kind_col, "created_at"],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=[flow_kind_col, "created_at"],
        )

    # Medications
    _create_index_if_missing(
        bind,
        "idx_medications_patient_id_created",
        "medications",
        ["patient_id", "prescription_date"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["patient_id", "prescription_date"],
    )
    _create_index_if_missing(
        bind,
        "idx_medications_prescribed_by_id",
        "medications",
        ["prescribed_by_id", "prescription_date"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["prescribed_by_id", "prescription_date"],
    )
    _create_index_if_missing(
        bind,
        "idx_medications_treatment_id",
        "medications",
        ["treatment_id", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["treatment_id", "created_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_medications_active",
        "medications",
        ["patient_id", "is_active", "start_date"],
        where="deleted_at IS NULL AND is_active = true",
        where_columns=["deleted_at", "is_active"],
        required_columns=["patient_id", "is_active", "start_date"],
    )
    _create_index_if_missing(
        bind,
        "idx_medications_expiring",
        "medications",
        ["end_date", "is_active"],
        where="deleted_at IS NULL AND is_active = true AND end_date IS NOT NULL",
        where_columns=["deleted_at", "is_active", "end_date"],
        required_columns=["end_date", "is_active"],
    )

    # Patients
    _create_index_if_missing(
        bind,
        "idx_patients_doctor_id_created",
        "patients",
        ["doctor_id", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["doctor_id", "created_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_patients_active",
        "patients",
        ["id", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["id", "created_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_patients_phone_hash",
        "patients",
        ["phone_hash"],
        where="deleted_at IS NULL AND phone_hash IS NOT NULL",
        where_columns=["deleted_at", "phone_hash"],
        required_columns=["phone_hash"],
    )
    _create_index_if_missing(
        bind,
        "idx_patients_email_hash",
        "patients",
        ["email_hash"],
        where="deleted_at IS NULL AND email_hash IS NOT NULL",
        where_columns=["deleted_at", "email_hash"],
        required_columns=["email_hash"],
    )

    if bind.dialect.name == "postgresql":
        _create_index_if_missing(
            bind,
            "idx_patients_name_trgm",
            "patients",
            ["name"],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=["name"],
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        )

    # Messages and alerts
    _create_index_if_missing(
        bind,
        "idx_messages_patient_created",
        "messages",
        ["patient_id", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["patient_id", "created_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_messages_direction_created",
        "messages",
        ["direction", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["direction", "created_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_messages_patient_direction_created",
        "messages",
        ["patient_id", "direction", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["patient_id", "direction", "created_at"],
    )
    _create_index_if_missing(
        bind,
        "idx_messages_status_created",
        "messages",
        ["status", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["status", "created_at"],
    )

    alert_status_col = _select_first_column(bind, "alerts", ["status", "acknowledged"])
    if alert_status_col:
        _create_index_if_missing(
            bind,
            "idx_alerts_status_created",
            "alerts",
            [alert_status_col, "created_at"],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=[alert_status_col, "created_at"],
        )
    _create_index_if_missing(
        bind,
        "idx_alerts_patient_id_created",
        "alerts",
        ["patient_id", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["patient_id", "created_at"],
    )

    # Flow analytics
    analytics_timestamp_col = _select_first_column(
        bind, "flow_analytics", ["timestamp", "last_interaction_at", "created_at"]
    )
    if analytics_timestamp_col:
        _create_index_if_missing(
            bind,
            "idx_flow_analytics_patient_timestamp",
            "flow_analytics",
            ["patient_id", analytics_timestamp_col],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=["patient_id", analytics_timestamp_col],
        )
    flow_type_col = _select_first_column(bind, "flow_analytics", ["flow_type"])
    if flow_type_col and analytics_timestamp_col:
        _create_index_if_missing(
            bind,
            "idx_flow_analytics_flow_type_timestamp",
            "flow_analytics",
            [flow_type_col, analytics_timestamp_col],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=[flow_type_col, analytics_timestamp_col],
        )
    event_type_col = _select_first_column(bind, "flow_analytics", ["event_type"])
    if event_type_col and analytics_timestamp_col:
        _create_index_if_missing(
            bind,
            "idx_flow_analytics_event_type_timestamp",
            "flow_analytics",
            [event_type_col, analytics_timestamp_col],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=[event_type_col, analytics_timestamp_col],
        )
    if analytics_timestamp_col:
        _create_index_if_missing(
            bind,
            "idx_flow_analytics_sentiment",
            "flow_analytics",
            ["patient_id", "sentiment_score", analytics_timestamp_col],
            where="sentiment_score IS NOT NULL AND deleted_at IS NULL",
            where_columns=["sentiment_score", "deleted_at"],
            required_columns=["patient_id", "sentiment_score", analytics_timestamp_col],
        )
        _create_index_if_missing(
            bind,
            "idx_flow_analytics_engagement",
            "flow_analytics",
            ["patient_id", "engagement_score", analytics_timestamp_col],
            where="engagement_score IS NOT NULL AND deleted_at IS NULL",
            where_columns=["engagement_score", "deleted_at"],
            required_columns=["patient_id", "engagement_score", analytics_timestamp_col],
        )

    response_time_col = _select_first_column(
        bind, "flow_analytics", ["response_time_seconds", "avg_response_time_seconds"]
    )
    if analytics_timestamp_col and response_time_col:
        _create_index_if_missing(
            bind,
            "idx_flow_analytics_response_time",
            "flow_analytics",
            ["patient_id", response_time_col, analytics_timestamp_col],
            where=f"{response_time_col} IS NOT NULL AND deleted_at IS NULL",
            where_columns=[response_time_col, "deleted_at"],
            required_columns=["patient_id", response_time_col, analytics_timestamp_col],
        )
    if analytics_timestamp_col and event_type_col:
        _create_index_if_missing(
            bind,
            "idx_flow_analytics_risk_analysis",
            "flow_analytics",
            ["patient_id", event_type_col, analytics_timestamp_col],
            where="event_type IN ('RESPONSE_RECEIVED', 'CONCERN_DETECTED') AND deleted_at IS NULL",
            where_columns=["event_type", "deleted_at"],
            required_columns=["patient_id", event_type_col, analytics_timestamp_col],
        )

    # Treatments and appointments
    _create_index_if_missing(
        bind,
        "idx_treatments_patient_id",
        "treatments",
        ["patient_id", "created_at"],
        where="deleted_at IS NULL",
        where_columns=["deleted_at"],
        required_columns=["patient_id", "created_at"],
    )
    appointment_datetime_col = _select_first_column(
        bind, "appointments", ["appointment_datetime", "scheduled_at"]
    )
    if appointment_datetime_col:
        _create_index_if_missing(
            bind,
            "idx_appointments_patient_id_datetime",
            "appointments",
            ["patient_id", appointment_datetime_col],
            where="deleted_at IS NULL",
            where_columns=["deleted_at"],
            required_columns=["patient_id", appointment_datetime_col],
        )


def downgrade() -> None:
    bind = op.get_bind()

    index_table_map = {
        "idx_quiz_sessions_patient_id_created": "quiz_sessions",
        "idx_quiz_sessions_template_id": "quiz_sessions",
        "idx_quiz_sessions_status": "quiz_sessions",
        "idx_quiz_responses_session_id": "quiz_responses",
        "idx_quiz_responses_patient_id_created": "quiz_responses",
        "idx_quiz_responses_template_id": "quiz_responses",
        "idx_flow_executions_flow_id_created": "patient_flow_states",
        "idx_flow_states_patient_id_created": "patient_flow_states",
        "idx_flow_states_active": "patient_flow_states",
        "idx_flow_template_versions_kind_id": "flow_template_versions",
        "idx_medications_patient_id_created": "medications",
        "idx_medications_prescribed_by_id": "medications",
        "idx_medications_treatment_id": "medications",
        "idx_medications_active": "medications",
        "idx_medications_expiring": "medications",
        "idx_patients_doctor_id_created": "patients",
        "idx_patients_active": "patients",
        "idx_patients_phone_hash": "patients",
        "idx_patients_email_hash": "patients",
        "idx_patients_name_trgm": "patients",
        "idx_messages_patient_created": "messages",
        "idx_messages_direction_created": "messages",
        "idx_messages_patient_direction_created": "messages",
        "idx_alerts_status_created": "alerts",
        "idx_messages_status_created": "messages",
        "idx_alerts_patient_id_created": "alerts",
        "idx_flow_analytics_patient_timestamp": "flow_analytics",
        "idx_flow_analytics_flow_type_timestamp": "flow_analytics",
        "idx_flow_analytics_event_type_timestamp": "flow_analytics",
        "idx_flow_analytics_sentiment": "flow_analytics",
        "idx_flow_analytics_engagement": "flow_analytics",
        "idx_flow_analytics_response_time": "flow_analytics",
        "idx_flow_analytics_risk_analysis": "flow_analytics",
        "idx_treatments_patient_id": "treatments",
        "idx_appointments_patient_id_datetime": "appointments",
    }

    for index_name, table_name in index_table_map.items():
        _drop_index_if_exists(bind, table_name, index_name)
