#!/usr/bin/env python3
"""
Check error logs table status after migration.
"""
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import get_settings

def check_error_logs_status():
    """Check error_logs table status after migration."""
    print("🔍 Error Logs Status Check")
    print("=" * 50)
    
    try:
        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if error_logs table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'error_logs'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("❌ error_logs table does not exist")
                return False
            
            print("✅ error_logs table exists")
            
            # Check table structure
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'error_logs' 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            
            print("\n📊 Table Structure:")
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                print(f"   {col[0]}: {col[1]} ({nullable})")
            
            # Check for indexes
            result = conn.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes 
                WHERE tablename = 'error_logs'
            """))
            indexes = result.fetchall()
            
            print(f"\n📊 Indexes:")
            for idx in indexes:
                print(f"   {idx[0]}: {idx[1]}")
            
            # Check total record count
            result = conn.execute(text("SELECT COUNT(*) FROM error_logs"))
            total_count = result.scalar()
            print(f"\n📊 Total Records: {total_count}")
            
            if total_count > 0:
                # Sample some records
                result = conn.execute(text("""
                    SELECT error_type, error_message, count, first_seen, last_seen
                    FROM error_logs 
                    ORDER BY last_seen DESC 
                    LIMIT 5
                """))
                samples = result.fetchall()
                
                print(f"\n📋 Sample records:")
                for record in samples:
                    print(f"   Type: {record[0]}, Message: {record[1][:50]}..., Count: {record[2]}")
            
    except Exception as e:
        print(f"❌ Error checking error logs: {e}")
        return False
    
    print(f"\n✅ Error logs check completed")
    return True

if __name__ == "__main__":
    check_error_logs_status()