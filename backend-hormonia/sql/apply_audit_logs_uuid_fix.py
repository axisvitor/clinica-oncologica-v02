#!/usr/bin/env python3
"""
Apply the audit_logs user_id UUID type fix.

This script fixes the type mismatch between the SQLAlchemy model (UUID)
and the database schema (String) for the audit_logs.user_id column.
"""
import os
import sys
import psycopg
from urllib.parse import urlparse

def get_database_url():
    """Get database URL from environment."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    return db_url

def apply_uuid_fix():
    """Apply the UUID type fix to audit_logs.user_id column."""
    
    db_url = get_database_url()
    
    # Parse the database URL
    parsed = urlparse(db_url)
    
    try:
        # Connect to database
        print("🔗 Connecting to database...")
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                print("🔍 Checking current audit_logs table structure...")
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'audit_logs' AND column_name = 'user_id'
                """)
                
                result = cur.fetchone()
                if not result:
                    print("❌ audit_logs table or user_id column not found")
                    return False
                    
                column_name, data_type, is_nullable = result
                print(f"📊 Current user_id column: {data_type} (nullable: {is_nullable})")
                
                if data_type == 'uuid':
                    print("✅ user_id column is already UUID type. No fix needed.")
                    return True
                
                print("🔧 Applying UUID type fix...")
                
                # Step 1: Add temporary UUID column
                print("   1. Adding temporary UUID column...")
                cur.execute("ALTER TABLE audit_logs ADD COLUMN user_id_temp UUID")
                
                # Step 2: Clean up empty string values
                print("   2. Cleaning up empty string values...")
                cur.execute("""
                    UPDATE audit_logs 
                    SET user_id = NULL 
                    WHERE user_id = ''
                """)
                
                # Step 3: Convert existing data
                print("   3. Converting existing data to UUID format...")
                cur.execute("""
                    UPDATE audit_logs 
                    SET user_id_temp = user_id::uuid 
                    WHERE user_id IS NOT NULL
                """)
                
                affected_rows = cur.rowcount
                print(f"      Converted {affected_rows} rows")
                
                # Step 4: Drop old column and index
                print("   4. Dropping old column and index...")
                cur.execute("DROP INDEX IF EXISTS idx_audit_user_event_time")
                cur.execute("ALTER TABLE audit_logs DROP COLUMN user_id")
                
                # Step 5: Rename temp column
                print("   5. Renaming temporary column...")
                cur.execute("ALTER TABLE audit_logs RENAME COLUMN user_id_temp TO user_id")
                
                # Step 6: Recreate index
                print("   6. Recreating index...")
                cur.execute("CREATE INDEX idx_audit_user_event_time ON audit_logs (user_id, event_type, created_at)")
                
                # Verify the change
                print("🔍 Verifying the fix...")
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'audit_logs' AND column_name = 'user_id'
                """)
                
                result = cur.fetchone()
                if result:
                    column_name, data_type, is_nullable = result
                    print(f"✅ Updated user_id column: {data_type} (nullable: {is_nullable})")
                    
                    if data_type == 'uuid':
                        print("🎉 UUID type fix applied successfully!")
                        return True
                    else:
                        print(f"❌ Fix failed. Column is still {data_type}")
                        return False
                else:
                    print("❌ Could not verify the fix")
                    return False
                    
    except Exception as e:
        print(f"❌ Error applying UUID fix: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Audit Logs UUID Type Fix")
    print("=" * 50)
    
    success = apply_uuid_fix()
    
    if success:
        print("\n✅ Fix completed successfully!")
        print("   The audit_logs.user_id column is now UUID type.")
        print("   You can now restart your application to use the fixed schema.")
    else:
        print("\n❌ Fix failed. Check the error messages above.")
        sys.exit(1)