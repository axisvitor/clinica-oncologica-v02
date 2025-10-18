"""
RBAC Tests for Patients API v2 - IMPLEMENTATION COMPLETE
Tests to prevent privacy regression - ensure doctors only see their own patients.

Issue: #16
Priority: P0 - Critical
Status: IMPLEMENTED
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from app.models.user import UserRole
from tests.conftest import create_test_user, create_test_patient


class TestPatientsRBAC:
    """Test Role-Based Access Control for patient endpoints."""
    
    def test_list_patients_rbac_doctor_sees_only_own(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Doctor can only list their own patients."""
        # Create second doctor
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        
        # Create patients
        own_patient = create_test_patient(db_session, doctor=test_user, name="Own Patient")
        other_patient = create_test_patient(db_session, doctor=doctor_b, name="Other Patient")
        
        response = client.get("/api/v2/patients", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        patient_ids = [p["id"] for p in data]
        assert str(own_patient.id) in patient_ids
        assert str(other_patient.id) not in patient_ids
        assert len(data) == 1
    
    def test_list_patients_rbac_admin_sees_all(
        self,
        client: TestClient,
        db_session,
        admin_user,
        admin_auth_headers
    ):
        """Admin can see all patients regardless of doctor_id."""
        # Create two doctors
        doctor_a = create_test_user(db_session, email="doctor_a@test.com", role=UserRole.DOCTOR)
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        
        # Create patients for each doctor
        patient_a = create_test_patient(db_session, doctor=doctor_a, name="Patient A")
        patient_b = create_test_patient(db_session, doctor=doctor_b, name="Patient B")
        
        response = client.get("/api/v2/patients", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        patient_ids = [p["id"] for p in data]
        assert str(patient_a.id) in patient_ids
        assert str(patient_b.id) in patient_ids
        assert len(data) == 2
    
    def test_get_patient_rbac_doctor_cannot_access_other_patient(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Doctor cannot access another doctor's patient (returns 404)."""
        # Create another doctor and their patient
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        other_patient = create_test_patient(db_session, doctor=doctor_b, name="Other Patient")
        
        response = client.get(f"/api/v2/patients/{other_patient.id}", headers=auth_headers)
        
        # Should return 404 to avoid info disclosure
        assert response.status_code == 404
    
    def test_get_patient_rbac_doctor_can_access_own(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Doctor can access their own patient."""
        own_patient = create_test_patient(db_session, doctor=test_user, name="Own Patient")
        
        response = client.get(f"/api/v2/patients/{own_patient.id}", headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["id"] == str(own_patient.id)
        assert response.json()["name"] == "Own Patient"
    
    def test_create_patient_sets_correct_doctor_id(
        self,
        client: TestClient,
        test_user,
        auth_headers
    ):
        """Creating a patient sets doctor_id to authenticated user."""
        from app.dependencies.auth_dependencies import get_doctor_user
        from app.main import app
        
        # Override get_doctor_user for write operations
        app.dependency_overrides[get_doctor_user] = lambda: test_user
        
        patient_data = {
            "name": "New Patient",
            "phone": "11999999999",
            "email": "newpatient@test.com",
            "doctor_id": str(test_user.id)
        }
        
        response = client.post("/api/v2/patients", json=patient_data, headers=auth_headers)
        
        assert response.status_code == 201
        assert response.json()["doctor_id"] == str(test_user.id)
        assert response.json()["name"] == "New Patient"
        
        # Cleanup
        app.dependency_overrides.clear()
    
    def test_update_patient_rbac_doctor_cannot_update_others(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Doctor cannot update another doctor's patient."""
        from app.dependencies.auth_dependencies import get_doctor_user
        from app.main import app
        
        # Create another doctor and their patient
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        other_patient = create_test_patient(db_session, doctor=doctor_b, name="Other Patient")
        
        # Override get_doctor_user for write operations
        app.dependency_overrides[get_doctor_user] = lambda: test_user
        
        update_data = {"name": "Hacked Name"}
        response = client.patch(
            f"/api/v2/patients/{other_patient.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
        
        # Cleanup
        app.dependency_overrides.clear()
    
    def test_delete_patient_rbac_doctor_cannot_delete_others(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Doctor cannot delete another doctor's patient."""
        from app.dependencies.auth_dependencies import get_doctor_user
        from app.main import app
        
        # Create another doctor and their patient
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        other_patient = create_test_patient(db_session, doctor=doctor_b, name="Other Patient")
        
        # Override get_doctor_user for write operations
        app.dependency_overrides[get_doctor_user] = lambda: test_user
        
        response = client.delete(f"/api/v2/patients/{other_patient.id}", headers=auth_headers)
        
        assert response.status_code == 404
        
        # Cleanup
        app.dependency_overrides.clear()
    
    def test_cursor_pagination_respects_rbac(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Cursor pagination only returns scoped patients."""
        from datetime import datetime, timedelta
        
        # Create another doctor
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        
        # Create 15 patients for test_user (doctor_a)
        for i in range(15):
            create_test_patient(
                db_session,
                doctor=test_user,
                name=f"Patient A{i}",
                created_at=datetime.utcnow() - timedelta(minutes=i)
            )
        
        # Create 15 patients for doctor_b (should NOT appear)
        for i in range(15):
            create_test_patient(
                db_session,
                doctor=doctor_b,
                name=f"Patient B{i}",
                created_at=datetime.utcnow() - timedelta(minutes=i)
            )
        
        # Fetch first page
        response1 = client.get("/api/v2/patients?limit=10", headers=auth_headers)
        assert response.status_code == 200
        page1 = response1.json()
        
        assert len(page1["data"]) == 10
        assert page1["has_more"] is True
        
        # All patients should belong to test_user
        for patient in page1["data"]:
            assert patient["doctor_id"] == str(test_user.id)
        
        # Fetch second page
        cursor = page1["next_cursor"]
        response2 = client.get(f"/api/v2/patients?limit=10&cursor={cursor}", headers=auth_headers)
        assert response2.status_code == 200
        page2 = response2.json()
        
        assert len(page2["data"]) == 5  # Remaining 5 patients
        assert page2["has_more"] is False
        
        # All should still belong to test_user
        for patient in page2["data"]:
            assert patient["doctor_id"] == str(test_user.id)
        
        # Verify no patients from doctor_b appeared
        all_patient_names = [p["name"] for p in page1["data"]] + [p["name"] for p in page2["data"]]
        for name in all_patient_names:
            assert not name.startswith("Patient B")
