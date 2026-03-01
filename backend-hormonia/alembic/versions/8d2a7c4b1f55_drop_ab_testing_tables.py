"""Drop deprecated A/B testing tables.

Revision ID: 8d2a7c4b1f55
Revises: 6f8c2d4a9b10
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8d2a7c4b1f55"
down_revision = "6f8c2d4a9b10"
branch_labels = None
depends_on = None


AB_TABLES_TO_DROP = (
    "ab_variant_assignments",
    "ab_experiment_results",
    "ab_experiment_monitoring",
    "ab_experiment_metrics",
    "ab_experiment_audit",
    "ab_experiments",
)

AB_ENUM_TYPES = (
    "varianttype",
    "experimentstatus",
)


def _is_postgresql(bind) -> bool:
    return bind.dialect.name == "postgresql"


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _drop_enum_if_unused(enum_name: str) -> None:
    # Drop enum only when no remaining column depends on it.
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = '{enum_name}'
                      AND n.nspname = current_schema()
                ) THEN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_attribute a
                        JOIN pg_type t ON t.oid = a.atttypid
                        JOIN pg_class c ON c.oid = a.attrelid
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE t.typname = '{enum_name}'
                          AND n.nspname = current_schema()
                          AND c.relkind IN ('r', 'p', 'v', 'm')
                          AND a.attnum > 0
                          AND NOT a.attisdropped
                    ) THEN
                        EXECUTE format('DROP TYPE IF EXISTS %I', '{enum_name}');
                    END IF;
                END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgresql(bind):
        return

    inspector = sa.inspect(bind)

    for table_name in AB_TABLES_TO_DROP:
        if _table_exists(inspector, table_name):
            op.execute(sa.text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))

    for enum_name in AB_ENUM_TYPES:
        _drop_enum_if_unused(enum_name)


def downgrade() -> None:
    # Intentionally omitted to avoid restoring deprecated A/B testing schema.
    pass

