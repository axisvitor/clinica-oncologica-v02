
import sys
import os
import uuid
from datetime import date
import json

# Add current directory to path
sys.path.append(os.getcwd())

# Force development environment and SQLite for safety
os.environ["APP_ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///./reproduction.db"

# Mock ENCRYPTION_KEY if not set
if "ENCRYPTION_KEY" not in os.environ:
    os.environ["ENCRYPTION_KEY"] = "TUMDOz5ZjuMiKaUDLsOim7IGS5KSLhRevvuhyNx5ALQ="

from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User, UserRole
from app.database import SessionLocal, engine, Base

# Mock user class
class MockUser:
    def __init__(self, id, role, email):
        self.id = id
        self.role = role
        self.email = email
        self.firebase_uid = f"firebase-{id}"
        self.full_name = "Test Doctor"

# Generate a doctor ID
doctor_id = uuid.uuid4()
doctor_email = f"test.doctor.{doctor_id}@example.com"

# Mock dependency
async def mock_get_current_user():
    return MockUser(id=doctor_id, role=UserRole.DOCTOR, email=doctor_email)

# Apply override
app.dependency_overrides[get_current_user_from_session] = mock_get_current_user

def setup_db():
    print("Setting up local SQLite database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.utils.security import get_password_hash
        user = User(
            id=doctor_id,
            email=doctor_email,
            full_name="Test Doctor",
            hashed_password=get_password_hash("password"),
            role=UserRole.DOCTOR,
            is_active=True,
            firebase_uid=f"firebase-{doctor_id}"
        )
        db.add(user)
        db.commit()
        print(f"Created Doctor User: {doctor_id}")
    except Exception as e:
        db.rollback()
        print(f"User creation error: {e}")
    finally:
        db.close()

def reproduce():
    print("--- Starting Reproduction Script v3 ---")
    setup_db()
    
    client = TestClient(app)
    
    # Payload for creating a patient
    payload = {
        "name": "Test Patient",
        "email": "test.patient@example.com", 
        "phone": "+5511999999999",
        "doctor_id": str(doctor_id),
        "birth_date": "1990-01-01",
        "treatment_type": "Reposição Hormonal",
        "treatment_start_date": str(date.today()),
        "timezone": "America/Sao_Paulo",
        "cpf": "12345678900" # Added CPF as it might be required by validators
    }

    print(f"Sending POST to /api/v2/patients/ with payload: {json.dumps(payload, indent=2)}")
    
    headers = {"X-Idempotency-Key": str(uuid.uuid4())}
    try:
        response = client.post("/api/v2/patients/", json=payload, headers=headers)
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")
        
        if response.status_code == 500:
            print("SUCCESS: Reproduced 500 Internal Server Error.")
            return True
        elif response.status_code == 201:
            print("FAILED: Got 201 Created. Bug not reproduced.")
            return False
        else:
            print(f"FAILED: Got status {response.status_code}.")
            return False
            
    except Exception as e:
        print(f"Exception during request: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    reproduce()
