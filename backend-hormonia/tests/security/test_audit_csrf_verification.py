import pytest
import time
import hmac
import hashlib
from fastapi.testclient import TestClient
from app.main import app
from app.middleware.csrf import generate_csrf_token, COOKIE_NAME, get_csrf_settings

@pytest.mark.security
class TestCSRFAuditVerification:
    """
    Audit verification tests for CSRF protection.
    Verifies Double Submit Cookie pattern and token rotation.
    """

    def test_csrf_success_flow(self):
        """Verify that matching header and cookie allow the request."""
        client = TestClient(app)
        
        # 1. Get a token
        token = generate_csrf_token()
        
        # 2. Make a POST request with both
        response = client.post(
            "/api/v2/patients/",
            headers={"X-CSRF-Token": token},
            cookies={COOKIE_NAME: token},
            json={"name": "Test"} # Minimal body, will fail validation later but should pass CSRF
        )
        
        # Should NOT be 403 Forbidden (CSRF)
        # It might be 401 Unauthorized because we didn't provide Auth, 
        # but 401 is AFTER CSRF in middleware execution order (if added correctly).
        # Wait, if added correctly, CSRF executes BEFORE Auth?
        # In middleware_setup.py:
        # [4/7] CSRF
        # [8/8] CORS (First)
        # Auth is a dependency, so it runs after all middleware.
        
        assert response.status_code != 403
        if response.status_code == 403:
            assert response.json().get("error") != "csrf_mismatch"

    def test_csrf_missing_header(self):
        """Verify that missing header fails with 403."""
        client = TestClient(app)
        token = generate_csrf_token()
        
        response = client.post(
            "/api/v2/patients/",
            cookies={COOKIE_NAME: token},
            json={"name": "Test"}
        )
        
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_token_missing"

    def test_csrf_missing_cookie(self):
        """Verify that missing cookie fails with 403."""
        client = TestClient(app)
        token = generate_csrf_token()
        
        response = client.post(
            "/api/v2/patients/",
            headers={"X-CSRF-Token": token},
            json={"name": "Test"}
        )
        
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_cookie_missing"

    def test_csrf_mismatch(self):
        """Verify that mismatched tokens fail with 403."""
        client = TestClient(app)
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        
        response = client.post(
            "/api/v2/patients/",
            headers={"X-CSRF-Token": token1},
            cookies={COOKIE_NAME: token2},
            json={"name": "Test"}
        )
        
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_mismatch"

    def test_csrf_expired_token(self):
        """Verify that expired token fails with 403."""
        # Manually generate an expired token
        settings = get_csrf_settings()
        old_timestamp = str(int(time.time()) - 4000) # > 3600s ago
        random_data = "abc123def456"
        payload = f"{old_timestamp}.{random_data}"
        signature = hmac.new(
            settings.secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        expired_token = f"{payload}.{signature}"
        
        client = TestClient(app)
        response = client.post(
            "/api/v2/patients/",
            headers={"X-CSRF-Token": expired_token},
            cookies={COOKIE_NAME: expired_token},
            json={"name": "Test"}
        )
        
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_token_invalid" # validate_csrf_token returns False for expired

    def test_csrf_token_rotation_endpoint(self):
        """Verify that the token rotation endpoint returns a valid token and sets cookie."""
        client = TestClient(app)
        
        # Use the established CSRF token endpoint
        response = client.get("/api/v2/auth/csrf-token")
        
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        
        token = data["csrf_token"]
        assert COOKIE_NAME in response.cookies
        assert response.cookies[COOKIE_NAME] == token
        
        # Verify the returned token is actually valid for a subsequent request
        response2 = client.post(
            "/api/v2/patients/",
            headers={"X-CSRF-Token": token},
            cookies={COOKIE_NAME: token},
            json={"name": "Test"}
        )
        assert response2.status_code != 403
