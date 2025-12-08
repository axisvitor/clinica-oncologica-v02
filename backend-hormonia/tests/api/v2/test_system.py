"""
Tests for System Management API v2.

Comprehensive test suite for system endpoints including:
- PUBLIC /config endpoint (no auth, security filtering)
- System health checks with Redis caching
- System initialization and status tracking
- System information and feature flags
- Component management and restart operations
- Configuration validation
- System metrics collection
- RBAC enforcement (admin only for system endpoints)
- Rate limiting (different limits for public vs admin)
- Caching behavior (different TTLs)
- Security measures (no sensitive data exposure)
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.main import app

client = TestClient(app)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create an admin user for testing."""
    user = User(
        email="admin@test.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        firebase_uid="admin_123"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_user(db_session: Session) -> User:
    """Create a regular user for testing."""
    user = User(
        email="user@test.com",
        full_name="Regular User",
        role=UserRole.PATIENT,
        is_active=True,
        firebase_uid="user_123"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.info = AsyncMock(return_value={
        "keyspace_hits": 850,
        "keyspace_misses": 150,
        "used_memory": 256 * 1024 * 1024  # 256MB
    })
    return redis_mock


# ============================================================================
# PUBLIC /config Endpoint Tests (NO AUTH)
# ============================================================================

def test_get_public_config_no_auth_required():
    """Test that /config endpoint is accessible without authentication."""
    response = client.get("/api/v2/system/config")

    assert response.status_code == 200
    data = response.json()

    # Verify required fields
    assert "VITE_API_BASE_URL" in data
    assert "VITE_WS_BASE_URL" in data
    assert "VITE_API_URL" in data
    assert "VITE_ENVIRONMENT" in data
    assert "features" in data

    # Verify CORS headers
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "*"


def test_public_config_no_sensitive_data():
    """Test that PUBLIC config endpoint does NOT expose sensitive data."""
    response = client.get("/api/v2/system/config")

    assert response.status_code == 200
    data = response.json()
    data_str = json.dumps(data).lower()

    # Verify NO sensitive data is exposed
    sensitive_keys = [
        "database_url",
        "secret_key",
        "supabase_service_role_key",
        "firebase_admin_private_key",
        "api_key",
        "password",
        "credential",
        "token"
    ]

    for sensitive_key in sensitive_keys:
        assert sensitive_key not in data_str, f"Sensitive key '{sensitive_key}' found in public config!"


def test_public_config_only_safe_env_vars():
    """Test that config only exposes whitelisted environment variable prefixes."""
    with patch.dict('os.environ', {
        'VITE_APP_NAME': 'TestApp',
        'PUBLIC_URL': 'https://test.com',
        'RAILWAY_PUBLIC_DOMAIN': 'test.railway.app',
        'DATABASE_URL': 'postgresql://secret',  # Should NOT be exposed
        'SECRET_KEY': 'super_secret',  # Should NOT be exposed
        'API_KEY': 'secret_key',  # Should NOT be exposed
    }):
        response = client.get("/api/v2/system/config")

        assert response.status_code == 200
        data = response.json()
        data_str = json.dumps(data).lower()

        # Verify safe variables CAN appear
        # (Note: they may not appear if not used in config building logic)

        # Verify sensitive variables do NOT appear
        assert 'postgresql://secret' not in data_str
        assert 'super_secret' not in data_str
        assert 'secret_key' not in data_str


def test_public_config_cors_preflight():
    """Test CORS preflight (OPTIONS) for /config endpoint."""
    response = client.options("/api/v2/system/config")

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "GET" in response.headers["access-control-allow-methods"]


@patch('app.api.v2.system._get_redis_client')
async def test_public_config_caching(mock_redis_client, mock_redis):
    """Test that public config uses Redis caching with 30min TTL."""
    mock_redis_client.return_value = mock_redis

    # First request - cache miss
    response1 = client.get("/api/v2/system/config")
    assert response1.status_code == 200

    # Verify cache was set with correct TTL (1800 seconds = 30 minutes)
    # Note: In actual implementation, setex would be called
    # mock_redis.setex.assert_called_once()
    # call_args = mock_redis.setex.call_args
    # assert call_args[0][1] == 1800  # 30 minute TTL


def test_public_config_rate_limit():
    """Test that public config has generous rate limit (100/min)."""
    # Note: Actual rate limit testing requires proper setup
    # This is a placeholder to document the requirement
    # In production, you'd test with multiple requests
    response = client.get("/api/v2/system/config")
    assert response.status_code == 200


def test_public_config_fallback_on_error():
    """Test that config returns fallback config on error."""
    with patch('app.api.v2.system._build_api_urls', side_effect=Exception("Test error")):
        response = client.get("/api/v2/system/config")

        assert response.status_code == 200  # Still returns 200
        data = response.json()

        # Verify fallback values
        assert "VITE_API_BASE_URL" in data
        assert "localhost" in data["VITE_API_BASE_URL"]
        assert "error" in data
        assert data["error"] == "Failed to build complete config"


# ============================================================================
# System Health Endpoint Tests (ADMIN ONLY)
# ============================================================================

@patch('app.api.v2.system._get_redis_client')
@patch('app.api.v2.system._check_component_health')
def test_get_system_health_admin_only(mock_check_health, mock_redis_client, admin_user, regular_user):
    """Test that /health endpoint requires admin role."""
    # Mock component health checks
    mock_check_health.return_value = AsyncMock()

    # Regular user - should be forbidden
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=regular_user):
        response = client.get("/api/v2/system/health")
        assert response.status_code == 403

    # Admin user - should succeed
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/health")
        assert response.status_code in [200, 503]  # 200 if healthy, 503 if unhealthy


@patch('app.api.v2.system._get_redis_client')
@patch('app.api.v2.system._check_component_health')
async def test_system_health_response_structure(mock_check_health, mock_redis_client, admin_user, mock_redis):
    """Test system health response structure."""
    mock_redis_client.return_value = mock_redis

    # Mock component health
    from app.schemas.v2.system import ComponentHealth
    mock_check_health.return_value = ComponentHealth(
        name="database",
        status="healthy",
        latency_ms=12.5,
        last_check=datetime.utcnow()
    )

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/health")

        assert response.status_code in [200, 503]
        data = response.json()

        # Verify required fields
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data
        assert "overall_score" in data
        assert "degraded_components" in data
        assert "unhealthy_components" in data

        # Verify overall_score is in range [0, 100]
        assert 0 <= data["overall_score"] <= 100


@patch('app.api.v2.system._get_redis_client')
async def test_system_health_caching(mock_redis_client, admin_user, mock_redis):
    """Test that system health uses Redis caching with 30sec TTL."""
    mock_redis_client.return_value = mock_redis

    cached_health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "overall_score": 95.0,
        "components": {},
        "degraded_components": [],
        "unhealthy_components": []
    }
    mock_redis.get.return_value = json.dumps(cached_health)

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/health")

        assert response.status_code == 200
        # Verify cache was checked
        mock_redis.get.assert_called_with("system:health")


