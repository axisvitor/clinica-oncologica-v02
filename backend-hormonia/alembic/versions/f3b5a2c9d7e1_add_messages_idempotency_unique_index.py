"""Add unique index for message idempotency.

Revision ID: f3b5a2c9d7e1
Revises: e2c4b1a9f7d3
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3b5a2c9d7e1"
down_revision = "e2c4b1a9f7d3"
branch_labels = None
depends_on = None


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    index_name = "ux_messages_patient_idempotency"
    if _index_exists(bind, "messages", index_name):
        return

    # Guardrail: fail fast if duplicates exist
    dupes = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM (
              SELECT 1
              FROM messages
              GROUP BY patient_id, idempotency_key
              HAVING COUNT(*) > 1
            ) dupes
            """
        )
    ).scalar()
    if dupes and int(dupes) > 0:
        raise RuntimeError(
            "Cannot create unique index ux_messages_patient_idempotency: duplicates exist."
        )

    op.create_index(
        index_name,
        "messages",
        ["patient_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    index_name = "ux_messages_patient_idempotency"
    if not _index_exists(bind, "messages", index_name):
        return

    op.drop_index(index_name, table_name="messages")
