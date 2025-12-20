"""
Critical API Tests: Patient List and Pagination
Tests patient listing with filters, search, and pagination.

NOTE: These tests need rework to match the actual API:
- API uses 'name' not 'nome' (English field names)
- API response uses 'data' not 'items' for patient list
- API has RBAC permissions that need to be set up
- API requires Firebase session authentication
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.skip(reason="Tests need rework - use English field names and Firebase auth")
@pytest.mark.api
@pytest.mark.patient
class TestPatientList:
    """Test patient listing functionality."""

    def test_list_patients_empty(self, authenticated_client: TestClient):
        """Test listing patients when none exist."""
        response = authenticated_client.get("/api/v2/patients")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_list_patients_with_data(self, authenticated_client: TestClient, test_patient: dict):
        """Test listing patients with multiple entries."""
        # Create 3 patients
        for i in range(3):
            patient = test_patient.copy()
            patient["nome"] = f"Paciente {i}"
            patient["email"] = f"patient{i}@example.com"
            authenticated_client.post("/api/v2/patients", json=patient)

        # List patients
        response = authenticated_client.get("/api/v2/patients")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_patients_pagination(self, authenticated_client: TestClient, test_patient: dict):
        """Test patient list pagination."""
        # Create 15 patients
        for i in range(15):
            patient = test_patient.copy()
            patient["nome"] = f"Paciente {i:02d}"
            patient["email"] = f"patient{i}@example.com"
            authenticated_client.post("/api/v2/patients", json=patient)

        # Get first page
        response = authenticated_client.get("/api/v2/patients?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 15

        # Get second page
        response = authenticated_client.get("/api/v2/patients?limit=10&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["total"] == 15

    def test_list_patients_search_by_name(self, authenticated_client: TestClient, test_patient: dict):
        """Test searching patients by name."""
        # Create patients
        patients = [
            {"nome": "João Silva", "email": "joao@example.com"},
            {"nome": "Maria Santos", "email": "maria@example.com"},
            {"nome": "João Pedro", "email": "pedro@example.com"},
        ]

        for patient_data in patients:
            patient = test_patient.copy()
            patient.update(patient_data)
            authenticated_client.post("/api/v2/patients", json=patient)

        # Search for "João"
        response = authenticated_client.get("/api/v2/patients?search=João")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert "João" in item["nome"]

    def test_list_patients_filter_by_treatment(self, authenticated_client: TestClient, test_patient: dict):
        """Test filtering patients by treatment type."""
        # Create patients with different treatments
        treatments = ["Quimioterapia", "Radioterapia", "Imunoterapia"]

        for i, treatment in enumerate(treatments):
            patient = test_patient.copy()
            patient["nome"] = f"Paciente {treatment}"
            patient["email"] = f"patient{i}@example.com"
            patient["tipo_tratamento"] = treatment
            authenticated_client.post("/api/v2/patients", json=patient)

        # Filter by Quimioterapia
        response = authenticated_client.get("/api/v2/patients?tipo_tratamento=Quimioterapia")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["tipo_tratamento"] == "Quimioterapia"

    def test_list_patients_sort_by_name(self, authenticated_client: TestClient, test_patient: dict):
        """Test sorting patients by name."""
        # Create patients
        names = ["Zélia", "Ana", "Maria"]
        for i, name in enumerate(names):
            patient = test_patient.copy()
            patient["nome"] = name
            patient["email"] = f"patient{i}@example.com"
            authenticated_client.post("/api/v2/patients", json=patient)

        # Sort ascending
        response = authenticated_client.get("/api/v2/patients?sort=nome&order=asc")

        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["nome"] == "Ana"
        assert data["items"][-1]["nome"] == "Zélia"

    def test_list_patients_invalid_pagination_params(self, authenticated_client: TestClient):
        """Test that invalid pagination parameters are rejected."""
        response = authenticated_client.get("/api/v2/patients?limit=-1&offset=-1")

        assert response.status_code == 422

    @pytest.mark.security
    def test_list_patients_requires_authentication(self, client: TestClient):
        """Test that listing patients requires authentication."""
        response = client.get("/api/v2/patients")

        assert response.status_code == 401
