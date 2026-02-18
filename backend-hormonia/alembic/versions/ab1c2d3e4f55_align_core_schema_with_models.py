"""Align core tables with SQLAlchemy models (patients/messages/flow templates).

Revision ID: ab1c2d3e4f55
Revises: 9b4e2d1c7f66
Create Date: 2026-02-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "ab1c2d3e4f55"
down_revision = "9b4e2d1c7f66"
branch_labels = None
depends_on = None


MESSAGE_TYPE_VALUES = (
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
)

MESSAGE_TYPE_VALUES_UPPER = tuple(value.upper() for value in MESSAGE_TYPE_VALUES)

MESSAGE_DIRECTION_VALUES = ("inbound", "outbound")
MESSAGE_DIRECTION_VALUES_UPPER = tuple(value.upper() for value in MESSAGE_DIRECTION_VALUES)

MESSAGE_DELIVERY_STATUS_VALUES = (
    "scheduled",
    "queued",
    "sending",
    "sent",
    "delivered",
    "read",
    "failed",
    "cancelled",
)
MESSAGE_DELIVERY_STATUS_VALUES_UPPER = tuple(
    value.upper() for value in MESSAGE_DELIVERY_STATUS_VALUES
)


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def _index_exists(bind: sa.engine.Connection, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def _enum_values(bind: sa.engine.Connection, enum_name: str) -> set[str]:
    rows = bind.execute(
        sa.text(
            """
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = :enum_name
            """
        ),
        {"enum_name": enum_name},
    ).fetchall()
    return {str(row[0]) for row in rows}


def _ensure_enum_values(bind: sa.engine.Connection, enum_name: str, values: tuple[str, ...]) -> None:
    existing = _enum_values(bind, enum_name)
    for value in values:
        if value in existing:
            continue
        op.execute(sa.text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))
        existing.add(value)


def _ensure_enum_types(bind: sa.engine.Connection) -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_direction') THEN
                    CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');
                END IF;
            END $$;
            """
        )
    )
    _ensure_enum_values(bind, "message_direction", MESSAGE_DIRECTION_VALUES_UPPER)
    _ensure_enum_values(bind, "message_direction", MESSAGE_DIRECTION_VALUES)

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'messagetype') THEN
                    CREATE TYPE messagetype AS ENUM (
                        'text',
                        'image',
                        'audio',
                        'video',
                        'document',
                        'button',
                        'list',
                        'media',
                        'location',
                        'quiz_intro',
                        'quiz_question',
                        'quiz_encouragement',
                        'quiz_completion',
                        'monthly_quiz_link',
                        'monthly_quiz_reminder',
                        'monthly_quiz_expired',
                        'monthly_quiz_completed'
                    );
                END IF;
            END $$;
            """
        )
    )
    _ensure_enum_values(bind, "messagetype", MESSAGE_TYPE_VALUES_UPPER)
    _ensure_enum_values(bind, "messagetype", MESSAGE_TYPE_VALUES)

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_delivery_status') THEN
                    CREATE TYPE message_delivery_status AS ENUM (
                        'scheduled',
                        'queued',
                        'sending',
                        'sent',
                        'delivered',
                        'read',
                        'failed',
                        'cancelled'
                    );
                END IF;
            END $$;
            """
        )
    )
    _ensure_enum_values(bind, "message_delivery_status", MESSAGE_DELIVERY_STATUS_VALUES_UPPER)
    _ensure_enum_values(bind, "message_delivery_status", MESSAGE_DELIVERY_STATUS_VALUES)


def _align_patients_table(bind: sa.engine.Connection) -> None:
    if not _column_exists(bind, "patients", "diagnosis"):
        op.add_column("patients", sa.Column("diagnosis", sa.Text(), nullable=True))
        op.create_index("ix_patients_diagnosis", "patients", ["diagnosis"], unique=False)

    if not _column_exists(bind, "patients", "treatment_phase"):
        op.add_column(
            "patients", sa.Column("treatment_phase", sa.String(length=100), nullable=True)
        )
        op.create_index(
            "ix_patients_treatment_phase", "patients", ["treatment_phase"], unique=False
        )

    if not _column_exists(bind, "patients", "doctor_notes"):
        op.add_column("patients", sa.Column("doctor_notes", sa.Text(), nullable=True))


