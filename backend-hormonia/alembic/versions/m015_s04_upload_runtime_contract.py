"""Align uploads table with runtime artifact route model contract.

Revision ID: m015_s04_upload_runtime_contract
Revises: m015_s02_notifications_profile_contract
Create Date: 2026-05-14

The private artifact app-routes persist Upload model rows. Runtime proof exposed
that the legacy bootstrap table only had user_id/upload_metadata timestamps, so
the real FastAPI upload path failed at INSERT time. This migration brings the
runtime table up to the model contract without relying on test-only DDL.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "m015_s04_upload_runtime_contract"
down_revision = "m015_s02_notifications_profile_contract"
branch_labels = None
depends_on = None


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    return any(col["name"] == column_name for col in sa.inspect(bind).get_columns(table_name))


def _index_exists(bind: sa.engine.Connection, table_name: str, index_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    return any(idx.get("name") == index_name for idx in sa.inspect(bind).get_indexes(table_name))


def _constraint_exists(bind: sa.engine.Connection, table_name: str, constraint_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    inspector = sa.inspect(bind)
    constraints = inspector.get_unique_constraints(table_name) + inspector.get_foreign_keys(table_name)
    return any(item.get("name") == constraint_name for item in constraints)


def _add_column_if_missing(bind: sa.engine.Connection, column: sa.Column) -> None:
    if not _column_exists(bind, "uploads", column.name):
        op.add_column("uploads", column)


def _create_uploads_table() -> None:
    op.create_table(
        "uploads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("storage_provider", sa.String(length=50), nullable=False, server_default="local"),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("file_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("virus_scanned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("virus_clean", sa.Boolean(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="uploads_user_id_fkey", ondelete="CASCADE"),
        sa.UniqueConstraint("storage_path", name="uq_uploads_storage_path"),
    )


def _backfill_required_fields(bind: sa.engine.Connection) -> None:
    file_metadata_source = "upload_metadata" if _column_exists(bind, "uploads", "upload_metadata") else "'{}'::jsonb"
    bind.execute(
        sa.text(
            f"""
            UPDATE uploads
            SET
                file_name = COALESCE(file_name, 'legacy-upload-' || id::text),
                file_size = COALESCE(file_size, 0),
                storage_path = COALESCE(storage_path, 'legacy://upload/' || id::text),
                storage_provider = COALESCE(storage_provider, 'local'),
                file_metadata = COALESCE(file_metadata, {file_metadata_source}, '{{}}'::jsonb),
                is_public = COALESCE(is_public, false),
                virus_scanned = COALESCE(virus_scanned, false)
            """
        )
    )


def _set_not_null_if_nullable(bind: sa.engine.Connection, column_name: str, column_type: sa.types.TypeEngine) -> None:
    columns = sa.inspect(bind).get_columns("uploads")
    column = next((item for item in columns if item["name"] == column_name), None)
    if column and column.get("nullable"):
        op.alter_column("uploads", column_name, existing_type=column_type, nullable=False)


def _create_indexes(bind: sa.engine.Connection) -> None:
    if not _index_exists(bind, "uploads", "ix_uploads_user_id"):
        op.create_index("ix_uploads_user_id", "uploads", ["user_id"], unique=False)
    if not _index_exists(bind, "uploads", "ix_uploads_user_quota"):
        op.create_index(
            "ix_uploads_user_quota",
            "uploads",
            ["user_id", "file_size"],
            unique=False,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )
    if not _index_exists(bind, "uploads", "ix_uploads_storage_path"):
        op.create_index("ix_uploads_storage_path", "uploads", ["storage_path"], unique=False)
    if not _index_exists(bind, "uploads", "ix_uploads_content_hash"):
        op.create_index(
            "ix_uploads_content_hash",
            "uploads",
            ["content_hash"],
            unique=False,
            postgresql_where=sa.text("content_hash IS NOT NULL"),
        )
    if not _index_exists(bind, "uploads", "ix_uploads_deleted_at"):
        op.create_index("ix_uploads_deleted_at", "uploads", ["deleted_at"], unique=False)

    if not _constraint_exists(bind, "uploads", "uq_uploads_storage_path"):
        op.create_unique_constraint("uq_uploads_storage_path", "uploads", ["storage_path"])


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "uploads"):
        _create_uploads_table()
        _create_indexes(bind)
        return

    _add_column_if_missing(bind, sa.Column("file_name", sa.String(length=500), nullable=True))
    _add_column_if_missing(bind, sa.Column("file_size", sa.Integer(), nullable=True))
    _add_column_if_missing(bind, sa.Column("file_type", sa.String(length=100), nullable=True))
    _add_column_if_missing(bind, sa.Column("storage_path", sa.String(length=1000), nullable=True))
    _add_column_if_missing(bind, sa.Column("storage_provider", sa.String(length=50), nullable=True, server_default="local"))
    _add_column_if_missing(bind, sa.Column("content_hash", sa.String(length=64), nullable=True))
    _add_column_if_missing(
        bind,
        sa.Column("file_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
    )
    _add_column_if_missing(bind, sa.Column("is_public", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    _add_column_if_missing(bind, sa.Column("virus_scanned", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    _add_column_if_missing(bind, sa.Column("virus_clean", sa.Boolean(), nullable=True))
    _add_column_if_missing(bind, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    _backfill_required_fields(bind)

    _set_not_null_if_nullable(bind, "file_name", sa.String(length=500))
    _set_not_null_if_nullable(bind, "file_size", sa.Integer())
    _set_not_null_if_nullable(bind, "storage_path", sa.String(length=1000))
    _set_not_null_if_nullable(bind, "storage_provider", sa.String(length=50))
    _set_not_null_if_nullable(bind, "is_public", sa.Boolean())
    _set_not_null_if_nullable(bind, "virus_scanned", sa.Boolean())

    _create_indexes(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "uploads"):
        return

    if _constraint_exists(bind, "uploads", "uq_uploads_storage_path"):
        op.drop_constraint("uq_uploads_storage_path", "uploads", type_="unique")

    for index_name in (
        "ix_uploads_content_hash",
        "ix_uploads_storage_path",
        "ix_uploads_user_quota",
    ):
        if _index_exists(bind, "uploads", index_name):
            op.drop_index(index_name, table_name="uploads")

    for column_name in (
        "virus_clean",
        "virus_scanned",
        "is_public",
        "file_metadata",
        "content_hash",
        "storage_provider",
        "storage_path",
        "file_type",
        "file_size",
        "file_name",
    ):
        if _column_exists(bind, "uploads", column_name):
            op.drop_column("uploads", column_name)
