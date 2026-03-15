"""Align audit/history head with canonical enums and archival residue.

Revision ID: m005_s03_t02_align_audit_history_head
Revises: m005_s03_t01_republish_users_canonical_contract
Create Date: 2026-03-15 17:20:00.000000

This final S03 revision closes the remaining honest-head gaps:
- `users.role` becomes the canonical `user_role` enum on clean replay and upgrades.
- `audit_logs.event_type` becomes the canonical `audit_event_type` enum on both paths.
- `firebase_sync_history` stops carrying transitional live columns and folds any
  preserved legacy values into explicit archival payload inside `changes.historical_shape`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "m005_s03_t02_align_audit_history_head"
down_revision = "m005_s03_t01_republish_users_canonical_contract"
branch_labels = None
depends_on = None

USER_ROLE_VALUES = ("admin", "doctor")
AUDIT_EVENT_TYPE_VALUES = (
    "login_success",
    "login_failure",
    "logout",
    "session_created",
    "session_expired",
    "session_invalidated",
    "token_refresh",
    "access_denied",
    "permission_changed",
    "role_changed",
    "password_changed",
    "password_reset_requested",
    "password_reset_completed",
    "account_locked",
    "account_unlocked",
    "account_disabled",
    "account_enabled",
    "profile_updated",
    "email_changed",
    "suspicious_activity",
    "rate_limit_exceeded",
    "invalid_token",
    "csrf_violation",
    "admin_user_create",
    "admin_user_update",
    "admin_user_delete",
    "admin_dlq_retry",
    "admin_dlq_purge",
    "admin_audit_export",
    "ai_query",
    "ai_humanization",
    "ai_sentiment",
    "ai_follow_up",
)
HISTORICAL_SHAPE_KEY = "historical_shape"


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _column_udt_name(
    bind: sa.engine.Connection,
    table_name: str,
    column_name: str,
) -> str | None:
    return bind.execute(
        sa.text(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar_one_or_none()


def _enum_labels(bind: sa.engine.Connection, enum_name: str) -> list[str]:
    rows = bind.execute(
        sa.text(
            """
            SELECT e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typname = :enum_name
            ORDER BY e.enumsortorder
            """
        ),
        {"enum_name": enum_name},
    ).scalars()
    return list(rows)


def _ensure_enum(bind: sa.engine.Connection, enum_name: str, values: tuple[str, ...]) -> None:
    existing_labels = _enum_labels(bind, enum_name)
    if not existing_labels:
        values_sql = ", ".join(f"'{value}'" for value in values)
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({values_sql})")
        return

    for value in values:
        if value not in existing_labels:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def _upgrade_users_role(bind: sa.engine.Connection) -> None:
    if not _column_exists(bind, "users", "role"):
        return

    _ensure_enum(bind, "user_role", USER_ROLE_VALUES)
    current_udt = _column_udt_name(bind, "users", "role")

    if current_udt != "user_role":
        op.execute(
            """
            ALTER TABLE users
            ALTER COLUMN role TYPE user_role
            USING (
                CASE
                    WHEN role IS NULL THEN 'doctor'::user_role
                    WHEN lower(trim(role::text)) = 'admin' THEN 'admin'::user_role
                    WHEN lower(trim(role::text)) = 'doctor' THEN 'doctor'::user_role
                    ELSE 'doctor'::user_role
                END
            )
            """
        )

    op.execute("UPDATE users SET role = 'doctor'::user_role WHERE role IS NULL")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'doctor'::user_role")
    op.execute("ALTER TABLE users ALTER COLUMN role SET NOT NULL")


def _upgrade_audit_event_type(bind: sa.engine.Connection) -> None:
    if not _column_exists(bind, "audit_logs", "event_type"):
        return

    _ensure_enum(bind, "audit_event_type", AUDIT_EVENT_TYPE_VALUES)
    current_udt = _column_udt_name(bind, "audit_logs", "event_type")
    valid_values_sql = ", ".join(f"'{value}'" for value in AUDIT_EVENT_TYPE_VALUES)

    if current_udt != "audit_event_type":
        op.execute(
            f"""
            ALTER TABLE audit_logs
            ALTER COLUMN event_type TYPE audit_event_type
            USING (
                CASE
                    WHEN event_type IS NULL THEN 'suspicious_activity'::audit_event_type
                    WHEN lower(trim(event_type::text)) IN ({valid_values_sql})
                        THEN lower(trim(event_type::text))::audit_event_type
                    ELSE 'suspicious_activity'::audit_event_type
                END
            )
            """
        )

    op.execute(
        "UPDATE audit_logs SET event_type = 'suspicious_activity'::audit_event_type WHERE event_type IS NULL"
    )
    op.execute("ALTER TABLE audit_logs ALTER COLUMN event_type SET NOT NULL")


def _archive_legacy_sync_shape(bind: sa.engine.Connection) -> None:
    if not _column_exists(bind, "firebase_sync_history", "changes"):
        return

    has_supabase_user_id = _column_exists(bind, "firebase_sync_history", "supabase_user_id")
    has_sync_action = _column_exists(bind, "firebase_sync_history", "sync_action")
    has_sync_status = _column_exists(bind, "firebase_sync_history", "sync_status")

    if has_supabase_user_id or has_sync_action or has_sync_status:
        supabase_expr = (
            "to_jsonb(supabase_user_id::text)" if has_supabase_user_id else "NULL::jsonb"
        )
        sync_action_expr = "to_jsonb(sync_action)" if has_sync_action else "NULL::jsonb"
        sync_status_expr = "to_jsonb(sync_status)" if has_sync_status else "NULL::jsonb"

        op.execute(
            f"""
            WITH archival AS (
                SELECT
                    id,
                    jsonb_strip_nulls(
                        jsonb_build_object(
                            'supabase_user_id', {supabase_expr},
                            'sync_action', {sync_action_expr},
                            'sync_status', {sync_status_expr}
                        )
                    ) AS legacy_payload
                FROM firebase_sync_history
            )
            UPDATE firebase_sync_history AS history
            SET changes = jsonb_set(
                COALESCE(history.changes, '{{}}'::jsonb),
                ARRAY['{HISTORICAL_SHAPE_KEY}'],
                COALESCE(COALESCE(history.changes, '{{}}'::jsonb) -> '{HISTORICAL_SHAPE_KEY}', '{{}}'::jsonb)
                    || archival.legacy_payload,
                true
            )
            FROM archival
            WHERE history.id = archival.id
              AND archival.legacy_payload <> '{{}}'::jsonb
            """
        )

    if has_supabase_user_id:
        op.drop_column("firebase_sync_history", "supabase_user_id")
    if has_sync_action:
        op.drop_column("firebase_sync_history", "sync_action")
    if has_sync_status:
        op.drop_column("firebase_sync_history", "sync_status")


def upgrade() -> None:
    bind = op.get_bind()

    _upgrade_users_role(bind)
    _upgrade_audit_event_type(bind)
    _archive_legacy_sync_shape(bind)


def _downgrade_users_role(bind: sa.engine.Connection) -> None:
    if not _column_exists(bind, "users", "role"):
        return

    if _column_udt_name(bind, "users", "role") == "user_role":
        op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
        op.execute("ALTER TABLE users ALTER COLUMN role DROP NOT NULL")
        op.execute(
            "ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) USING role::text"
        )

    if not bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_type t
            JOIN pg_depend d ON d.refobjid = t.oid
            WHERE t.typname = 'user_role'
            LIMIT 1
            """
        )
    ).scalar_one_or_none():
        op.execute("DROP TYPE IF EXISTS user_role")


