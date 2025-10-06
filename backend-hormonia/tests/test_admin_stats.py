"""
Tests for admin system statistics endpoint.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.services.admin_stats_service import AdminStatsService
from app.models.admin import SystemStatsResponse, SystemMetrics, UserMetrics, DatabaseMetrics


class TestAdminStatsService:
    """Test AdminStatsService functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        """Create AdminStatsService instance."""
        return AdminStatsService(mock_db)

    @patch('app.services.admin_stats_service.psutil')
    def test_get_system_metrics(self, mock_psutil, service):
        """Test system metrics collection."""
        # Mock psutil responses
        mock_psutil.cpu_percent.return_value = 25.5
        mock_psutil.virtual_memory.return_value = Mock(percent=60.2)
        mock_psutil.disk_usage.return_value = Mock(percent=75.8)
        mock_psutil.boot_time.return_value = datetime.now().timestamp() - 86400

        metrics = service.get_system_metrics()

        assert metrics['cpu_percent'] == 25.5
        assert metrics['memory_percent'] == 60.2
        assert metrics['disk_percent'] == 75.8
        assert metrics['uptime_seconds'] > 0

    @patch('app.services.admin_stats_service.psutil')
    def test_get_system_metrics_failure(self, mock_psutil, service):
        """Test system metrics fallback on failure."""
        mock_psutil.cpu_percent.side_effect = Exception("psutil error")

        metrics = service.get_system_metrics()

        # Should return fallback metrics
        assert metrics['cpu_percent'] == 0.0
        assert metrics['memory_percent'] == 0.0
        assert metrics['disk_percent'] == 0.0
        assert metrics['uptime_seconds'] == 0

    def test_get_user_metrics(self, service, mock_db):
        """Test user metrics collection."""
        from app.models.user import UserRole

        # Mock user counts
        mock_db.query.return_value.count.return_value = 100
        mock_db.query.return_value.filter.return_value.count.return_value = 25

        # Mock role distribution
        mock_db.query.return_value.group_by.return_value.all.return_value = [
            (UserRole.ADMIN, 10),
            (UserRole.DOCTOR, 90)
        ]

        metrics = service.get_user_metrics()

        assert metrics['total'] == 100
        assert metrics['active_now'] == 25
        assert metrics['by_role']['admin'] == 10
        assert metrics['by_role']['doctor'] == 90

    def test_get_database_metrics(self, service, mock_db):
        """Test database metrics collection."""
        # Mock counts
        mock_db.query.return_value.count.side_effect = [125, 1000]  # users, patients

        # Mock connection count
        mock_result = Mock()
        mock_result.scalar.return_value = 15
        mock_db.execute.return_value = mock_result

        metrics = service.get_database_metrics()

        assert metrics['total_users'] == 125
        assert metrics['total_patients'] == 1000
        assert metrics['total_records'] == 1125
        assert metrics['connections'] == 15

    def test_get_database_metrics_connection_fallback(self, service, mock_db):
        """Test database metrics with connection query failure."""
        # Mock counts
        mock_db.query.return_value.count.side_effect = [125, 1000]

        # Mock connection query failure
        mock_db.execute.side_effect = Exception("pg_stat_activity error")

        metrics = service.get_database_metrics()

        assert metrics['connections'] == 1  # Fallback value

    def test_get_all_stats(self, service, mock_db):
        """Test comprehensive stats collection."""
        with patch.object(service, 'get_system_metrics') as mock_sys, \
             patch.object(service, 'get_user_metrics') as mock_users, \
             patch.object(service, 'get_database_metrics') as mock_db_metrics:

            mock_sys.return_value = {
                'cpu_percent': 10.0,
                'memory_percent': 50.0,
                'disk_percent': 60.0,
                'uptime_seconds': 3600
            }
            mock_users.return_value = {
                'total': 100,
                'active_now': 20,
                'by_role': {'admin': 5, 'doctor': 95}
            }
            mock_db_metrics.return_value = {
                'total_records': 1000,
                'total_patients': 800,
                'total_users': 100,
                'connections': 10
            }

            stats = service.get_all_stats()

            assert 'system' in stats
            assert 'users' in stats
            assert 'database' in stats
            assert 'timestamp' in stats
            assert stats['system']['cpu_percent'] == 10.0
            assert stats['users']['total'] == 100
            assert stats['database']['connections'] == 10


