"""
Script to apply flow state version migration directly to the database.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def apply_migration():
    """Apply the flow state version migration."""
    
    # Get DATABASE_URL from environment
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return
    
    # Convert SQLAlchemy URL format to psycopg format
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    # SQL to add version column and index
    sql = """
    -- Add version column with default value 0
    ALTER TABLE patient_flow_states 
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 0;
    
    -- Create index for efficient version queries
    CREATE INDEX IF NOT EXISTS idx_patient_flow_states_version 
    ON patient_flow_states (id, version);
    """
    
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
                
                # Verify column was created
                cur.execute("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patient_flow_states'
                    AND column_name = 'version'
                """)
                result = cur.fetchone()
                
                if result:
                    print(f"✓ Column 'version' confirmed in patient_flow_states")
                    print(f"  - Type: {result[1]}")
                    print(f"  - Default: {result[2]}")
                    
                    # Check index
                    cur.execute("""
                        SELECT indexname 
                        FROM pg_indexes 
                        WHERE tablename = 'patient_flow_states'
                        AND indexname = 'idx_patient_flow_states_version'
                    """)
                    idx_result = cur.fetchone()
                    
                    if idx_result:
                        print(f"✓ Index 'idx_patient_flow_states_version' created")
                    else:
                        print("⚠ Index not found (may already exist)")
                else:
                    print("✗ Column verification failed")
                    
                # Update alembic version
                print("\nUpdating alembic version...")
                cur.execute("""
                    UPDATE alembic_version 
                    SET version_num = '004_add_flow_state_version'
                    WHERE version_num = '003_add_last_retry_at'
                """)
                
                if cur.rowcount > 0:
                    conn.commit()
                    print("✓ Alembic version updated to 004_add_flow_state_version")
                else:
                    # Try to insert if no previous version exists
                    cur.execute("""
                        INSERT INTO alembic_version (version_num) 
                        VALUES ('004_add_flow_state_version')
                        ON CONFLICT (version_num) DO NOTHING
                    """)
                    conn.commit()
                    print("✓ Alembic version set to 004_add_flow_state_version")
                    
    except Exception as e:
        print(f"✗ Error applying migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    apply_migration()
