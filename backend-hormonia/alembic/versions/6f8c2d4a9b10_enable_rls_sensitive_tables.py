"""Enable RLS hardening for sensitive tables.

Revision ID: 6f8c2d4a9b10
Revises: 3a4f5b6c7d88
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f8c2d4a9b10"
down_revision = "3a4f5b6c7d88"
branch_labels = None
depends_on = None


SENSITIVE_TABLES = (
    "patients",
    "messages",
    "quiz_sessions",
    "quiz_responses",
    "lgpd_audit_logs",
    "lgpd_data_access_requests",
    "consents",
)


def _is_postgresql(bind) -> bool:
    return bind.dialect.name == "postgresql"


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _policy_name(table_name: str) -> str:
    return f"rls_{table_name}_current_user_all"


def _create_policy_if_missing(table_name: str, policy_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_policies
                    WHERE schemaname = current_schema()
                      AND tablename = '{table_name}'
                      AND policyname = '{policy_name}'
                ) THEN
                    EXECUTE format(
                        'CREATE POLICY %I ON %I FOR ALL TO %I USING (true) WITH CHECK (true)',
                        '{policy_name}',
                        '{table_name}',
                        current_user
                    );
                END IF;
            END
            $$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgresql(bind):
        return

    inspector = sa.inspect(bind)

    for table_name in SENSITIVE_TABLES:
        if not _table_exists(inspector, table_name):
            continue

        op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"REVOKE ALL ON TABLE {table_name} FROM PUBLIC"))
        _create_policy_if_missing(table_name, _policy_name(table_name))


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgresql(bind):
        return

    inspector = sa.inspect(bind)

    for table_name in SENSITIVE_TABLES:
        if not _table_exists(inspector, table_name):
            continue

        op.execute(sa.text(f"DROP POLICY IF EXISTS {_policy_name(table_name)} ON {table_name}"))
        op.execute(sa.text(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))
