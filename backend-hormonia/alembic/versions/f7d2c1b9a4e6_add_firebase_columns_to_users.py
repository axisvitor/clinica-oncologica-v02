"""Add missing Firebase/auth columns to users table.

Revision ID: f7d2c1b9a4e6
Revises: c5a9e3d2b7f1
Create Date: 2026-02-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f7d2c1b9a4e6"
down_revision = "c5a9e3d2b7f1"
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


def upgrade() -> None:
    bind = op.get_bind()

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'auth_provider') THEN
                    CREATE TYPE auth_provider AS ENUM ('local', 'firebase');
                END IF;
            END $$;
            """
        )
    )

    if not _column_exists(bind, "users", "firebase_uid"):
        op.add_column("users", sa.Column("firebase_uid", sa.String(length=255), nullable=True))
    if not _index_exists(bind, "users", "ix_users_firebase_uid"):
        op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"], unique=True)

    if not _column_exists(bind, "users", "auth_provider"):
        op.add_column(
            "users",
            sa.Column(
                "auth_provider",
                sa.Enum("local", "firebase", name="auth_provider", native_enum=True, create_type=False),
                nullable=False,
                server_default=sa.text("'local'::auth_provider"),
            ),
        )

    if not _column_exists(bind, "users", "firebase_last_sign_in"):
        op.add_column("users", sa.Column("firebase_last_sign_in", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "users", "firebase_created_at"):
        op.add_column("users", sa.Column("firebase_created_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "users", "firebase_email_verified"):
        op.add_column(
            "users",
            sa.Column("firebase_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _column_exists(bind, "users", "firebase_display_name"):
        op.add_column("users", sa.Column("firebase_display_name", sa.String(length=255), nullable=True))
    if not _column_exists(bind, "users", "firebase_photo_url"):
        op.add_column("users", sa.Column("firebase_photo_url", sa.String(length=500), nullable=True))
    if not _column_exists(bind, "users", "firebase_custom_claims"):
        op.add_column(
            "users",
            sa.Column(
                "firebase_custom_claims",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    if not _column_exists(bind, "users", "last_firebase_sync"):
        op.add_column("users", sa.Column("last_firebase_sync", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    if _column_exists(bind, "users", "last_firebase_sync"):
        op.drop_column("users", "last_firebase_sync")
    if _column_exists(bind, "users", "firebase_custom_claims"):
        op.drop_column("users", "firebase_custom_claims")
    if _column_exists(bind, "users", "firebase_photo_url"):
        op.drop_column("users", "firebase_photo_url")
    if _column_exists(bind, "users", "firebase_display_name"):
        op.drop_column("users", "firebase_display_name")
    if _column_exists(bind, "users", "firebase_email_verified"):
        op.drop_column("users", "firebase_email_verified")
    if _column_exists(bind, "users", "firebase_created_at"):
        op.drop_column("users", "firebase_created_at")
    if _column_exists(bind, "users", "firebase_last_sign_in"):
        op.drop_column("users", "firebase_last_sign_in")
    if _column_exists(bind, "users", "auth_provider"):
        op.drop_column("users", "auth_provider")

    if _index_exists(bind, "users", "ix_users_firebase_uid"):
        op.drop_index("ix_users_firebase_uid", table_name="users")
    if _column_exists(bind, "users", "firebase_uid"):
        op.drop_column("users", "firebase_uid")

    op.execute(sa.text("DROP TYPE IF EXISTS auth_provider"))
