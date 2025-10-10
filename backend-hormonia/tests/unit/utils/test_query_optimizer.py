"""
Tests for Query Optimization Framework

Tests the @optimized_query decorator, query metrics collection, and performance monitoring.
"""

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime

from app.utils.query_optimizer import (
    QueryOptimizer,
    QueryMetrics,
    QueryStats,
    optimized_query,
    get_query_stats,
    reset_query_stats,
    get_optimization_report,
    track_queries,
    analyze_query_plan
)


class TestQueryOptimizer:
    """Test QueryOptimizer class"""

    def test_optimizer_initialization(self):
        """Test optimizer initializes with default settings"""
        optimizer = QueryOptimizer()

        assert optimizer.slow_query_threshold_ms == 100.0
        assert optimizer.stats.total_queries == 0
        assert optimizer.stats.total_time_ms == 0.0
        assert optimizer._enabled is True

    def test_optimizer_custom_threshold(self):
        """Test optimizer with custom slow query threshold"""
        optimizer = QueryOptimizer(slow_query_threshold_ms=50.0)

        assert optimizer.slow_query_threshold_ms == 50.0

    def test_optimized_query_decorator_basic(self):
        """Test basic @optimized_query decorator functionality"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query()
        def sample_query():
            time.sleep(0.05)  # 50ms
            return [1, 2, 3]

        result = sample_query()

        assert result == [1, 2, 3]
        assert optimizer.stats.total_queries == 1
        assert optimizer.stats.total_time_ms >= 50

    def test_optimized_query_decorator_with_relationships(self):
        """Test @optimized_query with relationship loading"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query(['patient', 'doctor'])
        def sample_query():
            return [{"id": 1}]

        result = sample_query()

        assert result == [{"id": 1}]
        assert optimizer.stats.total_queries == 1

    def test_slow_query_detection(self):
        """Test slow query detection and logging"""
        optimizer = QueryOptimizer(slow_query_threshold_ms=10.0)

        @optimizer.optimized_query()
        def slow_query():
            time.sleep(0.02)  # 20ms (above 10ms threshold)
            return []

        with patch('app.utils.query_optimizer.logger') as mock_logger:
            result = slow_query()

            assert optimizer.stats.slow_queries == 1
            mock_logger.warning.assert_called()

    def test_n1_query_detection(self):
        """Test N+1 query pattern detection"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query()
        def potential_n1_query():
            # Simulate multiple queries
            optimizer._query_count_per_request['test'] = 10
            return []

        result = potential_n1_query()

        assert 'potential_n1_query' in optimizer._n1_patterns

    def test_get_stats(self):
        """Test getting query statistics"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query()
        def test_query():
            return [1, 2, 3]

        test_query()
        stats = optimizer.get_stats()

        assert isinstance(stats, QueryStats)
        assert stats.total_queries == 1
        assert len(stats.metrics) == 1

    def test_reset_stats(self):
        """Test resetting statistics"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query()
        def test_query():
            return []

        test_query()
        assert optimizer.stats.total_queries == 1

        optimizer.reset_stats()
        assert optimizer.stats.total_queries == 0
        assert len(optimizer.stats.metrics) == 0

    def test_get_optimization_report(self):
        """Test generating optimization report"""
        optimizer = QueryOptimizer(slow_query_threshold_ms=10.0)

        @optimizer.optimized_query()
        def slow_query():
            time.sleep(0.02)  # Slow query
            return []

        slow_query()
        report = optimizer.get_optimization_report()

        assert 'summary' in report
        assert 'slow_queries' in report
        assert 'n1_patterns' in report
        assert 'suggestions' in report

        assert report['summary']['total_queries'] == 1
        assert report['summary']['slow_queries_count'] == 1

    def test_suggestions_generation(self):
        """Test optimization suggestions based on detected issues"""
        optimizer = QueryOptimizer(slow_query_threshold_ms=10.0)

        # Create slow query
        @optimizer.optimized_query()
        def slow_query():
            time.sleep(0.02)
            return []

        slow_query()
        report = optimizer.get_optimization_report()

        assert len(report['suggestions']) > 0
        assert any('slow queries' in s.lower() for s in report['suggestions'])

    def test_enable_disable(self):
        """Test enabling and disabling optimizer"""
        optimizer = QueryOptimizer()

        optimizer.disable()
        assert optimizer._enabled is False

        optimizer.enable()
        assert optimizer._enabled is True

    def test_disabled_optimizer(self):
        """Test that disabled optimizer doesn't track queries"""
        optimizer = QueryOptimizer()
        optimizer.disable()

        @optimizer.optimized_query()
        def test_query():
            return []

        test_query()

        # Should not track when disabled
        assert optimizer.stats.total_queries == 0

    def test_row_count_calculation(self):
        """Test row count calculation from results"""
        optimizer = QueryOptimizer()

        # Test with list result
        assert optimizer._get_row_count([1, 2, 3]) == 3

        # Test with single result
        assert optimizer._get_row_count({"id": 1}) == 1

        # Test with None
        assert optimizer._get_row_count(None) == 0


