"""
Script to verify the flow state version column exists and is working.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def verify_migration():
    """Verify the flow state version migration."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print(f"Connecting to database...")
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Check table structure
                print("\n=== Table Structure ===")
                cur.execute("""
                    SELECT column_name, data_type, column_default, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patient_flow_states'
                    ORDER BY ordinal_position
                """)
                
                columns = cur.fetchall()
                print(f"Total columns: {len(columns)}")
                
                version_found = False
                for col in columns:
                    if col[0] == 'version':
                        version_found = True
                        print(f"\n✓ Column 'version' found:")
                        print(f"  - Name: {col[0]}")
                        print(f"  - Type: {col[1]}")
                        print(f"  - Default: {col[2]}")
                        print(f"  - Nullable: {col[3]}")
                
                if not version_found:
                    print("\n✗ Column 'version' NOT FOUND!")
                    return
                
                # Check indexes
                print("\n=== Indexes ===")
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes 
                    WHERE tablename = 'patient_flow_states'
                    AND indexname LIKE '%version%'
                """)
                
                indexes = cur.fetchall()
                if indexes:
                    for idx in indexes:
                        print(f"✓ {idx[0]}")
                        print(f"  {idx[1]}")
                else:
                    print("⚠ No version-related indexes found")
                
                # Check alembic version
                print("\n=== Alembic Version ===")
                cur.execute("SELECT version_num FROM alembic_version")
                version = cur.fetchone()
                if version:
                    print(f"Current version: {version[0]}")
                else:
                    print("⚠ No alembic version found")
                
                # Test query with version
                print("\n=== Test Query ===")
                cur.execute("""
                    SELECT id, version, status, current_step
                    FROM patient_flow_states
                    LIMIT 5
                """)
                
                rows = cur.fetchall()
                if rows:
                    print(f"Found {len(rows)} flow states:")
                    for row in rows:
                        print(f"  - ID: {row[0]}, Version: {row[1]}, Status: {row[2]}, Step: {row[3]}")
                else:
                    print("No flow states found (table is empty)")
                
                print("\n✓ All verifications passed!")
                    
    except Exception as e:
        print(f"\n✗ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_migration()
