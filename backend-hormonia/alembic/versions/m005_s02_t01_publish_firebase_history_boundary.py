"""Publish explicit Firebase sync history boundary.

Revision ID: m005_s02_t01_publish_firebase_history_boundary
Revises: lgpd03_add_ai_audit_event_types
Create Date: 2026-03-14 16:10:00.000000

This revision renames the ambiguous legacy-looking `user_sync_log` table to the
explicit historical surface `firebase_sync_history`. Existing rows remain in
place, including legacy residue columns kept for forensic replay.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "m005_s02_t01_publish_firebase_history_boundary"
down_revision = "lgpd03_add_ai_audit_event_types"
branch_labels = None
depends_on = None

LEGACY_TABLE = "user_sync_log"
HISTORY_TABLE = "firebase_sync_history"


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys(table_name)
        if foreign_key.get("name")
    }


def _rename_index_if_present(existing_indexes: set[str], old_name: str, new_name: str) -> None:
    if old_name in existing_indexes and old_name != new_name:
        op.execute(f"ALTER INDEX {old_name} RENAME TO {new_name}")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if HISTORY_TABLE in tables:
        return
    if LEGACY_TABLE not in tables:
        raise RuntimeError(
            "sync_history_surface missing_source_table=user_sync_log "
            f"tables={sorted(tables)}"
        )

    existing_indexes = _index_names(inspector, LEGACY_TABLE)
    existing_foreign_keys = _foreign_key_names(inspector, LEGACY_TABLE)
    primary_key_name = inspector.get_pk_constraint(LEGACY_TABLE).get("name")

    op.rename_table(LEGACY_TABLE, HISTORY_TABLE)

    if primary_key_name == "user_sync_log_pkey":
        op.execute(
            "ALTER TABLE firebase_sync_history "
            "RENAME CONSTRAINT user_sync_log_pkey TO firebase_sync_history_pkey"
        )

    if "fk_user_sync_log_user_id" in existing_foreign_keys:
        op.execute(
            "ALTER TABLE firebase_sync_history "
            "RENAME CONSTRAINT fk_user_sync_log_user_id "
            "TO fk_firebase_sync_history_user_id"
        )

    _rename_index_if_present(
        existing_indexes,
        "ix_user_sync_log_created_at",
        "ix_firebase_sync_history_created_at",
    )
    _rename_index_if_present(
        existing_indexes,
        "ix_user_sync_log_firebase_uid",
        "ix_firebase_sync_history_firebase_uid",
    )
    _rename_index_if_present(
        existing_indexes,
        "ix_user_sync_log_user_id",
        "ix_firebase_sync_history_user_id",
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_firebase_sync_history_created_at "
        "ON firebase_sync_history(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_firebase_sync_history_firebase_uid "
        "ON firebase_sync_history(firebase_uid)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_firebase_sync_history_user_id "
        "ON firebase_sync_history(user_id)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if LEGACY_TABLE in tables:
        return
    if HISTORY_TABLE not in tables:
        raise RuntimeError(
            "sync_history_surface missing_source_table=firebase_sync_history "
            f"tables={sorted(tables)}"
        )

    existing_indexes = _index_names(inspector, HISTORY_TABLE)
    existing_foreign_keys = _foreign_key_names(inspector, HISTORY_TABLE)
    primary_key_name = inspector.get_pk_constraint(HISTORY_TABLE).get("name")

    op.rename_table(HISTORY_TABLE, LEGACY_TABLE)

    if primary_key_name == "firebase_sync_history_pkey":
        op.execute(
            "ALTER TABLE user_sync_log "
            "RENAME CONSTRAINT firebase_sync_history_pkey TO user_sync_log_pkey"
        )

    if "fk_firebase_sync_history_user_id" in existing_foreign_keys:
        op.execute(
            "ALTER TABLE user_sync_log "
            "RENAME CONSTRAINT fk_firebase_sync_history_user_id "
            "TO fk_user_sync_log_user_id"
        )

    _rename_index_if_present(
        existing_indexes,
        "ix_firebase_sync_history_created_at",
        "ix_user_sync_log_created_at",
    )
    _rename_index_if_present(
        existing_indexes,
        "ix_firebase_sync_history_firebase_uid",
        "ix_user_sync_log_firebase_uid",
    )
    _rename_index_if_present(
        existing_indexes,
        "ix_firebase_sync_history_user_id",
        "ix_user_sync_log_user_id",
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_sync_log_created_at "
        "ON user_sync_log(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_sync_log_firebase_uid "
        "ON user_sync_log(firebase_uid)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_sync_log_user_id "
        "ON user_sync_log(user_id)"
    )
