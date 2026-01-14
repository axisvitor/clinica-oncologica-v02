"""Add quiz session expiration support.

Revision ID: f16b221d27ad
Revises: 73a9d4d7cf05
Create Date: 2026-01-09

Adds expiration_date support, status constraint update, and trigger to
auto-populate expiration_date for active sessions.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f16b221d27ad"
down_revision = "73a9d4d7cf05"
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


def _check_constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "quiz_sessions"):
        return

    if not _column_exists(bind, "quiz_sessions", "expiration_date"):
        op.add_column(
            "quiz_sessions",
            sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=True),
        )

    if _is_postgres(bind):
        if _check_constraint_exists(bind, "quiz_sessions", "ck_quiz_session_status_valid"):
            op.drop_constraint(
                "ck_quiz_session_status_valid", "quiz_sessions", type_="check"
            )
        op.create_check_constraint(
            "ck_quiz_session_status_valid",
            "quiz_sessions",
            "status IN ('started', 'completed', 'cancelled', 'expired')",
        )

    if _is_postgres(bind):
        op.execute(
            """
            UPDATE quiz_sessions
            SET expiration_date = started_at + INTERVAL '48 hours'
            WHERE status = 'started' AND expiration_date IS NULL
            """
        )

    if _is_postgres(bind):
        op.execute(
            """
            CREATE OR REPLACE FUNCTION set_quiz_session_expiration()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.status = 'started' AND NEW.expiration_date IS NULL THEN
                    NEW.expiration_date := NEW.started_at + INTERVAL '48 hours';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute("DROP TRIGGER IF EXISTS trg_set_quiz_session_expiration ON quiz_sessions")
        op.execute(
            """
            CREATE TRIGGER trg_set_quiz_session_expiration
            BEFORE INSERT OR UPDATE ON quiz_sessions
            FOR EACH ROW
            WHEN (NEW.status = 'started')
            EXECUTE FUNCTION set_quiz_session_expiration();
            """
        )
        op.execute(
            "COMMENT ON COLUMN quiz_sessions.expiration_date IS "
            "'Expiration timestamp (default: started_at + 48 hours).'"
        )

    if not _index_exists(bind, "quiz_sessions", "idx_quiz_sessions_expiration_date"):
        op.create_index(
            "idx_quiz_sessions_expiration_date",
            "quiz_sessions",
            ["expiration_date"],
            postgresql_where=sa.text("status = 'started'"),
        )

    if not _index_exists(bind, "quiz_sessions", "idx_quiz_sessions_status_expiration"):
        op.create_index(
            "idx_quiz_sessions_status_expiration",
            "quiz_sessions",
            ["status", "expiration_date"],
            postgresql_where=sa.text("status = 'started' AND expiration_date IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "quiz_sessions"):
        return

    if _is_postgres(bind):
        op.execute("DROP TRIGGER IF EXISTS trg_set_quiz_session_expiration ON quiz_sessions")
        op.execute("DROP FUNCTION IF EXISTS set_quiz_session_expiration()")

    if _index_exists(bind, "quiz_sessions", "idx_quiz_sessions_status_expiration"):
        op.drop_index("idx_quiz_sessions_status_expiration", table_name="quiz_sessions")

    if _index_exists(bind, "quiz_sessions", "idx_quiz_sessions_expiration_date"):
        op.drop_index("idx_quiz_sessions_expiration_date", table_name="quiz_sessions")

    if _is_postgres(bind):
        op.execute("UPDATE quiz_sessions SET status = 'cancelled' WHERE status = 'expired'")
        if _check_constraint_exists(bind, "quiz_sessions", "ck_quiz_session_status_valid"):
            op.drop_constraint(
                "ck_quiz_session_status_valid", "quiz_sessions", type_="check"
            )
        op.create_check_constraint(
            "ck_quiz_session_status_valid",
            "quiz_sessions",
            "status IN ('started', 'completed', 'cancelled')",
        )

    if _column_exists(bind, "quiz_sessions", "expiration_date"):
        op.drop_column("quiz_sessions", "expiration_date")
