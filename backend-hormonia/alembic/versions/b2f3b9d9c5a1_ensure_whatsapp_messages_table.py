"""ensure_whatsapp_messages_table

Revision ID: b2f3b9d9c5a1
Revises: a1b2c3d4e5f6
Create Date: 2026-01-18 05:15:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b2f3b9d9c5a1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "whatsapp_messages" in inspector.get_table_names():
        return

    op.create_table(
        "whatsapp_messages",
        sa.Column("id", sa.TEXT(), nullable=False),
        sa.Column("instance_name", sa.TEXT(), nullable=False),
        sa.Column("chat_id", sa.TEXT(), nullable=False),
        sa.Column("sender_id", sa.TEXT(), nullable=False),
        sa.Column("recipient_id", sa.TEXT(), nullable=False),
        sa.Column("message_type", sa.TEXT(), nullable=False),
        sa.Column("content", sa.TEXT(), nullable=True),
        sa.Column("media_url", sa.TEXT(), nullable=True),
        sa.Column("media_caption", sa.TEXT(), nullable=True),
        sa.Column(
            "status",
            sa.TEXT(),
            server_default=sa.text("'pending'::text"),
            nullable=True,
        ),
        sa.Column("external_id", sa.TEXT(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("sent_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("delivered_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("read_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("failed_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column(
            "retry_count",
            sa.INTEGER(),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column("error_message", sa.TEXT(), nullable=True),
        sa.Column("message_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name="whatsapp_messages_pkey"),
        sa.UniqueConstraint(
            "external_id",
            name="whatsapp_messages_external_id_key",
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )

    op.create_index(
        "ix_whatsapp_messages_instance",
        "whatsapp_messages",
        ["instance_name"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_external",
        "whatsapp_messages",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_chat",
        "whatsapp_messages",
        ["chat_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "whatsapp_messages" not in inspector.get_table_names():
        return

    op.drop_index("ix_whatsapp_messages_chat", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_external", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_instance", table_name="whatsapp_messages")
    op.drop_table("whatsapp_messages")
