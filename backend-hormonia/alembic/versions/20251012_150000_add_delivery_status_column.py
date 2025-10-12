"""Add delivery_status column to messages table

Revision ID: 20251012_150000
Revises: 20251012_140000
Create Date: 2025-10-12 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251012_150000'
down_revision = '20251012_140000'
branch_labels = None
depends_on = None


def upgrade():
    """Add delivery_status column and related fields to messages table."""
    
    # Create DeliveryStatus enum if it doesn't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deliverystatus AS ENUM (
                'scheduled', 'queued', 'sending', 'sent', 
                'delivered', 'read', 'failed', 'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Add delivery_status column
    op.add_column('messages', sa.Column('delivery_status', 
                                       postgresql.ENUM('scheduled', 'queued', 'sending', 'sent', 
                                                     'delivered', 'read', 'failed', 'cancelled', 
                                                     name='deliverystatus'), 
                                       nullable=True))
    
    # Add other missing columns if they don't exist
    try:
        op.add_column('messages', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    except Exception:
        pass  # Column might already exist
        
    try:
        op.add_column('messages', sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True))
    except Exception:
        pass  # Column might already exist
        
    try:
        op.add_column('messages', sa.Column('failure_reason', sa.Text(), nullable=True))
    except Exception:
        pass  # Column might already exist
        
    try:
        op.add_column('messages', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
    except Exception:
        pass  # Column might already exist


def downgrade():
    """Remove delivery_status column and related fields."""
    
    # Remove columns
    op.drop_column('messages', 'next_retry_at')
    op.drop_column('messages', 'failure_reason')
    op.drop_column('messages', 'last_retry_at')
    op.drop_column('messages', 'retry_count')
    op.drop_column('messages', 'delivery_status')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS deliverystatus")