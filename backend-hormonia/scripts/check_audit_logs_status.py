#!/usr/bin/env python3
"""
Check audit logs data status and provide backfill policy recommendations.
"""
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import get_settings

def check_audit_logs_status():
    """Check audit logs table status and data integrity."""
    print("🔍 Audit Logs Status Check")
    print("=" * 50)
    
    try:
        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if audit_logs table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'audit_logs'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("❌ audit_logs table does not exist")
                return
            
            print("✅ audit_logs table exists")
            
            # Check table structure
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'audit_logs' 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            
            print("\n📊 Table Structure:")
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                print(f"   {col[0]}: {col[1]} ({nullable})")
            
            # Check total record count
            result = conn.execute(text("SELECT COUNT(*) FROM audit_logs"))
            total_count = result.scalar()
            print(f"\n📊 Total Records: {total_count}")
            
            if total_count == 0:
                print("✅ No data in audit_logs table - no backfill needed")
                return
            
            # Check user_id column status
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(user_id) as with_user_id,
                    COUNT(*) - COUNT(user_id) as null_user_id
                FROM audit_logs
            """))
            counts = result.fetchone()
            
            print(f"\n📊 User ID Status:")
            print(f"   Total records: {counts[0]}")
            print(f"   With user_id: {counts[1]}")
            print(f"   NULL user_id: {counts[2]}")
            
            if counts[2] > 0:
                print(f"\n⚠️  Found {counts[2]} records with NULL user_id")
                
                # Check if user_id column is UUID type
                result = conn.execute(text("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'audit_logs' 
                    AND column_name = 'user_id'
                    AND table_schema = 'public'
                """))
                user_id_type = result.scalar()
                print(f"   user_id column type: {user_id_type}")
                
                # Sample some NULL user_id records
                result = conn.execute(text("""
                    SELECT id, event_type, created_at, ip_address
                    FROM audit_logs 
                    WHERE user_id IS NULL 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """))
                null_samples = result.fetchall()
                
                print(f"\n📋 Sample NULL user_id records:")
                for record in null_samples:
                    print(f"   ID: {record[0]}, Event: {record[1]}, Time: {record[2]}, IP: {record[3]}")
                
                print(f"\n💡 Backfill Policy Recommendations:")
                print(f"   1. KEEP NULLs (Recommended): Ensure code handles NULL user_id gracefully")
                print(f"   2. BACKFILL: Only if you can reliably determine user from context")
                print(f"   3. DELETE: Only if records are clearly invalid (NOT recommended)")
                
            else:
                print("✅ All records have valid user_id")
            
            # Check for any indexes on user_id
            result = conn.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes 
                WHERE tablename = 'audit_logs' 
                AND indexdef LIKE '%user_id%'
            """))
            indexes = result.fetchall()
            
            if indexes:
                print(f"\n📊 Indexes on user_id:")
                for idx in indexes:
                    print(f"   {idx[0]}: {idx[1]}")
            else:
                print(f"\n💡 Consider adding index on user_id for better performance")
                
    except Exception as e:
        print(f"❌ Error checking audit logs: {e}")
        return False
    
    print(f"\n✅ Audit logs check completed")
    return True

if __name__ == "__main__":
    check_audit_logs_status()