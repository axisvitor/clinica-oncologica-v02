"""Canonicalize message enums and remove legacy message columns.

Revision ID: c5a9e3d2b7f1
Revises: ab1c2d3e4f55
Create Date: 2026-02-13
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c5a9e3d2b7f1"
down_revision = "ab1c2d3e4f55"
branch_labels = None
depends_on = None


MESSAGE_STATUS_VALUES = (
    "pending",
    "scheduled",
    "sending",
    "sent",
    "delivered",
    "read",
    "failed",
    "cancelled",
)

CANONICAL_ENUMS: dict[str, tuple[str, ...]] = {
    "message_direction": ("inbound", "outbound"),
    "messagetype": (
        "text",
        "image",
        "audio",
        "video",
        "document",
        "button",
        "list",
        "media",
        "location",
        "quiz_intro",
        "quiz_question",
        "quiz_encouragement",
        "quiz_completion",
        "monthly_quiz_link",
        "monthly_quiz_reminder",
        "monthly_quiz_expired",
        "monthly_quiz_completed",
    ),
    "message_delivery_status": (
        "scheduled",
        "queued",
        "sending",
        "sent",
        "delivered",
        "read",
        "failed",
        "cancelled",
    ),
    "message_status": MESSAGE_STATUS_VALUES,
}

ENUM_FALLBACK: dict[str, str] = {
    "message_direction": "outbound",
    "messagetype": "text",
    "message_delivery_status": "scheduled",
    "message_status": "pending",
}

_DEFAULT_LABEL_RE = re.compile(r"'([^']+)'")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _quote_table(schema: str, table: str) -> str:
    return f"{_quote_ident(schema)}.{_quote_ident(table)}"


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def _enum_exists(bind: sa.engine.Connection, enum_name: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_type WHERE typname = :enum_name"),
            {"enum_name": enum_name},
        ).scalar()
    )


def _index_exists(bind: sa.engine.Connection, *, schema: str, index_name: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = :schema
                  AND indexname = :index_name
                """
            ),
            {"schema": schema, "index_name": index_name},
        ).scalar()
    )


def _enum_columns(bind: sa.engine.Connection, enum_name: str) -> list[dict[str, str | None]]:
    rows = bind.execute(
        sa.text(
            """
            SELECT
                table_schema,
                table_name,
                column_name,
                column_default
            FROM information_schema.columns
            WHERE udt_name = :enum_name
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name, ordinal_position
            """
        ),
        {"enum_name": enum_name},
    ).fetchall()
    return [
        {
            "table_schema": str(row[0]),
            "table_name": str(row[1]),
            "column_name": str(row[2]),
            "column_default": str(row[3]) if row[3] is not None else None,
        }
        for row in rows
    ]


def _extract_default_label(default_expr: str | None) -> str | None:
    if not default_expr:
        return None
    match = _DEFAULT_LABEL_RE.search(default_expr)
    if not match:
        return None
    return match.group(1).strip().lower()


