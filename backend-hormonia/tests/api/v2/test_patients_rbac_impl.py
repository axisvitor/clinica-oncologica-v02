"""
RBAC Tests for Patients API v2 - IMPLEMENTATION COMPLETE
Tests to prevent privacy regression - ensure doctors only see their own patients.

Issue: #16
Priority: P0 - Critical
Status: IMPLEMENTED
"""
from fastapi.testclient import TestClient
from app.models.user import UserRole
from tests.conftest import create_test_user, create_test_patient


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
class TestPatientsRBAC:
    """Test Role-Based Access Control for patient endpoints."""
    
    def test_list_patients_rbac_doctor_sees_only_own(
        self,
        client: TestClient,
        db_session,
        test_doctor_user,
        auth_headers
    ):
        """Doctor can only list their own patients."""
        # Create second doctor
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        
        # Create patients
        own_patient = create_test_patient(db_session, doctor=test_doctor_user, name="Own Patient")
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
        unique = str(admin_user.id).replace("-", "")

        # Create two doctors with unique emails so this regression remains
        # independent from any rows created by broader focused suites.
        doctor_a = create_test_user(
            db_session,
            email=f"doctor_a_{unique}@test.com",
            role=UserRole.DOCTOR,
        )
        doctor_b = create_test_user(
            db_session,
            email=f"doctor_b_{unique}@test.com",
            role=UserRole.DOCTOR,
        )
        
        # Create patients for each doctor with a shared unique search prefix.
        search_prefix = f"Admin RBAC {unique}"
        patient_a = create_test_patient(
            db_session,
            doctor=doctor_a,
            name=f"{search_prefix} Patient A",
        )
        patient_b = create_test_patient(
            db_session,
            doctor=doctor_b,
            name=f"{search_prefix} Patient B",
        )
        
        response = client.get(
            "/api/v2/patients",
            params={"search": search_prefix, "limit": 10},
            headers=admin_auth_headers,
        )
        
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
        test_doctor_user,
        auth_headers
    ):
        """Doctor cannot access another doctor's patient (returns 403)."""
        # Create another doctor and their patient
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        other_patient = create_test_patient(db_session, doctor=doctor_b, name="Other Patient")
        
        response = client.get(f"/api/v2/patients/{other_patient.id}", headers=auth_headers)
        
        assert response.status_code == 403
    
    def test_get_patient_rbac_doctor_can_access_own(
        self,
        client: TestClient,
        db_session,
        test_doctor_user,
        auth_headers
    ):
        """Doctor can access their own patient."""
        own_patient = create_test_patient(db_session, doctor=test_doctor_user, name="Own Patient")
        
        response = client.get(f"/api/v2/patients/{own_patient.id}", headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["id"] == str(own_patient.id)
        assert response.json()["name"] == "Own Patient"
    
    def test_create_patient_sets_correct_doctor_id(
        self,
        client: TestClient,
        test_doctor_user,
        auth_headers
    ):
        """Creating a patient sets doctor_id to authenticated user."""
        patient_data = {
            "name": "New Patient",
            "phone": "11999999999",
            "email": "newpatient@gmail.com",
            "doctor_id": str(test_doctor_user.id)
        }
        
        response = client.post("/api/v2/patients", json=patient_data, headers=auth_headers)
        
        assert response.status_code == 201
        assert response.json()["doctor_id"] == str(test_doctor_user.id)
        assert response.json()["name"] == "New Patient"
    
    def test_update_patient_rbac_doctor_cannot_update_others(
        self,
        client: TestClient,
        db_session,
        test_doctor_user,
        auth_headers
    ):
        """Doctor cannot update another doctor's patient."""
        # Create another doctor and their patient
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        other_patient = create_test_patient(db_session, doctor=doctor_b, name="Other Patient")
        
        update_data = {"name": "Hacked Name"}
        response = client.patch(
            f"/api/v2/patients/{other_patient.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 403
    
    def test_delete_patient_rbac_doctor_cannot_delete_others(
        self,
        client: TestClient,
        db_session,
        test_doctor_user,
        auth_headers
    ):
        """Doctor cannot delete another doctor's patient."""
        # Create another doctor and their patient
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        other_patient = create_test_patient(db_session, doctor=doctor_b, name="Other Patient")
        
        response = client.delete(f"/api/v2/patients/{other_patient.id}", headers=auth_headers)
        
        assert response.status_code == 403
    
    def test_cursor_pagination_respects_rbac(
        self,
        client: TestClient,
        db_session,
        test_doctor_user,
        auth_headers
    ):
        """Cursor pagination only returns scoped patients."""
        from datetime import timedelta
        
        # Create another doctor
        doctor_b = create_test_user(db_session, email="doctor_b@test.com", role=UserRole.DOCTOR)
        
        # Create 15 patients for authenticated doctor
        for i in range(15):
            create_test_patient(
                db_session,
                doctor=test_doctor_user,
                name=f"Patient A{i}",
                created_at=now_sao_paulo_naive() - timedelta(minutes=i)
            )
        
        # Create 15 patients for doctor_b (should NOT appear)
        for i in range(15):
            create_test_patient(
                db_session,
                doctor=doctor_b,
                name=f"Patient B{i}",
                created_at=now_sao_paulo_naive() - timedelta(minutes=i)
            )
        
        # Fetch first page
        response1 = client.get("/api/v2/patients", params={"limit": 10}, headers=auth_headers)
        assert response1.status_code == 200
        page1 = response1.json()
        assert len(page1["data"]) == 10
        assert page1["has_more"] is True
        assert page1.get("next_cursor")

        # Fetch next page via cursor (scope must still be enforced)
        cursor = page1["next_cursor"]
        response2 = client.get(
            "/api/v2/patients",
            params={"limit": 10, "cursor": cursor},
            headers=auth_headers,
        )
        assert response2.status_code == 200
        page2 = response2.json()

        all_rows = list(page1["data"]) + list(page2["data"])

        # Verify scope constraints across returned pages
        for patient in all_rows:
            assert patient["doctor_id"] == str(test_doctor_user.id)
            assert not patient["name"].startswith("Patient B")

        names = {p["name"] for p in all_rows}
        own_names = {name for name in names if name.startswith("Patient A")}
        assert len(own_names) >= 10
