#!/usr/bin/env python3
"""
Test Simple Patients Endpoint
Create a minimal version of the patients endpoint to identify the issue.
"""

import os
import sys
import asyncio
from datetime import datetime
from typing import List, Optional
from uuid import UUID

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

async def test_simple_patients():
    """Test a simplified version of the patients endpoint logic."""
    
    print("🧪 TESTING SIMPLE PATIENTS ENDPOINT LOGIC")
    print("=" * 50)
    
    try:
        # Test 1: Import basic modules
        print("1. Testing basic imports...")
        
        from app.database import get_engine
        from sqlalchemy import text
        
        print("✅ Basic imports successful")
        
        # Test 2: Database connection
        print("2. Testing database connection...")
        
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM patients"))
            count = result.scalar()
            print(f"✅ Database connection successful - {count} patients found")
        
        # Test 3: Test ServiceProvider import
        print("3. Testing ServiceProvider import...")
        
        try:
            from app.services import ServiceProvider
            print("✅ ServiceProvider import successful")
        except Exception as e:
            print(f"❌ ServiceProvider import failed: {e}")
            return False
        
        # Test 4: Test session manager
        print("4. Testing session manager...")
        
        try:
            from app.core.session_manager import get_session_manager
            session_manager = get_session_manager()
            print(f"✅ Session manager available: {type(session_manager).__name__}")
        except Exception as e:
            print(f"❌ Session manager failed: {e}")
            return False
        
        # Test 5: Test patient service creation
        print("5. Testing patient service creation...")
        
        try:
            from app.database import SessionLocal
            from app.services.patient import PatientService
            
            # Create a simple database session
            db = SessionLocal()
            try:
                patient_service = PatientService(db)
                print(f"✅ PatientService created successfully")
                
                # Test a simple query
                patients = db.execute(text("SELECT id, name FROM patients LIMIT 3")).fetchall()
                print(f"✅ Simple query successful - found {len(patients)} patients")
                
            finally:
                db.close()
                
        except Exception as e:
            print(f"❌ Patient service creation failed: {e}")
            return False
        
        # Test 6: Test dependency injection components
        print("6. Testing dependency injection...")
        
        try:
            from app.dependencies.service_dependencies import get_patient_service
            print("✅ get_patient_service import successful")
            
            # Test the dependency function (without calling it)
            print(f"✅ Dependency function available: {get_patient_service}")
            
        except Exception as e:
            print(f"❌ Dependency injection failed: {e}")
            return False
        
        # Test 7: Test authentication dependencies
        print("7. Testing authentication dependencies...")
        
        try:
            from app.dependencies.auth_dependencies import get_current_user
            print("✅ get_current_user import successful")
            
        except Exception as e:
            print(f"❌ Authentication dependencies failed: {e}")
            return False
        
        # Test 8: Test models
        print("8. Testing models...")
        
        try:
            from app.models.patient import Patient
            from app.models.user import User
            from app.schemas.patient import PatientResponse, PatientListResponse
            print("✅ Models and schemas import successful")
            
        except Exception as e:
            print(f"❌ Models import failed: {e}")
            return False
        
        print("\n🎉 ALL TESTS PASSED!")
        print("The issue might be in:")
        print("  - FastAPI dependency resolution")
        print("  - Request context initialization")
        print("  - Authentication middleware")
        print("  - ServiceProvider factory method")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test."""
    success = asyncio.run(test_simple_patients())
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())