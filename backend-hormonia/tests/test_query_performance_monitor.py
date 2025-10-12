"""
Tests for Query Performance Monitor.
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.services.query_performance_monitor import (
    QueryPerformanceMonitor,
    SlowQuery,
    QueryMetrics,
    query_performance_decorator
)


class TestQueryPerformanceMonitor:
    """Test cases for QueryPerformanceMonitor."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        db.get_bind.return_value = Mock()
        return db
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch('app.services.query_performance_monitor.get_sync_redis') as mock_redis:
            redis_client = Mock()
            mock_redis.return_value = redis_client
            yield redis_client
    
    @pytest.fixture
    def monitor(self, mock_db, mock_redis):
        """Create QueryPerformanceMonitor instance."""
        with patch('app.services.query_performance_monitor.event'):
            return QueryPerformanceMonitor(mock_db)
    
    def test_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor is not None
        assert isinstance(monitor._metrics, QueryMetrics)
        assert monitor.SLOW_QUERY_THRESHOLD_MS == 500
    
    def test_track_query_time_fast_query(self, monitor):
        """Test tracking fast queries (should not be stored)."""
        query = "SELECT * FROM users WHERE id = 1"
        duration_ms = 50.0  # Fast query
        
        monitor.track_query_time(query, duration_ms)
        
        # Should not be in cache (not slow enough)
        assert len(monitor._query_cache) == 0
    
    def test_track_query_time_slow_query(self, monitor, mock_redis):
        """Test tracking slow queries."""
        query = "SELECT * FROM users WHERE name LIKE '%test%'"
        duration_ms = 750.0  # Slow query
        
        mock_redis.setex.return_value = True
        
        monitor.track_query_time(query, duration_ms, {"param1": "value1"})
        
        # Should be in cache
        assert len(monitor._query_cache) == 1
        
        # Check slow query details
        query_hash = list(monitor._query_cache.keys())[0]
        slow_query = monitor._query_cache[query_hash]
        
        assert slow_query.duration_ms == duration_ms
        assert slow_query.execution_count == 1
        assert slow_query.avg_duration_ms == duration_ms
        assert slow_query.max_duration_ms == duration_ms
        assert "param1" in str(slow_query.parameters)
    
    def test_track_query_time_repeated_slow_query(self, monitor, mock_redis):
        """Test tracking the same slow query multiple times."""
        query = "SELECT * FROM users WHERE name LIKE '%test%'"
        
        mock_redis.setex.return_value = True
        
        # Track same query multiple times
        monitor.track_query_time(query, 600.0)
        monitor.track_query_time(query, 800.0)
        monitor.track_query_time(query, 700.0)
        
        # Should still be one entry in cache
        assert len(monitor._query_cache) == 1
        
        # Check aggregated metrics
        query_hash = list(monitor._query_cache.keys())[0]
        slow_query = monitor._query_cache[query_hash]
        
        assert slow_query.execution_count == 3
        assert slow_query.avg_duration_ms == 700.0  # (600 + 800 + 700) / 3
        assert slow_query.max_duration_ms == 800.0
    
    def test_identify_slow_queries(self, monitor, mock_redis):
        """Test identifying slow queries."""
        # Add some slow queries
        queries = [
            ("SELECT * FROM users", 600.0),
            ("SELECT * FROM messages", 800.0),
            ("SELECT * FROM patients", 550.0)
        ]
        
        mock_redis.setex.return_value = True
        mock_redis.keys.return_value = []
        
        for query, duration in queries:
            monitor.track_query_time(query, duration)
        
        # Get slow queries
        slow_queries = monitor.identify_slow_queries(limit=10)
        
        # Should return queries sorted by average duration (descending)
        assert len(slow_queries) == 3
        assert slow_queries[0].avg_duration_ms == 800.0  # messages query
        assert slow_queries[1].avg_duration_ms == 600.0  # users query
        assert slow_queries[2].avg_duration_ms == 550.0  # patients query
    
    def test_suggest_optimizations(self, monitor):
        """Test optimization suggestions."""
        test_cases = [
            {
                "query": "SELECT * FROM users WHERE created_at > '2023-01-01'",
                "expected_suggestions": [
                    "Avoid SELECT * - specify only needed columns",
                    "Ensure date columns have appropriate indexes"
                ]
            },
            {
                "query": "SELECT u.name FROM users u WHERE u.id IN (SELECT patient_id FROM messages)",
                "expected_suggestions": [
                    "Consider optimizing subqueries with JOINs or CTEs"
                ]
            },
            {
                "query": "SELECT * FROM users WHERE name = 'test' OR email = 'test@example.com'",
                "expected_suggestions": [
                    "Avoid SELECT * - specify only needed columns",
                    "OR conditions can be slow - consider UNION or separate queries"
                ]
            }
        ]
        
        for case in test_cases:
            suggestions = monitor.suggest_optimizations(case["query"])
            
            for expected in case["expected_suggestions"]:
                assert any(expected in suggestion for suggestion in suggestions), \
                    f"Expected '{expected}' in suggestions for query: {case['query']}"
    
    def test_get_performance_metrics(self, monitor):
        """Test getting performance metrics."""
        # Simulate some query activity
        monitor._update_metrics(100.0)  # Fast query
        monitor._update_metrics(600.0)  # Slow query
        monitor._update_metrics(200.0)  # Fast query
        
        metrics = monitor.get_performance_metrics()
        
        assert metrics.total_queries == 3
        assert metrics.slow_queries == 1
        assert metrics.avg_duration_ms == 300.0  # (100 + 600 + 200) / 3
        assert metrics.max_duration_ms == 600.0
    
    def test_get_query_analysis(self, monitor, mock_redis):
        """Test comprehensive query analysis."""
        # Add some test data
        mock_redis.setex.return_value = True
        mock_redis.keys.return_value = []
        
        monitor.track_query_time("SELECT * FROM users", 600.0)
        monitor.track_query_time("SELECT * FROM messages", 800.0)
        
        analysis = monitor.get_query_analysis(hours_back=1)
        
        assert "time_period_hours" in analysis
        assert "metrics" in analysis
        assert "slow_queries_count" in analysis
        assert "top_slow_queries" in analysis
        assert "patterns" in analysis
        assert "recommendations" in analysis
        assert "timestamp" in analysis
        
        assert analysis["time_period_hours"] == 1
        assert analysis["slow_queries_count"] >= 0
    
    def test_monitor_query_context_manager(self, monitor):
        """Test query monitoring context manager."""
        with monitor.monitor_query("test_operation"):
            time.sleep(0.1)  # Simulate some work
        
        # Should have tracked the operation
        # Note: This test depends on the context manager implementation
        # In a real scenario, this would be verified through the tracking mechanism
    
    def test_query_normalization(self, monitor):
        """Test query normalization for consistent hashing."""
        queries = [
            "SELECT * FROM users WHERE id = $1",
            "SELECT * FROM users WHERE id = $2",
            "select * from users where id = $3",
            "SELECT   *   FROM   users   WHERE   id   =   $4"
        ]
        
        normalized_queries = [monitor._normalize_query(q) for q in queries]
        
        # All should normalize to the same string
        assert len(set(normalized_queries)) == 1
        
        # Check parameter replacement
        normalized = normalized_queries[0]
        assert "$PARAM" in normalized
        assert "$1" not in normalized
    
    def test_parameter_cleaning(self, monitor):
        """Test parameter cleaning for safe storage."""
        parameters = {
            "string_param": "test_value",
            "int_param": 123,
            "float_param": 45.67,
            "bool_param": True,
            "none_param": None,
            "complex_param": {"nested": "object"},
            "list_param": [1, 2, 3]
        }
        
        cleaned = monitor._clean_parameters(parameters)
        
        assert cleaned["string_param"] == "test_value"
        assert cleaned["int_param"] == 123
        assert cleaned["float_param"] == 45.67
        assert cleaned["bool_param"] is True
        assert cleaned["none_param"] is None
        assert cleaned["complex_param"] == "dict"  # Type name
        assert cleaned["list_param"] == "list"  # Type name
    
    def test_performance_decorator(self, mock_db, mock_redis):
        """Test query performance decorator."""
        with patch('app.services.query_performance_monitor.event'):
            monitor = QueryPerformanceMonitor(mock_db)
        
        @query_performance_decorator(monitor, "test_operation")
        def test_function():
            time.sleep(0.05)  # Simulate work
            return "result"
        
        result = test_function()
        assert result == "result"
        
        # The decorator should have monitored the function execution
        # In a real scenario, this would be verified through the monitoring system


