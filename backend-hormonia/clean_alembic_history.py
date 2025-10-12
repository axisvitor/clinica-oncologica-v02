#!/usr/bin/env python3
"""
Clean Alembic History - Remove all migration records from database
This script cleans the alembic_version table so Alembic stops looking for removed migrations.
"""

import sys
import os
import logging

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_alembic_history():
    """Clean all Alembic migration records from database."""
    
    print("🧹 CLEANING ALEMBIC MIGRATION HISTORY")
    print("=" * 50)
    print("This will remove all migration records from alembic_version table")
    print("so Alembic stops looking for removed migration files.")
    print()
    
    try:
        from app.core.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as session:
            print("🔍 Checking current Alembic state...")
            
            # Check if alembic_version table exists
            result = session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            """)).fetchone()
            
            if not result:
                print("✅ alembic_version table doesn't exist - nothing to clean")
                return True
            
            # Check current version records
            current_versions = session.execute(text("""
                SELECT version_num FROM alembic_version ORDER BY version_num
            """)).fetchall()
            
            if current_versions:
                print(f"📋 Found {len(current_versions)} migration records:")
                for version in current_versions:
                    print(f"   - {version[0]}")
                print()
                
                # Clear all migration records
                print("🗑️ Removing all migration records...")
                session.execute(text("DELETE FROM alembic_version"))
                session.commit()
                print("✅ All migration records removed")
                
                # Verify cleanup
                remaining = session.execute(text("SELECT COUNT(*) FROM alembic_version")).fetchone()
                print(f"✅ Verification: {remaining[0]} records remaining (should be 0)")
                
            else:
                print("✅ alembic_version table is already empty")
            
            return True
            
    except Exception as e:
        print(f"❌ Error cleaning Alembic history: {e}")
        logger.error(f"Cleanup error: {e}", exc_info=True)
        return False

def reset_circuit_breaker():
    """Reset circuit breaker after cleanup."""
    try:
        print("🔄 Resetting circuit breaker...")
        from app.utils.db_retry import reset_circuit_breaker
        reset_circuit_breaker()
        print("✅ Circuit breaker reset")
        return True
    except Exception as e:
        print(f"❌ Error resetting circuit breaker: {e}")
        return False

def add_metadata_column_if_missing():
    """Add metadata column if it's missing."""
    try:
        print("🔍 Checking metadata column...")
        from app.core.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as session:
            # Check if metadata column exists
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'patients' 
                AND column_name = 'metadata'
                AND table_schema = 'public'
            """)).fetchone()
            
            if not result:
                print("📝 Adding missing metadata column...")
                session.execute(text("""
                    ALTER TABLE patients 
                    ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb
                """))
                session.commit()
                print("✅ metadata column added")
            else:
                print("✅ metadata column already exists")
            
            # Test the column
            session.execute(text("SELECT metadata FROM patients LIMIT 1"))
            print("✅ metadata column is accessible")
            
            return True
            
    except Exception as e:
        print(f"❌ Error with metadata column: {e}")
        return False

def main():
    """Run complete cleanup and fix."""
    
    success = True
    
    print("🚀 COMPLETE ALEMBIC CLEANUP AND DATABASE FIX")
    print("This will resolve all migration-related startup issues")
    print()
    
    # 1. Clean Alembic history
    print("Step 1: Clean Alembic Migration History")
    if not clean_alembic_history():
        success = False
    print()
    
    # 2. Add metadata column if missing
    print("Step 2: Ensure Metadata Column Exists")
    if not add_metadata_column_if_missing():
        success = False
    print()
    
    # 3. Reset circuit breaker
    print("Step 3: Reset Circuit Breaker")
    if not reset_circuit_breaker():
        success = False
    print()
    
    # Final result
    print("=" * 50)
    if success:
        print("🎉 COMPLETE CLEANUP SUCCESSFUL!")
        print()
        print("✅ Alembic migration history cleared")
        print("✅ metadata column ensured in patients table")
        print("✅ Circuit breaker reset to CLOSED state")
        print()
        print("The container should now start without any migration errors.")
        print("The patients endpoint should return 200 with patient data.")
    else:
        print("❌ CLEANUP FAILED")
        print("Some steps failed. Check the error messages above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())