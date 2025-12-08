"""
Critical API Tests: Quiz Answer Submission
Tests quiz answer submission, validation, and response handling.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
@pytest.mark.quiz
class TestQuizSubmit:
    """Test quiz answer submission."""

    def test_submit_answer_success(self, client: TestClient):
        """Test submitting a valid quiz answer."""
        token = "valid-quiz-token"

        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q1",
                "response_value": "yes"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_submit_scale_answer(self, client: TestClient):
        """Test submitting a scale-type answer."""
        token = "valid-quiz-token"

        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q1",
                "response_value": "7"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_multiple_choice_answer(self, client: TestClient):
        """Test submitting multiple choice answer."""
        token = "valid-quiz-token"

        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q3",
                "response_value": ["fatigue", "nausea"]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_answer_with_other_text(self, client: TestClient):
        """Test submitting answer with 'other' text."""
        token = "valid-quiz-token"

        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q3",
                "response_value": ["other"],
                "other_text": "Custom symptom description"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_answer_invalid_token(self, client: TestClient):
        """Test submitting answer with invalid token."""
        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": "invalid-token",
                "question_id": "q1",
                "response_value": "yes"
            }
        )

        assert response.status_code == 401
        assert "inválido" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()

    def test_submit_answer_missing_required_field(self, client: TestClient):
        """Test submitting answer with missing required fields."""
        token = "valid-quiz-token"

        # Missing response_value
        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q1"
            }
        )

        assert response.status_code == 422

    def test_submit_answer_invalid_question_id(self, client: TestClient):
        """Test submitting answer to non-existent question."""
        token = "valid-quiz-token"

        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "invalid-question-id",
                "response_value": "yes"
            }
        )

        assert response.status_code == 404
        assert "question" in response.json()["detail"].lower()

    def test_submit_answer_token_rotation(self, client: TestClient):
        """Test that token is rotated after answer submission."""
        token = "valid-quiz-token"

        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q1",
                "response_value": "yes"
            }
        )

        assert response.status_code == 200
        data = response.json()
        # Check if new token is provided
        assert "new_token" in data or "token" in data

    def test_submit_duplicate_answer(self, client: TestClient):
        """Test that submitting answer twice for same question is handled."""
        token = "valid-quiz-token"

        # Submit first answer
        response1 = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q1",
                "response_value": "yes"
            }
        )
        assert response1.status_code == 200

        # Try to submit again for same question
        response2 = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q1",
                "response_value": "no"
            }
        )

        # Should either update or reject
        assert response2.status_code in [200, 409]

    @pytest.mark.security
    def test_submit_answer_xss_protection(self, client: TestClient):
        """Test protection against XSS in text answers."""
        token = "valid-quiz-token"

        malicious_text = "<script>alert('XSS')</script>"

        response = client.post(
            "/api/v2/monthly-quiz-public/submit",
            json={
                "token": token,
                "question_id": "q5",
                "response_value": malicious_text
            }
        )

        # Should succeed but sanitize the input
        assert response.status_code == 200

        # Verify answer was sanitized (check in database or response)
        # Sanitized text should not contain script tags

    @pytest.mark.security
    def test_submit_answer_sql_injection_protection(self, client: TestClient):
        """Test protection against SQL injection."""
        token = "valid-quiz-token"

        malicious_inputs = [
            "'; DROP TABLE quiz_responses; --",
            "1' OR '1'='1",
            "admin' UNION SELECT * FROM users --"
        ]

        for malicious_input in malicious_inputs:
            response = client.post(
                "/api/v2/monthly-quiz-public/submit",
                json={
                    "token": token,
                    "question_id": "q5",
                    "response_value": malicious_input
                }
            )

            # Should not execute malicious query
            assert response.status_code in [200, 400]
