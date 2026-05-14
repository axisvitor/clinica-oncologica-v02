"""Align notifications table with profile endpoint model contract.

Revision ID: m015_s02_notifications_profile_contract
Revises: m013_s04_upload_deleted_at
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "m015_s02_notifications_profile_contract"
down_revision = "m013_s04_upload_deleted_at"
branch_labels = None
depends_on = None


NOTIFICATION_TYPE_VALUES = ("INFO", "WARNING", "ERROR", "SUCCESS", "ALERT", "REMINDER")
NOTIFICATION_PRIORITY_VALUES = ("LOW", "MEDIUM", "HIGH", "URGENT")


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    return any(col["name"] == column_name for col in sa.inspect(bind).get_columns(table_name))


def _index_exists(bind: sa.engine.Connection, table_name: str, index_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    return any(idx.get("name") == index_name for idx in sa.inspect(bind).get_indexes(table_name))


def _ensure_enum_types(bind: sa.engine.Connection) -> None:
    sa.Enum(*NOTIFICATION_TYPE_VALUES, name="notificationtype").create(bind, checkfirst=True)
    sa.Enum(*NOTIFICATION_PRIORITY_VALUES, name="notificationpriority").create(bind, checkfirst=True)


def _create_notifications_table() -> None:
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
        sa.Column(
            "notification_type",
            sa.Enum(*NOTIFICATION_TYPE_VALUES, name="notificationtype", native_enum=True, create_type=False),
            nullable=False,
            server_default=sa.text("'INFO'"),
        ),
        sa.Column(
            "priority",
            sa.Enum(*NOTIFICATION_PRIORITY_VALUES, name="notificationpriority", native_enum=True, create_type=False),
            nullable=False,
            server_default=sa.text("'MEDIUM'"),
        ),
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("action_url", sa.String(length=500), nullable=True),
        sa.Column("action_label", sa.String(length=100), nullable=True),
        sa.Column("notification_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="notifications_user_id_fkey", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["related_patient_id"],
            ["patients.id"],
            name="notifications_related_patient_id_fkey",
            ondelete="CASCADE",
        ),
    )


def _add_column_if_missing(bind: sa.engine.Connection, column: sa.Column) -> None:
    if not _column_exists(bind, "notifications", column.name):
        op.add_column("notifications", column)


def _create_index_if_missing(bind: sa.engine.Connection, name: str, columns: list[str]) -> None:
    if not _index_exists(bind, "notifications", name):
        op.create_index(name, "notifications", columns, unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_enum_types(bind)

    if not _table_exists(bind, "notifications"):
        _create_notifications_table()
    else:
        _add_column_if_missing(
            bind,
            sa.Column(
                "notification_type",
                sa.Enum(*NOTIFICATION_TYPE_VALUES, name="notificationtype", native_enum=True, create_type=False),
                nullable=False,
                server_default=sa.text("'INFO'"),
            ),
        )
        _add_column_if_missing(
            bind,
            sa.Column(
                "priority",
                sa.Enum(*NOTIFICATION_PRIORITY_VALUES, name="notificationpriority", native_enum=True, create_type=False),
                nullable=False,
                server_default=sa.text("'MEDIUM'"),
            ),
        )
        _add_column_if_missing(bind, sa.Column("title", sa.String(length=200), nullable=False, server_default=""))
        _add_column_if_missing(bind, sa.Column("message", sa.Text(), nullable=False, server_default=""))
        _add_column_if_missing(bind, sa.Column("action_url", sa.String(length=500), nullable=True))
        _add_column_if_missing(bind, sa.Column("action_label", sa.String(length=100), nullable=True))
        _add_column_if_missing(
            bind,
            sa.Column("notification_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        _add_column_if_missing(bind, sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing(bind, sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        _add_column_if_missing(bind, sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing(bind, sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))

    _create_index_if_missing(bind, "ix_notifications_user_id", ["user_id"])
    _create_index_if_missing(bind, "ix_notifications_related_patient_id", ["related_patient_id"])
    _create_index_if_missing(bind, "ix_notifications_notification_type", ["notification_type"])
    _create_index_if_missing(bind, "ix_notifications_priority", ["priority"])
    _create_index_if_missing(bind, "ix_notifications_is_read", ["is_read"])
    _create_index_if_missing(bind, "ix_notifications_is_archived", ["is_archived"])
    _create_index_if_missing(bind, "ix_notifications_expires_at", ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "notifications"):
        return

    for index_name in (
        "ix_notifications_expires_at",
        "ix_notifications_is_archived",
        "ix_notifications_is_read",
        "ix_notifications_priority",
        "ix_notifications_notification_type",
        "ix_notifications_related_patient_id",
        "ix_notifications_user_id",
    ):
        if _index_exists(bind, "notifications", index_name):
            op.drop_index(index_name, table_name="notifications")

    for column_name in (
        "expires_at",
        "archived_at",
        "is_archived",
        "read_at",
        "notification_metadata",
        "action_label",
        "action_url",
        "message",
        "title",
        "priority",
        "notification_type",
    ):
        if _column_exists(bind, "notifications", column_name):
            op.drop_column("notifications", column_name)

    sa.Enum(*NOTIFICATION_PRIORITY_VALUES, name="notificationpriority").drop(bind, checkfirst=True)
    sa.Enum(*NOTIFICATION_TYPE_VALUES, name="notificationtype").drop(bind, checkfirst=True)
