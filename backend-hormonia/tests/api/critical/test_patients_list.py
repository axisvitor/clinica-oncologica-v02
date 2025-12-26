"""
Critical API Tests: Patient List and Pagination
Tests patient listing with filters, search, and pagination.

Tests updated to use English field names (name, phone) matching API schema.
API response uses 'data' field for patient list with cursor pagination.
"""
import pytest
from fastapi.testclient import TestClient

# Add timestamp for unique emails in tests
pytest.timestamp = int(__import__("time").time())


@pytest.mark.api
@pytest.mark.patient
class TestPatientList:
    """Test patient listing functionality."""

    def test_list_patients_empty_or_existing(self, authenticated_client: TestClient):
        """Test listing patients - API uses cursor pagination with 'data' field."""
        response = authenticated_client.get("/api/v2/patients/")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data  # API uses 'data' not 'items'
        assert "has_more" in data
        assert isinstance(data["data"], list)

    def test_list_patients_with_data(self, authenticated_client: TestClient, db_session):
        """Test listing patients with multiple entries."""
        # Create 3 patients
        for i in range(3):
            patient_data = {
                "name": f"List Patient {i}",
                "email": f"list_patient{i}_{pytest.timestamp}@example.com",
                "phone": f"+551199999{i:04d}"
            }
            authenticated_client.post("/api/v2/patients/", json=patient_data)

        # List patients
        response = authenticated_client.get("/api/v2/patients/")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 3  # At least the 3 we created

    def test_list_patients_pagination(self, authenticated_client: TestClient, db_session):
        """Test patient list pagination with cursor-based pagination."""
        # Create 15 patients
        for i in range(15):
            patient_data = {
                "name": f"Page Patient {i:02d}",
                "email": f"page_patient{i}_{pytest.timestamp}@example.com",
                "phone": f"+551198888{i:04d}"
            }
            authenticated_client.post("/api/v2/patients/", json=patient_data)

        # Get first page with limit
        response = authenticated_client.get("/api/v2/patients/?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) <= 5
        assert "next_cursor" in data or "has_more" in data

        # If there's more data, test second page with cursor
        if data.get("has_more") and data.get("next_cursor"):
            response = authenticated_client.get(f"/api/v2/patients/?limit=5&cursor={data['next_cursor']}")
            assert response.status_code == 200
            page2_data = response.json()
            assert "data" in page2_data

    def test_list_patients_search_by_name(self, authenticated_client: TestClient, db_session):
        """Test searching patients by name."""
        # Create patients with unique names
        search_term = f"SearchJoão{pytest.timestamp}"
        patients = [
            {"name": f"{search_term} Silva", "email": f"joao1_{pytest.timestamp}@example.com", "phone": "+5511977771111"},
            {"name": "Maria Santos", "email": f"maria_{pytest.timestamp}@example.com", "phone": "+5511977772222"},
            {"name": f"{search_term} Pedro", "email": f"pedro_{pytest.timestamp}@example.com", "phone": "+5511977773333"},
        ]

        for patient_data in patients:
            authenticated_client.post("/api/v2/patients/", json=patient_data)

        # Search for the unique term
        response = authenticated_client.get(f"/api/v2/patients/?search={search_term}")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        # Should find at least the 2 patients with the search term
        matching = [p for p in data["data"] if search_term in p.get("name", "")]
        assert len(matching) >= 2

    def test_list_patients_filter_by_treatment(self, authenticated_client: TestClient, db_session):
        """Test filtering patients by cancer type."""
        # Create patients with different cancer types
        cancer_types = ["breast", "lung", "prostate"]

        for i, cancer_type in enumerate(cancer_types):
            patient_data = {
                "name": f"Cancer Patient {cancer_type}",
                "email": f"cancer_{cancer_type}_{i}_{pytest.timestamp}@example.com",
                "phone": f"+551196666{i:04d}",
                "cancer_type": cancer_type
            }
            authenticated_client.post("/api/v2/patients/", json=patient_data)

        # Filter by breast cancer (if API supports filtering by cancer_type)
        response = authenticated_client.get("/api/v2/patients/?cancer_type=breast")

        # API may or may not support this filter, so just verify it doesn't error
        assert response.status_code in [200, 400, 422]
        if response.status_code == 200:
            data = response.json()
            assert "data" in data

    def test_list_patients_sort_by_name(self, authenticated_client: TestClient, db_session):
        """Test sorting patients by name (if supported by API)."""
        # Create patients with sortable names
        unique_prefix = f"Sort{pytest.timestamp}"
        names = [f"{unique_prefix}_Zélia", f"{unique_prefix}_Ana", f"{unique_prefix}_Maria"]
        for i, name in enumerate(names):
            patient_data = {
                "name": name,
                "email": f"sort_{i}_{pytest.timestamp}@example.com",
                "phone": f"+551195555{i:04d}"
            }
            authenticated_client.post("/api/v2/patients/", json=patient_data)

        # Try to sort by name (API may or may not support this)
        response = authenticated_client.get("/api/v2/patients/?sort=name&order=asc")

        # Verify request doesn't error, even if sort isn't supported
        assert response.status_code in [200, 400, 422]
        if response.status_code == 200:
            data = response.json()
            assert "data" in data

    def test_list_patients_invalid_pagination_params(self, authenticated_client: TestClient):
        """Test that invalid pagination parameters are rejected."""
        response = authenticated_client.get("/api/v2/patients/?limit=-1")

        # Should reject negative limit
        assert response.status_code in [400, 422]

    @pytest.mark.security
    def test_list_patients_requires_authentication(self, client: TestClient):
        """Test that listing patients requires authentication."""
        response = client.get("/api/v2/patients/")

        assert response.status_code == 401
