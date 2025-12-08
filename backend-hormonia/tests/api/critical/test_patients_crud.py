"""
Critical API Tests: Patient CRUD Operations
Tests the core patient management endpoints including create, read, update, delete.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.mark.api
@pytest.mark.crud
@pytest.mark.patient
class TestPatientCRUD:
    """Test patient CRUD operations."""

    def test_create_patient_success(self, authenticated_client: TestClient, test_patient: dict):
        """Test creating a new patient with valid data."""
        response = authenticated_client.post(
            "/api/v2/patients",
            json=test_patient
        )

        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == test_patient["nome"]
        assert data["email"] == test_patient["email"]
        assert "id" in data

    def test_create_patient_duplicate_email(self, authenticated_client: TestClient, test_patient: dict):
        """Test that duplicate email addresses are rejected."""
        # Create first patient
        authenticated_client.post("/api/v2/patients", json=test_patient)

        # Try to create another with same email
        response = authenticated_client.post("/api/v2/patients", json=test_patient)

        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()

    def test_create_patient_missing_required_fields(self, authenticated_client: TestClient):
        """Test that missing required fields are rejected."""
        incomplete_patient = {
            "nome": "João Silva"
            # Missing email, telefone, etc.
        }

        response = authenticated_client.post(
            "/api/v2/patients",
            json=incomplete_patient
        )

        assert response.status_code == 422

    def test_get_patient_by_id(self, authenticated_client: TestClient, test_patient: dict):
        """Test retrieving a patient by ID."""
        # Create patient
        create_response = authenticated_client.post("/api/v2/patients", json=test_patient)
        patient_id = create_response.json()["id"]

        # Get patient
        response = authenticated_client.get(f"/api/v2/patients/{patient_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == patient_id
        assert data["nome"] == test_patient["nome"]

    def test_get_patient_not_found(self, authenticated_client: TestClient):
        """Test that getting non-existent patient returns 404."""
        response = authenticated_client.get("/api/v2/patients/99999")

        assert response.status_code == 404

    def test_update_patient_success(self, authenticated_client: TestClient, test_patient: dict):
        """Test updating patient information."""
        # Create patient
        create_response = authenticated_client.post("/api/v2/patients", json=test_patient)
        patient_id = create_response.json()["id"]

        # Update patient
        updated_data = {
            "nome": "João Silva Updated",
            "telefone": "+5511988776655"
        }
        response = authenticated_client.patch(
            f"/api/v2/patients/{patient_id}",
            json=updated_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["nome"] == updated_data["nome"]
        assert data["telefone"] == updated_data["telefone"]

    def test_delete_patient_success(self, authenticated_client: TestClient, test_patient: dict):
        """Test deleting a patient."""
        # Create patient
        create_response = authenticated_client.post("/api/v2/patients", json=test_patient)
        patient_id = create_response.json()["id"]

        # Delete patient
        response = authenticated_client.delete(f"/api/v2/patients/{patient_id}")

        assert response.status_code == 204

        # Verify patient is deleted
        get_response = authenticated_client.get(f"/api/v2/patients/{patient_id}")
        assert get_response.status_code == 404

    def test_delete_patient_not_found(self, authenticated_client: TestClient):
        """Test that deleting non-existent patient returns 404."""
        response = authenticated_client.delete("/api/v2/patients/99999")

        assert response.status_code == 404

    @pytest.mark.security
    def test_crud_requires_authentication(self, client: TestClient):
        """Test that all CRUD operations require authentication."""
        endpoints = [
            ("GET", "/api/v2/patients"),
            ("POST", "/api/v2/patients"),
            ("GET", "/api/v2/patients/1"),
            ("PATCH", "/api/v2/patients/1"),
            ("DELETE", "/api/v2/patients/1"),
        ]

        for method, url in endpoints:
            response = client.request(method, url, json={})
            assert response.status_code == 401, f"{method} {url} should require authentication"
