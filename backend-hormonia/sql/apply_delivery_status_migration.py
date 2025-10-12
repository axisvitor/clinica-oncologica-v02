#!/usr/bin/env python3
"""
Apply the delivery_status migration manually.
"""
import os
import sys
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def apply_migration():
    """Apply the delivery_status migration."""
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
                print("Creating DeliveryStatus enum...")
                cur.execute("""
                    DO $$ BEGIN
                        CREATE TYPE deliverystatus AS ENUM (
                            'scheduled', 'queued', 'sending', 'sent', 
                            'delivered', 'read', 'failed', 'cancelled'
                        );
                    EXCEPTION
                        WHEN duplicate_object THEN 
                            RAISE NOTICE 'DeliveryStatus enum already exists';
                    END $$;
                """)
                
                print("Adding delivery_status column...")
                cur.execute("""
                    DO $$ BEGIN
                        ALTER TABLE messages ADD COLUMN delivery_status deliverystatus;
                    EXCEPTION
                        WHEN duplicate_column THEN 
                            RAISE NOTICE 'delivery_status column already exists';
                    END $$;
                """)
                
                print("Adding retry_count column...")
                cur.execute("""
                    DO $$ BEGIN
                        ALTER TABLE messages ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;
                    EXCEPTION
                        WHEN duplicate_column THEN 
                            RAISE NOTICE 'retry_count column already exists';
                    END $$;
                """)
                
                print("Adding last_retry_at column...")
                cur.execute("""
                    DO $$ BEGIN
                        ALTER TABLE messages ADD COLUMN last_retry_at TIMESTAMP WITH TIME ZONE;
                    EXCEPTION
                        WHEN duplicate_column THEN 
                            RAISE NOTICE 'last_retry_at column already exists';
                    END $$;
                """)
                
                print("Adding failure_reason column...")
                cur.execute("""
                    DO $$ BEGIN
                        ALTER TABLE messages ADD COLUMN failure_reason TEXT;
                    EXCEPTION
                        WHEN duplicate_column THEN 
                            RAISE NOTICE 'failure_reason column already exists';
                    END $$;
                """)
                
                print("Adding next_retry_at column...")
                cur.execute("""
                    DO $$ BEGIN
                        ALTER TABLE messages ADD COLUMN next_retry_at TIMESTAMP WITH TIME ZONE;
                    EXCEPTION
                        WHEN duplicate_column THEN 
                            RAISE NOTICE 'next_retry_at column already exists';
                    END $$;
                """)
                
                # Update alembic version
                print("Updating alembic version...")
                cur.execute("""
                    UPDATE alembic_version SET version_num = '20251012_150000';
                """)
                
                conn.commit()
                print("✅ Migration applied successfully!")
                
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    apply_migration()