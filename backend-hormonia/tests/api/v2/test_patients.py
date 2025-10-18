"""
Tests for Patients API v2
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.doctor import Doctor


class TestPatientsV2:
    """Test suite for patients v2 endpoints"""
    
    def test_list_patients_basic(self, client: TestClient, db: Session, auth_headers: dict):
        """Test basic patient listing"""
        response = client.get("/api/v2/patients", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data
        assert isinstance(data["data"], list)
    
    def test_list_patients_with_pagination(self, client: TestClient, db: Session, auth_headers: dict):
        """Test patient listing with pagination"""
        response = client.get(
            "/api/v2/patients?limit=5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) <= 5
    
    def test_list_patients_with_field_selection(self, client: TestClient, db: Session, auth_headers: dict):
        """Test patient listing with field selection"""
        response = client.get(
            "/api/v2/patients?fields=id,name,email",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["data"]:
            patient = data["data"][0]
            assert "id" in patient
            assert "name" in patient
            assert "email" in patient
            # These fields should not be present
            assert "phone" not in patient or patient.get("phone") is None
    
    def test_list_patients_with_eager_loading(self, client: TestClient, db: Session, auth_headers: dict):
        """Test patient listing with eager loading"""
        response = client.get(
            "/api/v2/patients?include=doctor",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["data"]:
            patient = data["data"][0]
            if patient.get("doctor"):
                assert "id" in patient["doctor"]
                assert "name" in patient["doctor"]
    
    def test_list_patients_with_search(self, client: TestClient, db: Session, auth_headers: dict):
        """Test patient listing with search"""
        response = client.get(
            "/api/v2/patients?search=test",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
    
    def test_get_patient_by_id(self, client: TestClient, db: Session, auth_headers: dict):
        """Test getting a single patient"""
        # Create a test patient first
        doctor = db.query(Doctor).first()
        if not doctor:
            pytest.skip("No doctor available for test")
        
        patient = Patient(
            name="Test Patient",
            email="test@example.com",
            doctor_id=doctor.id
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        
        response = client.get(
            f"/api/v2/patients/{patient.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == patient.id
        assert data["name"] == patient.name
        assert data["email"] == patient.email
    
    def test_get_patient_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting a non-existent patient"""
        response = client.get(
            "/api/v2/patients/999999",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_create_patient(self, client: TestClient, db: Session, auth_headers: dict):
        """Test creating a new patient"""
        doctor = db.query(Doctor).first()
        if not doctor:
            pytest.skip("No doctor available for test")
        
        patient_data = {
            "name": "New Patient",
            "email": f"new_patient_{pytest.timestamp}@example.com",
            "phone": "(11) 98765-4321",
            "doctor_id": doctor.id
        }
        
        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == patient_data["name"]
        assert data["email"] == patient_data["email"]
    
    def test_create_patient_duplicate_email(self, client: TestClient, db: Session, auth_headers: dict):
        """Test creating a patient with duplicate email"""
        doctor = db.query(Doctor).first()
        if not doctor:
            pytest.skip("No doctor available for test")
        
        # Create first patient
        patient = Patient(
            name="Existing Patient",
            email="existing@example.com",
            doctor_id=doctor.id
        )
        db.add(patient)
        db.commit()
        
        # Try to create duplicate
        patient_data = {
            "name": "Duplicate Patient",
            "email": "existing@example.com",
            "doctor_id": doctor.id
        }
        
        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )
        
        assert response.status_code == 409
    
    def test_update_patient(self, client: TestClient, db: Session, auth_headers: dict):
        """Test updating a patient"""
        doctor = db.query(Doctor).first()
        if not doctor:
            pytest.skip("No doctor available for test")
        
        # Create patient
        patient = Patient(
            name="Update Test",
            email="update@example.com",
            doctor_id=doctor.id
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        
        # Update patient
        update_data = {
            "phone": "(11) 91234-5678"
        }
        
        response = client.patch(
            f"/api/v2/patients/{patient.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["phone"] == update_data["phone"]
    
    def test_delete_patient(self, client: TestClient, db: Session, auth_headers: dict):
        """Test soft deleting a patient"""
        doctor = db.query(Doctor).first()
        if not doctor:
            pytest.skip("No doctor available for test")
        
        # Create patient
        patient = Patient(
            name="Delete Test",
            email="delete@example.com",
            doctor_id=doctor.id
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        
        # Delete patient
        response = client.delete(
            f"/api/v2/patients/{patient.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # Verify soft delete
        db.refresh(patient)
        assert patient.is_active == False
    
    def test_invalid_cursor(self, client: TestClient, auth_headers: dict):
        """Test with invalid cursor"""
        response = client.get(
            "/api/v2/patients?cursor=invalid_cursor",
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    def test_invalid_fields(self, client: TestClient, auth_headers: dict):
        """Test with empty fields parameter"""
        response = client.get(
            "/api/v2/patients?fields=",
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    def test_invalid_include(self, client: TestClient, auth_headers: dict):
        """Test with invalid include parameter"""
        response = client.get(
            "/api/v2/patients?include=invalid_relation",
            headers=auth_headers
        )
        
        assert response.status_code == 400


# Add timestamp for unique emails in tests
pytest.timestamp = int(__import__("time").time())
