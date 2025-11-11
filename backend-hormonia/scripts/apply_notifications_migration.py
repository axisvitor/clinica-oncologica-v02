"""
Script to apply notifications table migration directly to the database.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def apply_migration():
    """Apply the notifications table migration."""
    
    # Read the migration SQL
    migration_file = Path(__file__).parent.parent / "migrations" / "004_create_notifications_table.sql"
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Get DATABASE_URL from environment
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return
    
    # Convert SQLAlchemy URL format to psycopg format
    # postgresql+psycopg:// -> postgresql://
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    # Connect and execute
    print(f"Connecting to database...")
    print(f"Database URL: {db_url[:50]}...")
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("\nExecuting migration SQL...")
                cur.execute(sql)
                conn.commit()
                print("✓ Migration applied successfully!")
                
                # Verify table was created
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'notifications'
                """)
                result = cur.fetchone()
                
                if result:
                    print(f"✓ Table 'notifications' confirmed in database")
                    
                    # Check indexes
                    cur.execute("""
                        SELECT indexname 
                        FROM pg_indexes 
                        WHERE tablename = 'notifications'
                    """)
                    indexes = cur.fetchall()
                    print(f"✓ Created {len(indexes)} indexes:")
                    for idx in indexes:
                        print(f"  - {idx[0]}")
                else:
                    print("✗ Table verification failed")
                    
    except Exception as e:
        print(f"✗ Error applying migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    apply_migration()
