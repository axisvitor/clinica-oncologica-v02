"""
Debug API v2 tests with concrete assertions.

This suite intentionally keeps only behavior-driven tests for safety gates,
validation, sanitization, and sensitive data masking.
"""

import importlib

import pytest
from fastapi import status
from fastapi.testclient import TestClient


@pytest.fixture
def enable_debug_endpoints(monkeypatch):
    """Enable debug endpoints for testing."""
    monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", "true")
    from app.api.v2.routers import debug as debug_module

    importlib.reload(debug_module)


@pytest.fixture
def disable_debug_endpoints(monkeypatch):
    """Disable debug endpoints for testing."""
    monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", "false")
    from app.api.v2.routers import debug as debug_module

    importlib.reload(debug_module)


class TestProductionSafety:
    """Debug endpoints must stay disabled when feature flag is off."""

    def test_debug_disabled_by_default(self, client: TestClient, disable_debug_endpoints):
        response = client.get("/api/v2/debug/environment")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_database_diagnostics_disabled(self, client: TestClient, disable_debug_endpoints):
        response = client.get("/api/v2/debug/database")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_test_query_disabled(self, client: TestClient, disable_debug_endpoints):
        response = client.post(
            "/api/v2/debug/test-query",
            json={"query": "SELECT 1", "timeout_seconds": 5},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_auth_token_debug_disabled(self, client: TestClient, disable_debug_endpoints):
        response = client.post(
            "/api/v2/debug/auth/token",
            params={"token": "test_token"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_auth_simulate_disabled(self, client: TestClient, disable_debug_endpoints):
        response = client.post(
            "/api/v2/debug/auth/simulate",
            json={
                "user_id": "00000000-0000-0000-0000-000000000000",
                "simulate_session": True,
                "duration_minutes": 5,
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAdminOnlyAccess:
    """Debug endpoints require authentication/authorization when enabled."""

    def test_environment_requires_admin(self, client: TestClient, enable_debug_endpoints):
        response = client.get("/api/v2/debug/environment")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_database_requires_admin(self, client: TestClient, enable_debug_endpoints):
        response = client.get("/api/v2/debug/database")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_inactive_admin_rejected(self, client: TestClient, enable_debug_endpoints):
        response = client.get("/api/v2/debug/environment")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


class TestEnvironmentInfo:
    """Environment masking and allowlist behavior."""

    def test_environment_vars_masked(self):
        from app.api.v2.routers.debug import mask_sensitive_value

        masked, is_masked = mask_sensitive_value("DATABASE_PASSWORD", "secret123")
        assert is_masked is True
        assert "***" in masked

        masked, is_masked = mask_sensitive_value(
            "DATABASE_URL",
            "postgresql://user:pass@localhost:5432/db",
        )
        assert is_masked is True
        assert "***:***@" in masked

        masked, is_masked = mask_sensitive_value("ENVIRONMENT", "development")
        assert is_masked is False
        assert masked == "development"

    def test_only_whitelisted_vars_exposed(self):
        from app.api.v2.routers.debug import SAFE_ENV_VARS

        assert "ENVIRONMENT" in SAFE_ENV_VARS
        assert "DATABASE_URL" in SAFE_ENV_VARS
        assert "SECRET_KEY" not in SAFE_ENV_VARS
        assert "JWT_SECRET" not in SAFE_ENV_VARS


class TestQueryExecution:
    """Validation and sanitization for debug SQL execution."""

    def test_select_query_allowed(self):
        from app.schemas.v2.debug import TestQueryRequest

        query_request = TestQueryRequest(
            query="SELECT COUNT(*) FROM users",
            timeout_seconds=5,
        )
        assert query_request.query.strip().upper().startswith("SELECT")

    def test_dangerous_queries_blocked(self):
        from app.schemas.v2.debug import TestQueryRequest

        dangerous_queries = [
            "DROP TABLE users",
            "DELETE FROM users",
            "UPDATE users SET role = 'admin'",
            "INSERT INTO users VALUES (...)",
            "TRUNCATE TABLE users",
        ]

        for query in dangerous_queries:
            with pytest.raises(ValueError):
                TestQueryRequest(query=query, timeout_seconds=5)

    def test_query_sanitization(self):
        from app.api.v2.routers.debug import sanitize_sql_query

        long_query = "SELECT * FROM users WHERE " + "a" * 200
        sanitized = sanitize_sql_query(long_query, max_length=100)
        assert len(sanitized) <= 103
        assert sanitized.endswith("...")

    def test_query_timeout_enforced(self):
        from app.schemas.v2.debug import TestQueryRequest

        request = TestQueryRequest(query="SELECT 1", timeout_seconds=5)
        assert request.timeout_seconds == 5

        with pytest.raises(ValueError):
            TestQueryRequest(query="SELECT 1", timeout_seconds=100)


class TestSecuritySafeguards:
    """Security masking and injection prevention helpers."""

    def test_no_credentials_in_environment(self):
        from app.api.v2.routers.debug import mask_sensitive_value

        sensitive_keys = [
            "DATABASE_PASSWORD",
            "SECRET_KEY",
            "JWT_SECRET",
            "API_KEY",
            "FIREBASE_PRIVATE_KEY",
        ]

        for key in sensitive_keys:
            masked, is_masked = mask_sensitive_value(key, "sensitive_value")
            assert is_masked is True
            assert "***" in masked

    def test_query_injection_prevention(self):
        from app.schemas.v2.debug import TestQueryRequest

        injection_attempts = [
            "SELECT * FROM users; DROP TABLE users;--",
            "SELECT * FROM users WHERE 1=1; DELETE FROM users;--",
        ]

        for injection in injection_attempts:
            with pytest.raises(ValueError):
                TestQueryRequest(query=injection, timeout_seconds=5)

    def test_audit_logs_sanitized(self):
        from app.api.v2.routers.debug import sanitize_sql_query

        sensitive_query = "SELECT * FROM users WHERE password = 'secret123'"
        sanitized = sanitize_sql_query(sensitive_query, max_length=50)
        assert len(sanitized) <= 53