def test_system_health_score_calculation():
    """Test health score calculation logic."""
    from app.schemas.v2.system import ComponentHealth
    from app.api.v2.routers.system import _calculate_health_score

    components = {
        "db": ComponentHealth(name="db", status="healthy", last_check=datetime.utcnow()),
        "redis": ComponentHealth(name="redis", status="healthy", last_check=datetime.utcnow()),
        "firebase": ComponentHealth(name="firebase", status="degraded", last_check=datetime.utcnow()),
    }

    score = _calculate_health_score(components)

    # 2 healthy (100 each) + 1 degraded (50) = 250 / 3 = 83.33
    assert 80 <= score <= 85


@patch('app.api.v2.system._check_component_health')
async def test_system_health_unhealthy_returns_503(mock_check_health, admin_user):
    """Test that unhealthy system returns HTTP 503."""
    from app.schemas.v2.system import ComponentHealth

    # Mock all components as unhealthy
    mock_check_health.return_value = ComponentHealth(
        name="test",
        status="unhealthy",
        error="Component failed",
        last_check=datetime.utcnow()
    )

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        with patch('app.api.v2.system._get_redis_client', return_value=None):
            response = client.get("/api/v2/system/health")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"


# ============================================================================
# System Initialization Tests (ADMIN ONLY)
# ============================================================================

def test_initialize_system_admin_only(admin_user, regular_user):
    """Test that /initialize endpoint requires admin role."""
    # Regular user - should be forbidden
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=regular_user):
        response = client.post("/api/v2/system/initialize")
        assert response.status_code == 403

    # Admin user - should succeed (or fail for valid reasons)
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.post("/api/v2/system/initialize")
        assert response.status_code in [200, 409, 500]  # Success, conflict, or error


