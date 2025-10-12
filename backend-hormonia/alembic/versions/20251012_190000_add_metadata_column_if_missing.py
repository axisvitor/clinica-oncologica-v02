"""Add metadata column to patients table if missing

This migration ensures the metadata column exists in the patients table.
The column should exist from the baseline migration, but this provides
a safety net for databases that might be missing it.

Revision ID: 20251012_190000
Revises: 20251012_180000
Create Date: 2025-10-12 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251012_190000'
down_revision = '20251012_180000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add metadata column if it doesn't exist."""
    
    # Check if the column exists before adding it
    connection = op.get_bind()
    
    # Query to check if column exists
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'patients' 
        AND column_name = 'metadata'
    """)).fetchone()
    
    if not result:
        print("Adding missing metadata column to patients table...")
        op.add_column('patients', 
            sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}')
        )
        print("✅ metadata column added successfully")
    else:
        print("✅ metadata column already exists, skipping...")


def downgrade() -> None:
    """Remove metadata column."""
    
    # Check if the column exists before removing it
    connection = op.get_bind()
    
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'patients' 
        AND column_name = 'metadata'
    """)).fetchone()
    
    if result:
        print("Removing metadata column from patients table...")
        op.drop_column('patients', 'metadata')
        print("✅ metadata column removed successfully")
    else:
        print("✅ metadata column doesn't exist, skipping...")