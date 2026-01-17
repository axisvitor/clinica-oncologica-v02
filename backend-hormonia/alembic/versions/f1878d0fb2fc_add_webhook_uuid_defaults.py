"""Add server defaults for webhook UUIDs.

Revision ID: f1878d0fb2fc
Revises: 4697ee3a60f4
Create Date: 2026-01-09

Ensures webhook tables use gen_random_uuid() defaults for IDs.

WHY:
- Not recorded (legacy migration).

WHAT:
- Not recorded (legacy migration).

IMPACT:
- Not recorded (legacy migration).

BENCHMARK:
- Not recorded (legacy migration).

ROLLBACK:
- Not recorded (legacy migration).

RELATED:
- Not recorded (legacy migration).

MIGRATION TYPE:
- Not recorded (legacy migration).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f1878d0fb2fc"
down_revision = "4697ee3a60f4"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    for table_name in ("webhook_endpoints", "webhook_deliveries", "webhook_logs"):
        if not _table_exists(bind, table_name):
            continue
        if not _column_exists(bind, table_name, "id"):
            continue
        op.alter_column(
            table_name,
            "id",
            existing_type=postgresql.UUID(),
            server_default=sa.text("gen_random_uuid()"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    for table_name in ("webhook_endpoints", "webhook_deliveries", "webhook_logs"):
        if not _table_exists(bind, table_name):
            continue
        if not _column_exists(bind, table_name, "id"):
            continue
        op.alter_column(
            table_name,
            "id",
            existing_type=postgresql.UUID(),
            server_default=None,
        )
