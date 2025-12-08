"""Add soft delete to patients table

Revision ID: 017_add_patient_soft_delete
Revises: 016_validate_patient_metadata
Create Date: 2025-10-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '017_add_patient_soft_delete'
down_revision = '016_validate_patient_metadata'
branch_labels = None
depends_on = None


def upgrade():
    """Add deleted_at column for soft delete functionality."""
    
    # Add deleted_at column
    op.add_column('patients', 
        sa.Column('deleted_at', 
                 sa.DateTime(timezone=True), 
                 nullable=True)
    )
    
    # Add index for performance on active patients queries
    op.create_index('idx_patients_active', 'patients', ['deleted_at'])
    
    # Add partial index for deleted patients (PostgreSQL specific)
    op.execute("""
        CREATE INDEX idx_patients_deleted 
        ON patients (deleted_at) 
        WHERE deleted_at IS NOT NULL
    """)


def downgrade():
    """Remove soft delete functionality."""
    
    # Drop indexes
    op.drop_index('idx_patients_deleted', table_name='patients')
    op.drop_index('idx_patients_active', table_name='patients')
    
    # Drop column
    op.drop_column('patients', 'deleted_at')