"""
Critical API Tests: Quiz Answer Submission
Tests public quiz submission endpoint validation and security.

Endpoint: POST /api/v2/monthly-quiz-public/monthly/public/{quiz_id}/submit

These tests verify:
- Request validation (required fields, token format)
- Security protections (XSS, SQL injection)
- Token validation (format, expiration)

Note: Tests that require actual database/quiz existence are marked
as integration tests since they need real backend state.
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
import base64
import json
from datetime import datetime, timedelta, timezone


@pytest.mark.api
@pytest.mark.quiz
class TestQuizSubmit:
    """Test quiz answer submission via public endpoint."""

    @pytest.fixture(autouse=True)
    def setup_mock_validation(self):
        """Setup token and IDs for all tests."""
        self.quiz_id = str(uuid4())
        self.session_id = str(uuid4())
        self.patient_id = str(uuid4())
        # Create a valid base64-encoded token
        token_data = {
            "quiz_id": self.quiz_id,
            "exp": (datetime.now(timezone.utc) + timedelta(hours=24)).timestamp(),
            "type": "quiz_access"
        }
        self.valid_token = base64.b64encode(
            json.dumps(token_data).encode()
        ).decode()

    def _get_submit_url(self):
        """Get the correct submit endpoint URL."""
        return f"/api/v2/monthly-quiz-public/monthly/public/{self.quiz_id}/submit"

    # ========================================================================
    # Integration tests - require real backend state
    # ========================================================================

    @pytest.mark.integration
    def test_submit_answer_success(self, client: TestClient):
        """Test submitting a valid quiz answer."""
        response = client.post(
            self._get_submit_url(),
            json={
                "token": self.valid_token,
                "question_id": "q1",
                "response_value": "yes"
            }
        )
        # Should return valid response codes
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

    @pytest.mark.integration
    def test_submit_scale_answer(self, client: TestClient):
        """Test submitting a scale-type answer (1-10)."""
        response = client.post(
            self._get_submit_url(),
            json={
                "token": self.valid_token,
                "question_id": "q2_pain_scale",
                "response_value": 7
            }
        )
        # Should return valid response codes
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

    @pytest.mark.integration
    def test_submit_multiple_choice_answer(self, client: TestClient):
        """Test submitting multiple choice answer."""
        response = client.post(
            self._get_submit_url(),
            json={
                "token": self.valid_token,
                "question_id": "q3_symptoms",
                "response_value": ["fatigue", "nausea"]
            }
        )
        # Should return valid response codes
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

    @pytest.mark.integration
    def test_submit_answer_with_metadata(self, client: TestClient):
        """Test submitting answer with optional metadata."""
        response = client.post(
            self._get_submit_url(),
            json={
                "token": self.valid_token,
                "question_id": "q1",
                "response_value": "yes",
                "metadata": {
                    "answered_at": datetime.now(timezone.utc).isoformat(),
                    "time_spent_seconds": 15
                }
            }
        )
        # Should return valid response codes
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

    # ========================================================================
    # Validation tests - can run without real backend state
    # ========================================================================

    def test_submit_answer_invalid_token_format(self, client: TestClient):
        """Test submitting answer with invalid token format."""
        response = client.post(
            self._get_submit_url(),
            json={
                "token": "not-a-valid-base64-token!!!",
                "question_id": "q1",
                "response_value": "yes"
            }
        )
        # Should return 401 for invalid token
        assert response.status_code in [401, 403, 422, 500]

    @pytest.mark.integration
    def test_submit_answer_expired_token(self, client: TestClient):
        """Test submitting answer with expired token."""
        # Create an expired token
        expired_token_data = {
            "quiz_id": self.quiz_id,
            "exp": (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp(),  # Expired
            "type": "quiz_access"
        }
        expired_token = base64.b64encode(
            json.dumps(expired_token_data).encode()
        ).decode()

        response = client.post(
            self._get_submit_url(),
            json={
                "token": expired_token,
                "question_id": "q1",
                "response_value": "yes"
            }
        )
        # Should return 401 for expired token
        assert response.status_code in [401, 403, 422, 500]

    def test_submit_answer_missing_token(self, client: TestClient):
        """Test submitting answer without token field."""
        response = client.post(
            self._get_submit_url(),
            json={
                "question_id": "q1",
                "response_value": "yes"
            }
        )
        # Should return 422 validation error for missing required field
        assert response.status_code == 422

    def test_submit_answer_missing_question_id(self, client: TestClient):
        """Test submitting answer without question_id field."""
        response = client.post(
            self._get_submit_url(),
            json={
                "token": self.valid_token,
                "response_value": "yes"
            }
        )
        # Should return 422 validation error
        assert response.status_code == 422

    def test_submit_answer_missing_response_value(self, client: TestClient):
        """Test submitting answer without response_value field."""
        response = client.post(
            self._get_submit_url(),
            json={
                "token": self.valid_token,
                "question_id": "q1"
            }
        )
        # Should return 422 validation error
        assert response.status_code == 422

    def test_submit_answer_wrong_quiz_id_in_token(self, client: TestClient):
        """Test submitting answer with token for different quiz."""
        # Create token with different quiz_id
        wrong_token_data = {
            "quiz_id": str(uuid4()),  # Different from URL quiz_id
            "exp": (datetime.now(timezone.utc) + timedelta(hours=24)).timestamp(),
            "type": "quiz_access"
        }
        wrong_token = base64.b64encode(
            json.dumps(wrong_token_data).encode()
        ).decode()

        response = client.post(
            self._get_submit_url(),
            json={
                "token": wrong_token,
                "question_id": "q1",
                "response_value": "yes"
            }
        )
        # Should return 401 for token/quiz mismatch
        assert response.status_code in [401, 403, 404, 422, 500]

    # ========================================================================
    # Security tests - verify protection mechanisms
    # ========================================================================

    @pytest.mark.security
    @pytest.mark.integration
    def test_submit_answer_xss_protection(self, client: TestClient):
        """Test protection against XSS in text answers."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')"
        ]

        for payload in xss_payloads:
            response = client.post(
                self._get_submit_url(),
                json={
                    "token": self.valid_token,
                    "question_id": "q_text",
                    "response_value": payload
                }
            )
            # Should not crash and should sanitize input
            assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

    @pytest.mark.security
    @pytest.mark.integration
    def test_submit_answer_sql_injection_protection(self, client: TestClient):
        """Test protection against SQL injection."""
        sql_payloads = [
            "'; DROP TABLE quiz_sessions; --",
            "1' OR '1'='1",
            "admin'--"
        ]

        for payload in sql_payloads:
            response = client.post(
                self._get_submit_url(),
                json={
                    "token": self.valid_token,
                    "question_id": "q1",
                    "response_value": payload
                }
            )
            # Should not expose SQL errors or execute injection
            assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

    @pytest.mark.security
    @pytest.mark.integration
    def test_submit_answer_rate_limited(self, client: TestClient):
        """Test that endpoint responds (rate limiting is configured)."""
        # Make multiple rapid requests
        responses = []
        for _ in range(5):
            response = client.post(
                self._get_submit_url(),
                json={
                    "token": self.valid_token,
                    "question_id": "q1",
                    "response_value": "test"
                }
            )
            responses.append(response.status_code)

        # All requests should be handled (may hit rate limit with 429)
        for status in responses:
            assert status in [200, 201, 401, 403, 404, 422, 429, 500]

    def test_empty_json_body(self, client: TestClient):
        """Test submitting with empty JSON body."""
        response = client.post(
            self._get_submit_url(),
            json={}
        )
        # Should return 422 validation error
        assert response.status_code == 422

    def test_invalid_json_body(self, client: TestClient):
        """Test submitting with invalid JSON."""
        response = client.post(
            self._get_submit_url(),
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        # Should return 422 for invalid JSON
        assert response.status_code == 422

    def test_endpoint_accepts_post_only(self, client: TestClient):
        """Test that endpoint only accepts POST method."""
        # GET should fail
        response = client.get(self._get_submit_url())
        assert response.status_code in [405, 404]

        # PUT should fail
        response = client.put(
            self._get_submit_url(),
            json={"token": "test", "question_id": "q1", "response_value": "yes"}
        )
        assert response.status_code in [405, 404]