def _canonicalize_enum_type(
    bind: sa.engine.Connection,
    *,
    enum_name: str,
    labels: Sequence[str],
    fallback: str,
) -> None:
    if not _enum_exists(bind, enum_name):
        return

    tmp_enum_name = f"{enum_name}_tmp_canonical"
    if _enum_exists(bind, tmp_enum_name):
        op.execute(sa.text(f"DROP TYPE {_quote_ident(tmp_enum_name)}"))

    labels_sql = ", ".join(f"'{label}'" for label in labels)
    op.execute(
        sa.text(f"CREATE TYPE {_quote_ident(tmp_enum_name)} AS ENUM ({labels_sql})")
    )

    allowed_sql = ", ".join(f"'{label}'" for label in labels)
    columns = _enum_columns(bind, enum_name)
    pending_defaults: list[tuple[str, str, str]] = []

    for item in columns:
        schema = item["table_schema"] or "public"
        table_name = item["table_name"] or ""
        column_name = item["column_name"] or ""
        table_ref = _quote_table(schema, table_name)
        column_ref = _quote_ident(column_name)
        tmp_enum_ref = _quote_ident(tmp_enum_name)

        default_label = _extract_default_label(item["column_default"])
        if default_label:
            if default_label not in labels:
                default_label = fallback
            pending_defaults.append((table_ref, column_ref, default_label))

        op.execute(
            sa.text(
                f"ALTER TABLE {table_ref} "
                f"ALTER COLUMN {column_ref} DROP DEFAULT"
            )
        )
        op.execute(
            sa.text(
                f"""
                ALTER TABLE {table_ref}
                ALTER COLUMN {column_ref}
                TYPE {tmp_enum_ref}
                USING (
                    CASE
                        WHEN {column_ref} IS NULL THEN NULL
                        WHEN lower({column_ref}::text) IN ({allowed_sql})
                            THEN lower({column_ref}::text):: {tmp_enum_ref}
                        ELSE '{fallback}'::{tmp_enum_ref}
                    END
                )
                """
            )
        )

    op.execute(sa.text(f"DROP TYPE {_quote_ident(enum_name)}"))
    op.execute(
        sa.text(
            f"ALTER TYPE {_quote_ident(tmp_enum_name)} RENAME TO {_quote_ident(enum_name)}"
        )
    )

    final_enum_ref = _quote_ident(enum_name)
    for table_ref, column_ref, default_label in pending_defaults:
        op.execute(
            sa.text(
                f"ALTER TABLE {table_ref} ALTER COLUMN {column_ref} "
                f"SET DEFAULT '{default_label}'::{final_enum_ref}"
            )
        )


def _normalize_messages_status_column(bind: sa.engine.Connection) -> None:
    row = bind.execute(
        sa.text(
            """
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'messages'
              AND column_name = 'status'
            """
        )
    ).fetchone()
    if not row:
        return

    data_type = str(row[0]).lower()
    udt_name = str(row[1]).lower()
    if udt_name == "message_status":
        return
    if data_type not in {"character varying", "text"}:
        return

    dropped_pending_schedule_index = False
    if _index_exists(
        bind,
        schema="public",
        index_name="ix_messages_status_pending_schedule",
    ):
        op.execute(sa.text('DROP INDEX IF EXISTS "public"."ix_messages_status_pending_schedule"'))
        dropped_pending_schedule_index = True

    allowed_sql = ", ".join(f"'{label}'" for label in MESSAGE_STATUS_VALUES)
    fallback = "pending"
    op.execute(
        sa.text(
            f"""
            UPDATE "public"."messages"
            SET "status" = CASE
                WHEN "status" IS NULL OR btrim("status") = '' THEN '{fallback}'
                WHEN lower("status") IN ({allowed_sql}) THEN lower("status")
                ELSE '{fallback}'
            END
            """
        )
    )
    op.execute(sa.text('ALTER TABLE "public"."messages" ALTER COLUMN "status" DROP DEFAULT'))
    op.execute(
        sa.text(
            """
            ALTER TABLE "public"."messages"
            ALTER COLUMN "status"
            TYPE "message_status"
            USING "status"::"message_status"
            """
        )
    )

    if dropped_pending_schedule_index:
        op.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_messages_status_pending_schedule
                ON "public"."messages" ("status", "scheduled_for")
                WHERE "status" IN (
                    'pending'::"message_status",
                    'scheduled'::"message_status",
                    'failed'::"message_status"
                )
                """
            )
        )
    op.execute(
        sa.text(
            """
            ALTER TABLE "public"."messages"
            ALTER COLUMN "status"
            SET DEFAULT 'pending'::"message_status"
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE "public"."messages"
            ALTER COLUMN "status"
            SET NOT NULL
            """
        )
    )


def _drop_legacy_messages_columns(bind: sa.engine.Connection) -> None:
    if _column_exists(bind, "messages", "message_type"):
        op.drop_column("messages", "message_type")


def upgrade() -> None:
    bind = op.get_bind()

    for enum_name, labels in CANONICAL_ENUMS.items():
        _canonicalize_enum_type(
            bind,
            enum_name=enum_name,
            labels=labels,
            fallback=ENUM_FALLBACK[enum_name],
        )

    _normalize_messages_status_column(bind)
    _drop_legacy_messages_columns(bind)


def downgrade() -> None:
    # Canonicalization is intentionally one-way to prevent reintroducing legacy states.
    pass
