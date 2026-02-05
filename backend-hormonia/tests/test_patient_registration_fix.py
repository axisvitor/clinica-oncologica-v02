
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import UserRole
import uuid

# Mock user for authentication
class MockUser:
    def __init__(self, id, role):
        self.id = id
        self.role = role
        self.email = "test.doctor@example.com"
        self.firebase_uid = "mock-firebase-uid"
        self.full_name = "Test Doctor"

@pytest.fixture
def authenticated_client():
    doctor_id = uuid.uuid4()
    mock_user = MockUser(id=doctor_id, role=UserRole.DOCTOR)
    
    app.dependency_overrides[get_current_user_from_session] = lambda: mock_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

def test_patient_registration_validation_error_returns_422(authenticated_client):
    """
    Test that an invalid patient registration (e.g. invalid CPF) 
    returns a 422 Unprocessable Entity instead of a 500 Internal Server Error.
    
    This test specifically targets the fix for non-serializable objects 
    in the validation error context.
    """
    payload = {
        "name": "Test Patient",
        "email": "test.patient@example.com", 
        "phone": "+5511999999999",
        "doctor_id": str(uuid.uuid4()), # Any UUID will do for validation phase
        "birth_date": "1990-01-01",
        "treatment_type": "Reposição Hormonal",
        "treatment_start_date": "2025-12-31",
        "timezone": "America/Sao_Paulo",
        "cpf": "12345678900" # INVALID CPF (wrong check digits)
    }
    
    response = authenticated_client.post("/api/v2/patients/", json=payload)
    
    # Assert 422 instead of 500
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "details" in data
