"""
Critical API Tests: Quiz Session Management
Tests quiz session creation, initialization, and lifecycle management.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
@pytest.mark.quiz
class TestQuizSession:
    """Test quiz session management."""

    def test_create_quiz_session_success(self, authenticated_client: TestClient, test_patient: dict, test_quiz_template: dict):
        """Test creating a new quiz session."""
        # First create patient and template
        patient_response = authenticated_client.post("/api/v2/patients", json=test_patient)
        patient_id = patient_response.json()["id"]

        template_response = authenticated_client.post("/api/v2/quiz/templates", json=test_quiz_template)
        template_id = template_response.json()["id"]

        # Create quiz session
        response = authenticated_client.post(
            "/api/v2/quiz/sessions",
            json={
                "patient_id": patient_id,
                "template_id": template_id,
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "quiz_session_id" in data
        assert data["patient_id"] == patient_id
        assert data["template_id"] == template_id
        assert data["status"] == "created"

    def test_initialize_quiz_session(self, authenticated_client: TestClient):
        """Test initializing a quiz session for patient access."""
        # Create session first
        session_response = authenticated_client.post(
            "/api/v2/quiz/sessions",
            json={"patient_id": 1, "template_id": 1}
        )
        session_id = session_response.json()["quiz_session_id"]

        # Initialize session
        response = authenticated_client.post(
            f"/api/v2/quiz/sessions/{session_id}/initialize"
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "expires_at" in data
        assert data["status"] == "in_progress"

    def test_get_quiz_session_status(self, authenticated_client: TestClient):
        """Test retrieving quiz session status."""
        # Create session
        session_response = authenticated_client.post(
            "/api/v2/quiz/sessions",
            json={"patient_id": 1, "template_id": 1}
        )
        session_id = session_response.json()["quiz_session_id"]

        # Get status
        response = authenticated_client.get(
            f"/api/v2/quiz/sessions/{session_id}/status"
        )

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "current_question_index" in data
        assert "total_questions" in data

    def test_quiz_session_expiration(self, authenticated_client: TestClient, mock_redis):
        """Test that quiz sessions expire after timeout."""
        # Create session
        session_response = authenticated_client.post(
            "/api/v2/quiz/sessions",
            json={"patient_id": 1, "template_id": 1, "expires_in": 1}  # 1 second
        )
        session_id = session_response.json()["quiz_session_id"]

        # Wait for expiration
        import time
        time.sleep(2)

        # Try to access expired session
        response = authenticated_client.get(
            f"/api/v2/quiz/sessions/{session_id}/status"
        )

        assert response.status_code == 410  # Gone
        assert "expired" in response.json()["detail"].lower()

    def test_concurrent_quiz_sessions_same_patient(self, authenticated_client: TestClient):
        """Test that one patient can't have multiple active sessions."""
        # Create first session
        session1 = authenticated_client.post(
            "/api/v2/quiz/sessions",
            json={"patient_id": 1, "template_id": 1}
        )
        assert session1.status_code == 201

        # Try to create second session for same patient
        session2 = authenticated_client.post(
            "/api/v2/quiz/sessions",
            json={"patient_id": 1, "template_id": 1}
        )

        assert session2.status_code == 409  # Conflict
        assert "active session" in session2.json()["detail"].lower()

    def test_quiz_session_resume(self, authenticated_client: TestClient):
        """Test resuming an in-progress quiz session."""
        # Create and start session
        session_response = authenticated_client.post(
            "/api/v2/quiz/sessions",
            json={"patient_id": 1, "template_id": 1}
        )
        session_id = session_response.json()["quiz_session_id"]

        # Answer first question
        authenticated_client.post(
            f"/api/v2/quiz/sessions/{session_id}/submit",
            json={"question_id": "q1", "response_value": "yes"}
        )

        # Resume session
        response = authenticated_client.get(
            f"/api/v2/quiz/sessions/{session_id}/resume"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_question_index"] == 1  # Should resume from question 2

    @pytest.mark.security
    def test_quiz_session_requires_authentication(self, client: TestClient):
        """Test that quiz session management requires authentication."""
        endpoints = [
            ("POST", "/api/v2/quiz/sessions"),
            ("GET", "/api/v2/quiz/sessions/123/status"),
            ("POST", "/api/v2/quiz/sessions/123/initialize"),
        ]

        for method, url in endpoints:
            response = client.request(method, url, json={})
            assert response.status_code == 401