def _align_flow_template_versions_table(bind: sa.engine.Connection) -> None:
    if not _column_exists(bind, "flow_template_versions", "created_by"):
        op.add_column(
            "flow_template_versions",
            sa.Column("created_by", sa.UUID(), nullable=True),
        )

    if not _column_exists(bind, "flow_template_versions", "published_at"):
        op.add_column(
            "flow_template_versions",
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _column_exists(bind, "flow_template_versions", "deprecated_at"):
        op.add_column(
            "flow_template_versions",
            sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        )


def _align_messages_table(bind: sa.engine.Connection) -> None:
    _ensure_enum_types(bind)

    if not _column_exists(bind, "messages", "type"):
        op.add_column(
            "messages",
            sa.Column(
                "type",
                sa.Enum(
                    *MESSAGE_TYPE_VALUES,
                    name="messagetype",
                    native_enum=True,
                    create_type=False,
                    validate_strings=True,
                ),
                nullable=True,
            ),
        )
        if _column_exists(bind, "messages", "message_type"):
            op.execute(
                sa.text(
                    """
                    UPDATE messages
                    SET type = COALESCE(
                        type,
                        CASE
                            WHEN message_type IS NULL OR btrim(message_type) = '' THEN 'text'::messagetype
                            WHEN lower(message_type) IN (
                                'text',
                                'image',
                                'audio',
                                'video',
                                'document',
                                'button',
                                'list',
                                'media',
                                'location',
                                'quiz_intro',
                                'quiz_question',
                                'quiz_encouragement',
                                'quiz_completion',
                                'monthly_quiz_link',
                                'monthly_quiz_reminder',
                                'monthly_quiz_expired',
                                'monthly_quiz_completed'
                            ) THEN CAST(lower(message_type) AS messagetype)
                            WHEN upper(message_type) IN (
                                'TEXT',
                                'IMAGE',
                                'AUDIO',
                                'VIDEO',
                                'DOCUMENT',
                                'BUTTON',
                                'LIST',
                                'MEDIA',
                                'LOCATION',
                                'QUIZ_INTRO',
                                'QUIZ_QUESTION',
                                'QUIZ_ENCOURAGEMENT',
                                'QUIZ_COMPLETION',
                                'MONTHLY_QUIZ_LINK',
                                'MONTHLY_QUIZ_REMINDER',
                                'MONTHLY_QUIZ_EXPIRED',
                                'MONTHLY_QUIZ_COMPLETED'
                            ) THEN CAST(upper(message_type) AS messagetype)
                            ELSE 'text'::messagetype
                        END,
                        'text'::messagetype
                    )
                    """
                )
            )
        else:
            op.execute(sa.text("UPDATE messages SET type = 'text'::messagetype WHERE type IS NULL"))
        op.execute(sa.text("ALTER TABLE messages ALTER COLUMN type SET DEFAULT 'text'::messagetype"))
        op.execute(sa.text("ALTER TABLE messages ALTER COLUMN type SET NOT NULL"))

    if not _column_exists(bind, "messages", "direction"):
        op.add_column(
            "messages",
            sa.Column(
                "direction",
                sa.Enum(
                    "inbound",
                    "outbound",
                    name="message_direction",
                    native_enum=True,
                    create_type=False,
                    validate_strings=True,
                ),
                nullable=False,
                server_default=sa.text("'outbound'"),
            ),
        )

    if not _column_exists(bind, "messages", "whatsapp_id"):
        op.add_column("messages", sa.Column("whatsapp_id", sa.String(length=255), nullable=True))
    if not _index_exists(bind, "messages", "ix_messages_whatsapp_id"):
        op.create_index("ix_messages_whatsapp_id", "messages", ["whatsapp_id"], unique=False)

    if not _column_exists(bind, "messages", "delivered_at"):
        op.add_column("messages", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "messages", "read_at"):
        op.add_column("messages", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))

    if not _column_exists(bind, "messages", "delivery_status"):
        op.add_column(
            "messages",
            sa.Column(
                "delivery_status",
                sa.Enum(
                    "scheduled",
                    "queued",
                    "sending",
                    "sent",
                    "delivered",
                    "read",
                    "failed",
                    "cancelled",
                    name="message_delivery_status",
                    native_enum=True,
                    create_type=False,
                    validate_strings=True,
                ),
                nullable=True,
            ),
        )

    if not _column_exists(bind, "messages", "retry_count"):
        op.add_column(
            "messages",
            sa.Column(
                "retry_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    else:
        op.execute(sa.text("UPDATE messages SET retry_count = 0 WHERE retry_count IS NULL"))
        op.execute(sa.text("ALTER TABLE messages ALTER COLUMN retry_count SET DEFAULT 0"))
        op.execute(sa.text("ALTER TABLE messages ALTER COLUMN retry_count SET NOT NULL"))

    if not _column_exists(bind, "messages", "last_retry_at"):
        op.add_column("messages", sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "messages", "failure_reason"):
        op.add_column("messages", sa.Column("failure_reason", sa.Text(), nullable=True))
    if not _column_exists(bind, "messages", "next_retry_at"):
        op.add_column("messages", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))


def upgrade() -> None:
    bind = op.get_bind()
    _align_patients_table(bind)
    _align_flow_template_versions_table(bind)
    _align_messages_table(bind)


def downgrade() -> None:
    # Alignment migration intentionally keeps added columns on downgrade.
    pass
