"""Rename session_id to quiz_session_id in quiz_responses table

Revision ID: 20251012_160000
Revises: 20251012_150000
Create Date: 2025-10-12 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251012_160000'
down_revision = '20251012_150000'
branch_labels = None
depends_on = None


def upgrade():
    """Rename session_id to quiz_session_id in quiz_responses table."""
    
    # Check if the column exists before renaming
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'quiz_responses' 
                AND column_name = 'session_id'
                AND table_schema = 'public'
            ) THEN
                ALTER TABLE quiz_responses RENAME COLUMN session_id TO quiz_session_id;
                RAISE NOTICE 'Renamed session_id to quiz_session_id';
            ELSE
                RAISE NOTICE 'Column session_id does not exist, skipping rename';
            END IF;
        END $$;
    """)
    
    # Also add missing columns if they don't exist
    op.execute("""
        DO $$ BEGIN
            -- Add other_text column if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'quiz_responses' 
                AND column_name = 'other_text'
                AND table_schema = 'public'
            ) THEN
                ALTER TABLE quiz_responses ADD COLUMN other_text TEXT;
                RAISE NOTICE 'Added other_text column';
            END IF;
        END $$;
    """)


def downgrade():
    """Rename quiz_session_id back to session_id."""
    
    # Rename back to session_id
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'quiz_responses' 
                AND column_name = 'quiz_session_id'
                AND table_schema = 'public'
            ) THEN
                ALTER TABLE quiz_responses RENAME COLUMN quiz_session_id TO session_id;
                RAISE NOTICE 'Renamed quiz_session_id back to session_id';
            END IF;
        END $$;
    """)
    
    # Remove other_text column
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'quiz_responses' 
                AND column_name = 'other_text'
                AND table_schema = 'public'
            ) THEN
                ALTER TABLE quiz_responses DROP COLUMN other_text;
                RAISE NOTICE 'Removed other_text column';
            END IF;
        END $$;
    """)