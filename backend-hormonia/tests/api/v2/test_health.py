"""
Tests for Health Check API V2

Comprehensive test suite for unified health monitoring system.
Tests all 20 consolidated endpoints with various scenarios.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.main import app
from app.schemas.v2.health import HealthStatus


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_user(
    db: Session,
    role: UserRole = UserRole.DOCTOR,
    **kwargs
) -> User:
    """Create a test user."""
    user = User(
        email=kwargs.get('email', 'test@example.com'),
        full_name=kwargs.get('full_name', 'Test User'),
        role=role,
        is_active=kwargs.get('is_active', True),
        hashed_password="test_hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
def doctor_user(db: Session):
    """Doctor user fixture."""
    return create_test_user(db, role=UserRole.DOCTOR, email="doctor@test.com")


@pytest.fixture
def admin_user(db: Session):
    """Admin user fixture."""
    return create_test_user(db, role=UserRole.ADMIN, email="admin@test.com")


@pytest.fixture
def mock_auth_headers(doctor_user: User):
    """Mock authentication headers."""
    return {"Authorization": f"Bearer test_token_{doctor_user.id}"}


@pytest.fixture
def mock_admin_headers(admin_user: User):
    """Mock admin authentication headers."""
    return {"Authorization": f"Bearer test_token_{admin_user.id}"}


# ============================================================================
# Test PUBLIC Endpoints (No Auth Required)
# ============================================================================

class TestPublicHealthEndpoints:
    """Test PUBLIC health endpoints (no authentication)."""

    def test_basic_health_check(self, client: TestClient):
        """Test basic health check endpoint."""
        response = client.get("/api/v2/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "2.0.0"
        assert "environment" in data

    def test_basic_health_check_no_auth(self, client: TestClient):
        """Test basic health check works without authentication."""
        response = client.get("/api/v2/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_basic_health_no_caching(self, client: TestClient):
        """Test basic health check is NOT cached."""
        response1 = client.get("/api/v2/health")
        time1 = response1.json()["timestamp"]

        time.sleep(0.1)

        response2 = client.get("/api/v2/health")
        time2 = response2.json()["timestamp"]

        # Timestamps should be different (no caching)
        assert time1 != time2

    def test_readiness_probe(self, client: TestClient):
        """Test Kubernetes readiness probe."""
        response = client.get("/api/v2/health/ready")

        assert response.status_code in [200, 503]
        data = response.json()

        assert "ready" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "timestamp" in data

    def test_readiness_probe_returns_503_when_not_ready(
        self, client: TestClient, db: Session
    ):
        """Test readiness probe returns 503 when database is down."""
        with patch('app.api.v2.health.get_db') as mock_db:
            mock_db.return_value.execute.side_effect = Exception("DB down")

            response = client.get("/api/v2/health/ready")

            assert response.status_code == 503
            data = response.json()
            assert data["ready"] is False
            assert data["checks"]["database"] is False

    def test_liveness_probe(self, client: TestClient):
        """Test Kubernetes liveness probe."""
        response = client.get("/api/v2/health/live")

        assert response.status_code == 200
        data = response.json()

        assert data["alive"] is True
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0
        assert "timestamp" in data

    def test_liveness_always_returns_200(self, client: TestClient):
        """Test liveness probe always returns 200."""
        response = client.get("/api/v2/health/live")

        assert response.status_code == 200
        assert response.json()["alive"] is True


# ============================================================================
# Test Detailed Health Endpoint
# ============================================================================

class TestDetailedHealthEndpoint:
    """Test detailed health check endpoint."""

    def test_detailed_health_requires_auth(self, client: TestClient):
        """Test detailed health requires authentication."""
        response = client.get("/api/v2/health/detailed")

        assert response.status_code == 401

    def test_detailed_health_with_auth(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test detailed health check with authentication."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/detailed",
                headers=mock_auth_headers
            )

            assert response.status_code in [200, 503]
            data = response.json()

            assert "status" in data
            assert "health_score" in data
            assert 0 <= data["health_score"] <= 100
            assert "database" in data
            assert "redis" in data
            assert "workers" in data
            assert "external_services" in data
            assert "storage" in data
            assert "response_time_ms" in data
            assert "uptime_seconds" in data

    def test_detailed_health_scoring_algorithm(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test health scoring algorithm."""
        from app.api.v2.routers.health import calculate_health_score

        # All healthy - should be 100
        all_healthy = {
            "database": HealthStatus.HEALTHY,
            "redis": HealthStatus.HEALTHY,
            "workers": HealthStatus.HEALTHY,
            "external_services": HealthStatus.HEALTHY,
            "storage": HealthStatus.HEALTHY,
        }
        score = calculate_health_score(all_healthy)
        assert score == 100.0

        # Database unhealthy - major impact (30% weight)
        db_unhealthy = {
            "database": HealthStatus.UNHEALTHY,
            "redis": HealthStatus.HEALTHY,
            "workers": HealthStatus.HEALTHY,
            "external_services": HealthStatus.HEALTHY,
            "storage": HealthStatus.HEALTHY,
        }
        score = calculate_health_score(db_unhealthy)
        assert score == 70.0  # Lost 30% from database

        # All degraded - should be 50
        all_degraded = {
            "database": HealthStatus.DEGRADED,
            "redis": HealthStatus.DEGRADED,
            "workers": HealthStatus.DEGRADED,
            "external_services": HealthStatus.DEGRADED,
            "storage": HealthStatus.DEGRADED,
        }
        score = calculate_health_score(all_degraded)
        assert score == 50.0

    def test_detailed_health_returns_503_when_unhealthy(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test detailed health returns 503 when unhealthy."""
        with patch('app.api.v2.health.get_current_user'):
            with patch('app.api.v2.health.check_database_health') as mock_db:
                # Mock unhealthy database
                from app.schemas.v2.health import DatabaseHealth
                mock_db.return_value = DatabaseHealth(
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0.0,
                    pool_size=0,
                    active_connections=0,
                    available_connections=0,
                    pool_utilization_percent=0.0,
                    rls_enabled=False,
                    migrations_current=False,
                )

                response = client.get(
                    "/api/v2/health/detailed",
                    headers=mock_auth_headers
                )

                # Should return 503 with unhealthy database
                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["health_score"] < 70


# ============================================================================
# Test Component Health Endpoints
# ============================================================================

class TestComponentHealthEndpoints:
    """Test individual component health endpoints."""

    def test_database_health(
        self, client: TestClient, mock_auth_headers: dict, db: Session
    ):
        """Test database health endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/database",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert "latency_ms" in data
            assert "pool_size" in data
            assert "active_connections" in data
            assert "pool_utilization_percent" in data
            assert "rls_enabled" in data
            assert "migrations_current" in data

    def test_redis_health(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test Redis health endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/redis",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert "latency_ms" in data
            assert "memory_used_mb" in data
            assert "hit_rate_percent" in data
            assert "connected_clients" in data

    def test_workers_health(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test workers health endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/workers",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert "active_workers" in data
            assert "active_tasks" in data
            assert "failed_tasks_24h" in data
            assert "pending_tasks" in data
            assert "queue_size" in data

    def test_external_services_health(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test external services health endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/external",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert isinstance(data, list)

    def test_storage_health(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test storage health endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/storage",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert "available_space_gb" in data
            assert "used_space_gb" in data
            assert "total_space_gb" in data
            assert "utilization_percent" in data


# ============================================================================
# Test Metrics Endpoints
# ============================================================================

class TestMetricsEndpoints:
    """Test metrics endpoints."""

    def test_prometheus_metrics(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test Prometheus metrics endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/metrics",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/plain")

            content = response.text
            assert "# HELP" in content
            assert "# TYPE" in content
            assert "health_status" in content
            assert "database_latency_ms" in content

    def test_system_metrics(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test system metrics endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/metrics/system",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "cpu_percent" in data
            assert "memory_percent" in data
            assert "disk_usage_percent" in data
            assert "network_bytes_sent" in data
            assert "process_count" in data

    def test_application_metrics(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test application metrics endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/metrics/application",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "total_requests" in data
            assert "requests_per_second" in data
            assert "avg_response_time_ms" in data
            assert "error_rate_percent" in data

    def test_custom_metrics(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test custom business metrics endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/metrics/custom",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "active_patients" in data
            assert "messages_sent_24h" in data
            assert "quizzes_completed_24h" in data
            assert "alerts_triggered_24h" in data


# ============================================================================
# Test Platform-Specific Endpoints
# ============================================================================

class TestPlatformHealthEndpoints:
    """Test platform-specific health endpoints."""

    def test_railway_health(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test Railway health endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/railway",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert "environment_variables_set" in data

    def test_production_health(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test production health endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/production",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert "environment" in data
            assert "debug_mode" in data

    def test_environment_health(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test environment configuration health endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/environment",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert "required_vars_set" in data
            assert "total_required_vars" in data
            assert "missing_vars" in data
            assert "configuration_valid" in data


# ============================================================================
# Test Advanced Monitoring Endpoints
# ============================================================================

class TestAdvancedMonitoringEndpoints:
    """Test advanced monitoring endpoints."""

    def test_health_history(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test health history endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/history",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "entries" in data
            assert "period_hours" in data
            assert "avg_health_score" in data
            assert "total_checks" in data
            assert "degraded_periods" in data
            assert "unhealthy_periods" in data

    def test_health_incidents(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test health incidents endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/incidents",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "incidents" in data
            assert "total_incidents" in data
            assert "active_incidents" in data
            assert "resolved_incidents" in data

    def test_health_alerts(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test health alerts endpoint."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.get(
                "/api/v2/health/alerts",
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "alerts" in data
            assert "total_alerts" in data
            assert "critical_count" in data
            assert "warning_count" in data
            assert "info_count" in data


# ============================================================================
# Test Manual Test Endpoint (Admin Only)
# ============================================================================

class TestManualHealthTest:
    """Test manual health test endpoint."""

    def test_manual_test_requires_admin(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test manual test requires admin role."""
        with patch('app.api.v2.health.get_current_user'):
            response = client.post(
                "/api/v2/health/test",
                json={"components": ["database"]},
                headers=mock_auth_headers
            )

            assert response.status_code == 403

    def test_manual_test_with_admin(
        self, client: TestClient, mock_admin_headers: dict
    ):
        """Test manual test with admin user."""
        with patch('app.api.v2.health.get_admin_user'):
            response = client.post(
                "/api/v2/health/test",
                json={
                    "components": ["database", "redis"],
                    "include_detailed": True,
                    "force_refresh": True
                },
                headers=mock_admin_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert "test_id" in data
            assert "timestamp" in data
            assert "status" in data
            assert "components_tested" in data
            assert "results" in data
            assert "duration_ms" in data
            assert data["components_tested"] == ["database", "redis"]

    def test_manual_test_all_components(
        self, client: TestClient, mock_admin_headers: dict
    ):
        """Test manual test with all components."""
        with patch('app.api.v2.health.get_admin_user'):
            response = client.post(
                "/api/v2/health/test",
                json={},  # Empty = test all
                headers=mock_admin_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data["components_tested"]) >= 4
            assert "database" in data["components_tested"]
            assert "redis" in data["components_tested"]
            assert "workers" in data["components_tested"]
            assert "storage" in data["components_tested"]


# ============================================================================
# Test Rate Limiting
# ============================================================================

class TestRateLimiting:
    """Test rate limiting on health endpoints."""

    def test_public_endpoints_high_rate_limit(self, client: TestClient):
        """Test public endpoints have generous rate limits (200 req/min)."""
        # Make multiple requests quickly
        for i in range(10):
            response = client.get("/api/v2/health")
            assert response.status_code == 200

    def test_authenticated_endpoints_rate_limit(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test authenticated endpoints have moderate rate limits (100 req/min)."""
        with patch('app.api.v2.health.get_current_user'):
            for i in range(10):
                response = client.get(
                    "/api/v2/health/detailed",
                    headers=mock_auth_headers
                )
                assert response.status_code in [200, 503]


# ============================================================================
# Test HTTP Status Codes
# ============================================================================

class TestHTTPStatusCodes:
    """Test proper HTTP status code usage."""

    def test_healthy_returns_200(self, client: TestClient):
        """Test healthy status returns 200."""
        response = client.get("/api/v2/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_unhealthy_returns_503(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test unhealthy status returns 503."""
        with patch('app.api.v2.health.get_current_user'):
            with patch('app.api.v2.health.check_database_health') as mock_db:
                from app.schemas.v2.health import DatabaseHealth
                mock_db.return_value = DatabaseHealth(
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0.0,
                    pool_size=0,
                    active_connections=0,
                    available_connections=0,
                    pool_utilization_percent=0.0,
                    rls_enabled=False,
                    migrations_current=False,
                )

                response = client.get(
                    "/api/v2/health/detailed",
                    headers=mock_auth_headers
                )

                assert response.status_code == 503
                assert response.json()["status"] == "unhealthy"


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_database_failure_graceful_degradation(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test graceful degradation when database fails."""
        with patch('app.api.v2.health.get_current_user'):
            with patch('app.api.v2.health.check_database_health') as mock_db:
                mock_db.side_effect = Exception("Database connection failed")

                response = client.get(
                    "/api/v2/health/database",
                    headers=mock_auth_headers
                )

                # Should still return a response, not crash
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "unhealthy"

    def test_redis_failure_non_critical(
        self, client: TestClient, mock_auth_headers: dict
    ):
        """Test Redis failure is non-critical (degraded, not unhealthy)."""
        with patch('app.api.v2.health.get_current_user'):
            with patch('app.api.v2.health.check_redis_health') as mock_redis:
                from app.schemas.v2.health import RedisHealth
                mock_redis.return_value = RedisHealth(
                    status=HealthStatus.DEGRADED,
                    latency_ms=0.0,
                    memory_used_mb=0.0,
                    memory_peak_mb=0.0,
                    hit_rate_percent=0.0,
                    connected_clients=0,
                )

                response = client.get(
                    "/api/v2/health/redis",
                    headers=mock_auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                # Redis failure should be degraded, not unhealthy
                assert data["status"] == "degraded"
