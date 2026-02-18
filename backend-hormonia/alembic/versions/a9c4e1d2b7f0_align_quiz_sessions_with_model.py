"""Align quiz_sessions table with SQLAlchemy model columns.

Revision ID: a9c4e1d2b7f0
Revises: f7d2c1b9a4e6
Create Date: 2026-02-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a9c4e1d2b7f0"
down_revision = "f7d2c1b9a4e6"
branch_labels = None
depends_on = None


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def _index_exists(bind: sa.engine.Connection, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def _fk_exists(bind: sa.engine.Connection, table_name: str, fk_name: str) -> bool:
    inspector = sa.inspect(bind)
    fks = inspector.get_foreign_keys(table_name)
    return any(fk.get("name") == fk_name for fk in fks)


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, "quiz_sessions", "quiz_template_id"):
        op.add_column("quiz_sessions", sa.Column("quiz_template_id", sa.UUID(), nullable=True))

    if not _column_exists(bind, "quiz_sessions", "current_question"):
        op.add_column("quiz_sessions", sa.Column("current_question", sa.Integer(), nullable=True))

    if not _column_exists(bind, "quiz_sessions", "total_questions"):
        op.add_column("quiz_sessions", sa.Column("total_questions", sa.Integer(), nullable=True))

    if not _column_exists(bind, "quiz_sessions", "answered_questions"):
        op.add_column(
            "quiz_sessions",
            sa.Column("answered_questions", sa.Integer(), nullable=True, server_default=sa.text("0")),
        )

    if not _column_exists(bind, "quiz_sessions", "score"):
        op.add_column("quiz_sessions", sa.Column("score", sa.Numeric(5, 2), nullable=True))

    if not _column_exists(bind, "quiz_sessions", "max_score"):
        op.add_column("quiz_sessions", sa.Column("max_score", sa.Numeric(5, 2), nullable=True))

    if not _column_exists(bind, "quiz_sessions", "passed"):
        op.add_column("quiz_sessions", sa.Column("passed", sa.Boolean(), nullable=True))

    if not _column_exists(bind, "quiz_sessions", "completed_at"):
        op.add_column("quiz_sessions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    if not _column_exists(bind, "quiz_sessions", "time_spent_seconds"):
        op.add_column("quiz_sessions", sa.Column("time_spent_seconds", sa.Integer(), nullable=True))

    if not _column_exists(bind, "quiz_sessions", "session_metadata"):
        op.add_column(
            "quiz_sessions",
            sa.Column(
                "session_metadata",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    if not _fk_exists(bind, "quiz_sessions", "quiz_sessions_quiz_template_id_fkey"):
        op.create_foreign_key(
            "quiz_sessions_quiz_template_id_fkey",
            "quiz_sessions",
            "quiz_templates",
            ["quiz_template_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    if not _index_exists(bind, "quiz_sessions", "idx_quiz_sessions_quiz_template_id_v2"):
        op.create_index(
            "idx_quiz_sessions_quiz_template_id_v2",
            "quiz_sessions",
            ["quiz_template_id"],
            unique=False,
        )

    if not _index_exists(bind, "quiz_sessions", "idx_quiz_sessions_template_status_v2"):
        op.create_index(
            "idx_quiz_sessions_template_status_v2",
            "quiz_sessions",
            ["quiz_template_id", "status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _index_exists(bind, "quiz_sessions", "idx_quiz_sessions_template_status_v2"):
        op.drop_index("idx_quiz_sessions_template_status_v2", table_name="quiz_sessions")
    if _index_exists(bind, "quiz_sessions", "idx_quiz_sessions_quiz_template_id_v2"):
        op.drop_index("idx_quiz_sessions_quiz_template_id_v2", table_name="quiz_sessions")

    if _fk_exists(bind, "quiz_sessions", "quiz_sessions_quiz_template_id_fkey"):
        op.drop_constraint("quiz_sessions_quiz_template_id_fkey", "quiz_sessions", type_="foreignkey")

    if _column_exists(bind, "quiz_sessions", "session_metadata"):
        op.drop_column("quiz_sessions", "session_metadata")
    if _column_exists(bind, "quiz_sessions", "time_spent_seconds"):
        op.drop_column("quiz_sessions", "time_spent_seconds")
    if _column_exists(bind, "quiz_sessions", "completed_at"):
        op.drop_column("quiz_sessions", "completed_at")
    if _column_exists(bind, "quiz_sessions", "passed"):
        op.drop_column("quiz_sessions", "passed")
    if _column_exists(bind, "quiz_sessions", "max_score"):
        op.drop_column("quiz_sessions", "max_score")
    if _column_exists(bind, "quiz_sessions", "score"):
        op.drop_column("quiz_sessions", "score")
    if _column_exists(bind, "quiz_sessions", "answered_questions"):
        op.drop_column("quiz_sessions", "answered_questions")
    if _column_exists(bind, "quiz_sessions", "total_questions"):
        op.drop_column("quiz_sessions", "total_questions")
    if _column_exists(bind, "quiz_sessions", "current_question"):
        op.drop_column("quiz_sessions", "current_question")
    if _column_exists(bind, "quiz_sessions", "quiz_template_id"):
        op.drop_column("quiz_sessions", "quiz_template_id")
