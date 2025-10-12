#!/usr/bin/env python3
"""
Fix Patients Endpoint
Create a simplified version of the patients endpoint to identify and fix the 500 error.
"""

import os
import sys

def setup_environment():
    """Setup required environment variables."""
    required_vars = {
        'SECRET_KEY': 'TVj0AS9r2O7FaF7uUri4NtUMOEqyK8jf74nrWdgTwZWcNGsYZvhXJd9nMn4UzeAgzbusLuklRgegN8cvCuj8uQ',
        'DATABASE_URL': 'postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require',
        'JWT_SECRET_KEY': 'mYEeH00AvOtRUzpnqSDRerjFT4N-e5a1ywO-G5RCpwrHGH2Wktpx69qrMmCce9Lj8Tagsi_yTRHmpZg6JvX4oQ',
        'ENVIRONMENT': 'development',
        'DEBUG': 'true',
        'SESSION_COOKIE_SECURE': 'false',
        'SECURE_SSL_REDIRECT': 'false',
        'CSRF_SECRET_KEY': '-XJAoZm6wrtv1dc2WGDa_CQ03ZC99sQ1TLrCHxH2qe4',
        'ALLOWED_ORIGINS': '["http://localhost:3000"]',
        'FIREBASE_ADMIN_PROJECT_ID': 'sistema-oncologico-auth',
        'FIREBASE_ADMIN_CLIENT_EMAIL': 'firebase-adminsdk-fbsvc@sistema-oncologico-auth.iam.gserviceaccount.com',
        'FIREBASE_ADMIN_PRIVATE_KEY': '""',  # Empty for testing
        'REDIS_URL': 'redis://localhost:6379/0',
        'ENABLE_REDIS': 'false',
        'MONTHLY_QUIZ_TOKEN_SECRET': 'vfqzMK9OmQYX7uZnkihOIpj38eiiu9zcJOcEt7MZaZI',
        'MONTHLY_QUIZ_BASE_URL': 'http://localhost:3000',
        'GEMINI_API_KEY': 'test-key',
        'EVOLUTION_API_KEY': 'test-key'
    }
    
    for key, value in required_vars.items():
        os.environ[key] = value

def test_patients_endpoint_logic():
    """Test the patients endpoint logic step by step."""
    
    print("🔧 FIXING PATIENTS ENDPOINT")
    print("=" * 40)
    
    setup_environment()
    
    try:
        # Step 1: Test basic imports
        print("1. Testing basic imports...")
        from app.database import engine, SessionLocal
        from sqlalchemy import text
        print("✅ Database imports successful")
        
        # Step 2: Test database query directly
        print("2. Testing direct database query...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, phone, email, treatment_type, flow_state, created_at
                FROM patients 
                ORDER BY created_at DESC 
                LIMIT 5
            """))
            patients = result.fetchall()
            print(f"✅ Found {len(patients)} patients directly from database")
        
        # Step 3: Test PatientService
        print("3. Testing PatientService...")
        from app.services.patient import PatientService
        
        db = SessionLocal()
        try:
            patient_service = PatientService(db)
            print("✅ PatientService created successfully")
            
            # Test list_patients method
            patients, total = patient_service.list_patients(
                doctor_id='63db7cfc-12c8-4c03-a0e5-3773844e799c',  # Known doctor ID
                page=1,
                size=20
            )
            print(f"✅ PatientService.list_patients returned {len(patients)} patients (total: {total})")
            
        finally:
            db.close()
        
        # Step 4: Test ServiceProvider
        print("4. Testing ServiceProvider...")
        try:
            from app.services import ServiceProvider
            
            db = SessionLocal()
            try:
                provider = ServiceProvider(db)
                print("✅ ServiceProvider created successfully")
                
                # Test patient_service property
                patient_svc = provider.patient_service
                print(f"✅ ServiceProvider.patient_service: {type(patient_svc).__name__}")
                
            finally:
                db.close()
                
        except Exception as e:
            print(f"❌ ServiceProvider failed: {e}")
            return False
        
        # Step 5: Test dependency injection
        print("5. Testing dependency injection...")
        try:
            from app.dependencies.service_dependencies import get_patient_service
            print("✅ get_patient_service dependency imported")
            
            # Test the dependency callable
            print(f"✅ Dependency function: {get_patient_service}")
            
        except Exception as e:
            print(f"❌ Dependency injection failed: {e}")
            return False
        
        print("\n🎉 ALL TESTS PASSED!")
        print("\nThe issue is likely in:")
        print("  - Railway environment variables not being loaded")
        print("  - FastAPI dependency resolution in production")
        print("  - Session manager initialization")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_simple_patients_endpoint():
    """Create a simplified patients endpoint file."""
    
    print("\n📝 Creating simplified patients endpoint...")
    
    simple_endpoint = '''"""
Simple Patients Endpoint - Debugging Version
This is a minimal version to identify the 500 error.
"""
from typing import List
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.database import engine

router = APIRouter()

@router.get("/simple")
async def list_patients_simple():
    """Simple patients list without dependencies."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, phone, email, treatment_type, flow_state, created_at
                FROM patients 
                ORDER BY created_at DESC 
                LIMIT 10
            """))
            patients = result.fetchall()
            
            return {
                "data": [
                    {
                        "id": str(p[0]),
                        "name": p[1],
                        "phone": p[2],
                        "email": p[3],
                        "treatment_type": p[4],
                        "flow_state": p[5],
                        "created_at": p[6].isoformat() if p[6] else None
                    }
                    for p in patients
                ],
                "total": len(patients),
                "message": "Simple endpoint working"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
'''
    
    with open('backend-hormonia/app/api/v1/patients_simple.py', 'w') as f:
        f.write(simple_endpoint)
    
    print("✅ Created simple patients endpoint at app/api/v1/patients_simple.py")
    print("   Add this to your router registry to test: /api/v1/patients/simple")

def main():
    """Run the fix process."""
    success = test_patients_endpoint_logic()
    
    if success:
        create_simple_patients_endpoint()
        print("\n🎯 NEXT STEPS:")
        print("1. Add the simple endpoint to your router")
        print("2. Test /api/v1/patients/simple to verify it works")
        print("3. Compare with the original endpoint to find the issue")
        print("4. Check Railway environment variables configuration")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())