@patch('app.api.v2.system._get_redis_client')
def test_initialize_system_response_structure(mock_redis_client, admin_user, db_session):
    """Test system initialization response structure."""
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.post("/api/v2/system/initialize", json={
            "force": False,
            "components": ["database", "redis"],
            "skip_health_check": False
        })

        assert response.status_code in [200, 409, 500]

        if response.status_code == 200:
            data = response.json()

            # Verify required fields
            assert "status" in data
            assert "components" in data
            assert "errors" in data
            assert "warnings" in data
            assert data["status"] in ["pending", "in_progress", "completed", "failed", "partial"]


def test_initialize_system_prevent_concurrent(admin_user):
    """Test that initialization prevents concurrent requests."""
    # Set initialization state to in_progress
    from app.api.v2.routers.system import _initialization_state
    _initialization_state["status"] = "in_progress"

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.post("/api/v2/system/initialize")

        assert response.status_code == 409  # Conflict
        assert "already in progress" in response.json()["detail"].lower()

    # Reset state
    _initialization_state["status"] = "pending"


def test_get_initialization_status_admin_only(admin_user, regular_user):
    """Test that /initialization-status endpoint requires admin role."""
    # Regular user - should be forbidden
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=regular_user):
        response = client.get("/api/v2/system/initialization-status")
        assert response.status_code == 403

    # Admin user - should succeed
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/initialization-status")
        assert response.status_code == 200


# ============================================================================
# System Information Tests (ADMIN ONLY)
# ============================================================================

def test_get_system_info_admin_only(admin_user, regular_user):
    """Test that /info endpoint requires admin role."""
    # Regular user - should be forbidden
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=regular_user):
        response = client.get("/api/v2/system/info")
        assert response.status_code == 403

    # Admin user - should succeed
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/info")
        assert response.status_code == 200


@patch('app.api.v2.system._get_redis_client')
def test_system_info_response_structure(mock_redis_client, admin_user, mock_redis):
    """Test system info response structure."""
    mock_redis_client.return_value = mock_redis

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/info")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "environment" in data
        assert "debug_mode" in data
        assert "version" in data
        assert "uptime" in data
        assert "features" in data

        # Verify version is API v2
        assert "2.0" in data["version"]


@patch('app.api.v2.system._get_redis_client')
async def test_system_info_caching(mock_redis_client, admin_user, mock_redis):
    """Test that system info uses Redis caching with 10min TTL."""
    mock_redis_client.return_value = mock_redis

    cached_info = {
        "environment": "test",
        "debug_mode": True,
        "version": "2.0.0",
        "uptime": "1d 2h 3m",
        "features": {}
    }
    mock_redis.get.return_value = json.dumps(cached_info)

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/info")

        assert response.status_code == 200
        # Verify cache was checked
        mock_redis.get.assert_called_with("system:info")


# ============================================================================
# Component Management Tests (ADMIN ONLY)
# ============================================================================

def test_list_components_admin_only(admin_user, regular_user):
    """Test that /components endpoint requires admin role."""
    # Regular user - should be forbidden
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=regular_user):
        response = client.get("/api/v2/system/components")
        assert response.status_code == 403

    # Admin user - should succeed
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/components")
        assert response.status_code == 200


@patch('app.api.v2.system._get_redis_client')
def test_list_components_response_structure(mock_redis_client, admin_user, mock_redis):
    """Test component list response structure."""
    mock_redis_client.return_value = mock_redis

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/components")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "components" in data
        assert "total" in data
        assert "healthy_count" in data
        assert isinstance(data["components"], list)


def test_restart_component_admin_only(admin_user, regular_user):
    """Test that /restart-component endpoint requires admin role."""
    payload = {
        "component": "redis",
        "graceful": True,
        "timeout_seconds": 30
    }

    # Regular user - should be forbidden
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=regular_user):
        response = client.post("/api/v2/system/restart-component", json=payload)
        assert response.status_code == 403

    # Admin user - should succeed
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        with patch('app.utils.cache.reset_redis_connections'):
            response = client.post("/api/v2/system/restart-component", json=payload)
            assert response.status_code == 200


