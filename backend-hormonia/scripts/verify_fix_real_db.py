
import sys
import os
import uuid
from datetime import date
import json

# Add current directory to path
sys.path.append(os.getcwd())

from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.database import SessionLocal

# Real doctor ID from DB
doctor_id_str = "a86624ba-acf9-419b-b83b-6162e71c94ae"
doctor_uuid = uuid.UUID(doctor_id_str)

# Mock user class for session auth simulation
class MockUser:
    def __init__(self, id, role, email):
        self.id = id
        self.role = role
        self.email = email
        self.firebase_uid = f"firebase-{id}"
        self.full_name = "Real Doctor Mock"

async def mock_get_current_user():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == doctor_uuid).first()
        if not user:
            print(f"CRITICAL: Doctor {doctor_id_str} not found in real DB!")
            sys.exit(1)
        return user
    finally:
        db.close()

# Apply override
app.dependency_overrides[get_current_user_from_session] = mock_get_current_user

def verify():
    print("--- Starting Real DB Verification Script ---")
    
    client = TestClient(app)
    
    # Valid patient data with unique elements to avoid conflicts
    unique_suffix = str(uuid.uuid4())[:8]
    payload = {
        "name": f"Patient Real DB {unique_suffix}",
        "email": f"patient.{unique_suffix}@gmail.com", 
        "phone": "+55119" + "".join([str(uuid.uuid4().int % 10) for _ in range(8)]),
        "doctor_id": doctor_id_str,
        "birth_date": "1985-05-20",
        "treatment_type": "Reposição Hormonal",
        "treatment_start_date": str(date.today()),
        "timezone": "America/Sao_Paulo",
        "cpf": "12345678909" # Valid CPF digits
    }

    print(f"Sending POST to /api/v2/patients/ with data: {json.dumps(payload, indent=2)}")
    
    headers = {"X-Idempotency-Key": str(uuid.uuid4())}
    try:
        response = client.post("/api/v2/patients/", json=payload, headers=headers)
        
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 201:
            print("SUCCESS: Patient created successfully in REAL DB (201).")
            patient_data = response.json()
            patient_id = patient_data["id"]
            
            # Verify DB persistence
            db = SessionLocal()
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient:
                print(f"SUCCESS: Patient record verified in real database: {patient.name}")
                db.close()
                return True
            else:
                print("FAILED: Patient record NOT found in database after success response.")
                db.close()
                return False
        else:
            print(f"FAILED: Got status {response.status_code}.")
            print(f"Content: {response.text}")
            return False
            
    except Exception as e:
        print(f"Exception during request: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if not verify():
        sys.exit(1)
