"""
RBAC Tests for Patients API v2
Tests to prevent privacy regression - ensure doctors only see their own patients.

TODO: Implement these tests before production deployment.
Priority: P0 - Critical
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


class TestPatientsRBAC:
    """Test Role-Based Access Control for patient endpoints."""
    
    def test_list_patients_rbac_doctor_sees_only_own(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """
        Test that a doctor can only list their own patients.
        
        Setup:
        - Create two doctors: doctor_a and doctor_b
        - Create patient_a assigned to doctor_a
        - Create patient_b assigned to doctor_b
        
        Test:
        - Authenticate as doctor_a
        - Call GET /api/v2/patients
        - Assert only patient_a is returned
        - Assert patient_b is NOT in results
        """
        from app.models.patient import Patient
        from tests.conftest import create_test_user, create_test_patient
        
        # Create doctor B
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        
        # Create patients
        own_patient = create_test_patient(db_session, doctor=test_user, name="Own Patient")
        other_patient = create_test_patient(db_session, doctor=doctor_b, name="Other Patient")
        
        response = client.get("/api/v2/patients", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Should only see own patient
        patient_ids = [p["id"] for p in data]
        assert str(own_patient.id) in patient_ids
        assert str(other_patient.id) not in patient_ids
        assert len(data) == 1
    
    @pytest.mark.skip(reason="TODO: Implement before deployment")
    def test_list_patients_rbac_admin_sees_all(
        self,
        client: TestClient,
        admin_token: str,
        doctor_a_patient,
        doctor_b_patient
    ):
        """
        Test that an admin can list all patients regardless of doctor_id.
        
        Setup:
        - Create patients for multiple doctors
        - Authenticate as admin
        
        Test:
        - Call GET /api/v2/patients
        - Assert patients from all doctors are returned
        """
        response = client.get(
            "/api/v2/patients",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Admin should see all patients
        patient_ids = [p["id"] for p in data]
        assert str(doctor_a_patient.id) in patient_ids
        assert str(doctor_b_patient.id) in patient_ids
    
    @pytest.mark.skip(reason="TODO: Implement before deployment")
    def test_get_patient_rbac_doctor_cannot_access_other_patient(
        self,
        client: TestClient,
        doctor_token: str,
        other_doctor_patient
    ):
        """
        Test that a doctor cannot access another doctor's patient by ID.
        
        Expected: 404 Not Found (not 403, to avoid info disclosure)
        """
        response = client.get(
            f"/api/v2/patients/{other_doctor_patient.id}",
            headers={"Authorization": f"Bearer {doctor_token}"}
        )
        
        # Should return 404 to avoid revealing patient exists
        assert response.status_code == 404
    
    @pytest.mark.skip(reason="TODO: Implement before deployment")
    def test_get_patient_rbac_doctor_can_access_own(
        self,
        client: TestClient,
        doctor_token: str,
        own_patient
    ):
        """
        Test that a doctor can access their own patient by ID.
        """
        response = client.get(
            f"/api/v2/patients/{own_patient.id}",
            headers={"Authorization": f"Bearer {doctor_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["id"] == str(own_patient.id)
    
    @pytest.mark.skip(reason="TODO: Implement before deployment")
    def test_create_patient_sets_correct_doctor_id(
        self,
        client: TestClient,
        doctor_token: str,
        doctor_user
    ):
        """
        Test that creating a patient automatically sets doctor_id to current user.
        """
        patient_data = {
            "name": "Test Patient",
            "phone": "11999999999",
            "email": "test@example.com",
            "doctor_id": str(doctor_user.id)  # Should match authenticated user
        }
        
        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers={"Authorization": f"Bearer {doctor_token}"}
        )
        
        assert response.status_code == 201
        assert response.json()["doctor_id"] == str(doctor_user.id)
    
    @pytest.mark.skip(reason="TODO: Implement before deployment")
    def test_update_patient_rbac_doctor_cannot_update_others(
        self,
        client: TestClient,
        doctor_token: str,
        other_doctor_patient
    ):
        """
        Test that a doctor cannot update another doctor's patient.
        """
        update_data = {"name": "Hacked Name"}
        
        response = client.patch(
            f"/api/v2/patients/{other_doctor_patient.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {doctor_token}"}
        )
        
        assert response.status_code == 404
    
    @pytest.mark.skip(reason="TODO: Implement before deployment")
    def test_delete_patient_rbac_doctor_cannot_delete_others(
        self,
        client: TestClient,
        doctor_token: str,
        other_doctor_patient
    ):
        """
        Test that a doctor cannot delete another doctor's patient.
        """
        response = client.delete(
            f"/api/v2/patients/{other_doctor_patient.id}",
            headers={"Authorization": f"Bearer {doctor_token}"}
        )
        
        assert response.status_code == 404
    
    @pytest.mark.skip(reason="TODO: Implement before deployment")
    def test_cursor_pagination_respects_rbac(
        self,
        client: TestClient,
        doctor_token: str,
        doctor_user,
        create_multiple_patients
    ):
        """
        Test that cursor pagination only returns scoped patients.
        
        Setup:
        - Create 30 patients for doctor_a
        - Create 30 patients for doctor_b
        - Authenticate as doctor_a
        
        Test:
        - Paginate through all pages
        - Assert all returned patients belong to doctor_a
        - Assert no patients from doctor_b appear
        """
        all_patients = []
        cursor = None
        
        for _ in range(5):  # Max 5 pages
            url = "/api/v2/patients?limit=10"
            if cursor:
                url += f"&cursor={cursor}"
            
            response = client.get(
                url,
                headers={"Authorization": f"Bearer {doctor_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            all_patients.extend(data["data"])
            
            if not data["has_more"]:
                break
            
            cursor = data["next_cursor"]
        
        # Verify all patients belong to authenticated doctor
        for patient in all_patients:
            assert patient["doctor_id"] == str(doctor_user.id)


# Fixtures to implement
@pytest.fixture
def doctor_token(client, doctor_user):
    """TODO: Return valid JWT token for doctor_user"""
    raise NotImplementedError("Implement doctor authentication fixture")


@pytest.fixture
def admin_token(client, admin_user):
    """TODO: Return valid JWT token for admin_user"""
    raise NotImplementedError("Implement admin authentication fixture")


@pytest.fixture
def own_patient(db, doctor_user):
    """TODO: Create patient assigned to doctor_user"""
    raise NotImplementedError("Create patient fixture")


@pytest.fixture
def other_doctor_patient(db, other_doctor):
    """TODO: Create patient assigned to other_doctor"""
    raise NotImplementedError("Create other doctor's patient fixture")