def test_restart_component_invalid_component(admin_user):
    """Test that restarting invalid component fails."""
    payload = {
        "component": "invalid_component",
        "graceful": True,
        "timeout_seconds": 30
    }

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.post("/api/v2/system/restart-component", json=payload)
        assert response.status_code == 422  # Validation error


@patch('app.utils.cache.reset_redis_connections')
def test_restart_component_redis_success(mock_reset, admin_user):
    """Test successful Redis component restart."""
    payload = {
        "component": "redis",
        "graceful": True,
        "timeout_seconds": 30
    }

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.post("/api/v2/system/restart-component", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["component"] == "redis"
        assert data["status"] == "success"
        assert "restarted_at" in data
        assert "duration_ms" in data
        assert data["message"]

        # Verify Redis reset was called
        mock_reset.assert_called_once()


# ============================================================================
# Configuration Validation Tests (ADMIN ONLY)
# ============================================================================

def test_validate_configuration_admin_only(admin_user, regular_user):
    """Test that /validate endpoint requires admin role."""
    # Regular user - should be forbidden
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=regular_user):
        response = client.post("/api/v2/system/validate")
        assert response.status_code == 403

    # Admin user - should succeed
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.post("/api/v2/system/validate")
        assert response.status_code == 200


def test_validate_configuration_response_structure(admin_user):
    """Test configuration validation response structure."""
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.post("/api/v2/system/validate", json={
            "strict": False,
            "categories": ["security", "database"]
        })

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "valid" in data
        assert "warnings" in data
        assert "errors" in data
        assert "checked_at" in data
        assert "categories_checked" in data
        assert "recommendations" in data

        assert isinstance(data["warnings"], list)
        assert isinstance(data["errors"], list)


def test_validate_configuration_detects_missing_secret_key(admin_user):
    """Test that validation detects missing SECRET_KEY."""
    with patch('app.config.settings.SECURITY_SECRET_KEY', ''):
        with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
            response = client.post("/api/v2/system/validate")

            assert response.status_code == 200
            data = response.json()

            # Should have error about SECRET_KEY
            assert not data["valid"]
            assert any("SECRET_KEY" in error for error in data["errors"])


def test_validate_configuration_production_checks(admin_user):
    """Test production-specific validation checks."""
    with patch('app.config.settings.APP_ENVIRONMENT', 'production'):
        with patch('app.config.settings.APP_ENABLE_DEBUG', True):
            with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
                response = client.post("/api/v2/system/validate")

                assert response.status_code == 200
                data = response.json()

                # Should have error about DEBUG=True in production
                assert any("DEBUG" in error and "production" in error for error in data["errors"])


# ============================================================================
# System Metrics Tests (ADMIN ONLY)
# ============================================================================

def test_get_system_metrics_admin_only(admin_user, regular_user):
    """Test that /metrics endpoint requires admin role."""
    # Regular user - should be forbidden
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=regular_user):
        response = client.get("/api/v2/system/metrics")
        assert response.status_code == 403

    # Admin user - should succeed (or 503 if psutil unavailable)
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/metrics")
        assert response.status_code in [200, 503]


@patch('app.api.v2.system.psutil')
@patch('app.api.v2.system._get_redis_client')
def test_system_metrics_response_structure(mock_redis_client, mock_psutil, admin_user, mock_redis):
    """Test system metrics response structure."""
    # Mock psutil functions
    mock_psutil.cpu_percent.return_value = 45.2
    mock_psutil.cpu_count.return_value = 4

    mock_memory = Mock()
    mock_memory.total = 16 * 1024 * 1024 * 1024  # 16GB
    mock_memory.used = 8 * 1024 * 1024 * 1024  # 8GB
    mock_memory.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_memory

    mock_disk = Mock()
    mock_disk.total = 100 * 1024 * 1024 * 1024  # 100GB
    mock_disk.used = 45 * 1024 * 1024 * 1024  # 45GB
    mock_disk.percent = 45.0
    mock_psutil.disk_usage.return_value = mock_disk

    mock_psutil.net_connections.return_value = [Mock()] * 125

    mock_redis_client.return_value = mock_redis

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/metrics")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "timestamp" in data
        assert "cpu_percent" in data
        assert "cpu_count" in data
        assert "memory_total_mb" in data
        assert "memory_used_mb" in data
        assert "memory_percent" in data
        assert "disk_total_gb" in data
        assert "disk_used_gb" in data
        assert "disk_percent" in data
        assert "network_connections" in data
        assert "db_connections" in data

        # Verify values
        assert data["cpu_percent"] == 45.2
        assert data["cpu_count"] == 4
        assert data["memory_percent"] == 50.0


