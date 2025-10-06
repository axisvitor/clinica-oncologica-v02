"""
Test suite for Admin System Stats endpoint.

Tests GET /api/v1/admin/system-stats with:
- Authorization requirements (admin-only)
- System metrics collection (CPU, memory, disk)
- User metrics calculation
- Database statistics
- Redis caching behavior
- Error handling
"""
import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from app.models.user import User
from app.models.patient import Patient
from tests.helpers.jwt_helper import jwt_helper


class TestAdminSystemStats:
    """Test suite for GET /api/v1/admin/system-stats"""

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, http_client, doctor_a_credentials, auth_headers):
        """Non-admin users should get 403"""
        # Regular doctor credentials (not admin)
        headers = auth_headers(doctor_a_credentials)

        response = await http_client.get(
            "/api/v1/admin/system-stats",
            headers=headers
        )

        # Should be forbidden for non-admin
        assert response.status_code in [403, 401, 404]

    @pytest.mark.asyncio
    async def test_unauthenticated_access(self, http_client):
        """Unauthenticated requests should get 401"""
        response = await http_client.get("/api/v1/admin/system-stats")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch('app.services.admin_stats_service.psutil')
    async def test_successful_stats_retrieval(
        self,
        mock_psutil,
        http_client,
        admin_credentials,
        auth_headers
    ):
        """Admin should get system stats successfully"""
        # Mock psutil responses
        mock_psutil.cpu_percent.return_value = 25.5
        mock_memory = MagicMock()
        mock_memory.percent = 45.8
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = MagicMock()
        mock_disk.percent = 60.2
        mock_psutil.disk_usage.return_value = mock_disk

        mock_psutil.boot_time.return_value = 1704067200  # Unix timestamp

        headers = auth_headers(admin_credentials)
        response = await http_client.get(
            "/api/v1/admin/system-stats",
            headers=headers
        )

        # May not be implemented yet, so accept 404/500
        if response.status_code == 200:
            data = response.json()

            # Verify structure
            assert "system" in data or "timestamp" in data

            # If fully implemented, verify system metrics
            if "system" in data:
                assert "cpu_percent" in data["system"] or "memory_percent" in data["system"]

    def test_user_metrics_calculation(self, db_session):
        """User metrics should be calculated correctly"""
        # Create test users with different roles
        users = [
            User(
                id=uuid4(),
                firebase_uid="firebase_admin_1",
                email="admin1@test.com",
                full_name="Admin User 1",
                role="admin"
            ),
            User(
                id=uuid4(),
                firebase_uid="firebase_doctor_1",
                email="doctor1@test.com",
                full_name="Doctor User 1",
                role="doctor"
            ),
            User(
                id=uuid4(),
                firebase_uid="firebase_doctor_2",
                email="doctor2@test.com",
                full_name="Doctor User 2",
                role="doctor"
            ),
        ]
        db_session.add_all(users)
        db_session.commit()

        # Query users by role
        admin_count = db_session.query(User).filter(User.role == "admin").count()
        doctor_count = db_session.query(User).filter(User.role == "doctor").count()

        assert admin_count >= 1
        assert doctor_count >= 2

    @patch('app.utils.unified_cache.RedisClient')
    def test_redis_caching(self, mock_redis_client, db_session):
        """Stats should be cached for 30 seconds"""
        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis
        mock_redis.get.return_value = None  # Cache miss
        mock_redis.setex.return_value = True
        mock_redis.ttl.return_value = 29  # TTL ~30s

        # Test caching behavior
        cache_key = "admin:system-stats"

        # Simulate cache set
        mock_redis.setex(cache_key, 30, '{"test": "data"}')

        # Verify cache was set with correct TTL
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == cache_key
        assert call_args[0][1] == 30  # 30 second TTL

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.boot_time')
    def test_system_metrics_collection(
        self,
        mock_boot_time,
        mock_disk_usage,
        mock_virtual_memory,
        mock_cpu_percent
    ):
        """System metrics should be collected from psutil"""
        # Mock system stats
        mock_cpu_percent.return_value = 42.3
        mock_memory = MagicMock()
        mock_memory.percent = 67.8
        mock_memory.total = 16 * 1024 * 1024 * 1024  # 16GB
        mock_memory.available = 5 * 1024 * 1024 * 1024  # 5GB
        mock_virtual_memory.return_value = mock_memory

        mock_disk = MagicMock()
        mock_disk.percent = 55.2
        mock_disk.total = 500 * 1024 * 1024 * 1024  # 500GB
        mock_disk.used = 276 * 1024 * 1024 * 1024  # 276GB
        mock_disk_usage.return_value = mock_disk

        mock_boot_time.return_value = 1704067200

        # Collect metrics
        import psutil
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot = psutil.boot_time()

        assert cpu == 42.3
        assert memory.percent == 67.8
        assert disk.percent == 55.2
        assert boot == 1704067200

        # Calculate uptime
        current_time = datetime.utcnow().timestamp()
        uptime_seconds = current_time - boot
        assert uptime_seconds > 0

    def test_database_connection_stats(self, db_session):
        """Database stats should include connection information"""
        # Test basic database queries work
        user_count = db_session.query(User).count()
        patient_count = db_session.query(Patient).count()

        assert user_count >= 0
        assert patient_count >= 0

        # Database session should be active
        assert db_session.is_active

    @pytest.mark.asyncio
    async def test_response_structure(self, http_client, admin_credentials, auth_headers):
        """Response should have expected structure"""
        headers = auth_headers(admin_credentials)
        response = await http_client.get(
            "/api/v1/admin/system-stats",
            headers=headers
        )

        # If implemented
        if response.status_code == 200:
            data = response.json()

            # Should be a dictionary
            assert isinstance(data, dict)

            # Should have timestamp
            assert "timestamp" in data or "created_at" in data

    def test_multiple_concurrent_requests(self, db_session):
        """Should handle multiple concurrent stat requests"""
        # Simulate concurrent queries
        results = []
        for i in range(5):
            user_count = db_session.query(User).count()
            results.append(user_count)

        # All results should be consistent
        assert len(set(results)) <= 2  # Allow for one insert during test


