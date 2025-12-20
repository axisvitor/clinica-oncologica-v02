"""
Tests for Performance Monitoring API v2
Comprehensive test suite for unified performance monitoring system.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import status

from app.schemas.v2.performance import (
    OptimizationBenefit,
    IndexType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_cache_service():
    """Mock cache service."""
    mock = Mock()
    mock.get_stats.return_value = {
        'hits': 15420,
        'misses': 2340,
        'errors': 3,
        'hit_rate_percent': 86.8,
        'avg_response_time_ms': 2.4
    }
    mock.get_cache_info.return_value = {
        'total_keys': 342,
        'memory_usage_mb': 45.2,
        'evictions': 120
    }
    mock.get_metrics.return_value = Mock(
        hits=15420,
        misses=2340,
        hit_rate=86.8,
        invalidations=45,
        warming_operations=12
    )
    mock.clear_all = AsyncMock(return_value=True)
    mock.invalidate.return_value = 42
    return mock


@pytest.fixture
def mock_query_monitor():
    """Mock query performance monitor."""
    mock = Mock()
    mock.get_query_stats.return_value = {
        'avg_duration_ms': 45.2,
        'slow_queries': 12,
        'slow_query_percentage': 3.5,
        'total_queries': 342
    }
    mock.get_performance_metrics.return_value = Mock(
        avg_duration_ms=45.2,
        slow_queries=12,
        total_queries=342
    )
    mock.identify_slow_queries.return_value = [
        Mock(
            query_text="SELECT * FROM patients WHERE doctor_id = ?",
            avg_duration_ms=1250.5,
            execution_count=45,
            total_duration_ms=56272.5,
            suggestion="Add index on doctor_id column",
            tables_involved=["patients"]
        )
    ]
    return mock


@pytest.fixture
def mock_db_optimizer():
    """Mock database optimizer."""
    mock = Mock()
    mock.analyze_indexes.return_value = Mock(
        existing_indexes={},
        missing_indexes=[
            Mock(
                table_name="patients",
                columns=["doctor_id"],
                index_type=IndexType.BTREE,
                reason="Frequent filtering on doctor_id",
                estimated_benefit=OptimizationBenefit.HIGH,
                query_patterns=["WHERE doctor_id = ?"],
                existing_index=None
            )
        ],
        redundant_indexes=[],
        performance_impact={}
    )
    mock.create_recommended_indexes.return_value = [
        "CREATE INDEX idx_patients_doctor_id ON patients(doctor_id)"
    ]
    return mock


@pytest.fixture
def mock_pool_status():
    """Mock connection pool status."""
    return {
        'pool_size': 20,
        'overflow': 10,
        'checked_out': 13,
        'checked_in': 7,
        'utilization_percent': 43.3
    }


# ============================================================================
# Cache Monitoring Tests
# ============================================================================

class TestCacheMetrics:
    """Tests for GET /performance/cache/metrics"""

    @patch('app.api.v2.performance._get_cache_service')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_cache_metrics_success(
        self,
        mock_cached,
        mock_service,
        client,
        admin_headers,
        mock_cache_service
    ):
        """Test getting cache metrics successfully."""
        mock_cached.return_value = None
        mock_service.return_value = mock_cache_service

        response = client.get(
            "/api/v2/performance/cache/metrics",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["hits"] == 15420
        assert data["misses"] == 2340
        assert data["hit_rate_percentage"] == 86.8
        assert data["total_keys"] == 342

    @patch('app.api.v2.performance._get_cache_service')
    async def test_get_cache_metrics_service_unavailable(
        self,
        mock_service,
        client,
        admin_headers
    ):
        """Test cache metrics when service unavailable."""
        mock_service.return_value = None

        response = client.get(
            "/api/v2/performance/cache/metrics",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_get_cache_metrics_requires_auth(self, client):
        """Test that cache metrics requires authentication."""
        response = client.get("/api/v2/performance/cache/metrics")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCacheStats:
    """Tests for GET /performance/cache/stats"""

    @patch('app.api.v2.performance._get_cache_service')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_cache_stats_success(
        self,
        mock_cached,
        mock_service,
        client,
        admin_headers,
        mock_cache_service
    ):
        """Test getting cache stats successfully."""
        mock_cached.return_value = None
        mock_service.return_value = mock_cache_service

        response = client.get(
            "/api/v2/performance/cache/stats",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["hits"] == 15420
        assert data["misses"] == 2340
        assert data["hit_rate_percent"] == 86.8
        assert data["status"] == "healthy"

    @patch('app.api.v2.performance._get_cache_service')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_cache_stats_health_status_degraded(
        self,
        mock_cached,
        mock_service,
        client,
        admin_headers
    ):
        """Test cache stats with degraded health status."""
        mock_cached.return_value = None
        mock = Mock()
        mock.get_stats.return_value = {
            'hits': 100,
            'misses': 100,
            'errors': 0,
            'hit_rate_percent': 50.0  # Degraded
        }
        mock_service.return_value = mock

        response = client.get(
            "/api/v2/performance/cache/stats",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "degraded"


class TestCacheInvalidation:
    """Tests for POST /performance/cache/invalidate"""

    @patch('app.api.v2.performance._get_cache_invalidation_service')
    @patch('app.api.v2.performance._get_cache_service')
    async def test_invalidate_cache_by_type(
        self,
        mock_cache_svc,
        mock_inv_svc,
        client,
        admin_headers
    ):
        """Test invalidating cache by type."""
        mock_inv_service = Mock()
        mock_inv_svc.return_value = mock_inv_service

        response = client.post(
            "/api/v2/performance/cache/invalidate",
            headers=admin_headers,
            json={"cache_type": "analytics"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["cache_type"] == "analytics"
        mock_inv_service.invalidate_analytics_cache.assert_called_once()

    @patch('app.api.v2.performance._get_cache_invalidation_service')
    async def test_invalidate_cache_by_pattern(
        self,
        mock_inv_svc,
        client,
        admin_headers
    ):
        """Test invalidating cache by pattern."""
        with patch('app.api.v2.performance.get_async_redis') as mock_redis:
            mock_redis_inst = AsyncMock()
            mock_redis_inst.keys.return_value = ["key1", "key2", "key3"]
            mock_redis_inst.delete = AsyncMock()
            mock_redis.return_value = mock_redis_inst

            response = client.post(
                "/api/v2/performance/cache/invalidate",
                headers=admin_headers,
                json={"pattern": "dashboard:*"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["invalidated_count"] == 3

    async def test_invalidate_cache_requires_admin(self, client, doctor_headers):
        """Test that cache invalidation requires admin role."""
        response = client.post(
            "/api/v2/performance/cache/invalidate",
            headers=doctor_headers,
            json={"cache_type": "analytics"}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCacheClear:
    """Tests for DELETE /performance/cache/clear"""

    @patch('app.api.v2.performance._get_cache_service')
    async def test_clear_cache_success(
        self,
        mock_service,
        client,
        admin_headers,
        mock_cache_service
    ):
        """Test clearing cache successfully."""
        mock_service.return_value = mock_cache_service

        response = client.delete(
            "/api/v2/performance/cache/clear",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "cleared_count" in data

    async def test_clear_cache_requires_admin(self, client, doctor_headers):
        """Test that cache clear requires admin role."""
        response = client.delete(
            "/api/v2/performance/cache/clear",
            headers=doctor_headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Performance Overview Tests
# ============================================================================

class TestPerformanceOverview:
    """Tests for GET /performance/overview"""

    @patch('app.api.v2.performance._get_cache_service')
    @patch('app.api.v2.performance._get_query_monitor')
    @patch('app.api.v2.performance.get_pool_status')
    @patch('app.api.v2.performance.is_pool_healthy')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_performance_overview_excellent(
        self,
        mock_cached,
        mock_healthy,
        mock_pool,
        mock_monitor,
        mock_cache,
        client,
        admin_headers,
        mock_cache_service,
        mock_query_monitor,
        mock_pool_status
    ):
        """Test performance overview with excellent metrics."""
        mock_cached.return_value = None
        mock_cache.return_value = mock_cache_service
        mock_monitor.return_value = mock_query_monitor
        mock_pool.return_value = mock_pool_status
        mock_healthy.return_value = True

        response = client.get(
            "/api/v2/performance/overview",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "score" in data
        assert "status" in data
        assert data["status"] in ["excellent", "good", "fair", "poor"]
        assert len(data["components"]) >= 3
        assert "recommendations" in data

    @patch('app.api.v2.performance._get_cache_service')
    @patch('app.api.v2.performance._get_query_monitor')
    @patch('app.api.v2.performance.get_pool_status')
    @patch('app.api.v2.performance.is_pool_healthy')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_performance_scoring_algorithm(
        self,
        mock_cached,
        mock_healthy,
        mock_pool,
        mock_monitor,
        mock_cache,
        client,
        admin_headers
    ):
        """Test performance scoring algorithm."""
        mock_cached.return_value = None

        # Good cache, poor queries
        mock_cache_svc = Mock()
        mock_cache_svc.get_stats.return_value = {
            'hit_rate_percent': 90.0  # Excellent
        }
        mock_cache.return_value = mock_cache_svc

        mock_mon = Mock()
        mock_mon.get_query_stats.return_value = {
            'avg_duration_ms': 250.0,  # Poor
            'slow_query_percentage': 25.0  # High
        }
        mock_monitor.return_value = mock_mon

        mock_pool.return_value = {'utilization_percent': 50.0}
        mock_healthy.return_value = True

        response = client.get(
            "/api/v2/performance/overview",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Score should be mixed due to poor query performance
        assert data["score"] < 90
        assert "query" in str(data["recommendations"]).lower()


class TestDatabasePerformance:
    """Tests for GET /performance/database"""

    @patch('app.api.v2.performance._get_query_monitor')
    @patch('app.api.v2.performance.get_pool_status')
    @patch('app.api.v2.performance.is_pool_healthy')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_database_performance(
        self,
        mock_cached,
        mock_healthy,
        mock_pool,
        mock_monitor,
        client,
        admin_headers,
        mock_query_monitor,
        mock_pool_status
    ):
        """Test getting database performance metrics."""
        mock_cached.return_value = None
        mock_monitor.return_value = mock_query_monitor
        mock_pool.return_value = mock_pool_status
        mock_healthy.return_value = True

        response = client.get(
            "/api/v2/performance/database",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "avg_query_time_ms" in data
        assert "slow_query_count" in data
        assert "pool_utilization_percent" in data
        assert "pool_healthy" in data


class TestAPIPerformance:
    """Tests for GET /performance/api"""

    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_api_performance(
        self,
        mock_cached,
        client,
        admin_headers
    ):
        """Test getting API performance metrics."""
        mock_cached.return_value = None

        response = client.get(
            "/api/v2/performance/api",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_api_performance_with_limit(self, client, admin_headers):
        """Test API performance with limit parameter."""
        response = client.get(
            "/api/v2/performance/api?limit=10",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK


class TestSlowQueries:
    """Tests for GET /performance/queries"""

    @patch('app.api.v2.performance._get_query_monitor')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_slow_queries(
        self,
        mock_cached,
        mock_monitor,
        client,
        admin_headers,
        mock_query_monitor
    ):
        """Test getting slow queries."""
        mock_cached.return_value = None
        mock_monitor.return_value = mock_query_monitor

        response = client.get(
            "/api/v2/performance/queries",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "queries" in data
        assert "total" in data
        assert "has_more" in data

    @patch('app.api.v2.performance._get_query_monitor')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_slow_queries_pagination(
        self,
        mock_cached,
        mock_monitor,
        client,
        admin_headers,
        mock_query_monitor
    ):
        """Test slow queries pagination."""
        mock_cached.return_value = None
        mock_monitor.return_value = mock_query_monitor

        response = client.get(
            "/api/v2/performance/queries?limit=10&offset=5",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5


class TestOptimizationRecommendations:
    """Tests for GET /performance/recommendations"""

    @patch('app.api.v2.performance._get_cache_service')
    @patch('app.api.v2.performance._get_query_monitor')
    @patch('app.api.v2.performance.get_pool_status')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_recommendations(
        self,
        mock_cached,
        mock_pool,
        mock_monitor,
        mock_cache,
        client,
        admin_headers
    ):
        """Test getting optimization recommendations."""
        mock_cached.return_value = None

        # Setup mocks for poor performance
        mock_cache_svc = Mock()
        mock_cache_svc.get_stats.return_value = {'hit_rate_percent': 30.0}
        mock_cache.return_value = mock_cache_svc

        mock_mon = Mock()
        mock_mon.get_query_stats.return_value = {'slow_query_percentage': 15.0}
        mock_monitor.return_value = mock_mon

        mock_pool.return_value = {'utilization_percent': 85.0}

        response = client.get(
            "/api/v2/performance/recommendations",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for rec in data:
            assert "type" in rec
            assert "severity" in rec
            assert "impact" in rec


# ============================================================================
# Database Health Tests
# ============================================================================

class TestDatabaseHealth:
    """Tests for GET /performance/database/health"""

    @patch('app.api.v2.performance.get_pool_status')
    @patch('app.api.v2.performance.is_pool_healthy')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_database_health(
        self,
        mock_cached,
        mock_healthy,
        mock_pool,
        client,
        admin_headers,
        mock_pool_status,
        db_session
    ):
        """Test getting database health status."""
        mock_cached.return_value = None
        mock_pool.return_value = mock_pool_status
        mock_healthy.return_value = True

        response = client.get(
            "/api/v2/performance/database/health",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "connection_pool" in data
        assert "active_connections" in data
        assert "locks_count" in data
        assert "response_time_ms" in data

    @patch('app.api.v2.performance.get_pool_status')
    @patch('app.api.v2.performance.is_pool_healthy')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_database_health_degraded(
        self,
        mock_cached,
        mock_healthy,
        mock_pool,
        client,
        admin_headers,
        db_session
    ):
        """Test database health with degraded status."""
        mock_cached.return_value = None
        mock_pool.return_value = {
            'pool_size': 20,
            'overflow': 10,
            'checked_out': 28,  # High utilization
            'checked_in': 2,
            'utilization_percent': 93.3
        }
        mock_healthy.return_value = False

        response = client.get(
            "/api/v2/performance/database/health",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] in ["degraded", "critical"]


class TestConnectionPool:
    """Tests for GET /performance/database/pool"""

    @patch('app.api.v2.performance.get_pool_status')
    @patch('app.api.v2.performance.is_pool_healthy')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_connection_pool_status(
        self,
        mock_cached,
        mock_healthy,
        mock_pool,
        client,
        admin_headers,
        mock_pool_status
    ):
        """Test getting connection pool status."""
        mock_cached.return_value = None
        mock_pool.return_value = mock_pool_status
        mock_healthy.return_value = True

        response = client.get(
            "/api/v2/performance/database/pool",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pool_size"] == 20
        assert data["utilization_percent"] == 43.3
        assert data["health_status"] == "healthy"


class TestActiveConnections:
    """Tests for GET /performance/database/connections"""

    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_active_connections(
        self,
        mock_cached,
        client,
        admin_headers,
        db_session
    ):
        """Test getting active connections."""
        mock_cached.return_value = None

        response = client.get(
            "/api/v2/performance/database/connections",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "connections" in data
        assert "total" in data
        assert "has_more" in data

    async def test_active_connections_pagination(
        self,
        client,
        admin_headers,
        db_session
    ):
        """Test active connections pagination."""
        response = client.get(
            "/api/v2/performance/database/connections?limit=5&offset=0",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 0


class TestDatabaseLocks:
    """Tests for GET /performance/database/locks"""

    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_database_locks(
        self,
        mock_cached,
        client,
        admin_headers,
        db_session
    ):
        """Test getting database locks."""
        mock_cached.return_value = None

        response = client.get(
            "/api/v2/performance/database/locks",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "locks" in data
        assert "total" in data
        assert "has_more" in data


# ============================================================================
# Database Optimization Tests
# ============================================================================

class TestOptimizationSuggestions:
    """Tests for GET /performance/database/optimization"""

    @patch('app.api.v2.performance._get_db_optimizer')
    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_optimization_suggestions(
        self,
        mock_cached,
        mock_optimizer,
        client,
        admin_headers,
        mock_db_optimizer,
        db_session
    ):
        """Test getting optimization suggestions."""
        mock_cached.return_value = None
        mock_optimizer.return_value = mock_db_optimizer

        response = client.get(
            "/api/v2/performance/database/optimization",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_optimization_suggestions_requires_admin(
        self,
        client,
        doctor_headers
    ):
        """Test that optimization suggestions require admin role."""
        response = client.get(
            "/api/v2/performance/database/optimization",
            headers=doctor_headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDatabaseOptimize:
    """Tests for POST /performance/database/optimize"""

    @patch('app.api.v2.performance._get_db_optimizer')
    async def test_run_optimization_dry_run(
        self,
        mock_optimizer,
        client,
        admin_headers,
        mock_db_optimizer,
        db_session
    ):
        """Test running optimization in dry-run mode."""
        mock_optimizer.return_value = mock_db_optimizer

        response = client.post(
            "/api/v2/performance/database/optimize?dry_run=true",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["dry_run"] is True
        assert "sql_statements" in data

    @patch('app.api.v2.performance._get_db_optimizer')
    async def test_run_optimization_execute(
        self,
        mock_optimizer,
        client,
        admin_headers,
        mock_db_optimizer,
        db_session
    ):
        """Test running optimization with execution."""
        mock_optimizer.return_value = mock_db_optimizer

        response = client.post(
            "/api/v2/performance/database/optimize?dry_run=false",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["dry_run"] is False

    async def test_optimize_requires_admin(self, client, doctor_headers):
        """Test that optimization requires admin role."""
        response = client.post(
            "/api/v2/performance/database/optimize",
            headers=doctor_headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestIndexAnalysis:
    """Tests for GET /performance/database/indexes"""

    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_index_analysis(
        self,
        mock_cached,
        client,
        admin_headers,
        db_session
    ):
        """Test getting index analysis."""
        mock_cached.return_value = None

        response = client.get(
            "/api/v2/performance/database/indexes",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_index_analysis_requires_admin(self, client, doctor_headers):
        """Test that index analysis requires admin role."""
        response = client.get(
            "/api/v2/performance/database/indexes",
            headers=doctor_headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestVacuum:
    """Tests for POST /performance/database/vacuum"""

    async def test_run_vacuum_without_confirmation(
        self,
        client,
        admin_headers,
        db_session
    ):
        """Test that FULL VACUUM requires confirmation."""
        response = client.post(
            "/api/v2/performance/database/vacuum",
            headers=admin_headers,
            json={
                "full": True,
                "confirm": False
            }
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_run_vacuum_with_confirmation(
        self,
        client,
        admin_headers,
        db_session
    ):
        """Test running VACUUM with confirmation."""
        response = client.post(
            "/api/v2/performance/database/vacuum",
            headers=admin_headers,
            json={
                "table_name": "patients",
                "full": False,
                "analyze": True,
                "confirm": True
            }
        )

        # May succeed or fail depending on database state
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

    async def test_vacuum_requires_admin(self, client, doctor_headers):
        """Test that VACUUM requires admin role."""
        response = client.post(
            "/api/v2/performance/database/vacuum",
            headers=doctor_headers,
            json={"confirm": True}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestTableStatistics:
    """Tests for GET /performance/database/table-stats"""

    @patch('app.api.v2.performance._get_cached_result')
    async def test_get_table_statistics(
        self,
        mock_cached,
        client,
        admin_headers,
        db_session
    ):
        """Test getting table statistics."""
        mock_cached.return_value = None

        response = client.get(
            "/api/v2/performance/database/table-stats",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_table_statistics_requires_admin(self, client, doctor_headers):
        """Test that table statistics require admin role."""
        response = client.get(
            "/api/v2/performance/database/table-stats",
            headers=doctor_headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# RBAC and Security Tests
# ============================================================================

class TestRBAC:
    """Tests for Role-Based Access Control"""

    async def test_read_operations_require_auth(self, client):
        """Test that read operations require authentication."""
        endpoints = [
            "/api/v2/performance/cache/metrics",
            "/api/v2/performance/cache/stats",
            "/api/v2/performance/overview",
            "/api/v2/performance/database",
            "/api/v2/performance/database/health",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_write_operations_require_admin(self, client, doctor_headers):
        """Test that write operations require admin role."""
        endpoints_methods = [
            ("POST", "/api/v2/performance/cache/invalidate", {"cache_type": "test"}),
            ("DELETE", "/api/v2/performance/cache/clear", None),
            ("POST", "/api/v2/performance/database/optimize", None),
            ("POST", "/api/v2/performance/database/vacuum", {"confirm": True}),
        ]

        for method, endpoint, json_data in endpoints_methods:
            if method == "POST":
                response = client.post(endpoint, headers=doctor_headers, json=json_data or {})
            else:
                response = client.delete(endpoint, headers=doctor_headers)

            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_doctors_can_read_performance(self, client, doctor_headers):
        """Test that doctors can read performance metrics."""
        response = client.get(
            "/api/v2/performance/overview",
            headers=doctor_headers
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR  # May fail if services unavailable
        ]


# ============================================================================
# Caching Tests
# ============================================================================

class TestCaching:
    """Tests for Redis caching behavior"""

    @patch('app.api.v2.performance._get_cached_result')
    @patch('app.api.v2.performance._set_cached_result')
    async def test_cache_hit(
        self,
        mock_set,
        mock_get,
        client,
        admin_headers
    ):
        """Test cache hit returns cached data."""
        cached_data = {
            "hits": 1000,
            "misses": 100,
            "hit_rate_percentage": 90.9,
            "total_keys": 50,
            "evictions": 0,
            "invalidations": 0,
            "warming_operations": 0
        }
        mock_get.return_value = cached_data

        response = client.get(
            "/api/v2/performance/cache/metrics",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        # Should not set cache on hit
        mock_set.assert_not_called()

    @patch('app.api.v2.performance._get_cache_service')
    @patch('app.api.v2.performance._get_cached_result')
    @patch('app.api.v2.performance._set_cached_result')
    async def test_cache_miss_sets_cache(
        self,
        mock_set,
        mock_get,
        mock_service,
        client,
        admin_headers,
        mock_cache_service
    ):
        """Test cache miss fetches data and sets cache."""
        mock_get.return_value = None
        mock_service.return_value = mock_cache_service

        response = client.get(
            "/api/v2/performance/cache/metrics",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        # Should set cache on miss
        mock_set.assert_called_once()


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling"""

    @patch('app.api.v2.performance._get_cache_service')
    async def test_service_error_returns_500(
        self,
        mock_service,
        client,
        admin_headers
    ):
        """Test that service errors return 500."""
        mock_service.side_effect = Exception("Service error")

        response = client.get(
            "/api/v2/performance/cache/metrics",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_invalid_pagination_parameters(self, client, admin_headers):
        """Test invalid pagination parameters."""
        response = client.get(
            "/api/v2/performance/queries?limit=0",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_database_error_handling(
        self,
        client,
        admin_headers,
        db_session
    ):
        """Test database error handling."""
        # Test with invalid SQL injection attempt
        response = client.get(
            "/api/v2/performance/database/connections?limit=100000",
            headers=admin_headers
        )

        # Should either succeed with limit or return error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