class TestQueryMetrics:
    """Test QueryMetrics dataclass"""

    def test_metrics_creation(self):
        """Test creating query metrics"""
        metrics = QueryMetrics(
            query_text="SELECT * FROM patients",
            execution_time_ms=45.5,
            row_count=10,
            function_name="get_patients"
        )

        assert metrics.query_text == "SELECT * FROM patients"
        assert metrics.execution_time_ms == 45.5
        assert metrics.row_count == 10
        assert metrics.function_name == "get_patients"
        assert metrics.is_slow is False
        assert isinstance(metrics.timestamp, datetime)

    def test_slow_query_flag(self):
        """Test is_slow flag"""
        metrics = QueryMetrics(
            query_text="SELECT * FROM patients",
            execution_time_ms=150.0,
            row_count=10,
            is_slow=True
        )

        assert metrics.is_slow is True


class TestGlobalOptimizer:
    """Test global optimizer functions"""

    def test_global_optimized_query(self):
        """Test global optimized_query decorator"""
        reset_query_stats()

        @optimized_query(['patient'])
        def test_query():
            return [1, 2, 3]

        result = test_query()
        stats = get_query_stats()

        assert result == [1, 2, 3]
        assert stats.total_queries == 1

    def test_get_global_stats(self):
        """Test getting global statistics"""
        reset_query_stats()

        @optimized_query()
        def test_query():
            return []

        test_query()
        stats = get_query_stats()

        assert isinstance(stats, QueryStats)
        assert stats.total_queries == 1

    def test_reset_global_stats(self):
        """Test resetting global statistics"""
        @optimized_query()
        def test_query():
            return []

        test_query()
        reset_query_stats()
        stats = get_query_stats()

        assert stats.total_queries == 0

    def test_get_global_report(self):
        """Test getting global optimization report"""
        reset_query_stats()

        @optimized_query()
        def test_query():
            return []

        test_query()
        report = get_optimization_report()

        assert 'summary' in report
        assert 'slow_queries' in report


class TestTrackQueries:
    """Test track_queries context manager"""

    @pytest.fixture
    def mock_session(self):
        """Create mock SQLAlchemy session"""
        session = Mock()
        return session

    def test_track_queries_context(self, mock_session):
        """Test track_queries context manager"""
        with track_queries(mock_session) as tracker:
            # Tracker should be initialized
            assert tracker.query_count == 0
            assert tracker.queries == []


