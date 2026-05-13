"""Add soft-delete timestamp to uploads.

Revision ID: m013_s04_upload_deleted_at
Revises: m012_s01_patient_flow_overrides
Create Date: 2026-05-12 21:10:00.000000

The private upload serving boundary treats deleted upload records as missing.
This column makes that lifecycle state explicit for metadata, download, and
delete handlers.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m013_s04_upload_deleted_at"
down_revision = "m012_s01_patient_flow_overrides"
branch_labels = None
depends_on = None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar_one_or_none()
    )


def _index_exists(connection, index_name: str) -> bool:
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE indexname = :index_name
                """
            ),
            {"index_name": index_name},
        ).scalar_one_or_none()
    )


def upgrade() -> None:
    connection = op.get_bind()

    if not _column_exists(connection, "uploads", "deleted_at"):
        op.add_column(
            "uploads",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _index_exists(connection, "ix_uploads_deleted_at"):
        op.create_index(
            "ix_uploads_deleted_at",
            "uploads",
            ["deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    connection = op.get_bind()

    if _index_exists(connection, "ix_uploads_deleted_at"):
        op.drop_index("ix_uploads_deleted_at", table_name="uploads")

    if _column_exists(connection, "uploads", "deleted_at"):
        op.drop_column("uploads", "deleted_at")
