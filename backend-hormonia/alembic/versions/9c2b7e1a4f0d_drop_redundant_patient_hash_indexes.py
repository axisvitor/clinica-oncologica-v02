"""Drop redundant patient hash indexes.

Revision ID: 9c2b7e1a4f0d
Revises: fc449418ac7b
Create Date: 2026-01-09

Removes legacy hash indexes that duplicate newer ix_* indexes.

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


# revision identifiers, used by Alembic.
revision = "9c2b7e1a4f0d"
down_revision = "fc449418ac7b"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "patients"):
        return

    for index_name in (
        "idx_patients_cpf_hash",
        "idx_patients_email_hash",
        "idx_patients_phone_hash",
    ):
        if _index_exists(bind, "patients", index_name):
            op.drop_index(index_name, table_name="patients")


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "patients"):
        return

    if _column_exists(bind, "patients", "cpf_hash") and not _index_exists(
        bind, "patients", "idx_patients_cpf_hash"
    ):
        op.create_index(
            "idx_patients_cpf_hash",
            "patients",
            ["cpf_hash"],
            postgresql_where=sa.text("cpf_hash IS NOT NULL"),
        )

    if _column_exists(bind, "patients", "email_hash") and not _index_exists(
        bind, "patients", "idx_patients_email_hash"
    ):
        op.create_index(
            "idx_patients_email_hash",
            "patients",
            ["email_hash"],
            postgresql_where=sa.text("email_hash IS NOT NULL"),
        )

    if _column_exists(bind, "patients", "phone_hash") and not _index_exists(
        bind, "patients", "idx_patients_phone_hash"
    ):
        op.create_index(
            "idx_patients_phone_hash",
            "patients",
            ["phone_hash"],
            postgresql_where=sa.text("phone_hash IS NOT NULL"),
        )
