"""Add account security fields and indexes for users.

Revision ID: 98ba470eed4a
Revises: f16b221d27ad
Create Date: 2026-01-09

Migrates ad-hoc account security SQL into Alembic-managed changes.

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
revision = "98ba470eed4a"
down_revision = "f16b221d27ad"
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


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "users"):
        return

    if not _column_exists(bind, "users", "failed_login_attempts"):
        op.add_column(
            "users",
            sa.Column(
                "failed_login_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )

    if not _column_exists(bind, "users", "is_locked"):
        op.add_column(
            "users",
            sa.Column(
                "is_locked",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if not _column_exists(bind, "users", "locked_until"):
        op.add_column(
            "users",
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        )

    if not _column_exists(bind, "users", "force_change_password"):
        op.add_column(
            "users",
            sa.Column(
                "force_change_password",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if not _column_exists(bind, "users", "last_password_change"):
        op.add_column(
            "users",
            sa.Column("last_password_change", sa.DateTime(timezone=True), nullable=True),
        )

    if not _index_exists(bind, "users", "idx_users_locked"):
        op.create_index(
            "idx_users_locked",
            "users",
            ["is_locked"],
            postgresql_where=sa.text("is_locked = true"),
        )

    if not _index_exists(bind, "users", "idx_users_locked_until"):
        op.create_index(
            "idx_users_locked_until",
            "users",
            ["locked_until"],
            postgresql_where=sa.text("locked_until IS NOT NULL"),
        )

    if _is_postgres(bind):
        if _column_exists(bind, "users", "failed_login_attempts"):
            op.execute(
                "COMMENT ON COLUMN users.failed_login_attempts IS "
                "'Counter for failed login attempts (resets on successful login)'"
            )
        if _column_exists(bind, "users", "is_locked"):
            op.execute(
                "COMMENT ON COLUMN users.is_locked IS "
                "'Whether the account is currently locked'"
            )
        if _column_exists(bind, "users", "locked_until"):
            op.execute(
                "COMMENT ON COLUMN users.locked_until IS "
                "'Timestamp until which the account is locked (NULL = permanent lock)'"
            )
        if _column_exists(bind, "users", "force_change_password"):
            op.execute(
                "COMMENT ON COLUMN users.force_change_password IS "
                "'Whether user must change password on next login'"
            )
        if _column_exists(bind, "users", "last_password_change"):
            op.execute(
                "COMMENT ON COLUMN users.last_password_change IS "
                "'Timestamp of last password change'"
            )


def downgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "users"):
        return

    if _index_exists(bind, "users", "idx_users_locked_until"):
        op.drop_index("idx_users_locked_until", table_name="users")

    if _index_exists(bind, "users", "idx_users_locked"):
        op.drop_index("idx_users_locked", table_name="users")

    if _column_exists(bind, "users", "last_password_change"):
        op.drop_column("users", "last_password_change")
    if _column_exists(bind, "users", "force_change_password"):
        op.drop_column("users", "force_change_password")
    if _column_exists(bind, "users", "locked_until"):
        op.drop_column("users", "locked_until")
    if _column_exists(bind, "users", "is_locked"):
        op.drop_column("users", "is_locked")
    if _column_exists(bind, "users", "failed_login_attempts"):
        op.drop_column("users", "failed_login_attempts")