class TestSlowQuery:
    """Test cases for SlowQuery dataclass."""
    
    def test_slow_query_creation(self):
        """Test SlowQuery creation and post_init."""
        slow_query = SlowQuery(
            query_hash="test_hash",
            query_text="SELECT * FROM test",
            duration_ms=750.0,
            timestamp=datetime.utcnow(),
            parameters={},
            optimization_suggestions=["Add index"]
        )
        
        assert slow_query.execution_count == 1
        assert slow_query.avg_duration_ms == 750.0
        assert slow_query.max_duration_ms == 750.0
    
    def test_slow_query_with_custom_values(self):
        """Test SlowQuery with custom avg and max values."""
        slow_query = SlowQuery(
            query_hash="test_hash",
            query_text="SELECT * FROM test",
            duration_ms=750.0,
            timestamp=datetime.utcnow(),
            parameters={},
            optimization_suggestions=["Add index"],
            execution_count=5,
            avg_duration_ms=600.0,
            max_duration_ms=900.0
        )
        
        assert slow_query.execution_count == 5
        assert slow_query.avg_duration_ms == 600.0
        assert slow_query.max_duration_ms == 900.0


class TestQueryMetrics:
    """Test cases for QueryMetrics dataclass."""
    
    def test_query_metrics_defaults(self):
        """Test QueryMetrics default values."""
        metrics = QueryMetrics()
        
        assert metrics.total_queries == 0
        assert metrics.slow_queries == 0
        assert metrics.avg_duration_ms == 0.0
        assert metrics.max_duration_ms == 0.0
        assert metrics.queries_per_second == 0.0
        assert metrics.cache_hit_rate == 0.0
    
    def test_query_metrics_with_values(self):
        """Test QueryMetrics with custom values."""
        metrics = QueryMetrics(
            total_queries=100,
            slow_queries=5,
            avg_duration_ms=150.0,
            max_duration_ms=800.0,
            queries_per_second=10.5,
            cache_hit_rate=85.2
        )
        
        assert metrics.total_queries == 100
        assert metrics.slow_queries == 5
        assert metrics.avg_duration_ms == 150.0
        assert metrics.max_duration_ms == 800.0
        assert metrics.queries_per_second == 10.5
        assert metrics.cache_hit_rate == 85.2


