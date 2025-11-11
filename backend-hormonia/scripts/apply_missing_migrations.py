"""
Script to apply missing migrations directly to the database.
- 003_add_last_retry_at: Add last_retry_at column to patient_onboarding_saga
- 006_add_message_priority: Add priority enum and column to messages
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def apply_migrations():
    """Apply the missing migrations."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("=" * 70)
    print("APPLYING MISSING MIGRATIONS")
    print("=" * 70)
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                # ============================================================
                # Migration 003: Add last_retry_at to patient_onboarding_saga
                # ============================================================
                print("\n📦 Migration 003: Add last_retry_at to patient_onboarding_saga")
                print("-" * 70)
                
                # Check if column already exists
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patient_onboarding_saga'
                    AND column_name = 'last_retry_at'
                """)
                
                if cur.fetchone():
                    print("⚠ Column 'last_retry_at' already exists, skipping...")
                else:
                    print("Adding column 'last_retry_at'...")
                    cur.execute("""
                        ALTER TABLE patient_onboarding_saga 
                        ADD COLUMN IF NOT EXISTS last_retry_at TIMESTAMP WITH TIME ZONE;
                    """)
                    
                    print("Creating index 'idx_patient_onboarding_saga_last_retry'...")
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_patient_onboarding_saga_last_retry 
                        ON patient_onboarding_saga (last_retry_at);
                    """)
                    
                    conn.commit()
                    print("✓ Migration 003 applied successfully!")
                
                # ============================================================
                # Migration 006: Add priority to messages
                # ============================================================
                print("\n📦 Migration 006: Add priority enum and column to messages")
                print("-" * 70)
                
                # Check if enum exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_type WHERE typname = 'message_priority'
                    )
                """)
                
                enum_exists = cur.fetchone()[0]
                
                if not enum_exists:
                    print("Creating enum 'message_priority'...")
                    cur.execute("""
                        CREATE TYPE message_priority AS ENUM (
                            'critical', 'high', 'normal', 'low'
                        );
                    """)
                    print("✓ Enum 'message_priority' created")
                else:
                    print("⚠ Enum 'message_priority' already exists")
                
                # Check if column exists
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'messages'
                    AND column_name = 'priority'
                """)
                
                if cur.fetchone():
                    print("⚠ Column 'priority' already exists, skipping...")
                else:
                    print("Adding column 'priority' to messages...")
                    cur.execute("""
                        ALTER TABLE messages 
                        ADD COLUMN priority message_priority NOT NULL DEFAULT 'normal'::message_priority;
                    """)
                    
                    conn.commit()
                    print("✓ Migration 006 applied successfully!")
                
                # ============================================================
                # Verification
                # ============================================================
                print("\n" + "=" * 70)
                print("VERIFICATION")
                print("=" * 70)
                
                # Verify patient_onboarding_saga.last_retry_at
                print("\n1. Checking patient_onboarding_saga.last_retry_at...")
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patient_onboarding_saga'
                    AND column_name = 'last_retry_at'
                """)
                result = cur.fetchone()
                if result:
                    print(f"   ✓ Column exists: {result[0]} ({result[1]}, nullable: {result[2]})")
                else:
                    print("   ✗ Column NOT FOUND!")
                
                # Verify index
                cur.execute("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'patient_onboarding_saga'
                    AND indexname = 'idx_patient_onboarding_saga_last_retry'
                """)
                if cur.fetchone():
                    print("   ✓ Index 'idx_patient_onboarding_saga_last_retry' exists")
                else:
                    print("   ✗ Index NOT FOUND!")
                
                # Verify messages.priority
                print("\n2. Checking messages.priority...")
                cur.execute("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'messages'
                    AND column_name = 'priority'
                """)
                result = cur.fetchone()
                if result:
                    print(f"   ✓ Column exists: {result[0]} ({result[1]}, default: {result[2]})")
                else:
                    print("   ✗ Column NOT FOUND!")
                
                # Verify enum
                cur.execute("""
                    SELECT typname, enumlabel 
                    FROM pg_type 
                    JOIN pg_enum ON pg_type.oid = pg_enum.enumtypid
                    WHERE typname = 'message_priority'
                    ORDER BY enumsortorder
                """)
                enum_values = cur.fetchall()
                if enum_values:
                    print(f"   ✓ Enum 'message_priority' exists with values:")
                    for val in enum_values:
                        print(f"     - {val[1]}")
                else:
                    print("   ✗ Enum NOT FOUND!")
                
                # Update alembic version
                print("\n3. Updating alembic version...")
                cur.execute("""
                    SELECT version_num FROM alembic_version
                """)
                current_version = cur.fetchone()
                if current_version:
                    print(f"   Current version: {current_version[0]}")
                
                # Update to latest migration
                cur.execute("""
                    UPDATE alembic_version 
                    SET version_num = '006_add_message_priority'
                """)
                conn.commit()
                print("   ✓ Alembic version updated to 006_add_message_priority")
                
                print("\n" + "=" * 70)
                print("✓ ALL MIGRATIONS APPLIED SUCCESSFULLY!")
                print("=" * 70)
                
    except Exception as e:
        print(f"\n✗ Error applying migrations: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    apply_migrations()