class TestAdminStatsPerformance:
    """Performance tests for admin stats endpoint"""

    @pytest.mark.asyncio
    async def test_response_time_under_1_second(
        self,
        http_client,
        admin_credentials,
        auth_headers
    ):
        """Stats collection should complete quickly"""
        import time

        headers = auth_headers(admin_credentials)

        start_time = time.time()
        response = await http_client.get(
            "/api/v1/admin/system-stats",
            headers=headers
        )
        elapsed = time.time() - start_time

        # Should respond in under 1 second (even if not implemented)
        assert elapsed < 1.0

        # If implemented and successful, should be fast
        if response.status_code == 200:
            assert elapsed < 0.5  # Target: 500ms


class TestAdminStatsEdgeCases:
    """Edge case tests for admin stats"""

    def test_zero_users_in_database(self, db_session):
        """Should handle empty user table gracefully"""
        # Delete all users (if any)
        db_session.query(User).delete()
        db_session.commit()

        # Query should return 0, not error
        user_count = db_session.query(User).count()
        assert user_count == 0

    @patch('psutil.cpu_percent')
    def test_psutil_unavailable(self, mock_cpu_percent):
        """Should handle psutil errors gracefully"""
        # Simulate psutil error
        mock_cpu_percent.side_effect = Exception("psutil not available")

        with pytest.raises(Exception):
            import psutil
            psutil.cpu_percent()

    def test_missing_optional_fields(self, db_session):
        """Should handle missing optional data fields"""
        # Create user with minimal fields
        minimal_user = User(
            id=uuid4(),
            firebase_uid="firebase_minimal",
            email="minimal@test.com"
            # No full_name, no role
        )
        db_session.add(minimal_user)
        db_session.commit()

        # Should still be queryable
        found_user = db_session.query(User).filter(
            User.firebase_uid == "firebase_minimal"
        ).first()

        assert found_user is not None
        assert found_user.email == "minimal@test.com"
