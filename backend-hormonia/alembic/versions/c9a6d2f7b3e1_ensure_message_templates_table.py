"""ensure_message_templates_table

Revision ID: c9a6d2f7b3e1
Revises: b2f3b9d9c5a1
Create Date: 2026-02-01 12:00:00.000000
"""
from datetime import datetime
import uuid

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.utils.timezone import now_sao_paulo_naive
# revision identifiers, used by Alembic.
revision = "c9a6d2f7b3e1"
down_revision = "b2f3b9d9c5a1"
branch_labels = None
depends_on = None

WELCOME_TEMPLATE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
TEMPLATE_NAME = "welcome_message"
WELCOME_TEMPLATE_CONTENT = (
    "Ol\\u00e1 {patient_name}, bem-vindo(a) \\u00e0 Cl\\u00ednica Hormonia! "
    "Seu cadastro foi realizado com sucesso. Em breve entraremos em contato "
    "para dar in\\u00edcio ao seu acompanhamento."
)
WELCOME_TEMPLATE_VARIABLES = '["patient_name"]'


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    table_created = False
    if "message_templates" not in inspector.get_table_names():
        op.create_table(
            "message_templates",
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("message_type", sa.String(), nullable=False),
            sa.Column("media_url", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id", name="message_templates_pkey"),
        )
        table_created = True

    if table_created or not _index_exists(inspector, "message_templates", "ix_message_templates_name"):
        op.create_index(
            "ix_message_templates_name",
            "message_templates",
            ["name"],
            unique=True,
        )

    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM message_templates WHERE name = :name"),
        {"name": TEMPLATE_NAME},
    ).fetchone()
    if not result:
        conn.execute(
            sa.text(
                """
                INSERT INTO message_templates
                    (id, name, content, variables, message_type, is_active, created_at, updated_at)
                VALUES
                    (:id, :name, :content, :variables, :message_type, :is_active, :created_at, :updated_at)
                """
            ),
            {
                "id": str(WELCOME_TEMPLATE_ID),
                "name": TEMPLATE_NAME,
                "content": WELCOME_TEMPLATE_CONTENT,
                "variables": WELCOME_TEMPLATE_VARIABLES,
                "message_type": "text",
                "is_active": True,
                "created_at": now_sao_paulo_naive(),
                "updated_at": now_sao_paulo_naive(),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM message_templates WHERE name = :name"),
        {"name": TEMPLATE_NAME},
    )