"""
Tests for AnalyticsCache.

Tests all functionality of the specialized analytics cache wrapper.

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4
from datetime import datetime

from app.services.cache.specialized.analytics_cache import (
    AnalyticsCache,
    get_analytics_cache,
)
from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive


@pytest.fixture
async def analytics_cache():
    """Create analytics cache instance for testing."""
    yield AnalyticsCache()


@pytest.fixture
def sample_metric():
    """Sample metric data."""
    return {
        "value": 42,
        "timestamp": now_sao_paulo_naive().isoformat(),
        "unit": "count",
    }


@pytest.fixture
def sample_report():
    """Sample report data."""
    return {
        "title": "Patient Summary Report",
        "data": {
            "total_patients": 100,
            "active_treatments": 45,
            "completed_treatments": 30,
        },
        "generated_at": now_sao_paulo_naive().isoformat(),
    }


@pytest.fixture
def sample_dashboard():
    """Sample dashboard data."""
    return {
        "widgets": [
            {"id": "widget1", "type": "chart", "data": [1, 2, 3]},
            {"id": "widget2", "type": "metric", "value": 100},
        ],
        "layout": "grid",
    }


class TestMetricsCaching:
    """Test metrics caching functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_metric(self, analytics_cache, sample_metric):
        """Test setting and getting a metric."""
        # Set metric
        success = await analytics_cache.set_metric("patient_count", sample_metric)
        assert success is True

        # Get metric
        result = await analytics_cache.get_metric("patient_count")
        assert result is not None
        assert result["value"] == 42
        assert result["unit"] == "count"

    @pytest.mark.asyncio
    async def test_metric_with_scope(self, analytics_cache, sample_metric):
        """Test metric with scope."""
        # Set metric with scope
        await analytics_cache.set_metric("patient_count", sample_metric, scope="daily")

        # Get metric with scope
        result = await analytics_cache.get_metric("patient_count", scope="daily")
        assert result is not None
        assert result["value"] == 42

        # Different scope should not exist
        result_no_scope = await analytics_cache.get_metric("patient_count")
        assert result_no_scope is None

    @pytest.mark.asyncio
    async def test_increment_counter(self, analytics_cache):
        """Test counter increment."""
        # Increment counter
        value1 = await analytics_cache.increment_counter("api_calls")
        assert value1 == 1

        # Increment again
        value2 = await analytics_cache.increment_counter("api_calls")
        assert value2 == 2

        # Increment with custom value
        value3 = await analytics_cache.increment_counter("api_calls", increment=5)
        assert value3 == 7

    @pytest.mark.asyncio
    async def test_counter_with_scope(self, analytics_cache):
        """Test counter with scope."""
        # Increment counter with scope
        value1 = await analytics_cache.increment_counter("api_calls", scope="user:123")
        assert value1 == 1

        value2 = await analytics_cache.increment_counter("api_calls", scope="user:456")
        assert value2 == 1

        # Different scopes should be independent
        value3 = await analytics_cache.increment_counter("api_calls", scope="user:123")
        assert value3 == 2

    @pytest.mark.asyncio
    async def test_get_counter(self, analytics_cache):
        """Test getting counter value."""
        # Non-existent counter should return 0
        value = await analytics_cache.get_counter("new_counter")
        assert value == 0

        # Increment and get
        await analytics_cache.increment_counter("new_counter")
        value = await analytics_cache.get_counter("new_counter")
        assert value == 1


class TestReportsCaching:
    """Test reports caching functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_report(self, analytics_cache, sample_report):
        """Test setting and getting a report."""
        # Set report
        success = await analytics_cache.set_report("patient_summary", sample_report)
        assert success is True

        # Get report
        result = await analytics_cache.get_report("patient_summary")
        assert result is not None
        assert result["title"] == "Patient Summary Report"
        assert result["data"]["total_patients"] == 100

    @pytest.mark.asyncio
    async def test_report_with_filters(self, analytics_cache, sample_report):
        """Test report with filters."""
        filters = {"date_from": "2025-01-01", "date_to": "2025-01-31"}

        # Set report with filters
        await analytics_cache.set_report(
            "patient_summary", sample_report, filters=filters
        )

        # Get report with same filters
        result = await analytics_cache.get_report("patient_summary", filters=filters)
        assert result is not None

        # Different filters should not exist
        different_filters = {"date_from": "2025-02-01"}
        result_diff = await analytics_cache.get_report(
            "patient_summary", filters=different_filters
        )
        assert result_diff is None

    @pytest.mark.asyncio
    async def test_invalidate_report(self, analytics_cache, sample_report):
        """Test report invalidation."""
        # Set report
        await analytics_cache.set_report("patient_summary", sample_report)

        # Verify it exists
        result = await analytics_cache.get_report("patient_summary")
        assert result is not None

        # Invalidate
        deleted = await analytics_cache.invalidate_report("patient_summary")
        assert deleted is True

        # Verify it's gone
        result = await analytics_cache.get_report("patient_summary")
        assert result is None


class TestDashboardsCaching:
    """Test dashboards caching functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_dashboard(self, analytics_cache, sample_dashboard):
        """Test setting and getting a dashboard."""
        # Set dashboard
        success = await analytics_cache.set_dashboard(
            "main_dashboard", sample_dashboard
        )
        assert success is True

        # Get dashboard
        result = await analytics_cache.get_dashboard("main_dashboard")
        assert result is not None
        assert len(result["widgets"]) == 2
        assert result["layout"] == "grid"

    @pytest.mark.asyncio
    async def test_dashboard_with_user_id(self, analytics_cache, sample_dashboard):
        """Test dashboard with user ID."""
        user_id = uuid4()

        # Set dashboard for user
        await analytics_cache.set_dashboard(
            "user_dashboard", sample_dashboard, user_id=user_id
        )

        # Get dashboard for user
        result = await analytics_cache.get_dashboard("user_dashboard", user_id=user_id)
        assert result is not None

        # Different user should not exist
        other_user_id = uuid4()
        result_other = await analytics_cache.get_dashboard(
            "user_dashboard", user_id=other_user_id
        )
        assert result_other is None

    @pytest.mark.asyncio
    async def test_invalidate_dashboard(self, analytics_cache, sample_dashboard):
        """Test dashboard invalidation."""
        user_id = uuid4()

        # Set dashboard
        await analytics_cache.set_dashboard(
            "user_dashboard", sample_dashboard, user_id=user_id
        )

        # Verify it exists
        result = await analytics_cache.get_dashboard("user_dashboard", user_id=user_id)
        assert result is not None

        # Invalidate
        deleted = await analytics_cache.invalidate_dashboard(
            "user_dashboard", user_id=user_id
        )
        assert deleted is True

        # Verify it's gone
        result = await analytics_cache.get_dashboard("user_dashboard", user_id=user_id)
        assert result is None


