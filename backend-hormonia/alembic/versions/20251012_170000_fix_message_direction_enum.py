"""Fix message direction enum case mismatch

This migration fixes the case mismatch between the database enum values
(lowercase) and the Python enum values (uppercase) by updating the database
enum to use uppercase values.

Revision ID: 20251012_170000
Revises: 20251012_160000_rename_session_id_to_quiz_session_id
Create Date: 2025-10-12 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251012_170000'
down_revision = '20251012_160000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix message direction enum case mismatch.
    
    Updates the messagedirection enum to use uppercase values
    to match the Python MessageDirection enum.
    """
    # First, create the new enum with uppercase values
    op.execute("CREATE TYPE messagedirection_new AS ENUM ('INBOUND', 'OUTBOUND')")
    
    # Update existing data to use uppercase values
    op.execute("""
        UPDATE messages 
        SET direction = CASE 
            WHEN direction::text = 'inbound' THEN 'INBOUND'::messagedirection_new
            WHEN direction::text = 'outbound' THEN 'OUTBOUND'::messagedirection_new
            ELSE direction::text::messagedirection_new
        END::text::messagedirection_new
    """)
    
    # Drop the old enum constraint and column type
    op.execute("ALTER TABLE messages ALTER COLUMN direction TYPE messagedirection_new USING direction::text::messagedirection_new")
    
    # Drop the old enum type
    op.execute("DROP TYPE messagedirection")
    
    # Rename the new enum type to the original name
    op.execute("ALTER TYPE messagedirection_new RENAME TO messagedirection")


def downgrade() -> None:
    """
    Revert message direction enum to lowercase values.
    
    This reverts the enum back to lowercase values for rollback safety.
    """
    # Create the old enum with lowercase values
    op.execute("CREATE TYPE messagedirection_old AS ENUM ('inbound', 'outbound')")
    
    # Update existing data to use lowercase values
    op.execute("""
        UPDATE messages 
        SET direction = CASE 
            WHEN direction::text = 'INBOUND' THEN 'inbound'::messagedirection_old
            WHEN direction::text = 'OUTBOUND' THEN 'outbound'::messagedirection_old
            ELSE direction::text::messagedirection_old
        END::text::messagedirection_old
    """)
    
    # Drop the current enum constraint and column type
    op.execute("ALTER TABLE messages ALTER COLUMN direction TYPE messagedirection_old USING direction::text::messagedirection_old")
    
    # Drop the current enum type
    op.execute("DROP TYPE messagedirection")
    
    # Rename the old enum type back to the original name
    op.execute("ALTER TYPE messagedirection_old RENAME TO messagedirection")