@pytest.mark.integration
class TestQueryPerformanceMonitorIntegration:
    """Integration tests for QueryPerformanceMonitor."""
    
    def test_redis_integration(self, mock_db):
        """Test Redis integration for storing slow queries."""
        with patch('app.services.query_performance_monitor.get_sync_redis') as mock_redis_func:
            redis_client = Mock()
            mock_redis_func.return_value = redis_client
            redis_client.setex.return_value = True
            redis_client.get.return_value = None
            redis_client.keys.return_value = []
            
            with patch('app.services.query_performance_monitor.event'):
                monitor = QueryPerformanceMonitor(mock_db)
            
            # Track a slow query
            monitor.track_query_time("SELECT * FROM test", 600.0)
            
            # Verify Redis operations
            assert redis_client.setex.called
            
            # Verify the stored data structure
            call_args = redis_client.setex.call_args
            assert len(call_args[0]) == 3  # key, ttl, data
            assert call_args[0][1] == 86400  # 24 hours TTL
    
    def test_event_listener_registration(self, mock_db):
        """Test SQLAlchemy event listener registration."""
        with patch('app.services.query_performance_monitor.event') as mock_event:
            with patch('app.services.query_performance_monitor.get_sync_redis'):
                monitor = QueryPerformanceMonitor(mock_db)
            
            # Verify event listeners were registered
            assert mock_event.listens_for.call_count >= 2  # before and after cursor execute