class TestAggregationsCaching:
    """Test aggregations caching functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_aggregation(self, analytics_cache):
        """Test setting and getting an aggregation."""
        aggregation_data = {
            "count": 100,
            "sum": 5000,
            "avg": 50,
        }

        # Set aggregation
        success = await analytics_cache.set_aggregation(
            "patients", "count", aggregation_data
        )
        assert success is True

        # Get aggregation
        result = await analytics_cache.get_aggregation("patients", "count")
        assert result is not None
        assert result["count"] == 100
        assert result["avg"] == 50

    @pytest.mark.asyncio
    async def test_aggregation_with_filters(self, analytics_cache):
        """Test aggregation with filters."""
        aggregation_data = {"count": 50}
        filters = {"status": "active"}

        # Set aggregation with filters
        await analytics_cache.set_aggregation(
            "patients", "count", aggregation_data, filters=filters
        )

        # Get aggregation with same filters
        result = await analytics_cache.get_aggregation(
            "patients", "count", filters=filters
        )
        assert result is not None
        assert result["count"] == 50

    @pytest.mark.asyncio
    async def test_aggregation_with_period(self, analytics_cache):
        """Test aggregation with time period."""
        aggregation_data = {"count": 30}

        # Set aggregation with period
        await analytics_cache.set_aggregation(
            "patients", "count", aggregation_data, period="daily"
        )

        # Get aggregation with period
        result = await analytics_cache.get_aggregation(
            "patients", "count", period="daily"
        )
        assert result is not None
        assert result["count"] == 30


class TestBulkOperations:
    """Test bulk operations."""

    @pytest.mark.asyncio
    async def test_invalidate_all_metrics(self, analytics_cache, sample_metric):
        """Test invalidating all metrics."""
        # Set multiple metrics
        await analytics_cache.set_metric("metric1", sample_metric)
        await analytics_cache.set_metric("metric2", sample_metric)

        # Invalidate all
        deleted = await analytics_cache.invalidate_all_metrics()
        assert deleted >= 2

        # Verify they're gone
        result1 = await analytics_cache.get_metric("metric1")
        result2 = await analytics_cache.get_metric("metric2")
        assert result1 is None
        assert result2 is None

    @pytest.mark.asyncio
    async def test_invalidate_all_reports(self, analytics_cache, sample_report):
        """Test invalidating all reports."""
        # Set multiple reports
        await analytics_cache.set_report("report1", sample_report)
        await analytics_cache.set_report("report2", sample_report)

        # Invalidate all
        deleted = await analytics_cache.invalidate_all_reports()
        assert deleted >= 2

    @pytest.mark.asyncio
    async def test_clear_all(self, analytics_cache, sample_metric, sample_report):
        """Test clearing all analytics cache."""
        # Set various items
        await analytics_cache.set_metric("metric1", sample_metric)
        await analytics_cache.set_report("report1", sample_report)
        await analytics_cache.increment_counter("counter1")

        # Clear all
        deleted = await analytics_cache.clear_all()
        assert deleted >= 3


class TestCacheStats:
    """Test cache statistics."""

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, analytics_cache, sample_metric, sample_report):
        """Test getting cache statistics."""
        # Set some data
        await analytics_cache.set_metric("metric1", sample_metric)
        await analytics_cache.set_report("report1", sample_report)
        await analytics_cache.increment_counter("counter1")

        # Get stats
        stats = await analytics_cache.get_cache_stats()
        assert "strategy" in stats
        assert "namespaces" in stats
        assert stats["namespaces"]["metrics"] >= 1
        assert stats["namespaces"]["reports"] >= 1
        assert stats["namespaces"]["counters"] >= 1


class TestSingleton:
    """Test singleton pattern."""

    def test_get_analytics_cache_singleton(self):
        """Test that get_analytics_cache returns singleton."""
        cache1 = get_analytics_cache()
        cache2 = get_analytics_cache()
        assert cache1 is cache2


class TestTTLs:
    """Test TTL functionality."""

    @pytest.mark.asyncio
    async def test_custom_ttl(self, analytics_cache, sample_metric):
        """Test custom TTL override."""
        # Set metric with custom TTL
        success = await analytics_cache.set_metric("short_lived", sample_metric, ttl=1)
        assert success is True

        # Immediately should exist
        result = await analytics_cache.get_metric("short_lived")
        assert result is not None

        # Note: Testing actual expiration requires waiting or mocking
        # In real tests, you might use freezegun or similar