def _downgrade_audit_event_type(bind: sa.engine.Connection) -> None:
    if not _column_exists(bind, "audit_logs", "event_type"):
        return

    if _column_udt_name(bind, "audit_logs", "event_type") == "audit_event_type":
        op.execute("ALTER TABLE audit_logs ALTER COLUMN event_type DROP NOT NULL")
        op.execute(
            "ALTER TABLE audit_logs ALTER COLUMN event_type TYPE VARCHAR(100) USING event_type::text"
        )

    if not bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_type t
            JOIN pg_depend d ON d.refobjid = t.oid
            WHERE t.typname = 'audit_event_type'
            LIMIT 1
            """
        )
    ).scalar_one_or_none():
        op.execute("DROP TYPE IF EXISTS audit_event_type")


def _downgrade_sync_history_shape(bind: sa.engine.Connection) -> None:
    if not _column_exists(bind, "firebase_sync_history", "supabase_user_id"):
        op.add_column(
            "firebase_sync_history",
            sa.Column("supabase_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if not _column_exists(bind, "firebase_sync_history", "sync_action"):
        op.add_column(
            "firebase_sync_history",
            sa.Column("sync_action", sa.String(length=50), nullable=True),
        )
    if not _column_exists(bind, "firebase_sync_history", "sync_status"):
        op.add_column(
            "firebase_sync_history",
            sa.Column("sync_status", sa.String(length=50), nullable=True),
        )

    if _column_exists(bind, "firebase_sync_history", "changes"):
        op.execute(
            f"""
            UPDATE firebase_sync_history
            SET supabase_user_id = NULLIF(changes -> '{HISTORICAL_SHAPE_KEY}' ->> 'supabase_user_id', '')::uuid,
                sync_action = changes -> '{HISTORICAL_SHAPE_KEY}' ->> 'sync_action',
                sync_status = changes -> '{HISTORICAL_SHAPE_KEY}' ->> 'sync_status'
            WHERE COALESCE(changes, '{{}}'::jsonb) ? '{HISTORICAL_SHAPE_KEY}'
            """
        )


def downgrade() -> None:
    bind = op.get_bind()

    _downgrade_sync_history_shape(bind)
    _downgrade_audit_event_type(bind)
    _downgrade_users_role(bind)
