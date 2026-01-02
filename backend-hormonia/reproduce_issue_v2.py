
import sys
import os
import uuid
from datetime import date
from fastapi.testclient import TestClient

# Add current directory to path
sys.path.append(os.getcwd())

from app.main import app
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User, UserRole
from app.database import SessionLocal
from app.utils.security import get_password_hash

# Mock user class for dependency override (we still use this for auth, but we need the user in DB for foreign key checks)
class MockUser:
    def __init__(self, id, role):
        self.id = id
        self.role = role
        self.email = f"test.doctor.{id}@hormonia.com.br"
        self.firebase_uid = "mock-firebase-uid"

# Generate a doctor ID
doctor_id = uuid.uuid4()

# Setup database
def setup_db():
    db = SessionLocal()
    try:
        # Check if user exists or create one
        # We create a user with the specific UUID we want to use
        user = User(
            id=doctor_id,
            email=f"test.doctor.{doctor_id}@hormonia.com.br",
            full_name="Test Doctor",
            hashed_password=get_password_hash("password"),
            role=UserRole.DOCTOR,
            is_active=True,
            firebase_uid=f"firebase-{doctor_id}"
        )
        db.add(user)
        db.commit()
        print(f"Created/Ensured Doctor User: {doctor_id}")
    except Exception as e:
        db.rollback()
        # If it fails, maybe it already exists or constraint violation, we'll try to fetch it
        print(f"User creation warning (might already exist): {e}")
    finally:
        db.close()

# Mock dependency
async def mock_get_current_user():
    return MockUser(id=doctor_id, role=UserRole.DOCTOR)

# Apply override
app.dependency_overrides[get_current_user_from_session] = mock_get_current_user

client = TestClient(app)

def reproduce():
    print("--- Starting Reproduction Script ---")
    setup_db()
    
    # Payload for creating a patient
    # Using a valid email domain to avoid MX check failures if enabled
    payload = {
        "name": "Test Patient",
        "email": "joao.patient@gmail.com", 
        "phone": "+5511999999999",
        "doctor_id": str(doctor_id),
        "birth_date": "1990-01-01",
        "treatment_type": "Reposição Hormonal",
        "treatment_start_date": str(date.today()),
        "timezone": "America/Sao_Paulo"
    }

    print(f"Sending POST to /api/v2/patients/ with payload: {payload}")
    
    headers = {"X-Idempotency-Key": str(uuid.uuid4())}
    try:
        response = client.post("/api/v2/patients/", json=payload, headers=headers)
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")
        
        if response.status_code == 201:
            print("SUCCESS: Patient created successfully (201).")
            patient_id = response.json()["id"]
            
            # 2. GET Patient
            print(f"Sending GET to /api/v2/patients/{patient_id}")
            get_response = client.get(f"/api/v2/patients/{patient_id}")
            print(f"GET Response Status: {get_response.status_code}")
            if get_response.status_code == 200:
                 print("SUCCESS: Patient retrieved.")
            else:
                 print(f"FAILED: Could not retrieve patient. {get_response.text}")

            # 3. PATCH Patient
            print(f"Sending PATCH to /api/v2/patients/{patient_id}")
            patch_payload = {"phone": "+5511988888888", "doctor_notes": "Updated notes"}
            patch_response = client.patch(f"/api/v2/patients/{patient_id}", json=patch_payload)
            print(f"PATCH Response Status: {patch_response.status_code}")
            if patch_response.status_code == 200:
                print("SUCCESS: Patient updated.")
                updated_data = patch_response.json()
                if updated_data["phone"] == "+5511988888888" and updated_data["doctor_notes"] == "Updated notes":
                    print("SUCCESS: Data verified.")
                else:
                    print("FAILED: Data mismatch.")
            else:
                print(f"FAILED: Could not update patient. {patch_response.text}")

        elif response.status_code == 500:
            print("SUCCESS: Reproduced 500 Internal Server Error.")
        else:
            print(f"FAILED: Did not reproduce 500. Got {response.status_code}.")
            
    except Exception as e:
        print(f"Exception during request: {e}")

if __name__ == "__main__":
    reproduce()
