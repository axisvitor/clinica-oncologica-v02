"""Republish live users contract under canonical storage.

Revision ID: m005_s03_t01_republish_users_canonical_contract
Revises: m005_s02_t01_publish_firebase_history_boundary
Create Date: 2026-03-15 16:35:00.000000

This revision keeps Firebase-era linkage/history columns intact for compatibility, but
republishes the still-live login/profile/settings data under neutral names in `users`.
It is intentionally idempotent so both clean replay and upgrades from the S02 head can
land on the same canonical live storage.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "m005_s03_t01_republish_users_canonical_contract"
down_revision = "m005_s02_t01_publish_firebase_history_boundary"
branch_labels = None
depends_on = None


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def _add_column_if_missing(bind: sa.engine.Connection, table_name: str, column: sa.Column) -> None:
    if not _column_exists(bind, table_name, column.name):
        op.add_column(table_name, column)


def _backfill_scalar_from_legacy(bind: sa.engine.Connection) -> None:
    statements = (
        """
        UPDATE users
        SET last_login = firebase_last_sign_in
        WHERE last_login IS NULL AND firebase_last_sign_in IS NOT NULL
        """,
        """
        UPDATE users
        SET auth_created_at = firebase_created_at
        WHERE auth_created_at IS NULL AND firebase_created_at IS NOT NULL
        """,
        """
        UPDATE users
        SET display_name = COALESCE(firebase_display_name, full_name)
        WHERE display_name IS NULL
          AND (firebase_display_name IS NOT NULL OR full_name IS NOT NULL)
        """,
        """
        UPDATE users
        SET photo_url = firebase_photo_url
        WHERE photo_url IS NULL AND firebase_photo_url IS NOT NULL
        """,
        """
        UPDATE users
        SET specialty = COALESCE(
            firebase_custom_claims ->> 'specialty',
            CASE
                WHEN jsonb_typeof(firebase_custom_claims -> 'specialties') = 'array'
                     AND jsonb_array_length(firebase_custom_claims -> 'specialties') > 0
                THEN firebase_custom_claims -> 'specialties' ->> 0
                ELSE NULL
            END
        )
        WHERE specialty IS NULL AND firebase_custom_claims IS NOT NULL
        """,
        """
        UPDATE users
        SET license_number = firebase_custom_claims ->> 'license_number'
        WHERE license_number IS NULL
          AND firebase_custom_claims IS NOT NULL
          AND firebase_custom_claims ? 'license_number'
        """,
        """
        UPDATE users
        SET phone = firebase_custom_claims ->> 'phone'
        WHERE phone IS NULL
          AND firebase_custom_claims IS NOT NULL
          AND firebase_custom_claims ? 'phone'
        """,
        """
        UPDATE users
        SET bio = firebase_custom_claims ->> 'bio'
        WHERE bio IS NULL
          AND firebase_custom_claims IS NOT NULL
          AND firebase_custom_claims ? 'bio'
        """,
        """
        UPDATE users
        SET avatar_url = firebase_custom_claims ->> 'avatar_url'
        WHERE avatar_url IS NULL
          AND firebase_custom_claims IS NOT NULL
          AND firebase_custom_claims ? 'avatar_url'
        """,
    )
    for statement in statements:
        bind.execute(sa.text(statement))


def _backfill_jsonb_from_legacy(bind: sa.engine.Connection) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE users
            SET preferences = CASE
                WHEN firebase_custom_claims IS NOT NULL
                     AND jsonb_typeof(firebase_custom_claims) = 'object'
                     AND jsonb_typeof(firebase_custom_claims -> 'preferences') = 'object'
                THEN firebase_custom_claims -> 'preferences'
                ELSE '{}'::jsonb
            END
            WHERE preferences IS NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE users
            SET specialties = CASE
                WHEN firebase_custom_claims IS NOT NULL
                     AND jsonb_typeof(firebase_custom_claims) = 'object'
                     AND jsonb_typeof(firebase_custom_claims -> 'specialties') = 'array'
                THEN firebase_custom_claims -> 'specialties'
                WHEN firebase_custom_claims IS NOT NULL
                     AND jsonb_typeof(firebase_custom_claims) = 'object'
                     AND jsonb_typeof(firebase_custom_claims -> 'specialty') = 'string'
                THEN jsonb_build_array(firebase_custom_claims ->> 'specialty')
                ELSE '[]'::jsonb
            END
            WHERE specialties IS NULL
            """
        )
    )


def _harden_defaults(bind: sa.engine.Connection) -> None:
    bind.execute(sa.text("UPDATE users SET email_verified = COALESCE(email_verified, firebase_email_verified, false) WHERE email_verified IS NULL"))
    bind.execute(sa.text("UPDATE users SET preferences = '{}'::jsonb WHERE preferences IS NULL"))
    bind.execute(sa.text("UPDATE users SET specialties = '[]'::jsonb WHERE specialties IS NULL"))

    op.execute("ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT false")
    op.execute("ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN preferences SET DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE users ALTER COLUMN preferences SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN specialties SET DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE users ALTER COLUMN specialties SET NOT NULL")


def upgrade() -> None:
    bind = op.get_bind()

    _add_column_if_missing(bind, "users", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(bind, "users", sa.Column("auth_created_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(bind, "users", sa.Column("email_verified", sa.Boolean(), nullable=True))
    _add_column_if_missing(bind, "users", sa.Column("display_name", sa.String(length=255), nullable=True))
    _add_column_if_missing(bind, "users", sa.Column("photo_url", sa.String(length=500), nullable=True))
    _add_column_if_missing(
        bind,
        "users",
        sa.Column("preferences", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    _add_column_if_missing(bind, "users", sa.Column("specialty", sa.String(length=255), nullable=True))
    _add_column_if_missing(
        bind,
        "users",
        sa.Column("specialties", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    _add_column_if_missing(bind, "users", sa.Column("license_number", sa.String(length=50), nullable=True))
    _add_column_if_missing(bind, "users", sa.Column("phone", sa.String(length=32), nullable=True))
    _add_column_if_missing(bind, "users", sa.Column("bio", sa.Text(), nullable=True))
    _add_column_if_missing(bind, "users", sa.Column("avatar_url", sa.String(length=500), nullable=True))

    _backfill_scalar_from_legacy(bind)
    _backfill_jsonb_from_legacy(bind)
    _harden_defaults(bind)


def downgrade() -> None:
    bind = op.get_bind()

    for column_name in (
        "avatar_url",
        "bio",
        "phone",
        "license_number",
        "specialties",
        "specialty",
        "preferences",
        "photo_url",
        "display_name",
        "email_verified",
        "auth_created_at",
        "last_login",
    ):
        if _column_exists(bind, "users", column_name):
            op.drop_column("users", column_name)
