"""Fix audit_logs user_id column type from String to UUID

Revision ID: 20251011_140000
Revises: 20251011_130000
Create Date: 2025-01-11 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251011_140000'
down_revision = '20251011_130000'
branch_labels = None
depends_on = None


def upgrade():
    """
    Fix audit_logs.user_id column type from String(255) to UUID.
    
    This migration addresses the type mismatch between the SQLAlchemy model
    (which expects UUID) and the database schema (which was created as String).
    """
    
    # First, we need to convert existing string UUIDs to proper UUID type
    # This is safe because all user_id values should already be valid UUIDs
    
    # Step 1: Add a temporary UUID column
    op.add_column('audit_logs', sa.Column('user_id_temp', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Step 2: Copy data from string column to UUID column, converting the format
    op.execute("""
        UPDATE audit_logs 
        SET user_id_temp = user_id::uuid 
        WHERE user_id IS NOT NULL AND user_id != ''
    """)
    
    # Step 3: Drop the old string column
    op.drop_index('idx_audit_user_event_time', table_name='audit_logs')
    op.drop_column('audit_logs', 'user_id')
    
    # Step 4: Rename the temp column to user_id
    op.alter_column('audit_logs', 'user_id_temp', new_column_name='user_id')
    
    # Step 5: Recreate the index
    op.create_index('idx_audit_user_event_time', 'audit_logs', ['user_id', 'event_type', 'created_at'])


def downgrade():
    """
    Revert audit_logs.user_id column type from UUID back to String(255).
    
    This converts UUID values back to string format.
    """
    
    # Step 1: Add a temporary string column
    op.add_column('audit_logs', sa.Column('user_id_temp', sa.String(255), nullable=True))
    
    # Step 2: Copy data from UUID column to string column
    op.execute("""
        UPDATE audit_logs 
        SET user_id_temp = user_id::text 
        WHERE user_id IS NOT NULL
    """)
    
    # Step 3: Drop the UUID column and its index
    op.drop_index('idx_audit_user_event_time', table_name='audit_logs')
    op.drop_column('audit_logs', 'user_id')
    
    # Step 4: Rename the temp column to user_id
    op.alter_column('audit_logs', 'user_id_temp', new_column_name='user_id')
    
    # Step 5: Recreate the index
    op.create_index('idx_audit_user_event_time', 'audit_logs', ['user_id', 'event_type', 'created_at'])