class TestSystemStatsModels:
    """Test Pydantic models for system stats."""

    def test_system_metrics_model(self):
        """Test SystemMetrics model validation."""
        metrics = SystemMetrics(
            cpu_percent=25.5,
            memory_percent=60.2,
            disk_percent=75.8,
            uptime_seconds=86400
        )
        assert metrics.cpu_percent == 25.5
        assert metrics.uptime_seconds == 86400

    def test_user_metrics_model(self):
        """Test UserMetrics model validation."""
        metrics = UserMetrics(
            total=125,
            active_now=23,
            by_role={'admin': 5, 'doctor': 120}
        )
        assert metrics.total == 125
        assert metrics.by_role['admin'] == 5

    def test_database_metrics_model(self):
        """Test DatabaseMetrics model validation."""
        metrics = DatabaseMetrics(
            total_records=1250,
            total_patients=1000,
            total_users=125,
            connections=12
        )
        assert metrics.total_records == 1250
        assert metrics.connections == 12

    def test_system_stats_response_model(self):
        """Test complete SystemStatsResponse model."""
        response = SystemStatsResponse(
            system=SystemMetrics(
                cpu_percent=15.2,
                memory_percent=45.8,
                disk_percent=62.3,
                uptime_seconds=86400
            ),
            users=UserMetrics(
                total=125,
                active_now=23,
                by_role={'admin': 5, 'doctor': 120}
            ),
            database=DatabaseMetrics(
                total_records=1250,
                total_patients=1000,
                total_users=125,
                connections=12
            ),
            timestamp="2025-10-06T14:30:00.000Z"
        )
        assert response.system.cpu_percent == 15.2
        assert response.users.total == 125
        assert response.database.connections == 12
        assert "2025-10-06" in response.timestamp


@pytest.mark.asyncio
class TestSystemStatsEndpoint:
    """Test system stats API endpoint."""

    async def test_get_system_stats_success(self, test_client, admin_token):
        """Test successful system stats retrieval."""
        response = test_client.get(
            "/api/v1/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert 'system' in data
        assert 'users' in data
        assert 'database' in data
        assert 'timestamp' in data

        # Validate system metrics
        assert 'cpu_percent' in data['system']
        assert 'memory_percent' in data['system']
        assert 'disk_percent' in data['system']
        assert 'uptime_seconds' in data['system']

        # Validate user metrics
        assert 'total' in data['users']
        assert 'active_now' in data['users']
        assert 'by_role' in data['users']

        # Validate database metrics
        assert 'total_records' in data['database']
        assert 'connections' in data['database']

    async def test_get_system_stats_unauthorized(self, test_client):
        """Test unauthorized access."""
        response = test_client.get("/api/v1/admin/system-stats")
        assert response.status_code == 401

    async def test_get_system_stats_forbidden(self, test_client, doctor_token):
        """Test forbidden access (non-admin user)."""
        response = test_client.get(
            "/api/v1/admin/system-stats",
            headers={"Authorization": f"Bearer {doctor_token}"}
        )
        assert response.status_code == 403

    async def test_get_system_stats_caching(self, test_client, admin_token):
        """Test that stats are cached correctly."""
        # First request
        response1 = test_client.get(
            "/api/v1/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data1 = response1.json()

        # Second request (should be cached)
        response2 = test_client.get(
            "/api/v1/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data2 = response2.json()

        # Timestamps should be the same (cached)
        assert data1['timestamp'] == data2['timestamp']
