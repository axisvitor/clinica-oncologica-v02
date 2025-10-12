#!/usr/bin/env python3
"""
Apply the quiz_session_id migration manually.
"""
import os
import sys
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def apply_migration():
    """Apply the quiz_session_id migration."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not found in environment")
        return
    
    # Convert SQLAlchemy URL to psycopg format
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                print("Checking if session_id column exists...")
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'quiz_responses' 
                        AND column_name = 'session_id'
                        AND table_schema = 'public'
                    );
                """)
                
                session_id_exists = cur.fetchone()[0]
                print(f"session_id column exists: {session_id_exists}")
                
                if session_id_exists:
                    print("Renaming session_id to quiz_session_id...")
                    cur.execute("ALTER TABLE quiz_responses RENAME COLUMN session_id TO quiz_session_id;")
                    print("✅ Renamed session_id to quiz_session_id")
                else:
                    print("session_id column does not exist, checking quiz_session_id...")
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'quiz_responses' 
                            AND column_name = 'quiz_session_id'
                            AND table_schema = 'public'
                        );
                    """)
                    
                    quiz_session_id_exists = cur.fetchone()[0]
                    if quiz_session_id_exists:
                        print("✅ quiz_session_id column already exists")
                    else:
                        print("❌ Neither session_id nor quiz_session_id exists!")
                
                # Check if other_text column exists and add if missing
                print("Checking if other_text column exists...")
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'quiz_responses' 
                        AND column_name = 'other_text'
                        AND table_schema = 'public'
                    );
                """)
                
                other_text_exists = cur.fetchone()[0]
                print(f"other_text column exists: {other_text_exists}")
                
                if not other_text_exists:
                    print("Adding other_text column...")
                    cur.execute("ALTER TABLE quiz_responses ADD COLUMN other_text TEXT;")
                    print("✅ Added other_text column")
                
                # Update alembic version
                print("Updating alembic version...")
                cur.execute("UPDATE alembic_version SET version_num = '20251012_160000';")
                
                conn.commit()
                print("✅ Migration applied successfully!")
                
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    apply_migration()