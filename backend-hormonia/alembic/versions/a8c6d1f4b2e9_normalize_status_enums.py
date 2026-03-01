"""Normalize status enums for appointments, DLQ, and message status events.

Revision ID: a8c6d1f4b2e9
Revises: f3b5a2c9d7e1
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a8c6d1f4b2e9"
down_revision = "f3b5a2c9d7e1"
branch_labels = None
depends_on = None


def _enum_create_if_missing(bind, enum: sa.Enum) -> None:
    enum.create(bind, checkfirst=True)


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    appointment_status = sa.Enum(
        "scheduled",
        "confirmed",
        "in_progress",
        "completed",
        "cancelled",
        "no_show",
        name="appointment_status",
    )
    appointment_type = sa.Enum(
        "consultation",
        "followup",
        "treatment",
        "exam",
        "emergency",
        "telemedicine",
        name="appointment_type",
    )
    dlq_status = sa.Enum(
        "pending_review",
        "under_review",
        "retry_scheduled",
        "retrying",
        "max_retries_exceeded",
        "resolved",
        "discarded",
        name="dlq_status",
    )
    webhook_idempotency_status = sa.Enum(
        "processing",
        "completed",
        "failed",
        name="webhook_idempotency_status",
    )
    webhook_endpoint_status = sa.Enum(
        "active",
        "inactive",
        "paused",
        "error",
        name="webhook_endpoint_status",
    )
    webhook_delivery_status = sa.Enum(
        "pending",
        "success",
        "failed",
        "retrying",
        name="webhook_delivery_status",
    )

    _enum_create_if_missing(bind, appointment_status)
    _enum_create_if_missing(bind, appointment_type)
    _enum_create_if_missing(bind, dlq_status)
    _enum_create_if_missing(bind, webhook_idempotency_status)
    _enum_create_if_missing(bind, webhook_endpoint_status)
    _enum_create_if_missing(bind, webhook_delivery_status)

    # Appointments: normalize status/type
    if _table_exists(bind, "appointments"):
        op.execute(
            """
            UPDATE appointments
            SET status = 'scheduled'
            WHERE status IS NULL OR status NOT IN (
                'scheduled','confirmed','in_progress','completed','cancelled','no_show'
            )
            """
        )
        op.execute(
            """
            UPDATE appointments
            SET appointment_type = 'consultation'
            WHERE appointment_type IS NULL OR appointment_type NOT IN (
                'consultation','followup','treatment','exam','emergency','telemedicine'
            )
            """
        )

        op.execute(
            "ALTER TABLE appointments ALTER COLUMN status TYPE appointment_status USING status::appointment_status"
        )
        op.execute(
            "ALTER TABLE appointments ALTER COLUMN appointment_type TYPE appointment_type USING appointment_type::appointment_type"
        )

    # DLQ: normalize status
    if _table_exists(bind, "whatsapp_delivery_failures"):
        op.execute(
            """
            UPDATE whatsapp_delivery_failures
            SET status = 'pending_review'
            WHERE status IS NULL OR status = 'pending'
            """
        )
        op.execute(
            """
            UPDATE whatsapp_delivery_failures
            SET status = 'pending_review'
            WHERE status NOT IN (
                'pending_review','under_review','retry_scheduled',
                'retrying','max_retries_exceeded','resolved','discarded'
            )
            """
        )
        op.execute(
            "ALTER TABLE whatsapp_delivery_failures ALTER COLUMN status TYPE dlq_status USING status::dlq_status"
        )

    # Message status events: enforce existing message_status enum
    if _table_exists(bind, "message_status_events"):
        op.execute(
            """
            UPDATE message_status_events
            SET status = 'pending'
            WHERE status IS NULL OR status NOT IN (
                'pending','scheduled','sending','sent','delivered','read','failed','cancelled'
            )
            """
        )
        op.execute(
            """
            UPDATE message_status_events
            SET previous_status = NULL
            WHERE previous_status IS NOT NULL AND previous_status NOT IN (
                'pending','scheduled','sending','sent','delivered','read','failed','cancelled'
            )
            """
        )
        op.execute(
            "ALTER TABLE message_status_events ALTER COLUMN status TYPE message_status USING status::message_status"
        )
        op.execute(
            "ALTER TABLE message_status_events ALTER COLUMN previous_status TYPE message_status USING previous_status::message_status"
        )

    # Webhook idempotency: normalize status
    if _table_exists(bind, "webhook_idempotency"):
        op.execute(
            """
            UPDATE webhook_idempotency
            SET status = 'processing'
            WHERE status IS NULL OR status NOT IN ('processing','completed','failed')
            """
        )
        op.execute(
            "ALTER TABLE webhook_idempotency ALTER COLUMN status TYPE webhook_idempotency_status USING status::webhook_idempotency_status"
        )

    # Webhook endpoint/delivery statuses
    if _table_exists(bind, "webhook_endpoints"):
        op.execute(
            """
            UPDATE webhook_endpoints
            SET status = 'active'
            WHERE status IS NULL OR status NOT IN ('active','inactive','paused','error')
            """
        )
        op.execute(
            "ALTER TABLE webhook_endpoints ALTER COLUMN status TYPE webhook_endpoint_status USING status::webhook_endpoint_status"
        )

    if _table_exists(bind, "webhook_deliveries"):
        op.execute(
            """
            UPDATE webhook_deliveries
            SET status = 'pending'
            WHERE status IS NULL OR status NOT IN ('pending','success','failed','retrying')
            """
        )
        op.execute(
            "ALTER TABLE webhook_deliveries ALTER COLUMN status TYPE webhook_delivery_status USING status::webhook_delivery_status"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE message_status_events ALTER COLUMN previous_status TYPE VARCHAR(50)")
    op.execute("ALTER TABLE message_status_events ALTER COLUMN status TYPE VARCHAR(50)")

    op.execute("ALTER TABLE whatsapp_delivery_failures ALTER COLUMN status TYPE VARCHAR(20)")

    op.execute("ALTER TABLE appointments ALTER COLUMN appointment_type TYPE VARCHAR(100)")
    op.execute("ALTER TABLE appointments ALTER COLUMN status TYPE VARCHAR(50)")

    op.execute("ALTER TABLE webhook_idempotency ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute("ALTER TABLE webhook_deliveries ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute("ALTER TABLE webhook_endpoints ALTER COLUMN status TYPE VARCHAR(20)")

    sa.Enum(name="webhook_delivery_status").drop(bind, checkfirst=True)
    sa.Enum(name="webhook_endpoint_status").drop(bind, checkfirst=True)
    sa.Enum(name="webhook_idempotency_status").drop(bind, checkfirst=True)
    sa.Enum(name="dlq_status").drop(bind, checkfirst=True)
    sa.Enum(name="appointment_type").drop(bind, checkfirst=True)
    sa.Enum(name="appointment_status").drop(bind, checkfirst=True)
