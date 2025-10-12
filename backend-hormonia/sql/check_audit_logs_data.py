#!/usr/bin/env python3
"""
Check audit_logs table data before running UUID migration.

This script helps identify potential issues with user_id values
that might cause the UUID migration to fail.
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

def check_audit_logs_data():
    """Check audit_logs table data for potential migration issues."""
    
    db_url = get_database_url()
    
    try:
        # Connect to database
        print("🔗 Connecting to database...")
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                # Check if audit_logs table exists
                print("🔍 Checking if audit_logs table exists...")
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'audit_logs'
                    )
                """)
                
                table_exists = cur.fetchone()[0]
                if not table_exists:
                    print("ℹ️  audit_logs table does not exist yet. Migration will create it.")
                    return True
                
                # Check table structure
                print("📊 Checking audit_logs table structure...")
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'audit_logs' 
                    ORDER BY ordinal_position
                """)
                
                columns = cur.fetchall()
                print("   Columns:")
                for col_name, data_type, is_nullable in columns:
                    print(f"   - {col_name}: {data_type} (nullable: {is_nullable})")
                
                # Check user_id column specifically
                user_id_col = next((col for col in columns if col[0] == 'user_id'), None)
                if not user_id_col:
                    print("❌ user_id column not found in audit_logs table")
                    return False
                
                _, user_id_type, _ = user_id_col
                print(f"\n🎯 user_id column type: {user_id_type}")
                
                if user_id_type == 'uuid':
                    print("✅ user_id is already UUID type. No migration needed.")
                    return True
                
                # Check data in user_id column
                print("\n🔍 Analyzing user_id data...")
                
                # Count total rows
                cur.execute("SELECT COUNT(*) FROM audit_logs")
                total_rows = cur.fetchone()[0]
                print(f"   Total rows: {total_rows}")
                
                if total_rows == 0:
                    print("✅ No data in audit_logs table. Migration will be safe.")
                    return True
                
                # Count NULL values
                cur.execute("SELECT COUNT(*) FROM audit_logs WHERE user_id IS NULL")
                null_count = cur.fetchone()[0]
                print(f"   NULL values: {null_count}")
                
                # Count empty strings
                cur.execute("SELECT COUNT(*) FROM audit_logs WHERE user_id = ''")
                empty_count = cur.fetchone()[0]
                print(f"   Empty strings: {empty_count}")
                
                # Count valid UUID-like strings
                cur.execute("""
                    SELECT COUNT(*) FROM audit_logs 
                    WHERE user_id IS NOT NULL 
                    AND user_id != ''
                    AND LENGTH(user_id) = 36
                    AND user_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                """)
                valid_uuid_count = cur.fetchone()[0]
                print(f"   Valid UUID format: {valid_uuid_count}")
                
                # Count invalid values
                cur.execute("""
                    SELECT COUNT(*) FROM audit_logs 
                    WHERE user_id IS NOT NULL 
                    AND user_id != ''
                    AND (LENGTH(user_id) != 36 OR user_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
                """)
                invalid_count = cur.fetchone()[0]
                print(f"   Invalid format: {invalid_count}")
                
                # Show sample invalid values if any
                if invalid_count > 0:
                    print("\n⚠️  Sample invalid user_id values:")
                    cur.execute("""
                        SELECT DISTINCT user_id FROM audit_logs 
                        WHERE user_id IS NOT NULL 
                        AND user_id != ''
                        AND (LENGTH(user_id) != 36 OR user_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
                        LIMIT 5
                    """)
                    invalid_samples = cur.fetchall()
                    for sample in invalid_samples:
                        print(f"      '{sample[0]}' (length: {len(sample[0])})")
                
                # Migration safety assessment
                print(f"\n📋 Migration Assessment:")
                if empty_count > 0:
                    print(f"   ⚠️  {empty_count} empty strings will be converted to NULL")
                if invalid_count > 0:
                    print(f"   ❌ {invalid_count} invalid values will cause migration to fail")
                    print("      These need to be cleaned up before migration")
                    return False
                else:
                    print("   ✅ All user_id values are valid for UUID conversion")
                    return True
                    
    except Exception as e:
        print(f"❌ Error checking audit_logs data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 Audit Logs Data Check")
    print("=" * 50)
    
    success = check_audit_logs_data()
    
    if success:
        print("\n✅ Data check completed. Migration should be safe to run.")
    else:
        print("\n❌ Data issues found. Fix these before running migration.")
        sys.exit(1)