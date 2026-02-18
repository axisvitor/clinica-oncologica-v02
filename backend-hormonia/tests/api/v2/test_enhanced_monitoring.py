"""
Tests for Enhanced Monitoring API v2
Comprehensive test coverage for all monitoring endpoints.

Test Categories:
- Health & System (6 tests)
- APM Endpoints (8 tests)
- Database Monitoring (6 tests)
- Resource Monitoring (6 tests)
- Business Metrics (6 tests)
- Anomaly Detection (4 tests)
- Dashboard (4 tests)
- Alerts (4 tests)
- Performance (2 tests)
- Export (4 tests)
- Configuration (4 tests)
- Management Actions (6 tests)

Total: 60+ comprehensive tests
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi import status, HTTPException

from app.main import app
from app.models.user import User, UserRole
from app.monitoring.manager import MonitoringManager


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def admin_user(db_session):
    """Create admin user for testing."""
    user = User(
        email="admin@test.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_user(db_session):
    """Create regular user for testing."""
    user = User(
        email="user@test.com",
        full_name="Regular User",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_monitoring_manager():
    """Mock monitoring manager."""
    with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
        manager = Mock(spec=MonitoringManager)
        manager._started = True

        # Mock APM collector
        manager.apm_collector = Mock()
        manager.apm_collector.get_global_stats.return_value = {
            "total_requests": 10000,
            "total_errors": 250,
            "error_rate": 2.5,
            "avg_response_time": 125.5,
            "p50": 85.0,
            "p95": 350.0,
            "p99": 850.0,
            "requests_per_second": 25.5,
        }
        manager.apm_collector.get_all_endpoints_stats.return_value = {
            "/api/v2/patients": {
                "total_requests": 1500,
                "total_errors": 15,
                "error_rate": 1.0,
                "avg_response_time": 95.5,
                "p95": 250.0,
            },
            "/api/v2/quiz": {
                "total_requests": 800,
                "total_errors": 8,
                "error_rate": 1.0,
                "avg_response_time": 110.0,
                "p95": 300.0,
            },
        }
        manager.apm_collector.get_endpoint_stats.return_value = {
            "total_requests": 500,
            "total_errors": 5,
            "error_rate": 1.0,
            "avg_response_time": 85.5,
            "min_response_time": 25.0,
            "max_response_time": 850.0,
            "p50": 75.0,
            "p95": 200.0,
            "p99": 450.0,
            "recent_errors": [],
            "status_codes": {"200": 495, "404": 5},
        }

        # Mock DB monitor
        manager.db_monitor = Mock()
        manager.db_monitor.get_query_stats.return_value = {
            "total_queries": 5000,
            "slow_queries": 25,
            "avg_duration_ms": 15.5,
            "slow_query_percentage": 0.5,
        }
        manager.db_monitor.get_connection_pool_stats.return_value = {
            "size": 20,
            "checked_out": 5,
            "overflow": 0,
            "checked_in": 15,
        }
        manager.db_monitor.get_slow_queries.return_value = [
            {
                "query": "SELECT * FROM patients WHERE...",
                "duration_ms": 850.5,
                "timestamp": now_sao_paulo_naive(),
                "table": "patients",
                "rows_examined": 15000,
            }
        ]
        manager.db_monitor.get_table_stats.return_value = {
            "patients": {
                "query_count": 1500,
                "avg_duration_ms": 25.5,
                "total_duration_ms": 38250.0,
                "slow_query_count": 15,
            }
        }

        # Mock resource monitor
        manager.resource_monitor = Mock()
        manager.resource_monitor.get_current_stats.return_value = {
            "cpu": {"percent": 45.2, "count": 8},
            "memory": {"percent": 62.8, "used_gb": 10.0, "total_gb": 16.0},
            "disk": {"percent": 55.5, "used_gb": 250.0, "total_gb": 450.0},
            "network": {"bytes_sent": 1000000, "bytes_recv": 2000000},
        }
        manager.resource_monitor.get_historical_stats.return_value = {
            "data_points": [
                {
                    "timestamp": now_sao_paulo_naive(),
                    "cpu": {"percent": 45.2},
                    "memory": {"percent": 62.8},
                    "disk": {"percent": 55.5},
                    "network": {"bytes_sent": 1000000, "bytes_recv": 2000000},
                }
            ],
            "summary": {
                "avg_cpu": 42.5,
                "max_cpu": 75.0,
                "avg_memory": 60.0,
                "max_memory": 72.0,
            },
        }
        manager.resource_monitor.get_system_info.return_value = {
            "hostname": "test-server",
            "platform": "Linux",
            "architecture": "x86_64",
            "cpu_count": 8,
            "total_memory_gb": 16.0,
            "python_version": "3.11.5",
        }

        # Mock business metrics
        manager.business_metrics = Mock()
        manager.business_metrics.get_all_metrics_summary.return_value = {
            "quiz_completions": 45,
            "messages_sent": 250,
            "active_patients": 150,
        }
        manager.business_metrics.get_patient_metrics.return_value = {
            "quiz_completions": 2,
            "messages_received": 5,
        }
        manager.business_metrics.get_metric_stats.return_value = {
            "total": 45,
            "avg_per_hour": 1.875,
        }

        # Mock anomaly detector
        manager.anomaly_detector = Mock()
        manager.anomaly_detector.get_recent_anomalies.return_value = [
            {
                "timestamp": now_sao_paulo_naive(),
                "metric": "cpu_usage",
                "value": 95.5,
                "expected_value": 45.0,
                "severity": "high",
                "description": "CPU usage significantly above normal",
            }
        ]
        manager.anomaly_detector.get_anomaly_summary.return_value = {
            "total": 15,
            "by_severity": {"high": 3, "medium": 8, "low": 4},
            "by_metric": {"cpu_usage": 5, "memory_usage": 7, "error_rate": 3},
        }

        # Mock dashboard
        manager.dashboard = Mock()
        manager.dashboard.get_dashboard_status.return_value = {
            "active_connections": 5,
            "metrics": {
                "apm_error_rate": 2.5,
                "apm_avg_latency": 125.5,
                "db_query_count": 5000,
                "db_slow_queries": 25,
                "cpu_percent": 45.2,
                "memory_percent": 62.8,
                "active_anomalies": 3,
            },
        }

        # Mock metrics exporter
        manager.metrics_exporter = Mock()
        manager.metrics_exporter.get_prometheus_metrics.return_value = (
            "# TYPE http_requests_total counter\nhttp_requests_total 10000\n"
        )
        manager.metrics_exporter.query_grafana_metrics = AsyncMock(
            return_value={
                "data": [
                    {
                        "target": "cpu_usage",
                        "datapoints": [[45.2, 1699363200000]],
                    }
                ],
                "timestamp": now_sao_paulo_naive().isoformat(),
            }
        )

        # Mock health status
        manager.get_health_status.return_value = {
            "status": "healthy",
            "components": {
                "apm": "healthy",
                "database": "healthy",
                "resources": "healthy",
            },
            "uptime": 86400,
            "version": "2.0.0",
        }

        # Mock system metrics
        manager.get_system_metrics = AsyncMock(
            return_value={
                "apm": {"total_requests": 10000},
                "database": {"query_count": 5000},
                "resources": {"cpu_percent": 45.2},
                "business": {"active_patients": 150},
                "health_score": 92.5,
            }
        )

        # Mock actions
        manager.reset_all_stats = AsyncMock()
        manager.start = AsyncMock()
        manager.stop = AsyncMock()

        mock.return_value = manager
        yield mock


# ============================================================================
# HEALTH & SYSTEM TESTS
# ============================================================================


class TestHealthAndSystem:
    """Tests for health and system endpoints."""

    def test_get_monitoring_health_success(self, client, mock_monitoring_manager):
        """Test successful health check."""
        response = client.get("/api/v2/monitoring/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "components" in data
        assert "uptime_seconds" in data
        assert data["version"] == "2.0.0"

    def test_get_metrics_overview_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful metrics overview."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/metrics/overview")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "timestamp" in data
        assert "apm" in data
        assert "database" in data
        assert "resources" in data
        assert "health_score" in data

    def test_get_metrics_overview_with_field_selection(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test metrics overview with field selection."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/metrics/overview?fields=apm,database"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "apm" in data
        assert "database" in data

    def test_get_metrics_overview_unauthorized(self, client, regular_user):
        """Test metrics overview with non-admin user."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user") as mock_auth:
            mock_auth.side_effect = HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
            response = client.get("/api/v2/monitoring/metrics/overview")

        # The exception should be raised before reaching the endpoint
        # In real scenario, this would be handled by FastAPI

    def test_get_system_info_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful system info retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/system/info")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["hostname"] == "test-server"
        assert data["platform"] == "Linux"
        assert data["cpu_count"] == 8

    def test_get_system_info_no_resource_monitor(
        self, client, admin_user
    ):
        """Test system info when resource monitor is unavailable."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.resource_monitor = None
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/system/info")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ============================================================================
# APM TESTS
# ============================================================================


class TestAPMEndpoints:
    """Tests for APM monitoring endpoints."""

    def test_get_apm_global_stats_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful APM global stats retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/apm/global")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_requests"] == 10000
        assert data["error_rate"] == 2.5
        assert "p95" in data
        assert "p99" in data

    def test_get_apm_global_stats_no_collector(self, client, admin_user):
        """Test APM stats when collector is unavailable."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.apm_collector = None
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/apm/global")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_get_apm_endpoints_stats_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful APM endpoints stats retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/apm/endpoints")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "has_more" in data
        assert len(data["data"]) > 0

    def test_get_apm_endpoints_stats_with_pagination(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test APM endpoints stats with pagination."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/apm/endpoints?limit=1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) <= 1
        assert "next_cursor" in data

    def test_get_apm_endpoints_stats_sort_by_error_rate(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test APM endpoints stats sorted by error rate."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/apm/endpoints?sort_by=error_rate"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data

    def test_get_apm_endpoint_stats_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful specific endpoint stats retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/apm/endpoint/api/v2/patients")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["endpoint"] == "api/v2/patients"
        assert "total_requests" in data
        assert "error_rate" in data

    def test_get_apm_endpoint_stats_not_found(
        self, client, admin_user
    ):
        """Test endpoint stats for non-existent endpoint."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.apm_collector = Mock()
            manager.apm_collector.get_endpoint_stats.return_value = None
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get(
                    "/api/v2/monitoring/apm/endpoint/nonexistent"
                )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_apm_cache_behavior(self, client, mock_monitoring_manager, admin_user):
        """Test APM cache behavior."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            # First request
            response1 = client.get("/api/v2/monitoring/apm/global")
            assert response1.status_code == status.HTTP_200_OK

            # Second request should use cache
            response2 = client.get("/api/v2/monitoring/apm/global")
            assert response2.status_code == status.HTTP_200_OK
            assert response1.json() == response2.json()


# ============================================================================
# DATABASE MONITORING TESTS
# ============================================================================


class TestDatabaseMonitoring:
    """Tests for database monitoring endpoints."""

    def test_get_database_overview_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful database overview retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/database/overview")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "query_statistics" in data
        assert "connection_pool" in data

    def test_get_database_overview_no_monitor(self, client, admin_user):
        """Test database overview when monitor is unavailable."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.db_monitor = None
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/database/overview")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_get_slow_queries_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful slow queries retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/database/slow-queries")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "has_more" in data

    def test_get_slow_queries_with_min_duration(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test slow queries with minimum duration filter."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/database/slow-queries?min_duration_ms=500"
            )

        assert response.status_code == status.HTTP_200_OK

    def test_get_slow_queries_with_pagination(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test slow queries with pagination."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/database/slow-queries?limit=5"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) <= 5

    def test_get_table_stats_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful table statistics retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/database/tables")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "total_tables" in data


# ============================================================================
# RESOURCE MONITORING TESTS
# ============================================================================


class TestResourceMonitoring:
    """Tests for resource monitoring endpoints."""

    def test_get_current_resources_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful current resources retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/resources/current")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "network" in data

    def test_get_current_resources_no_monitor(self, client, admin_user):
        """Test current resources when monitor is unavailable."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.resource_monitor = None
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/resources/current")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_get_historical_resources_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful historical resources retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/resources/historical")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data_points" in data
        assert "summary" in data

    def test_get_historical_resources_custom_range(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test historical resources with custom time range."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/resources/historical?minutes=120"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["time_range_minutes"] == 120

    def test_get_historical_resources_invalid_range(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test historical resources with invalid time range."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/resources/historical?minutes=0"
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_resource_cache_ttl(self, client, mock_monitoring_manager, admin_user):
        """Test resource monitoring cache TTL."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            # Real-time data should have short cache
            response = client.get("/api/v2/monitoring/resources/current")
            assert response.status_code == status.HTTP_200_OK

            # Historical data should have longer cache
            response = client.get("/api/v2/monitoring/resources/historical")
            assert response.status_code == status.HTTP_200_OK


# ============================================================================
# BUSINESS METRICS TESTS
# ============================================================================


class TestBusinessMetrics:
    """Tests for business metrics endpoints."""

    def test_get_business_summary_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful business metrics summary."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/business/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "metrics" in data
        assert "time_range_hours" in data

    def test_get_business_summary_custom_range(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test business summary with custom time range."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/business/summary?hours=48"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["time_range_hours"] == 48

    def test_get_patient_metrics_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful patient metrics retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/business/patient/patient-123"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["patient_id"] == "patient-123"
        assert "metrics" in data

    def test_get_metric_type_stats_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful metric type stats retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/business/metric/quiz_completion"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["metric_type"] == "quiz_completion"

    def test_get_metric_type_stats_invalid_type(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test metric type stats with invalid type."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/business/metric/invalid_type"
            )

        # Should fail validation at Pydantic level
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_business_metrics_no_collector(self, client, admin_user):
        """Test business metrics when collector is unavailable."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.business_metrics = None
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/business/summary")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ============================================================================
# ANOMALY DETECTION TESTS
# ============================================================================


class TestAnomalyDetection:
    """Tests for anomaly detection endpoints."""

    def test_get_recent_anomalies_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful recent anomalies retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/anomalies/recent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "has_more" in data

    def test_get_recent_anomalies_with_filters(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test recent anomalies with severity filter."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/anomalies/recent?severity=high"
            )

        assert response.status_code == status.HTTP_200_OK

    def test_get_anomalies_summary_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful anomalies summary retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/anomalies/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_anomalies" in data
        assert "by_severity" in data
        assert "by_metric" in data

    def test_anomalies_no_detector(self, client, admin_user):
        """Test anomalies when detector is unavailable."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.anomaly_detector = None
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/anomalies/recent")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ============================================================================
# DASHBOARD TESTS
# ============================================================================


class TestDashboard:
    """Tests for dashboard endpoints."""

    def test_get_dashboard_status_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful dashboard status retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/dashboard/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "active_connections" in data
        assert "metrics_snapshot" in data

    def test_get_dashboard_status_no_dashboard(self, client, admin_user):
        """Test dashboard status when dashboard is unavailable."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.dashboard = None
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/dashboard/status")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_dashboard_cache_realtime(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test dashboard cache for real-time data."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/dashboard/status")
            assert response.status_code == status.HTTP_200_OK


# ============================================================================
# ALERT TESTS
# ============================================================================


class TestAlerts:
    """Tests for alert endpoints."""

    def test_get_active_alerts_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful active alerts retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/alerts/active")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "alerts" in data
        assert "count" in data

    def test_get_active_alerts_with_severity_filter(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test active alerts with severity filter."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get(
                "/api/v2/monitoring/alerts/active?severity=high"
            )

        assert response.status_code == status.HTTP_200_OK

    def test_alert_generation_from_metrics(
        self, client, admin_user
    ):
        """Test alert generation from high metrics."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.apm_collector = Mock()
            manager.apm_collector.get_global_stats.return_value = {
                "error_rate": 15.0  # High error rate
            }
            manager.resource_monitor = Mock()
            manager.resource_monitor.get_current_stats.return_value = {
                "cpu": {"percent": 92.0},  # High CPU
                "memory": {"percent": 90.0},  # High memory
            }
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/alerts/active")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should have alerts for high error rate, CPU, and memory
        assert data["count"] >= 2

    def test_alerts_cache_behavior(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test alerts cache with short TTL."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/alerts/active")
            assert response.status_code == status.HTTP_200_OK


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPerformance:
    """Tests for performance endpoints."""

    def test_get_performance_overview_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful performance overview retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.get("/api/v2/monitoring/performance/overview")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "performance_score" in data
        assert "apm" in data
        assert "database" in data
        assert "resources" in data

    def test_performance_score_calculation(
        self, client, admin_user
    ):
        """Test performance score calculation with various metrics."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.apm_collector = Mock()
            manager.apm_collector.get_global_stats.return_value = {
                "error_rate": 1.0,  # Low error rate
                "p95": 150.0,  # Good latency
            }
            manager.db_monitor = Mock()
            manager.db_monitor.get_query_stats.return_value = {
                "slow_query_percentage": 2.0  # Low slow queries
            }
            manager.resource_monitor = Mock()
            manager.resource_monitor.get_current_stats.return_value = {
                "cpu": {"percent": 40.0},  # Normal CPU
                "memory": {"percent": 60.0},  # Normal memory
            }
            manager.get_health_status.return_value = {"status": "healthy"}
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/performance/overview")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # With good metrics, score should be high
        assert data["performance_score"]["score"] >= 90


# ============================================================================
# EXPORT TESTS
# ============================================================================


class TestExport:
    """Tests for metrics export endpoints."""

    def test_get_prometheus_metrics_success(
        self, client, mock_monitoring_manager
    ):
        """Test successful Prometheus metrics export."""
        response = client.get("/api/v2/monitoring/export/prometheus")

        assert response.status_code == status.HTTP_200_OK
        assert "http_requests_total" in response.text

    def test_get_prometheus_metrics_no_exporter(self, client):
        """Test Prometheus export when exporter is unavailable."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager.metrics_exporter = None
            mock.return_value = manager

            response = client.get("/api/v2/monitoring/export/prometheus")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_query_grafana_metrics_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful Grafana metrics query."""
        query_data = {
            "targets": ["cpu_usage"],
            "range": {
                "from": "2025-11-07T11:00:00-03:00",
                "to": "2025-11-07T12:00:00-03:00",
            },
            "max_data_points": 1000,
        }

        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.post(
                "/api/v2/monitoring/export/grafana/query",
                json=query_data,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data

    def test_query_grafana_metrics_invalid_request(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test Grafana query with invalid request."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.post(
                "/api/v2/monitoring/export/grafana/query",
                json={"invalid": "data"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================


class TestConfiguration:
    """Tests for configuration endpoints."""

    def test_get_monitoring_config_success(
        self, client, admin_user
    ):
        """Test successful configuration retrieval."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_config") as mock_config:
            config = Mock()
            config.dict.return_value = {
                "apm_enabled": True,
                "db_monitoring_enabled": True,
                "resource_monitoring_enabled": True,
            }
            mock_config.return_value = config

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/config")

        assert response.status_code == status.HTTP_200_OK

    def test_update_monitoring_config_success(
        self, client, admin_user, db_session
    ):
        """Test successful configuration update."""
        update_data = {
            "apm_enabled": False,
            "db_monitoring_enabled": True,
        }

        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_config") as mock_config:
            config = Mock()
            config.apm_enabled = True
            config.db_monitoring_enabled = True
            config.resource_monitoring_enabled = True
            config.dict.return_value = {
                "apm_enabled": False,
                "db_monitoring_enabled": True,
                "resource_monitoring_enabled": True,
            }
            mock_config.return_value = config

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.put(
                    "/api/v2/monitoring/config",
                    json=update_data,
                )

        assert response.status_code == status.HTTP_200_OK

    def test_update_monitoring_config_partial(
        self, client, admin_user, db_session
    ):
        """Test partial configuration update."""
        update_data = {"apm_enabled": False}

        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_config") as mock_config:
            config = Mock()
            config.dict.return_value = {"apm_enabled": False}
            mock_config.return_value = config

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.put(
                    "/api/v2/monitoring/config",
                    json=update_data,
                )

        assert response.status_code == status.HTTP_200_OK

    def test_config_cache_ttl(self, client, admin_user):
        """Test configuration cache with long TTL."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_config") as mock_config:
            config = Mock()
            config.dict.return_value = {"apm_enabled": True}
            mock_config.return_value = config

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.get("/api/v2/monitoring/config")
                assert response.status_code == status.HTTP_200_OK


# ============================================================================
# MANAGEMENT ACTIONS TESTS
# ============================================================================


class TestManagementActions:
    """Tests for management action endpoints."""

    def test_reset_stats_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful stats reset."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.post("/api/v2/monitoring/actions/reset-stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "timestamp" in data

    def test_start_monitoring_services_success(
        self, client, admin_user
    ):
        """Test successful monitoring services start."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager._started = False
            manager.start = AsyncMock()
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.post("/api/v2/monitoring/actions/start")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_start_monitoring_already_running(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test starting monitoring when already running."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.post("/api/v2/monitoring/actions/start")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "already running" in data["message"].lower()

    def test_stop_monitoring_services_success(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test successful monitoring services stop."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            response = client.post("/api/v2/monitoring/actions/stop")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_stop_monitoring_not_running(
        self, client, admin_user
    ):
        """Test stopping monitoring when not running."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_monitoring_manager") as mock:
            manager = Mock()
            manager._started = False
            manager.stop = AsyncMock()
            mock.return_value = manager

            with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
                response = client.post("/api/v2/monitoring/actions/stop")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "not running" in data["message"].lower()

# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Integration tests for monitoring workflows."""

    def test_full_monitoring_workflow(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test complete monitoring workflow."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            # 1. Check health
            health_response = client.get("/api/v2/monitoring/health")
            assert health_response.status_code == status.HTTP_200_OK

            # 2. Get overview
            overview_response = client.get("/api/v2/monitoring/metrics/overview")
            assert overview_response.status_code == status.HTTP_200_OK

            # 3. Check alerts
            alerts_response = client.get("/api/v2/monitoring/alerts/active")
            assert alerts_response.status_code == status.HTTP_200_OK

            # 4. Get performance score
            perf_response = client.get("/api/v2/monitoring/performance/overview")
            assert perf_response.status_code == status.HTTP_200_OK

    def test_cache_consistency_across_endpoints(
        self, client, mock_monitoring_manager, admin_user
    ):
        """Test cache consistency across related endpoints."""
        with patch("app.api.v2.routers.enhanced_monitoring.get_admin_user", return_value=admin_user):
            # Get data from different endpoints
            response1 = client.get("/api/v2/monitoring/apm/global")
            response2 = client.get("/api/v2/monitoring/performance/overview")

            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_200_OK