class TestQueryStrategies:
    """Test different eager loading strategies"""

    def test_auto_strategy(self):
        """Test auto strategy selection"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query(['patient'], strategy='auto')
        def test_query():
            return []

        # Should not raise errors
        test_query()

    def test_joined_strategy(self):
        """Test joined loading strategy"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query(['patient'], strategy='joined')
        def test_query():
            return []

        # Should not raise errors
        test_query()

    def test_select_strategy(self):
        """Test select loading strategy"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query(['patient', 'doctor'], strategy='select')
        def test_query():
            return []

        # Should not raise errors
        test_query()


class TestPerformanceMetrics:
    """Test performance metrics collection"""

    def test_execution_time_tracking(self):
        """Test accurate execution time tracking"""
        optimizer = QueryOptimizer()
        sleep_time = 0.05  # 50ms

        @optimizer.optimized_query()
        def timed_query():
            time.sleep(sleep_time)
            return []

        timed_query()
        stats = optimizer.get_stats()

        # Execution time should be at least 50ms
        assert stats.total_time_ms >= 50
        assert stats.metrics[0].execution_time_ms >= 50

    def test_average_time_calculation(self):
        """Test average execution time calculation"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query()
        def query1():
            time.sleep(0.01)  # 10ms
            return []

        @optimizer.optimized_query()
        def query2():
            time.sleep(0.03)  # 30ms
            return []

        query1()
        query2()

        stats = optimizer.get_stats()

        # Average should be around 20ms
        assert 15 <= stats.avg_execution_time_ms <= 50


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_relationships(self):
        """Test decorator with empty relationships list"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query([])
        def test_query():
            return []

        # Should work without errors
        result = test_query()
        assert result == []

    def test_none_relationships(self):
        """Test decorator with None relationships"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query(None)
        def test_query():
            return []

        # Should work without errors
        result = test_query()
        assert result == []

    def test_nested_relationships(self):
        """Test nested relationship paths"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query(['patient.doctor', 'patient.alerts'])
        def test_query():
            return []

        # Should not raise errors
        test_query()

    def test_exception_in_query(self):
        """Test that exceptions in queries are handled properly"""
        optimizer = QueryOptimizer()

        @optimizer.optimized_query()
        def failing_query():
            raise ValueError("Query failed")

        with pytest.raises(ValueError, match="Query failed"):
            failing_query()


class TestQuerySignature:
    """Test query signature generation for duplicate detection"""

    def test_query_normalization(self):
        """Test query signature normalization"""
        from app.utils.query_optimizer import _global_optimizer as optimizer

        # These should have same signature
        query1 = "SELECT * FROM patients WHERE id = 123"
        query2 = "SELECT * FROM patients WHERE id = 456"

        sig1 = optimizer._get_query_signature(query1)
        sig2 = optimizer._get_query_signature(query2)

        # Signatures should be similar (normalized)
        assert sig1 == sig2


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration tests for real-world scenarios"""

    def test_repository_pattern(self):
        """Test optimizer with repository pattern"""
        optimizer = QueryOptimizer()

        class MockRepository:
            @optimizer.optimized_query(['patient', 'doctor'])
            def get_by_id(self, id):
                time.sleep(0.01)
                return {"id": id}

            @optimizer.optimized_query(['patients.alerts'])
            def get_with_alerts(self, id):
                time.sleep(0.02)
                return {"id": id, "alerts": []}

        repo = MockRepository()

        result1 = repo.get_by_id(1)
        result2 = repo.get_with_alerts(2)

        stats = optimizer.get_stats()
        assert stats.total_queries == 2

    def test_performance_degradation_detection(self):
        """Test detection of performance degradation"""
        optimizer = QueryOptimizer(slow_query_threshold_ms=20.0)

        @optimizer.optimized_query()
        def normal_query():
            time.sleep(0.01)  # 10ms - normal
            return []

        @optimizer.optimized_query()
        def degraded_query():
            time.sleep(0.03)  # 30ms - degraded
            return []

        normal_query()
        degraded_query()

        report = optimizer.get_optimization_report()

        assert report['summary']['total_queries'] == 2
        assert report['summary']['slow_queries_count'] == 1
        assert len(report['slow_queries']) == 1
