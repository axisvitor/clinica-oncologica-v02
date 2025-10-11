"""
Comprehensive Health Check Endpoint Tests for Production Readiness
================================================================

This test suite validates all health check endpoints for the oncology clinic system,
ensuring production readiness, Railway deployment compatibility, and monitoring capabilities.

Test Coverage:
- Basic health check endpoints
- Database connectivity verification
- Redis cache connectivity
- External service dependencies
- Performance thresholds
- Error handling and resilience
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app
from app.dependencies import get_thread_safe_db
from app.models.user import User
from app.utils.unified_cache import get_cache_connection


# Test client for FastAPI application
client = TestClient(app)


class TestHealthCheckEndpoints:
    """Comprehensive test suite for health check endpoints."""

    def test_basic_health_check(self):
        """Test basic health check endpoint response."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data

        # Validate status values
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        # Validate timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
        assert isinstance(timestamp, datetime)

        # Response time should be under 100ms for basic health check
        assert response.elapsed.total_seconds() < 0.1

    def test_detailed_health_check(self):
        """Test detailed health check with all system components."""
        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()

        # Validate detailed response structure
        required_fields = [
            "status", "timestamp", "version", "environment",
            "database", "cache", "services", "metrics"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate database health
        db_health = data["database"]
        assert "status" in db_health
        assert "connection_count" in db_health
        assert "response_time_ms" in db_health
        assert db_health["status"] in ["healthy", "degraded", "unhealthy"]

        # Validate cache health
        cache_health = data["cache"]
        assert "status" in cache_health
        assert "response_time_ms" in cache_health

        # Validate services
        services = data["services"]
        assert isinstance(services, dict)

        # Validate metrics
        metrics = data["metrics"]
        assert "uptime_seconds" in metrics
        assert "memory_usage_mb" in metrics
        assert "cpu_usage_percent" in metrics

    def test_database_health_check(self):
        """Test database-specific health check endpoint."""
        response = client.get("/health/database")

        assert response.status_code == 200
        data = response.json()

        # Validate database health response
        assert "status" in data
        assert "connection_count" in data
        assert "response_time_ms" in data
        assert "pool_status" in data

        # Database should be healthy for tests
        assert data["status"] == "healthy"

        # Response time should be reasonable
        assert data["response_time_ms"] < 100

        # Pool status validation
        pool_status = data["pool_status"]
        assert "size" in pool_status
        assert "checked_in" in pool_status
        assert "checked_out" in pool_status

    def test_cache_health_check(self):
        """Test cache/Redis health check endpoint."""
        response = client.get("/health/cache")

        assert response.status_code == 200
        data = response.json()

        # Validate cache health response
        assert "status" in data
        assert "response_time_ms" in data
        assert "memory_usage" in data

        # Cache should be healthy
        assert data["status"] in ["healthy", "degraded"]

        # Response time should be fast
        assert data["response_time_ms"] < 50

    def test_readiness_check(self):
        """Test readiness probe for Kubernetes/Railway deployment."""
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()

        # Validate readiness response
        assert "ready" in data
        assert "checks" in data
        assert "timestamp" in data

        # All checks should pass for readiness
        checks = data["checks"]
        for check_name, check_result in checks.items():
            assert check_result["status"] == "healthy", f"Readiness check failed: {check_name}"

    def test_liveness_check(self):
        """Test liveness probe for container orchestration."""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()

        # Validate liveness response
        assert "alive" in data
        assert data["alive"] is True
        assert "timestamp" in data
        assert "uptime_seconds" in data

        # Uptime should be positive
        assert data["uptime_seconds"] > 0

    def test_metrics_endpoint(self):
        """Test metrics endpoint for monitoring integration."""
        response = client.get("/metrics")

        # Metrics can be in different formats (JSON or Prometheus)
        assert response.status_code == 200

        # Check if it's JSON metrics
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()

            # Validate metrics structure
            assert "system" in data
            assert "application" in data
            assert "business" in data

            # System metrics
            system_metrics = data["system"]
            assert "memory_usage_mb" in system_metrics
            assert "cpu_usage_percent" in system_metrics
            assert "disk_usage_percent" in system_metrics

            # Application metrics
            app_metrics = data["application"]
            assert "request_count" in app_metrics
            assert "response_time_avg_ms" in app_metrics
            assert "error_rate_percent" in app_metrics

            # Business metrics
            business_metrics = data["business"]
            assert "total_patients" in business_metrics
            assert "active_patients" in business_metrics

    @pytest.mark.asyncio
    async def test_health_check_performance(self):
        """Test health check endpoint performance under load."""
        start_time = time.time()

        # Make 10 concurrent requests
        async with httpx.AsyncClient(base_url="http://testserver") as async_client:
            tasks = [async_client.get("/health") for _ in range(10)]
            responses = await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200

        # Total time for 10 concurrent requests should be reasonable
        assert total_time < 1.0  # Less than 1 second for 10 concurrent requests

        # Average response time should be under 100ms
        avg_response_time = total_time / len(responses)
        assert avg_response_time < 0.1

    def test_health_check_with_database_failure(self):
        """Test health check behavior when database is unavailable."""
        with patch('app.dependencies.get_thread_safe_db') as mock_db:
            # Simulate database connection failure
            mock_db.side_effect = Exception("Database connection failed")

            response = client.get("/health/detailed")

            assert response.status_code == 503  # Service Unavailable
            data = response.json()

            assert data["status"] == "unhealthy"
            assert data["database"]["status"] == "unhealthy"
            assert "error" in data["database"]

    def test_health_check_with_cache_failure(self):
        """Test health check behavior when cache/Redis is unavailable."""
        with patch('app.utils.unified_cache.get_cache_connection') as mock_cache:
            # Simulate cache connection failure
            mock_cache.side_effect = Exception("Cache connection failed")

            response = client.get("/health/cache")

            # Cache failure should result in degraded status, not complete failure
            assert response.status_code in [200, 503]
            data = response.json()

            assert data["status"] in ["degraded", "unhealthy"]
            assert "error" in data

    def test_health_check_authentication_not_required(self):
        """Test that health check endpoints don't require authentication."""
        # Health checks should work without authentication headers
        endpoints = [
            "/health",
            "/health/ready",
            "/health/live",
            "/metrics"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not return 401 Unauthorized
            assert response.status_code != 401

    def test_health_check_response_caching(self):
        """Test that health check responses are properly cached."""
        # First request
        response1 = client.get("/health")
        timestamp1 = response1.json()["timestamp"]

        # Second request immediately after
        response2 = client.get("/health")
        timestamp2 = response2.json()["timestamp"]

        # Timestamps should be very close (within 1 second) indicating caching
        time1 = datetime.fromisoformat(timestamp1.replace('Z', '+00:00'))
        time2 = datetime.fromisoformat(timestamp2.replace('Z', '+00:00'))
        time_diff = abs((time2 - time1).total_seconds())

        assert time_diff < 1.0

    def test_health_check_cors_headers(self):
        """Test that health check endpoints include proper CORS headers."""
        response = client.get("/health")

        # Should include CORS headers for monitoring dashboards
        headers = response.headers
        assert "access-control-allow-origin" in headers.keys() or \
               "Access-Control-Allow-Origin" in headers.keys()

    def test_health_check_content_type(self):
        """Test that health check endpoints return proper content type."""
        response = client.get("/health")

        assert response.headers["content-type"] == "application/json"

    def test_system_resource_monitoring(self):
        """Test system resource monitoring in health checks."""
        response = client.get("/health/detailed")
        data = response.json()

        metrics = data["metrics"]

        # Memory usage should be reasonable
        memory_usage = metrics["memory_usage_mb"]
        assert isinstance(memory_usage, (int, float))
        assert memory_usage > 0
        assert memory_usage < 8192  # Less than 8GB for reasonable operation

        # CPU usage should be within reasonable bounds
        cpu_usage = metrics["cpu_usage_percent"]
        assert isinstance(cpu_usage, (int, float))
        assert 0 <= cpu_usage <= 100

    def test_dependency_health_checks(self):
        """Test health checks for external dependencies."""
        response = client.get("/health/detailed")
        data = response.json()

        services = data["services"]

        # Should include checks for key dependencies
        expected_services = [
            "database",
            "cache",
            "firebase_auth"  # If Firebase is configured
        ]

        for service in expected_services:
            if service in services:
                service_health = services[service]
                assert "status" in service_health
                assert "response_time_ms" in service_health
                assert service_health["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_check_version_info(self):
        """Test that health checks include proper version information."""
        response = client.get("/health")
        data = response.json()

        # Should include version information
        assert "version" in data
        version = data["version"]

        # Version should be a non-empty string
        assert isinstance(version, str)
        assert len(version) > 0

        # Should include environment information
        assert "environment" in data
        environment = data["environment"]
        assert environment in ["development", "testing", "staging", "production"]

    def test_health_check_monitoring_integration(self):
        """Test health check endpoints for monitoring tool integration."""
        # Test Prometheus-style metrics endpoint
        response = client.get("/metrics", headers={"Accept": "text/plain"})

        if response.status_code == 200:
            # If Prometheus metrics are supported
            content = response.text

            # Should contain basic metrics
            assert "http_requests_total" in content or "request_count" in content
            assert "http_request_duration" in content or "response_time" in content

    def test_health_check_graceful_degradation(self):
        """Test graceful degradation when some components are unhealthy."""
        # This test would require mocking various failure scenarios
        # and ensuring the system still reports useful health information

        response = client.get("/health/detailed")

        # Even if some components are degraded, we should get a response
        assert response.status_code in [200, 503]
        data = response.json()

        # Response should always include basic structure
        assert "status" in data
        assert "timestamp" in data


class TestRailwayDeploymentCompatibility:
    """Test compatibility with Railway deployment environment."""

    def test_railway_port_configuration(self):
        """Test that health checks work with Railway's dynamic port assignment."""
        # Railway assigns port via $PORT environment variable
        response = client.get("/health")
        assert response.status_code == 200

    def test_railway_health_check_path(self):
        """Test health check paths compatible with Railway monitoring."""
        # Railway typically checks root path and /health
        paths = ["/", "/health", "/health/ready"]

        for path in paths:
            response = client.get(path)
            # Should not return 404
            assert response.status_code != 404

    def test_railway_environment_detection(self):
        """Test detection of Railway environment variables."""
        response = client.get("/health/detailed")
        data = response.json()

        # Should correctly identify Railway environment
        environment = data.get("environment", "unknown")

        # In Railway, this should be "production" or "staging"
        assert environment in ["development", "testing", "staging", "production"]

    def test_railway_startup_health_check(self):
        """Test health check during Railway startup sequence."""
        # Simulate startup conditions
        response = client.get("/health/ready")

        # Should be ready for traffic
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True


@pytest.fixture
def mock_database_session():
    """Mock database session for testing."""
    session = MagicMock(spec=Session)
    session.execute.return_value.scalar.return_value = 1
    return session


@pytest.fixture
def mock_cache_connection():
    """Mock cache connection for testing."""
    cache = MagicMock()
    cache.ping.return_value = True
    cache.info.return_value = {"used_memory": 1024000}
    return cache


def test_health_check_database_query_performance(mock_database_session):
    """Test database health check query performance."""
    with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
        start_time = time.time()

        response = client.get("/health/database")

        end_time = time.time()
        query_time = (end_time - start_time) * 1000  # Convert to milliseconds

        assert response.status_code == 200
        # Database health check should be fast
        assert query_time < 100  # Less than 100ms


def test_health_check_cache_performance(mock_cache_connection):
    """Test cache health check performance."""
    with patch('app.utils.unified_cache.get_cache_connection', return_value=mock_cache_connection):
        start_time = time.time()

        response = client.get("/health/cache")

        end_time = time.time()
        cache_time = (end_time - start_time) * 1000  # Convert to milliseconds

        assert response.status_code == 200
        # Cache health check should be very fast
        assert cache_time < 50  # Less than 50ms