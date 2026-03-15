"""Drop Firebase-prefixed `users` residue from the canonical head.

Revision ID: m006_s02_t03_drop_users_firebase_residue
Revises: m005_s03_t02_align_audit_history_head
Create Date: 2026-03-15 18:05:00.000000

This revision removes the remaining Firebase-prefixed `users` columns and the
legacy `ix_users_firebase_uid` index now that the live runtime is canonical-only
for auth/session/profile state. It intentionally preserves `auth_provider` as a
live boundary and leaves `firebase_sync_history` untouched as the explicit
historical archive.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "m006_s02_t03_drop_users_firebase_residue"
down_revision = "m005_s03_t02_align_audit_history_head"
branch_labels = None
depends_on = None

REMOVED_USERS_COLUMNS = (
    "firebase_uid",
    "firebase_last_sign_in",
    "firebase_created_at",
    "firebase_email_verified",
    "firebase_display_name",
    "firebase_photo_url",
    "firebase_custom_claims",
    "last_firebase_sync",
)


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(bind: sa.engine.Connection, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def _add_column_if_missing(bind: sa.engine.Connection, table_name: str, column: sa.Column) -> None:
    if not _column_exists(bind, table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()

    if _index_exists(bind, "users", "ix_users_firebase_uid"):
        op.drop_index("ix_users_firebase_uid", table_name="users")

    for column_name in REMOVED_USERS_COLUMNS:
        if _column_exists(bind, "users", column_name):
            op.drop_column("users", column_name)


def downgrade() -> None:
    bind = op.get_bind()

    _add_column_if_missing(
        bind,
        "users",
        sa.Column("firebase_uid", sa.String(length=255), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "users",
        sa.Column("firebase_last_sign_in", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "users",
        sa.Column("firebase_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "users",
        sa.Column(
            "firebase_email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    _add_column_if_missing(
        bind,
        "users",
        sa.Column("firebase_display_name", sa.String(length=255), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "users",
        sa.Column("firebase_photo_url", sa.String(length=500), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "users",
        sa.Column(
            "firebase_custom_claims",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    _add_column_if_missing(
        bind,
        "users",
        sa.Column("last_firebase_sync", sa.DateTime(timezone=True), nullable=True),
    )

    if not _index_exists(bind, "users", "ix_users_firebase_uid"):
        op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"], unique=True)
