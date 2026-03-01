"""Optimize message/patient indexes and clean duplicate PK shadow indexes.

Revision ID: 3a4f5b6c7d88
Revises: 1e7d9c4b2a11
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a4f5b6c7d88"
down_revision = "1e7d9c4b2a11"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _execute_concurrently(sql: str) -> None:
    # Normalize to transactional DDL for deterministic execution in all envs.
    normalized = sql.replace(" CONCURRENTLY", "")
    op.execute(sa.text(normalized))


def upgrade() -> None:
    if not _is_postgresql():
        return

    inspector = sa.inspect(op.get_bind())

    if _table_exists(inspector, "messages"):
        message_columns = {
            column["name"] for column in inspector.get_columns("messages")
        }
        _execute_concurrently(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_patient_created_desc
            ON messages (patient_id, created_at DESC, id)
            """
        )
        if "direction" in message_columns:
            _execute_concurrently(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_outbound_queue_pending
                ON messages (scheduled_for, id)
                WHERE direction = 'outbound'
                  AND status IN ('pending', 'scheduled', 'failed')
                """
            )
        _execute_concurrently(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_status_pending_schedule
            ON messages (status, scheduled_for)
            WHERE status IN ('pending', 'scheduled', 'failed')
            """
        )
        _execute_concurrently("DROP INDEX CONCURRENTLY IF EXISTS ix_messages_id")

    if _table_exists(inspector, "patients"):
        _execute_concurrently(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_patients_doctor_id
            ON patients (doctor_id)
            """
        )

    if _table_exists(inspector, "quiz_sessions"):
        _execute_concurrently("DROP INDEX CONCURRENTLY IF EXISTS ix_quiz_sessions_id")

    if _table_exists(inspector, "quiz_responses"):
        _execute_concurrently("DROP INDEX CONCURRENTLY IF EXISTS ix_quiz_responses_id")


def downgrade() -> None:
    if not _is_postgresql():
        return

    inspector = sa.inspect(op.get_bind())

    if _table_exists(inspector, "messages"):
        _execute_concurrently(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_messages_status_pending_schedule"
        )
        _execute_concurrently(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_messages_outbound_queue_pending"
        )
        _execute_concurrently(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_messages_patient_created_desc"
        )
        _execute_concurrently(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_id ON messages (id)"
        )

    if _table_exists(inspector, "patients"):
        _execute_concurrently("DROP INDEX CONCURRENTLY IF EXISTS ix_patients_doctor_id")

    if _table_exists(inspector, "quiz_sessions"):
        _execute_concurrently(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_quiz_sessions_id ON quiz_sessions (id)"
        )

    if _table_exists(inspector, "quiz_responses"):
        _execute_concurrently(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_quiz_responses_id ON quiz_responses (id)"
        )
