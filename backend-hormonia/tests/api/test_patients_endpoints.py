"""
Test suite for Patient CRUD API endpoints.

Tests cover:
- Patient creation (POST /api/v2/patients)
- Patient retrieval (GET /api/v2/patients/{id})
- Patient list with pagination (GET /api/v2/patients)
- Patient update (PUT /api/v2/patients/{id})
- Patient soft delete (DELETE /api/v2/patients/{id})
- Authentication and authorization
- Input validation
- Error handling
"""

import pytest
from uuid import UUID, uuid4
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.patient import Patient


class TestPatientCRUDEndpoints:
    """Test patient CRUD operations via API endpoints."""

    @pytest.fixture(autouse=True)
    def _disable_flow_auto_enrollment(self, monkeypatch: pytest.MonkeyPatch):
        """Disable flow auto-enrollment to avoid template dependencies in API tests."""
        monkeypatch.setattr(settings, "FLOW_ENABLE_AUTO_ENROLLMENT", False)

    @pytest.fixture
    def patient_data(self, test_user):
        """Valid patient creation data."""
        return {
            "name": "Test Patient",
            "email": "test.patient@gmail.com",
            "phone": "+5511999999999",
            "birth_date": "1990-01-01",
            "cpf": "12345678909",
            "treatment_type": "Quimioterapia",
            "diagnosis": "Test diagnosis",
            "doctor_id": str(test_user.id),
            "metadata": {"test": "data"}
        }

    @pytest.mark.api
    def test_create_patient_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient_data: dict
    ):
        """Test successful patient creation."""
        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == patient_data["name"]
        assert data["email"] == patient_data["email"]
        assert data["phone"] == patient_data["phone"]
        assert "id" in data
        assert data.get("deleted_at") is None

        # Verify in database
        patient = db.query(Patient).filter(Patient.id == UUID(data["id"])).first()
        assert patient is not None
        assert patient.name == patient_data["name"]

    @pytest.mark.api
    def test_create_patient_duplicate_email(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient_data: dict
    ):
        """Test patient creation with duplicate email fails."""
        # Create first patient
        client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=authenticated_headers
        )

        # Try to create duplicate
        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.api
    def test_create_patient_invalid_data(
        self,
        client: TestClient,
        authenticated_headers: dict
    ):
        """Test patient creation with invalid data."""
        invalid_data = {
            "name": "",  # Empty name
            "email": "invalid-email",  # Invalid email format
            "phone": "123"  # Invalid phone
        }

        response = client.post(
            "/api/v2/patients",
            json=invalid_data,
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.api
    def test_get_patient_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient_data: dict
    ):
        """Test successful patient retrieval by ID."""
        # Create patient first
        create_response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=authenticated_headers
        )
        patient_id = create_response.json()["id"]
        patient_uuid = UUID(patient_id)

        # Retrieve patient
        response = client.get(
            f"/api/v2/patients/{patient_id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == patient_id
        assert data["name"] == patient_data["name"]
        assert data["email"] == patient_data["email"]

    @pytest.mark.api
    def test_get_patient_not_found(
        self,
        client: TestClient,
        authenticated_headers: dict
    ):
        """Test patient retrieval with non-existent ID."""
        fake_id = str(uuid4())

        response = client.get(
            f"/api/v2/patients/{fake_id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.api
    def test_get_patient_soft_deleted(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient_data: dict
    ):
        """Test that soft-deleted patients are not retrievable."""
        # Create and delete patient
        create_response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=authenticated_headers
        )
        patient_id = create_response.json()["id"]

        client.delete(
            f"/api/v2/patients/{patient_id}",
            headers=authenticated_headers
        )

        # Try to retrieve deleted patient
        response = client.get(
            f"/api/v2/patients/{patient_id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.api
    def test_list_patients_pagination(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient_data: dict
    ):
        """Test patient list with pagination."""
        doctor_id = UUID(patient_data["doctor_id"])
        batch_tag = f"pagination-{uuid4().hex[:8]}"

        # Create patients directly in DB to avoid saga pipeline failures
        # that are irrelevant to pagination behavior
        for i in range(5):
            patient = Patient(
                name=f"{batch_tag}-patient-{i}",
                email=f"{batch_tag}.{i}@gmail.com",
                phone=f"+551188888888{i}",
                doctor_id=doctor_id,
                treatment_type="Quimioterapia",
                diagnosis="Test diagnosis",
            )
            db.add(patient)
        db.flush()

        # Test pagination
        response = client.get(
            f"/api/v2/patients?skip=0&limit=3&search={batch_tag}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["data"]) == 3
        assert data["total"] >= 5
        assert data["has_more"] is True

    @pytest.mark.api
    def test_update_patient_success(
        self,
        client: TestClient,
        authenticated_headers: dict,
        patient_data: dict
    ):
        """Test successful patient update."""
        # Create patient
        create_response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=authenticated_headers
        )
        patient_id = create_response.json()["id"]

        # Update patient
        update_data = {
            "name": "Updated Patient Name",
            "diagnosis": "Updated diagnosis"
        }

        response = client.put(
            f"/api/v2/patients/{patient_id}",
            json=update_data,
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["name"] == update_data["name"]
        assert data["diagnosis"] == update_data["diagnosis"]
        assert data["email"] == patient_data["email"]  # Unchanged fields preserved

    @pytest.mark.api
    def test_update_patient_not_found(
        self,
        client: TestClient,
        authenticated_headers: dict
    ):
        """Test patient update with non-existent ID."""
        fake_id = str(uuid4())

        response = client.put(
            f"/api/v2/patients/{fake_id}",
            json={"name": "Updated Name"},
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.api
    def test_delete_patient_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient_data: dict
    ):
        """Test successful patient soft delete."""
        # Create patient
        create_response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=authenticated_headers
        )
        patient_id = create_response.json()["id"]
        patient_uuid = UUID(patient_id)

        # Delete patient
        response = client.delete(
            f"/api/v2/patients/{patient_id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify soft delete in database
        patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
        assert patient is not None
        assert patient.deleted_at is not None

    @pytest.mark.api
    def test_delete_patient_not_found(
        self,
        client: TestClient,
        authenticated_headers: dict
    ):
        """Test patient deletion with non-existent ID."""
        fake_id = str(uuid4())

        response = client.delete(
            f"/api/v2/patients/{fake_id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.api
    def test_unauthorized_access(
        self,
        client: TestClient,
        patient_data: dict
    ):
        """Test that unauthenticated requests are rejected."""
        # Try to create without auth
        response = client.post(
            "/api/v2/patients",
            json=patient_data
        )

        # CSRF middleware runs before auth dependencies for mutating requests.
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.api
    @pytest.mark.performance
    def test_list_patients_no_n_plus_one(
        self,
        client: TestClient,
        authenticated_headers: dict,
        patient_data: dict,
        query_counter
    ):
        """Test that patient list doesn't cause N+1 queries."""
        # Create patients
        for i in range(10):
            data = patient_data.copy()
            data["email"] = f"patient{i}@gmail.com"
            data["phone"] = f"+551199999999{i}"
            client.post(
                "/api/v2/patients",
                json=data,
                headers=authenticated_headers
            )

        # Count queries for list operation
        with query_counter() as counter:
            response = client.get(
                "/api/v2/patients?limit=10",
                headers=authenticated_headers
            )

            assert response.status_code == status.HTTP_200_OK

            # Should use a single query with eager loading
            # Allow 2-3 queries: 1 for count, 1 for data with joins
            assert counter.count <= 3, f"N+1 query detected: {counter.count} queries"


@pytest.fixture
def authenticated_headers(admin_user):
    """Create authenticated headers for testing."""
    from fastapi import Request

    from app.dependencies import RequestContext, get_request_context
    from app.dependencies.auth_dependencies import (
        get_current_user,
        get_current_user_from_session,
        get_current_user_object_from_session,
        get_optional_user,
    )
    from app.main import app
    from app.middleware.csrf import get_csrf_token
    from tests.conftest import TestUser

    session_user = TestUser(admin_user, "testpass123").session_dict()
    session_id = f"admin-session-{admin_user.id}"

    async def _override_session(request: Request):
        request.state.user_id = session_user.get("id")
        request.state.user_role = session_user.get("role")
        request.state.session_id = session_id
        return session_user

    async def _override_current_user(request: Request):
        request.state.user = admin_user
        request.state.user_id = str(admin_user.id)
        request.state.user_role = (
            admin_user.role.value
            if hasattr(admin_user.role, "value")
            else str(admin_user.role)
        )
        request.state.session_id = session_id
        return admin_user

    async def _override_optional_user(credentials=None, services=None):
        return admin_user

    async def _override_request_context(request: Request):
        return RequestContext(
            ip_address="127.0.0.1",
            user_agent="pytest",
            user_id=admin_user.id,
            session_id=session_id,
        )

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = lambda: admin_user
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_optional_user] = _override_optional_user
    app.dependency_overrides[get_request_context] = _override_request_context

    csrf_token = get_csrf_token()
    headers = {
        "X-Session-ID": session_id,
        "Authorization": f"Bearer admin-token-{admin_user.id}",
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}",
    }
    yield headers
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_request_context, None)


@pytest.fixture
def query_counter(db: Session):
    """Context manager to count database queries."""
    from contextlib import contextmanager
    from sqlalchemy import event

    @contextmanager
    def counter():
        class Counter:
            count = 0

        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            Counter.count += 1

        event.listen(
            db.bind,
            "after_cursor_execute",
            receive_after_cursor_execute
        )

        try:
            yield Counter
        finally:
            event.remove(
                db.bind,
                "after_cursor_execute",
                receive_after_cursor_execute
            )

    return counter
