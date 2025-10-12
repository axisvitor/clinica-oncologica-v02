#!/usr/bin/env python3
"""
DIRECT DATABASE FIX: Add metadata column directly to database
This script bypasses Alembic completely and fixes the database schema directly.
This is the definitive solution for the metadata column issue.
"""

import sys
import os
import logging

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def emergency_add_metadata_column():
    """Add metadata column directly to database, bypassing Alembic."""
    
    print("🔧 DIRECT DATABASE SCHEMA FIX")
    print("=" * 60)
    print("Adding metadata column directly to patients table")
    print("Bypassing Alembic to resolve migration chain issues")
    print()
    
    try:
        from app.core.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as session:
            print("🔍 Checking current database state...")
            
            # 1. Check if patients table exists
            result = session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'patients'
            """)).fetchone()
            
            if not result:
                print("❌ ERROR: patients table does not exist!")
                print("   The database may not be properly initialized.")
                return False
            
            print("✅ patients table exists")
            
            # 2. Check if metadata column exists
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'patients' 
                AND column_name = 'metadata'
                AND table_schema = 'public'
            """)).fetchone()
            
            if result:
                print("✅ metadata column already exists")
                
                # Test if it's accessible
                try:
                    test_result = session.execute(text("SELECT metadata FROM patients LIMIT 1")).fetchone()
                    print("✅ metadata column is accessible")
                    return True
                except Exception as e:
                    print(f"⚠️ metadata column exists but has issues: {e}")
                    return False
            
            # 3. Add the metadata column
            print("📝 Adding metadata column...")
            
            try:
                session.execute(text("""
                    ALTER TABLE patients 
                    ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb
                """))
                session.commit()
                print("✅ metadata column added successfully")
                
                # 4. Verify it works
                test_result = session.execute(text("SELECT metadata FROM patients LIMIT 1")).fetchone()
                print("✅ metadata column is accessible after creation")
                
                return True
                
            except Exception as e:
                print(f"❌ Error adding metadata column: {e}")
                session.rollback()
                return False
                
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        logger.error(f"Connection error: {e}", exc_info=True)
        return False

def reset_circuit_breaker():
    """Reset circuit breaker after fixing database."""
    try:
        print("🔄 Resetting circuit breaker...")
        from app.utils.db_retry import reset_circuit_breaker
        reset_circuit_breaker()
        print("✅ Circuit breaker reset")
        return True
    except Exception as e:
        print(f"❌ Error resetting circuit breaker: {e}")
        return False

def test_patients_query():
    """Test if patients query works after fix."""
    try:
        print("🧪 Testing patients query...")
        from app.core.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as session:
            # Test the exact query that was failing
            result = session.execute(text("""
                SELECT patients.doctor_id, patients.phone, patients.name, 
                       patients.email, patients.metadata, patients.id, 
                       patients.created_at, patients.updated_at 
                FROM patients 
                LIMIT 1
            """)).fetchone()
            
            print("✅ Patients query works correctly")
            return True
            
    except Exception as e:
        print(f"❌ Patients query still failing: {e}")
        return False

def main():
    """Run emergency fix."""
    
    success = True
    
    # 1. Fix metadata column
    if not emergency_add_metadata_column():
        success = False
    
    # 2. Reset circuit breaker
    if not reset_circuit_breaker():
        success = False
    
    # 3. Test patients query
    if not test_patients_query():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 EMERGENCY FIX COMPLETED SUCCESSFULLY!")
        print("The patients endpoint should now work.")
        print("You can now restart the application.")
    else:
        print("❌ EMERGENCY FIX FAILED")
        print("Manual intervention may be required.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())