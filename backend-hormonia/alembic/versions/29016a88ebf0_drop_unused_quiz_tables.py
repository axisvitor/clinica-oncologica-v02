"""Drop unused quiz tables.

Revision ID: 29016a88ebf0
Revises: 9139c2862e40
Create Date: 2026-01-04

Drops unused quiz tables that are not referenced by any model:
- quiz_responses_with_text (VIEW)
- quiz_sessions_v2
- quiz_template_versions_v2
- quiz_questions
- quiz_response_migration_log
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers
revision = "29016a88ebf0"
down_revision = "9139c2862e40"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Drop unused quiz tables and views."""
    bind = op.get_bind()

    # Drop VIEW first (it may depend on quiz_responses)
    op.execute("DROP VIEW IF EXISTS quiz_responses_with_text")

    # Drop unused v2 tables (CASCADE required for dependent FKs)
    for table_name in (
        "quiz_sessions_v2",
        "quiz_template_versions_v2",
        "quiz_questions",
        "quiz_response_migration_log",
    ):
        if _table_exists(bind, table_name):
            op.drop_table(table_name)


def downgrade() -> None:
    """Recreate dropped tables (empty structure for rollback)."""
    bind = op.get_bind()

    if not _table_exists(bind, "quiz_questions"):
        op.create_table(
            "quiz_questions",
            sa.Column("quiz_template_id", sa.UUID(), nullable=False),
            sa.Column("question_text", sa.String(), nullable=False),
            sa.Column("question_type", sa.String(length=50), nullable=False),
            sa.Column("question_order", sa.Integer(), nullable=False),
            sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("correct_answer", sa.String(), nullable=True),
            sa.Column("points", sa.Integer(), nullable=True),
            sa.Column("is_required", sa.Boolean(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["quiz_template_id"], ["quiz_templates.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_quiz_questions_id", "quiz_questions", ["id"])
        op.create_index(
            "ix_quiz_questions_quiz_template_id",
            "quiz_questions",
            ["quiz_template_id"],
        )

    if not _table_exists(bind, "quiz_template_versions_v2"):
        op.create_table(
            "quiz_template_versions_v2",
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("template_id", sa.UUID(), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("scoring_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=True),
            sa.Column("is_draft", sa.Boolean(), server_default=sa.text("true"), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.UUID(), nullable=True),
            sa.Column("change_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(
                ["created_by"],
                ["users.id"],
                name="quiz_template_versions_v2_created_by_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["template_id"],
                ["quiz_templates.id"],
                name="quiz_template_versions_v2_template_id_fkey",
            ),
            sa.PrimaryKeyConstraint("id", name="quiz_template_versions_v2_pkey"),
            sa.UniqueConstraint(
                "template_id",
                "version_number",
                name="unique_template_version",
                postgresql_nulls_not_distinct=False,
            ),
        )
        op.create_index(
            "idx_quiz_template_versions_v2_template",
            "quiz_template_versions_v2",
            ["template_id"],
        )
        op.create_index(
            "idx_quiz_template_versions_v2_active",
            "quiz_template_versions_v2",
            ["template_id", "is_active"],
            postgresql_where=sa.text("(is_active = true)"),
        )

    if not _table_exists(bind, "quiz_sessions_v2"):
        op.create_table(
            "quiz_sessions_v2",
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("patient_id", sa.UUID(), nullable=False),
            sa.Column("template_version_id", sa.UUID(), nullable=False),
            sa.Column("status", sa.String(length=50), server_default=sa.text("'started'::character varying"), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("session_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(
                ["patient_id"],
                ["patients.id"],
                name="quiz_sessions_v2_patient_id_fkey",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["template_version_id"],
                ["quiz_template_versions_v2.id"],
                name="quiz_sessions_v2_template_version_id_fkey",
            ),
            sa.PrimaryKeyConstraint("id", name="quiz_sessions_v2_pkey"),
        )
        op.create_index(
            "idx_quiz_sessions_v2_template_version",
            "quiz_sessions_v2",
            ["template_version_id"],
        )
        op.create_index(
            "idx_quiz_sessions_v2_patient",
            "quiz_sessions_v2",
            ["patient_id"],
        )

    if not _table_exists(bind, "quiz_response_migration_log"):
        op.create_table(
            "quiz_response_migration_log",
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("quiz_response_id", sa.UUID(), nullable=False),
            sa.Column("original_value", sa.Text(), nullable=True),
            sa.Column("converted_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("conversion_status", sa.Text(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("migrated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id", name="quiz_response_migration_log_pkey"),
        )
        op.create_index(
            "idx_migration_log_status",
            "quiz_response_migration_log",
            ["conversion_status"],
        )
        op.create_index(
            "idx_migration_log_errors",
            "quiz_response_migration_log",
            ["quiz_response_id"],
            postgresql_where=sa.text("(error_message IS NOT NULL)"),
        )

    op.execute(
        """
        CREATE OR REPLACE VIEW quiz_responses_with_text AS
        SELECT
            qr.*,
            qr.response_value::text AS response_value_text,
            CASE
                WHEN jsonb_typeof(qr.response_value) = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(qr.response_value))
                ELSE NULL
            END AS response_value_array,
            CASE
                WHEN jsonb_typeof(qr.response_value) = 'number'
                THEN (qr.response_value)::numeric
                ELSE NULL
            END AS response_value_numeric
        FROM quiz_responses qr
        """
    )
