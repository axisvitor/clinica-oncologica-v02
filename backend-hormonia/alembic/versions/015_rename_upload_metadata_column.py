"""Rename uploads.metadata to uploads.file_metadata

Revision ID: 015_rename_upload_metadata
Revises: 014
Create Date: 2025-11-16 19:37:00.000000

This migration renames the 'metadata' column in the 'uploads' table to
'file_metadata' to avoid conflicts with SQLAlchemy's reserved 'metadata' attribute.

Background:
- SQLAlchemy uses 'metadata' as a reserved attribute for table metadata
- Having a column named 'metadata' can cause attribute access conflicts
- Renaming to 'file_metadata' resolves the conflict while maintaining clarity

Impact:
- Column rename is backward compatible at database level
- Application code already uses 'file_metadata' in the model
- No data migration needed - just column rename

WHY:
- Not recorded (legacy migration).

WHAT:
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
revision = '015_rename_upload_metadata'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Rename uploads.metadata to uploads.file_metadata

    This operation is safe and fast:
    - No data changes required
    - No locks on table for reads
    - Only brief lock for metadata update
    """
    # Check if column exists before renaming
    # This handles cases where migration might be re-run
    connection = op.get_bind()

    # Check if 'metadata' column exists
    result = connection.execute(sa.text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'uploads'
        AND column_name = 'metadata'
    """))

    has_metadata = result.fetchone() is not None

    if has_metadata:
        # Rename column
        op.alter_column(
            'uploads',
            'metadata',
            new_column_name='file_metadata',
            existing_type=sa.dialects.postgresql.JSONB,
            existing_nullable=True,
            existing_server_default='{}',
            comment='Additional file metadata (JSONB) - renamed from metadata to avoid SQLAlchemy conflict'
        )

        print("✅ Renamed uploads.metadata → uploads.file_metadata")
    else:
        print("ℹ️  Column 'metadata' not found (already renamed or table structure different)")

        # Check if file_metadata exists
        result = connection.execute(sa.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'uploads'
            AND column_name = 'file_metadata'
        """))

        has_file_metadata = result.fetchone() is not None

        if has_file_metadata:
            print("✅ Column 'file_metadata' already exists - migration already applied")
        else:
            print("⚠️  Neither 'metadata' nor 'file_metadata' found - check table structure")


def downgrade() -> None:
    """
    Rename uploads.file_metadata back to uploads.metadata

    WARNING: This downgrade will restore the SQLAlchemy conflict.
    Only use if rolling back to code that expects 'metadata' column name.
    """
    # Check if column exists before renaming
    connection = op.get_bind()

    # Check if 'file_metadata' column exists
    result = connection.execute(sa.text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'uploads'
        AND column_name = 'file_metadata'
    """))

    has_file_metadata = result.fetchone() is not None

    if has_file_metadata:
        # Rename back to metadata
        op.alter_column(
            'uploads',
            'file_metadata',
            new_column_name='metadata',
            existing_type=sa.dialects.postgresql.JSONB,
            existing_nullable=True,
            existing_server_default='{}',
            comment='Additional file metadata (JSONB)'
        )

        print("⚠️  Renamed uploads.file_metadata → uploads.metadata (SQLAlchemy conflict restored)")
    else:
        print("ℹ️  Column 'file_metadata' not found - downgrade already applied or table structure different")