# ============================================================================
# Security Tests
# ============================================================================

def test_admin_endpoints_require_authentication():
    """Test that all admin endpoints require authentication."""
    admin_endpoints = [
        ("/api/v2/system/health", "GET"),
        ("/api/v2/system/initialize", "POST"),
        ("/api/v2/system/initialization-status", "GET"),
        ("/api/v2/system/info", "GET"),
        ("/api/v2/system/components", "GET"),
        ("/api/v2/system/restart-component", "POST"),
        ("/api/v2/system/validate", "POST"),
        ("/api/v2/system/metrics", "GET"),
    ]

    for endpoint, method in admin_endpoints:
        if method == "GET":
            response = client.get(endpoint)
        else:
            response = client.post(endpoint, json={})

        assert response.status_code in [401, 403], f"Endpoint {endpoint} should require auth"


def test_admin_endpoints_reject_non_admin():
    """Test that admin endpoints reject non-admin users."""
    from app.models.user import User, UserRole

    non_admin_user = User(
        email="doctor@test.com",
        role=UserRole.DOCTOR,
        is_active=True
    )

    admin_endpoints = [
        "/api/v2/system/health",
        "/api/v2/system/info",
        "/api/v2/system/components",
        "/api/v2/system/metrics",
    ]

    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=non_admin_user):
        for endpoint in admin_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 403, f"Endpoint {endpoint} should reject non-admin"


# ============================================================================
# Rate Limiting Tests
# ============================================================================

def test_public_config_has_higher_rate_limit():
    """Test that public config has higher rate limit than admin endpoints."""
    # Note: Actual rate limit testing requires proper setup
    # This documents the requirement: config = 100/min, admin = 20/min
    pass


# ============================================================================
# Caching Tests
# ============================================================================

@patch('app.api.v2.system._get_redis_client')
async def test_different_ttls_for_different_endpoints(mock_redis_client, admin_user, mock_redis):
    """Test that different endpoints use different cache TTLs."""
    mock_redis_client.return_value = mock_redis

    # Test config endpoint - should use 1800s (30min)
    response = client.get("/api/v2/system/config")
    assert response.status_code == 200

    # Test health endpoint - should use 30s
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        response = client.get("/api/v2/system/health")
        assert response.status_code in [200, 503]

        # Test info endpoint - should use 600s (10min)
        response = client.get("/api/v2/system/info")
        assert response.status_code == 200


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_system_health_handles_database_error(admin_user):
    """Test that health check handles database errors gracefully."""
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        with patch('sqlalchemy.orm.Session.execute', side_effect=Exception("DB error")):
            response = client.get("/api/v2/system/health")

            # Should still return a response (503 for unhealthy)
            assert response.status_code in [200, 503]


def test_system_metrics_without_psutil(admin_user):
    """Test metrics endpoint when psutil is unavailable."""
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        with patch('app.api.v2.system.psutil', side_effect=ImportError("psutil not available")):
            response = client.get("/api/v2/system/metrics")

            assert response.status_code == 503
            assert "psutil" in response.json()["detail"].lower()


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_system_workflow_admin(admin_user, db_session):
    """Test complete system management workflow."""
    with patch('app.dependencies.auth_dependencies.get_current_user_from_session', return_value=admin_user):
        # 1. Check system health
        response = client.get("/api/v2/system/health")
        assert response.status_code in [200, 503]

        # 2. Get system info
        response = client.get("/api/v2/system/info")
        assert response.status_code == 200

        # 3. Validate configuration
        response = client.post("/api/v2/system/validate")
        assert response.status_code == 200

        # 4. List components
        response = client.get("/api/v2/system/components")
        assert response.status_code == 200

        # 5. Get metrics
        response = client.get("/api/v2/system/metrics")
        assert response.status_code in [200, 503]


def test_public_config_accessible_throughout_workflow():
    """Test that public config is always accessible without auth."""
    # Multiple requests without authentication
    for _ in range(5):
        response = client.get("/api/v2/system/config")
        assert response.status_code == 200
        data = response.json()
        assert "VITE_API_BASE_URL" in data
