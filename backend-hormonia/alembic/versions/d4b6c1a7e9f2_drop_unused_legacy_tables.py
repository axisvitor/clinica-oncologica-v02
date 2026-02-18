"""Drop unused legacy tables.

Revision ID: d4b6c1a7e9f2
Revises: 7f3a2c6c1b8e
Create Date: 2026-01-21

Drops legacy tables that are not used by runtime code and are empty in production.
These tables were created by earlier migrations for documentation/admin features
that are no longer part of the active system.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "d4b6c1a7e9f2"
down_revision = "7f3a2c6c1b8e"
branch_labels = None
depends_on = None


TABLES_TO_DROP = (
    "admin_audit_log",
    "admin_ip_blacklist",
    "admin_ip_whitelist",
    "admin_permissions",
    "admin_role_permissions",
    "admin_roles",
    "admin_security_events",
    "admin_sessions",
    "admin_user_permissions",
    "admin_users",
    "audit_logs_archive_2025",
    "audit_logs_archive_2026",
    "audit_logs_archive_2027",
    "audit_logs_archive_2028",
    "audit_logs_archive_2029",
    "audit_logs_archive_2030",
    "audit_logs_archive_2031",
    "contacts",
    "flow_states",
    "flow_template_categories",
    "flow_template_shares",
    "flow_template_stats",
    "user_profiles",
)


def upgrade() -> None:
    for table_name in TABLES_TO_DROP:
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")


def downgrade() -> None:
    # Downgrade is intentionally omitted to avoid reintroducing legacy schema.
    pass
