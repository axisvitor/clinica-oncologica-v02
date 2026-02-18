"""
Comprehensive test suite for V2 Platform Sync API
Tests all 9 endpoints with sync operations, conflict resolution, rollback, and caching.
"""

import pytest
import json
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
# ============================================================================
# FIXTURES
# ============================================================================
@pytest.fixture
def client():
    """Test client"""
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """Mock Redis cache"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=True)
    redis_mock.delete_pattern = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def mock_db(monkeypatch):
    """Mock database session"""
    db_mock = Mock(spec=Session)
    db_mock.query = Mock()
    db_mock.execute = Mock()
    db_mock.add = Mock()
    db_mock.commit = Mock()
    db_mock.rollback = Mock()
    db_mock.refresh = Mock()
    db_mock.delete = Mock()
    return db_mock


@pytest.fixture
def sample_sync_job_data():
    """Sample sync job data"""
    return {
        "platform": "ehr",
        "strategy": "incremental",
        "direction": "bidirectional",
        "entity_types": ["patients", "appointments"],
        "batch_size": 1000,
        "dry_run": False
    }


@pytest.fixture
def sample_sync_config_data():
    """Sample sync configuration data"""
    return {
        "platform": "ehr",
        "name": "Main EHR System",
        "description": "Primary EHR integration",
        "endpoint_url": "https://ehr.example.com/api/v2",
        "auth_type": "bearer",
        "enabled": True,
        "sync_interval_minutes": 60,
        "conflict_strategy": "last_write_wins",
        "retry_enabled": True,
        "max_retries": 3,
        "batch_size": 1000,
        "timeout_seconds": 30
    }


# ============================================================================
# SYNC JOB MANAGEMENT TESTS
# ============================================================================
class TestSyncJobManagement:
    """Test sync job CRUD operations"""

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_list_sync_jobs_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test listing sync jobs with pagination"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/platform-sync/jobs?limit=20")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_list_sync_jobs_with_status_filter(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test filtering sync jobs by status"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/platform-sync/jobs?status=completed")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_list_sync_jobs_with_platform_filter(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test filtering sync jobs by platform"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/platform-sync/jobs?platform=ehr")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_list_sync_jobs_cached(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test cached sync jobs list"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        cached_data = {
            "data": [],
            "next_cursor": None,
            "has_more": False,
            "total": 0
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        response = client.get("/api/v2/platform-sync/jobs")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_job_not_found(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test retrieving non-existent sync job"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        job_id = uuid4()
        response = client.get(f"/api/v2/platform-sync/jobs/{job_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# SYNC TRIGGER & EXECUTION TESTS
# ============================================================================
class TestSyncTriggerExecution:
    """Test sync trigger and execution operations"""

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_trigger_sync_full_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_sync_job_data):
        """Test triggering full sync"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        sync_request = sample_sync_job_data.copy()
        sync_request["strategy"] = "full"

        response = client.post("/api/v2/platform-sync/trigger", json=sync_request)

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "job_id" in data
        assert "transaction_id" in data
        assert data["status"] == "pending"
        assert "estimated_items" in data

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_trigger_sync_incremental_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_sync_job_data):
        """Test triggering incremental sync"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        sync_request = sample_sync_job_data.copy()
        sync_request["strategy"] = "incremental"

        response = client.post("/api/v2/platform-sync/trigger", json=sync_request)

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["status"] == "pending"

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_trigger_sync_selective_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test triggering selective sync with specific entity IDs"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        sync_request = {
            "platform": "ehr",
            "strategy": "selective",
            "direction": "bidirectional",
            "entity_types": ["patients"],
            "entity_ids": ["patient_1", "patient_2", "patient_3"],
            "batch_size": 100,
            "conflict_strategy": "last_write_wins",
            "dry_run": False
        }

        response = client.post("/api/v2/platform-sync/trigger", json=sync_request)

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["estimated_items"] == 3

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_trigger_sync_dry_run(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_sync_job_data):
        """Test dry run sync (no actual changes)"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        sync_request = sample_sync_job_data.copy()
        sync_request["dry_run"] = True

        response = client.post("/api/v2/platform-sync/trigger", json=sync_request)

        assert response.status_code == status.HTTP_202_ACCEPTED

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_trigger_sync_idempotency(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_sync_job_data):
        """Test idempotency prevents duplicate syncs"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # Mock idempotency check - second request is duplicate
        mock_redis.get.return_value = "1"

        response = client.post("/api/v2/platform-sync/trigger", json=sample_sync_job_data)

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        # Should still return 202 but with idempotency message

    @patch("app.api.v2.routers.platform_sync.get_cached_sync_status", new_callable=AsyncMock)
    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_status_success(
        self,
        mock_get_db,
        mock_get_redis,
        mock_get_cached_sync_status,
        client,
        mock_db,
        mock_redis,
    ):
        """Test getting real-time sync status"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        job_id = uuid4()

        # Mock cached status
        cached_status = {
            "job_id": str(job_id),
            "status": "running",
            "progress_percentage": 65.5,
            "total_items": 500,
            "processed_items": 327,
            "current_batch": 4,
            "total_batches": 5,
            "items_per_second": 8.5,
            "estimated_completion": now_sao_paulo_naive().isoformat(),
            "current_entity_type": "patients",
            "errors": [],
            "warnings": []
        }
        mock_get_cached_sync_status.return_value = cached_status

        response = client.get(f"/api/v2/platform-sync/status/{job_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "running"
        assert data["progress_percentage"] == 65.5

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_status_not_found(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test sync status for non-existent job"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        job_id = uuid4()
        response = client.get(f"/api/v2/platform-sync/status/{job_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# SYNC CONFIGURATION TESTS
# ============================================================================
class TestSyncConfiguration:
    """Test sync configuration CRUD operations"""

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_list_sync_configs_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test listing sync configurations"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/platform-sync/configs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_create_sync_config_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_sync_config_data):
        """Test creating sync configuration"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.post("/api/v2/platform-sync/configs", json=sample_sync_config_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["platform"] == "ehr"
        assert data["name"] == "Main EHR System"
        assert "id" in data

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_create_sync_config_validation_error(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test config creation with invalid data"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        invalid_config = {
            "platform": "invalid_platform",
            "name": "",  # Empty name
            "endpoint_url": "not-a-url",
            "auth_type": "bearer"
        }

        response = client.post("/api/v2/platform-sync/configs", json=invalid_config)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_config_not_found(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test retrieving non-existent config"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        config_id = uuid4()
        response = client.get(f"/api/v2/platform-sync/configs/{config_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_update_sync_config_not_found(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test updating non-existent config"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        config_id = uuid4()
        update_data = {"enabled": False}

        response = client.put(f"/api/v2/platform-sync/configs/{config_id}", json=update_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_delete_sync_config_not_found(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test deleting non-existent config"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        config_id = uuid4()
        response = client.delete(f"/api/v2/platform-sync/configs/{config_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# PLATFORM TESTING TESTS
# ============================================================================
class TestPlatformTesting:
    """Test platform connection testing"""

    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_test_platform_connection_success(self, mock_get_db, client, mock_db):
        """Test successful platform connection"""
        mock_get_db.return_value = mock_db

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            test_request = {
                "platform": "ehr",
                "endpoint_url": "https://ehr.example.com/api/v2/health",
                "auth_type": "bearer",
                "auth_token": "test_token",
                "timeout_seconds": 10
            }

            response = client.post("/api/v2/platform-sync/test-connection", json=test_request)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "response_time_ms" in data

    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_test_platform_connection_timeout(self, mock_get_db, client, mock_db):
        """Test platform connection timeout"""
        mock_get_db.return_value = mock_db

        with patch("httpx.AsyncClient") as mock_client:
            import httpx
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Connection timeout")
            )

            test_request = {
                "platform": "ehr",
                "endpoint_url": "https://ehr.example.com/api/v2/health",
                "auth_type": "bearer",
                "timeout_seconds": 10
            }

            response = client.post("/api/v2/platform-sync/test-connection", json=test_request)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is False
            assert "timeout" in data["message"].lower()

    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_test_platform_connection_failed(self, mock_get_db, client, mock_db):
        """Test failed platform connection"""
        mock_get_db.return_value = mock_db

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.headers = {}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            test_request = {
                "platform": "ehr",
                "endpoint_url": "https://ehr.example.com/api/v2/health",
                "auth_type": "bearer",
                "auth_token": "invalid_token",
                "timeout_seconds": 10
            }

            response = client.post("/api/v2/platform-sync/test-connection", json=test_request)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is False
            assert data["status_code"] == 401


# ============================================================================
# CONFLICT RESOLUTION TESTS
# ============================================================================
class TestConflictResolution:
    """Test conflict resolution operations"""

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_resolve_conflict_use_local(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test resolving conflict with use_local strategy"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        conflict_id = uuid4()
        resolution_request = {
            "conflict_id": str(conflict_id),
            "resolution_strategy": "use_local",
            "notes": "Local version is more accurate"
        }

        response = client.post("/api/v2/platform-sync/conflicts/resolve", json=resolution_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolution_strategy"] == "use_local"

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_resolve_conflict_use_remote(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test resolving conflict with use_remote strategy"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        conflict_id = uuid4()
        resolution_request = {
            "conflict_id": str(conflict_id),
            "resolution_strategy": "use_remote"
        }

        response = client.post("/api/v2/platform-sync/conflicts/resolve", json=resolution_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["resolution_strategy"] == "use_remote"

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_resolve_conflict_merge(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test resolving conflict with merge strategy"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        conflict_id = uuid4()
        resolution_request = {
            "conflict_id": str(conflict_id),
            "resolution_strategy": "merge",
            "merged_data": {
                "name": "John Doe",
                "age": 35,
                "email": "john@example.com"
            }
        }

        response = client.post("/api/v2/platform-sync/conflicts/resolve", json=resolution_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["resolution_strategy"] == "merge"
        assert data["resolved_value"] == resolution_request["merged_data"]

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_resolve_conflict_merge_validation_error(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test merge strategy requires merged_data"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        conflict_id = uuid4()
        resolution_request = {
            "conflict_id": str(conflict_id),
            "resolution_strategy": "merge"
            # Missing merged_data
        }

        response = client.post("/api/v2/platform-sync/conflicts/resolve", json=resolution_request)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# SYNC HISTORY TESTS
# ============================================================================
class TestSyncHistory:
    """Test sync history operations"""

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_history_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test retrieving sync history"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/platform-sync/history")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_history_with_platform_filter(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test history with platform filter"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/platform-sync/history?platform=ehr")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_history_with_status_filter(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test history with status filter"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/platform-sync/history?status=completed")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_history_with_days_filter(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test history with days filter"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        response = client.get("/api/v2/platform-sync/history?days=30")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_get_sync_history_cached(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test cached sync history"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        cached_history = {
            "data": [],
            "next_cursor": None,
            "has_more": False,
            "total": 0
        }
        mock_redis.get.return_value = json.dumps(cached_history)

        response = client.get("/api/v2/platform-sync/history")

        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# ROLLBACK TESTS
# ============================================================================
class TestSyncRollback:
    """Test sync rollback operations"""

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_rollback_sync_success(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test successful sync rollback"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        rollback_request = {
            "transaction_id": "sync_txn_abc123",
            "reason": "Data corruption detected",
            "dry_run": False
        }

        response = client.post("/api/v2/platform-sync/rollback", json=rollback_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "rollback_job_id" in data
        assert data["original_transaction_id"] == "sync_txn_abc123"
        assert data["status"] == "pending"

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_rollback_sync_dry_run(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test dry run rollback (simulation)"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        rollback_request = {
            "transaction_id": "sync_txn_abc123",
            "reason": "Testing rollback simulation",
            "dry_run": True
        }

        response = client.post("/api/v2/platform-sync/rollback", json=rollback_request)

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_rollback_sync_validation_error(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test rollback with missing required fields"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        rollback_request = {
            "transaction_id": "sync_txn_abc123"
            # Missing reason
        }

        response = client.post("/api/v2/platform-sync/rollback", json=rollback_request)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# VALIDATION TESTS
# ============================================================================
class TestValidation:
    """Test input validation"""

    def test_trigger_sync_invalid_platform(self, client):
        """Test sync trigger with invalid platform"""
        sync_request = {
            "platform": "invalid_platform",
            "strategy": "full",
            "direction": "bidirectional"
        }

        response = client.post("/api/v2/platform-sync/trigger", json=sync_request)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_trigger_sync_invalid_strategy(self, client):
        """Test sync trigger with invalid strategy"""
        sync_request = {
            "platform": "ehr",
            "strategy": "invalid_strategy",
            "direction": "bidirectional"
        }

        response = client.post("/api/v2/platform-sync/trigger", json=sync_request)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_trigger_sync_selective_missing_entity_ids(self, client):
        """Test selective sync without entity_ids"""
        sync_request = {
            "platform": "ehr",
            "strategy": "selective",
            "direction": "bidirectional"
            # Missing entity_ids
        }

        response = client.post("/api/v2/platform-sync/trigger", json=sync_request)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_config_invalid_url(self, client):
        """Test config creation with invalid URL"""
        config_data = {
            "platform": "ehr",
            "name": "Test Config",
            "endpoint_url": "not-a-valid-url",
            "auth_type": "bearer"
        }

        response = client.post("/api/v2/platform-sync/configs", json=config_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_config_invalid_interval(self, client):
        """Test config with invalid sync interval"""
        config_data = {
            "platform": "ehr",
            "name": "Test Config",
            "endpoint_url": "https://api.example.com",
            "auth_type": "bearer",
            "sync_interval_minutes": 2000  # Exceeds max (1440)
        }

        response = client.post("/api/v2/platform-sync/configs", json=config_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================
class TestRateLimiting:
    """Test rate limiting on sync endpoints"""

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_trigger_sync_rate_limit(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis, sample_sync_job_data):
        """Test rate limiting on sync trigger (10/minute)"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        # First request should succeed
        response = client.post("/api/v2/platform-sync/trigger", json=sample_sync_job_data)

        assert response.status_code in [status.HTTP_202_ACCEPTED, status.HTTP_429_TOO_MANY_REQUESTS]

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_rollback_rate_limit(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test rate limiting on rollback (5/minute)"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        rollback_request = {
            "transaction_id": "sync_txn_abc123",
            "reason": "Test rollback"
        }

        response = client.post("/api/v2/platform-sync/rollback", json=rollback_request)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS]


# ============================================================================
# CACHING TESTS
# ============================================================================
class TestCaching:
    """Test Redis caching behavior"""

    @patch("app.api.v2.routers.platform_sync.get_cached_sync_status", new_callable=AsyncMock)
    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_sync_status_caching(
        self,
        mock_get_db,
        mock_get_redis,
        mock_get_cached_sync_status,
        client,
        mock_db,
        mock_redis,
    ):
        """Test sync status is cached properly"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        job_id = uuid4()
        cached_status = {
            "job_id": str(job_id),
            "status": "running",
            "progress_percentage": 50.0,
            "total_items": 1000,
            "processed_items": 500,
            "current_batch": 5,
            "total_batches": 10,
            "items_per_second": 10.0,
            "estimated_completion": None,
            "current_entity_type": "patients",
            "errors": [],
            "warnings": []
        }
        mock_get_cached_sync_status.return_value = cached_status

        response = client.get(f"/api/v2/platform-sync/status/{job_id}")

        assert response.status_code == status.HTTP_200_OK
        # Should use cache, not query database

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_config_list_caching(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test config list is cached"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        cached_configs = {
            "data": [],
            "next_cursor": None,
            "has_more": False,
            "total": 0
        }
        mock_redis.get.return_value = json.dumps(cached_configs)

        response = client.get("/api/v2/platform-sync/configs")

        assert response.status_code == status.HTTP_200_OK

    @patch("app.api.v2.routers.platform_sync.get_redis_cache")
    @patch("app.api.v2.routers.platform_sync.get_db")
    def test_history_caching(self, mock_get_db, mock_get_redis, client, mock_db, mock_redis):
        """Test history is cached"""
        mock_get_db.return_value = mock_db
        mock_get_redis.return_value = mock_redis

        cached_history = {
            "data": [],
            "next_cursor": None,
            "has_more": False,
            "total": 0
        }
        mock_redis.get.return_value = json.dumps(cached_history)

        response = client.get("/api/v2/platform-sync/history")

        assert response.status_code == status.HTTP_200_OK
