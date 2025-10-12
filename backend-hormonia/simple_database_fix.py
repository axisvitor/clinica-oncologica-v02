#!/usr/bin/env python3
"""
Simple Database Fix - No App Dependencies
This script connects directly to PostgreSQL and fixes the issues without loading app config.
"""

import os
import sys
import psycopg
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment variables."""
    # Try common environment variable names
    db_url = (
        os.getenv('DATABASE_URL') or 
        os.getenv('POSTGRES_URL') or 
        os.getenv('DB_URL') or
        os.getenv('SUPABASE_DB_URL')
    )
    
    if not db_url:
        print("❌ No database URL found in environment variables")
        print("   Please set one of: DATABASE_URL, POSTGRES_URL, DB_URL, SUPABASE_DB_URL")
        return None
    
    return db_url

def clean_alembic_and_fix_schema():
    """Clean Alembic history and fix schema issues."""
    
    print("🔧 SIMPLE DATABASE FIX")
    print("=" * 40)
    
    db_url = get_database_url()
    if not db_url:
        return False
    
    try:
        print(f"🔌 Connecting to database...")
        
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("✅ Connected to database")
                
                # 1. Check and clean alembic_version table
                print("\n🧹 Cleaning Alembic migration history...")
                
                # Check if alembic_version exists
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                """)
                
                if cur.fetchone():
                    # Show current versions
                    cur.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
                    versions = cur.fetchall()
                    
                    if versions:
                        print(f"   Found {len(versions)} migration records:")
                        for version in versions:
                            print(f"   - {version[0]}")
                        
                        # Clear all records
                        cur.execute("DELETE FROM alembic_version")
                        print("   ✅ All migration records removed")
                    else:
                        print("   ✅ alembic_version table already empty")
                else:
                    print("   ✅ alembic_version table doesn't exist")
                
                # 2. Check and add metadata column
                print("\n📝 Checking metadata column...")
                
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'patients' 
                    AND column_name = 'metadata'
                    AND table_schema = 'public'
                """)
                
                if not cur.fetchone():
                    print("   Adding missing metadata column...")
                    cur.execute("""
                        ALTER TABLE patients 
                        ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb
                    """)
                    print("   ✅ metadata column added")
                else:
                    print("   ✅ metadata column already exists")
                
                # 3. Test metadata column access
                print("\n🧪 Testing metadata column access...")
                cur.execute("SELECT metadata FROM patients LIMIT 1")
                print("   ✅ metadata column is accessible")
                
                # 4. Get patient count
                cur.execute("SELECT COUNT(*) FROM patients")
                count = cur.fetchone()[0]
                print(f"   ✅ Found {count} patients in database")
                
                # Commit all changes
                conn.commit()
                print("\n✅ All changes committed successfully")
                
                return True
                
    except Exception as e:
        print(f"\n❌ Database operation failed: {e}")
        logger.error(f"Database error: {e}", exc_info=True)
        return False

def main():
    """Run the simple database fix."""
    
    success = clean_alembic_and_fix_schema()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 DATABASE FIX COMPLETED!")
        print()
        print("✅ Alembic migration history cleaned")
        print("✅ metadata column ensured in patients table")
        print()
        print("The container should now start without migration errors.")
        print("The patients endpoint should work correctly.")
    else:
        print("❌ DATABASE FIX FAILED")
        print("Check the error messages above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())