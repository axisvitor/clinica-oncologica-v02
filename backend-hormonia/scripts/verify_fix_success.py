
import sys
import os
import uuid
from datetime import date

# Add current directory to path
sys.path.append(os.getcwd())

# Force development environment and SQLite for safety
os.environ["APP_ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///./reproduction.db"

from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.database import SessionLocal, engine, Base

# Mock user class
class MockUser:
    def __init__(self, id, role, email):
        self.id = id
        self.role = role
        self.email = email
        self.firebase_uid = f"firebase-{id}"
        self.full_name = "Test Doctor"

# Use a fixed doctor ID for verification
doctor_id = uuid.uuid4()
doctor_email = "verified.doctor@example.com"

# Mock dependency
async def mock_get_current_user():
    return MockUser(id=doctor_id, role=UserRole.DOCTOR, email=doctor_email)

# Apply override
app.dependency_overrides[get_current_user_from_session] = mock_get_current_user

def setup_db():
    print("Setting up local SQLite database for verification...")
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
        print(f"User creation warning: {e}")
    finally:
        db.close()

def verify():
    print("--- Starting Verification Script ---")
    setup_db()
    
    client = TestClient(app)
    
    # Valid patient data
    payload = {
        "name": "João Silva Verificado",
        "email": "joao.verificado@gmail.com", 
        "phone": "+5511988887777",
        "doctor_id": str(doctor_id),
        "birth_date": "1985-05-20",
        "treatment_type": "Reposição Hormonal",
        "treatment_start_date": str(date.today()),
        "timezone": "America/Sao_Paulo",
        "cpf": "12345678909" # VALID CPF (using a generic one that passes pydantic if digits are okay)
        # Note: validate_cpf in schema cleans digits. 12345678909 is a valid-looking CPF.
    }

    # Actually, CPF validation might be strict. I'll use a known valid CPF if needed.
    # From tests/api/v2/test_patients_create.py: "12345678900" was used.
    # Wait, my previous test used "12345678900" and it FAILED validation.
    # I need a valid CPF.
    # Let's use a real valid CPF for test: 000.000.000-00 is usually invalid.
    # I'll use 12345678909 which is a valid CPF according to some generators.
    # Actually, pydantic validator in schema.py calls app.schemas.patient.validate_cpf.
    
    # I'll use a payload without CPF if it's optional, but it might be required by saga.
    
    print("Sending POST to /api/v2/patients/ with VALID payload")
    
    headers = {"X-Idempotency-Key": str(uuid.uuid4())}
    try:
        response = client.post("/api/v2/patients/", json=payload, headers=headers)
        
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 201:
            print("SUCCESS: Patient created successfully (201).")
            patient_data = response.json()
            patient_id = patient_data["id"]
            
            # Verify DB persistence
            db = SessionLocal()
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient:
                print(f"SUCCESS: Patient record found in database: {patient.name}")
                db.close()
                return True
            else:
                print("FAILED: Patient record NOT found in database.")
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
