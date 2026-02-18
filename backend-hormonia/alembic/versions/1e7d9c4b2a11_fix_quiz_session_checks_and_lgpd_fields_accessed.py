"""Fix quiz session check conflicts and harden LGPD fields_accessed integrity.

Revision ID: 1e7d9c4b2a11
Revises: a8c6d1f4b2e9
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1e7d9c4b2a11"
down_revision = "a8c6d1f4b2e9"
branch_labels = None
depends_on = None


def _is_postgresql(bind) -> bool:
    return bind.dialect.name == "postgresql"


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgresql(bind):
        return

    if _table_exists(bind, "quiz_sessions") and _column_exists(bind, "quiz_sessions", "status"):
        op.execute("ALTER TABLE quiz_sessions DROP CONSTRAINT IF EXISTS ck_quiz_session_status_valid")
        op.execute("ALTER TABLE quiz_sessions DROP CONSTRAINT IF EXISTS quiz_sessions_status_check")
        op.create_check_constraint(
            "ck_quiz_session_status_valid",
            "quiz_sessions",
            "status IN ('started', 'completed', 'cancelled', 'expired')",
        )

    if _table_exists(bind, "lgpd_audit_logs") and _column_exists(bind, "lgpd_audit_logs", "fields_accessed"):
        op.execute(
            """
            UPDATE lgpd_audit_logs
            SET fields_accessed = '[]'::jsonb
            WHERE fields_accessed IS NULL
               OR jsonb_typeof(fields_accessed) IS DISTINCT FROM 'array'
            """
        )
        op.execute("ALTER TABLE lgpd_audit_logs ALTER COLUMN fields_accessed SET DEFAULT '[]'::jsonb")
        op.execute("ALTER TABLE lgpd_audit_logs ALTER COLUMN fields_accessed SET NOT NULL")
        op.execute("ALTER TABLE lgpd_audit_logs DROP CONSTRAINT IF EXISTS ck_lgpd_audit_logs_fields_accessed_array")
        op.create_check_constraint(
            "ck_lgpd_audit_logs_fields_accessed_array",
            "lgpd_audit_logs",
            "jsonb_typeof(fields_accessed) = 'array'",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgresql(bind):
        return

    if _table_exists(bind, "lgpd_audit_logs") and _column_exists(bind, "lgpd_audit_logs", "fields_accessed"):
        op.execute("ALTER TABLE lgpd_audit_logs DROP CONSTRAINT IF EXISTS ck_lgpd_audit_logs_fields_accessed_array")
        op.execute("ALTER TABLE lgpd_audit_logs ALTER COLUMN fields_accessed DROP NOT NULL")
        op.execute("ALTER TABLE lgpd_audit_logs ALTER COLUMN fields_accessed DROP DEFAULT")

    if _table_exists(bind, "quiz_sessions") and _column_exists(bind, "quiz_sessions", "status"):
        op.execute("UPDATE quiz_sessions SET status = 'cancelled' WHERE status = 'expired'")
        op.execute("ALTER TABLE quiz_sessions DROP CONSTRAINT IF EXISTS ck_quiz_session_status_valid")
        op.execute("ALTER TABLE quiz_sessions DROP CONSTRAINT IF EXISTS quiz_sessions_status_check")
        op.create_check_constraint(
            "quiz_sessions_status_check",
            "quiz_sessions",
            "status IN ('started', 'completed', 'cancelled')",
        )
