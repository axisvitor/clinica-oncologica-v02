"""Add missing foreign key indexes.

Revision ID: 21f306d5c4b8
Revises: 9c2b7e1a4f0d
Create Date: 2026-01-09

Adds indexes for foreign key columns that were missing coverage.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "21f306d5c4b8"
down_revision = "9c2b7e1a4f0d"
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


def _column_has_index(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    for idx in inspector.get_indexes(table_name):
        columns = idx.get("column_names") or []
        if column_name in columns:
            return True
    for constraint in inspector.get_unique_constraints(table_name):
        columns = constraint.get("column_names") or []
        if column_name in columns:
            return True
    return False


def _create_fk_index_if_missing(bind, table_name: str, column_name: str, index_name: str) -> None:
    if not _table_exists(bind, table_name):
        return
    if not _column_exists(bind, table_name, column_name):
        return
    if _index_exists(bind, table_name, index_name):
        return
    if _column_has_index(bind, table_name, column_name):
        return
    op.create_index(index_name, table_name, [column_name])


def upgrade() -> None:
    bind = op.get_bind()

    targets = [
        ("flow_template_versions", "created_by", "idx_flow_template_versions_created_by"),
        ("admin_users", "created_by", "idx_admin_users_created_by"),
        ("admin_users", "updated_by", "idx_admin_users_updated_by"),
        ("admin_user_permissions", "granted_by", "idx_admin_user_permissions_granted_by"),
        ("admin_audit_log", "session_id", "idx_admin_audit_log_session_id"),
        ("admin_security_events", "session_id", "idx_admin_security_events_session_id"),
        ("admin_ip_whitelist", "added_by", "idx_admin_ip_whitelist_added_by"),
        ("admin_ip_blacklist", "blocked_by", "idx_admin_ip_blacklist_blocked_by"),
        ("contacts", "related_patient_id", "idx_contacts_related_patient_id"),
        ("contacts", "related_user_id", "idx_contacts_related_user_id"),
        (
            "whatsapp_delivery_failures",
            "original_message_id",
            "idx_whatsapp_delivery_failures_original_message_id",
        ),
        (
            "whatsapp_delivery_failures",
            "reviewed_by",
            "idx_whatsapp_delivery_failures_reviewed_by",
        ),
        ("patient_summaries", "generated_by", "idx_patient_summaries_generated_by"),
        ("consents", "witness_id", "idx_consents_witness_id"),
        (
            "lgpd_data_access_requests",
            "assigned_to_id",
            "idx_lgpd_data_access_requests_assigned_to_id",
        ),
    ]

    for table_name, column_name, index_name in targets:
        _create_fk_index_if_missing(bind, table_name, column_name, index_name)


def downgrade() -> None:
    bind = op.get_bind()

    for table_name, index_name in [
        ("flow_template_versions", "idx_flow_template_versions_created_by"),
        ("admin_users", "idx_admin_users_created_by"),
        ("admin_users", "idx_admin_users_updated_by"),
        ("admin_user_permissions", "idx_admin_user_permissions_granted_by"),
        ("admin_audit_log", "idx_admin_audit_log_session_id"),
        ("admin_security_events", "idx_admin_security_events_session_id"),
        ("admin_ip_whitelist", "idx_admin_ip_whitelist_added_by"),
        ("admin_ip_blacklist", "idx_admin_ip_blacklist_blocked_by"),
        ("contacts", "idx_contacts_related_patient_id"),
        ("contacts", "idx_contacts_related_user_id"),
        ("whatsapp_delivery_failures", "idx_whatsapp_delivery_failures_original_message_id"),
        ("whatsapp_delivery_failures", "idx_whatsapp_delivery_failures_reviewed_by"),
        ("patient_summaries", "idx_patient_summaries_generated_by"),
        ("consents", "idx_consents_witness_id"),
        ("lgpd_data_access_requests", "idx_lgpd_data_access_requests_assigned_to_id"),
    ]:
        if _table_exists(bind, table_name) and _index_exists(bind, table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
