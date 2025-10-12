#!/usr/bin/env python3
"""
DIRECT DATABASE FIX - Final Solution
Executes SQL directly on database and resets circuit breaker.
No Alembic dependencies.
"""

import sys
import os
import logging

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def execute_sql_fix():
    """Execute the SQL fix directly on the database."""
    
    print("🔧 EXECUTING DIRECT DATABASE FIX")
    print("=" * 50)
    
    try:
        from app.core.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as session:
            print("🔍 Checking and fixing database schema...")
            
            # Execute the metadata column fix
            sql_fix = """
            DO $$
            BEGIN
                -- Check if the column exists
                IF NOT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patients' 
                    AND column_name = 'metadata'
                ) THEN
                    -- Add the metadata column
                    ALTER TABLE patients ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
                    RAISE NOTICE 'metadata column added to patients table';
                ELSE
                    RAISE NOTICE 'metadata column already exists in patients table';
                END IF;
            END $$;
            """
            
            session.execute(text(sql_fix))
            session.commit()
            print("✅ SQL fix executed successfully")
            
            # Verify the fix worked
            result = session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'patients' 
                AND column_name = 'metadata'
            """)).fetchone()
            
            if result:
                print(f"✅ metadata column verified: {result}")
            else:
                print("❌ metadata column not found after fix")
                return False
            
            # Test querying the column
            test_result = session.execute(text("SELECT metadata FROM patients LIMIT 1")).fetchone()
            print("✅ metadata column is queryable")
            
            return True
            
    except Exception as e:
        print(f"❌ Database fix failed: {e}")
        logger.error(f"Database fix error: {e}", exc_info=True)
        return False

def reset_circuit_breaker():
    """Reset the circuit breaker."""
    try:
        print("🔄 Resetting circuit breaker...")
        from app.utils.db_retry import reset_circuit_breaker
        reset_circuit_breaker()
        print("✅ Circuit breaker reset to CLOSED state")
        return True
    except Exception as e:
        print(f"❌ Error resetting circuit breaker: {e}")
        return False

def test_patients_endpoint():
    """Test the patients query that was failing."""
    try:
        print("🧪 Testing patients query...")
        from app.core.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as session:
            # Test the exact query pattern that SQLAlchemy generates
            result = session.execute(text("""
                SELECT 
                    patients.doctor_id AS patients_doctor_id,
                    patients.phone AS patients_phone,
                    patients.name AS patients_name,
                    patients.email AS patients_email,
                    patients.metadata AS patients_metadata,
                    patients.id AS patients_id,
                    patients.created_at AS patients_created_at,
                    patients.updated_at AS patients_updated_at
                FROM patients 
                LIMIT 1
            """)).fetchone()
            
            print("✅ SQLAlchemy-style query works correctly")
            
            # Test count query (used in pagination)
            count_result = session.execute(text("SELECT COUNT(*) FROM patients")).fetchone()
            print(f"✅ Count query works: {count_result[0]} patients in database")
            
            return True
            
    except Exception as e:
        print(f"❌ Patients query test failed: {e}")
        logger.error(f"Query test error: {e}", exc_info=True)
        return False

def main():
    """Execute the complete fix."""
    
    success = True
    
    print("🚀 STARTING DIRECT DATABASE FIX")
    print("This will bypass all Alembic issues and fix the database directly")
    print()
    
    # 1. Execute SQL fix
    print("Step 1: Database Schema Fix")
    if not execute_sql_fix():
        success = False
    print()
    
    # 2. Reset circuit breaker
    print("Step 2: Circuit Breaker Reset")
    if not reset_circuit_breaker():
        success = False
    print()
    
    # 3. Test patients endpoint
    print("Step 3: Endpoint Testing")
    if not test_patients_endpoint():
        success = False
    print()
    
    # Final result
    print("=" * 50)
    if success:
        print("🎉 DIRECT DATABASE FIX COMPLETED SUCCESSFULLY!")
        print()
        print("✅ metadata column added to patients table")
        print("✅ Circuit breaker reset to CLOSED state") 
        print("✅ Patients queries working correctly")
        print()
        print("The application should now work without any migration issues.")
        print("You can restart the container and the patients endpoint should return 200.")
    else:
        print("❌ DIRECT DATABASE FIX FAILED")
        print("Some steps failed. Check the error messages above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())