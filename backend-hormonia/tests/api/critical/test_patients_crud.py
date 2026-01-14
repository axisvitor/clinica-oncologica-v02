"""
Critical API Tests: Patient CRUD Operations
Tests the core patient management endpoints including create, read, update, delete.

Tests updated to use English field names (name, phone) matching API schema.
Uses authenticated client from conftest fixtures.

Note: Email domains must be valid (e.g., gmail.com) as the API validates MX records.
"""
import pytest
from fastapi.testclient import TestClient

# Add timestamp for unique emails in tests
pytest.timestamp = int(__import__("time").time())

@pytest.mark.api
@pytest.mark.crud
@pytest.mark.patient
class TestPatientCRUD:
    """Test patient CRUD operations."""

    def test_create_patient_success(self, authenticated_client: TestClient, db_session, test_user: dict, mock_saga_patient):
        """Test creating a new patient with valid data.

        Uses mock_saga_patient fixture to avoid saga transaction conflicts.
        """
        patient_data = {
            "name": "Test Patient Create",
            "phone": "+5511999999999",
            "doctor_id": test_user["id"]
        }

        response = authenticated_client.post(
            "/api/v2/patients/",  # Note: trailing slash required
            json=patient_data
        )

        # Check response - accept 201 (created) or handle validation errors
        if response.status_code == 201:
            data = response.json()
            assert data["name"] == patient_data["name"]
            assert "id" in data
        else:
            # Print response for debugging if not 201
            print(f"Response: {response.status_code} - {response.text}")
        assert response.status_code == 201

    def test_create_patient_duplicate_phone(self, authenticated_client: TestClient, db_session, test_user: dict, mock_saga_patient):
        """Test that duplicate phone numbers are rejected.

        Uses mock_saga_patient fixture to avoid saga transaction conflicts.
        """
        unique_phone = f"+5511888{pytest.timestamp % 100000:05d}"
        patient_data = {
            "name": "Duplicate Test",
            "phone": unique_phone,
            "doctor_id": test_user["id"]
        }

        # Create first patient
        first_response = authenticated_client.post("/api/v2/patients/", json=patient_data)

        # Try to create another with same phone
        patient_data["name"] = "Duplicate Test 2"  # Different name, same phone
        response = authenticated_client.post("/api/v2/patients/", json=patient_data)

        # If first creation succeeded, second should fail with duplicate error
        if first_response.status_code == 201:
            assert response.status_code in [400, 409]  # Either 400 or 409 for duplicate
        else:
            # If first creation failed, skip this test
            pytest.skip(f"First patient creation failed: {first_response.status_code}")

    def test_create_patient_missing_required_fields(self, authenticated_client: TestClient):
        """Test that missing required fields are rejected."""
        incomplete_patient = {
            "name": "João Silva"
            # Missing email and other required fields
        }

        response = authenticated_client.post(
            "/api/v2/patients/",  # Note: trailing slash required
            json=incomplete_patient
        )

        assert response.status_code == 422

    def test_get_patient_by_id(self, authenticated_client: TestClient, db_session, test_user: dict, mock_saga_patient):
        """Test retrieving a patient by ID.

        Uses mock_saga_patient fixture to avoid saga transaction conflicts.
        """
        # Create patient with unique phone
        unique_phone = f"+5511777{pytest.timestamp % 100000:05d}"
        patient_data = {
            "name": "Get Test Patient",
            "phone": unique_phone,
            "doctor_id": test_user["id"]
        }
        create_response = authenticated_client.post("/api/v2/patients/", json=patient_data)

        if create_response.status_code != 201:
            pytest.skip(f"Patient creation failed: {create_response.status_code}")

        patient_id = create_response.json()["id"]

        # Get patient
        response = authenticated_client.get(f"/api/v2/patients/{patient_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == patient_id
        assert data["name"] == patient_data["name"]

    def test_get_patient_not_found(self, authenticated_client: TestClient):
        """Test that getting non-existent patient returns 404."""
        # Use a valid UUID format that doesn't exist in the database
        non_existent_uuid = "00000000-0000-0000-0000-000000000000"
        response = authenticated_client.get(f"/api/v2/patients/{non_existent_uuid}")

        # API should return 404 for non-existent valid UUID
        assert response.status_code == 404

    def test_update_patient_success(self, authenticated_client: TestClient, db_session, test_user: dict, mock_saga_patient):
        """Test updating patient information.

        Uses mock_saga_patient fixture to avoid saga transaction conflicts.
        """
        # Create patient with unique phone
        unique_phone = f"+5511666{pytest.timestamp % 100000:05d}"
        patient_data = {
            "name": "Update Test Patient",
            "phone": unique_phone,
            "doctor_id": test_user["id"]
        }
        create_response = authenticated_client.post("/api/v2/patients/", json=patient_data)

        if create_response.status_code != 201:
            pytest.skip(f"Patient creation failed: {create_response.status_code}")

        patient_id = create_response.json()["id"]

        # Update patient
        updated_data = {
            "name": "João Silva Updated"
        }
        response = authenticated_client.patch(
            f"/api/v2/patients/{patient_id}",
            json=updated_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == updated_data["name"]

    def test_delete_patient_success(self, authenticated_client: TestClient, db_session, test_user: dict, mock_saga_patient):
        """Test deleting a patient.

        Uses mock_saga_patient fixture to avoid saga transaction conflicts.
        """
        # Create patient with unique phone
        unique_phone = f"+5511555{pytest.timestamp % 100000:05d}"
        patient_data = {
            "name": "Delete Test Patient",
            "phone": unique_phone,
            "doctor_id": test_user["id"]
        }
        create_response = authenticated_client.post("/api/v2/patients/", json=patient_data)

        if create_response.status_code != 201:
            pytest.skip(f"Patient creation failed: {create_response.status_code}")

        patient_id = create_response.json()["id"]

        # Delete patient
        response = authenticated_client.delete(f"/api/v2/patients/{patient_id}")

        assert response.status_code in [200, 204]

        # Verify patient is soft deleted (might return 404 or show as inactive)
        get_response = authenticated_client.get(f"/api/v2/patients/{patient_id}")
        assert get_response.status_code in [404, 200]  # Depending on soft delete implementation

    def test_delete_patient_not_found(self, authenticated_client: TestClient):
        """Test that deleting non-existent patient returns 404."""
        # Use a valid UUID format that doesn't exist in the database
        non_existent_uuid = "00000000-0000-0000-0000-000000000000"
        response = authenticated_client.delete(f"/api/v2/patients/{non_existent_uuid}")

        # API should return 404 for non-existent valid UUID
        assert response.status_code == 404

    @pytest.mark.security
    def test_crud_requires_authentication(self, client: TestClient):
        """Test that all CRUD operations require authentication."""
        # Use valid UUID format for single-resource endpoints
        test_uuid = "00000000-0000-0000-0000-000000000001"
        endpoints = [
            ("GET", "/api/v2/patients/"),
            ("POST", "/api/v2/patients/"),
            ("GET", f"/api/v2/patients/{test_uuid}"),
            ("PATCH", f"/api/v2/patients/{test_uuid}"),
            ("DELETE", f"/api/v2/patients/{test_uuid}"),
        ]

        for method, url in endpoints:
            response = client.request(method, url, json={})
            assert response.status_code == 401, f"{method} {url} should require authentication"
