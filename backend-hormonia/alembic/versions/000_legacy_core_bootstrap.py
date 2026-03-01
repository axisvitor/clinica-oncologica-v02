"""Bootstrap legacy core schema required before revision 001.

Revision ID: 000_legacy_core_bootstrap
Revises:
Create Date: 2026-02-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "000_legacy_core_bootstrap"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()

    # Needed by legacy schema defaults that rely on gen_random_uuid().
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    if not _table_exists(bind, "users"):
        op.create_table(
            "users",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("role", sa.String(length=50), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("email", name="users_email_key"),
        )

    if not _table_exists(bind, "patients"):
        op.create_table(
            "patients",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column("birth_date", sa.Date(), nullable=True),
            sa.Column("treatment_type", sa.String(length=100), nullable=True),
            sa.Column("treatment_start_date", sa.Date(), nullable=True),
            sa.Column("flow_state", sa.String(length=50), nullable=True),
            sa.Column("current_day", sa.Integer(), nullable=True, server_default=sa.text("1")),
            sa.Column("cpf", sa.String(length=14), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=20), nullable=False),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "patient_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["doctor_id"],
                ["users.id"],
                name="patients_doctor_id_fkey",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("cpf", name="patients_cpf_key"),
            sa.UniqueConstraint("phone", name="patients_phone_key"),
        )

    if not _table_exists(bind, "flow_kinds"):
        op.create_table(
            "flow_kinds",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("kind_key", sa.String(length=100), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("kind_key", name="flow_kinds_kind_key_key"),
        )

    if not _table_exists(bind, "flow_template_versions"):
        op.create_table(
            "flow_template_versions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("flow_kind_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("template_name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "steps",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["flow_kind_id"],
                ["flow_kinds.id"],
                name="flow_template_versions_flow_kind_id_fkey",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "flow_kind_id",
                "version_number",
                name="uq_flow_template_versions_kind_version",
            ),
        )

    if not _table_exists(bind, "patient_flow_states"):
        op.create_table(
            "patient_flow_states",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("flow_template_version_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("current_step", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column(
                "step_data",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("flow_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="patient_flow_states_patient_id_fkey",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["flow_template_version_id"],
                ["flow_template_versions.id"],
                name="patient_flow_states_flow_template_version_id_fkey",
                ondelete="SET NULL",
            ),
            sa.UniqueConstraint(
                "patient_id",
                "flow_template_version_id",
                name="uq_patient_flow_state_unique_version",
            ),
        )

    if not _table_exists(bind, "messages"):
        op.create_table(
            "messages",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("message_type", sa.String(length=50), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "message_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="messages_patient_id_fkey",
                ondelete="CASCADE",
            ),
        )

    if not _table_exists(bind, "quiz_sessions"):
        op.create_table(
            "quiz_sessions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="quiz_sessions_patient_id_fkey",
                ondelete="CASCADE",
            ),
        )

    if not _table_exists(bind, "quiz_templates"):
        op.create_table(
            "quiz_templates",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    if not _table_exists(bind, "quiz_responses"):
        op.create_table(
            "quiz_responses",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("response_type", sa.String(length=50), nullable=True),
            sa.Column("response_value", sa.Text(), nullable=True),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="quiz_responses_patient_id_fkey",
                ondelete="CASCADE",
            ),
        )

    if not _table_exists(bind, "alerts"):
        op.create_table(
            "alerts",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "acknowledged",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="alerts_patient_id_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["acknowledged_by"],
                ["users.id"],
                name="alerts_acknowledged_by_fkey",
            ),
        )

    if not _table_exists(bind, "medical_reports"):
        op.create_table(
            "medical_reports",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("period_start", sa.Date(), nullable=True),
            sa.Column("period_end", sa.Date(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="medical_reports_patient_id_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["generated_by"],
                ["users.id"],
                name="medical_reports_generated_by_fkey",
            ),
        )

    if not _table_exists(bind, "reports"):
        op.create_table(
            "reports",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="reports_patient_id_fkey",
            ),
        )

    if not _table_exists(bind, "notifications"):
        op.create_table(
            "notifications",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("related_patient_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name="notifications_user_id_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["related_patient_id"],
                ["patients.id"],
                name="notifications_related_patient_id_fkey",
            ),
        )

    if not _table_exists(bind, "flow_analytics"):
        op.create_table(
            "flow_analytics",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("flow_template_version_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="flow_analytics_patient_id_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["flow_template_version_id"],
                ["flow_template_versions.id"],
                name="flow_analytics_flow_template_version_id_fkey",
            ),
        )

    if not _table_exists(bind, "flow_messages"):
        op.create_table(
            "flow_messages",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("flow_template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("step_number", sa.Integer(), nullable=True),
            sa.Column("message_key", sa.String(length=100), nullable=True),
            sa.Column("message_text", sa.Text(), nullable=True),
            sa.Column("message_type", sa.String(length=50), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["flow_template_version_id"],
                ["flow_template_versions.id"],
                name="flow_messages_flow_template_version_id_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="flow_messages_patient_id_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["message_id"],
                ["messages.id"],
                name="flow_messages_message_id_fkey",
            ),
        )

    if not _table_exists(bind, "webhook_events"):
        op.create_table(
            "webhook_events",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("related_message_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("related_patient_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    if not _table_exists(bind, "audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("event_type", sa.String(length=100), nullable=True),
            sa.Column("event_status", sa.String(length=20), nullable=True),
            sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("user_email", sa.String(length=255), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name="audit_logs_user_id_fkey",
                ondelete="SET NULL",
            ),
        )

    if not _table_exists(bind, "uploads"):
        op.create_table(
            "uploads",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "upload_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name="uploads_user_id_fkey",
                ondelete="SET NULL",
            ),
        )

    if not _table_exists(bind, "user_sync_log"):
        op.create_table(
            "user_sync_log",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("firebase_uid", sa.String(length=128), nullable=True),
            sa.Column("supabase_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("sync_action", sa.String(length=50), nullable=True),
            sa.Column("sync_status", sa.String(length=50), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    if not _table_exists(bind, "sessions"):
        op.create_table(
            "sessions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name="sessions_user_id_fkey",
                ondelete="CASCADE",
            ),
        )

    if not _table_exists(bind, "flow_executions"):
        op.create_table(
            "flow_executions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )


def downgrade() -> None:
    # Keep downgrade intentionally conservative to avoid dropping production data.
    pass
