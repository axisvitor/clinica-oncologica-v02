"""
Tests for Enhanced Analytics API v2
Comprehensive test suite with 25+ tests covering all endpoints.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from unittest.mock import patch


class TestEnhancedDashboard:
    """Test suite for enhanced dashboard endpoint."""

    def test_get_enhanced_dashboard_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test enhanced dashboard retrieval."""
        response = client.get("/api/v2/enhanced-analytics/dashboard-enhanced", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "time_range" in data
        assert "period" in data
        assert "metrics" in data
        assert "risk_stratification" in data
        assert "treatment_distribution" in data
        assert "alerts" in data
        assert "generated_at" in data

        # Verify metrics structure
        metrics = data["metrics"]
        assert "total_patients" in metrics
        assert "active_patients" in metrics
        assert "new_patients" in metrics
        assert "patient_growth_rate" in metrics
        assert "engagement_score" in metrics

        # Verify data types
        assert isinstance(metrics["total_patients"], int)
        assert isinstance(metrics["engagement_score"], (int, float))

    def test_enhanced_dashboard_with_time_range(self, client: TestClient, db: Session, auth_headers: dict):
        """Test dashboard with different time ranges."""
        time_ranges = ["7d", "30d", "90d", "6m", "1y"]

        for time_range in time_ranges:
            response = client.get(
                f"/api/v2/enhanced-analytics/dashboard-enhanced?time_range={time_range}",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["time_range"] == time_range

    def test_enhanced_dashboard_with_predictions(self, client: TestClient, db: Session, auth_headers: dict):
        """Test dashboard with predictive insights enabled."""
        response = client.get(
            "/api/v2/enhanced-analytics/dashboard-enhanced?include_predictions=true",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data

    def test_enhanced_dashboard_field_selection(self, client: TestClient, db: Session, auth_headers: dict):
        """Test field selection parameter."""
        response = client.get(
            "/api/v2/enhanced-analytics/dashboard-enhanced?fields=metrics,alerts",
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_enhanced_dashboard_caching(self, client: TestClient, db: Session, auth_headers: dict):
        """Test that dashboard results are cached."""
        # First request
        response1 = client.get("/api/v2/enhanced-analytics/dashboard-enhanced", headers=auth_headers)
        assert response1.status_code == 200

        # Second request should hit cache
        response2 = client.get("/api/v2/enhanced-analytics/dashboard-enhanced", headers=auth_headers)
        assert response2.status_code == 200

        # Results should be identical
        assert response1.json() == response2.json()


class TestCohortAnalysis:
    """Test suite for cohort analysis endpoint."""

    def test_get_cohort_analysis_all(self, client: TestClient, db: Session, auth_headers: dict):
        """Test cohort analysis with 'all' filter."""
        response = client.get(
            "/api/v2/enhanced-analytics/cohort-analysis?cohort_filter=all",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "cohort_filter" in data
        assert "cohort_metrics" in data
        assert "demographics" in data
        assert "pagination" in data

        # Verify cohort metrics
        metrics = data["cohort_metrics"]
        assert "cohort_size" in metrics
        assert "avg_quizzes_per_patient" in metrics
        assert "completion_rate" in metrics

    def test_cohort_analysis_new_patients(self, client: TestClient, db: Session, auth_headers: dict):
        """Test new patients cohort filter."""
        response = client.get(
            "/api/v2/enhanced-analytics/cohort-analysis?cohort_filter=new_patients&time_range=30d",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cohort_filter"] == "new_patients"

    def test_cohort_analysis_high_engagement(self, client: TestClient, db: Session, auth_headers: dict):
        """Test high engagement cohort filter."""
        response = client.get(
            "/api/v2/enhanced-analytics/cohort-analysis?cohort_filter=high_engagement",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cohort_filter"] == "high_engagement"

    def test_cohort_analysis_with_treatment_filter(self, client: TestClient, db: Session, auth_headers: dict):
        """Test cohort analysis with treatment type filter."""
        response = client.get(
            "/api/v2/enhanced-analytics/cohort-analysis?treatment_type=Quimioterapia",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # Should respect treatment filter

    def test_cohort_analysis_pagination(self, client: TestClient, db: Session, auth_headers: dict):
        """Test cursor-based pagination."""
        # First page
        response1 = client.get(
            "/api/v2/enhanced-analytics/cohort-analysis?limit=10",
            headers=auth_headers
        )

        assert response1.status_code == 200
        data1 = response1.json()

        pagination = data1["pagination"]
        assert "next_cursor" in pagination
        assert "has_more" in pagination

        # Second page if available
        if pagination["next_cursor"]:
            response2 = client.get(
                f"/api/v2/enhanced-analytics/cohort-analysis?limit=10&cursor={pagination['next_cursor']}",
                headers=auth_headers
            )
            assert response2.status_code == 200


class TestEngagementFunnel:
    """Test suite for engagement funnel endpoint."""

    def test_get_engagement_funnel(self, client: TestClient, db: Session, auth_headers: dict):
        """Test engagement funnel retrieval."""
        response = client.get(
            "/api/v2/enhanced-analytics/engagement-funnel",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "funnel_stages" in data
        assert "overall_conversion" in data
        assert "total_enrolled" in data
        assert "total_converted" in data

        # Verify funnel stages
        stages = data["funnel_stages"]
        assert isinstance(stages, list)
        assert len(stages) == 5  # Should have 5 stages

        # Verify each stage has required fields
        for stage in stages:
            assert "stage" in stage
            assert "count" in stage
            assert "conversion_rate" in stage
            assert "drop_off_rate" in stage

    def test_engagement_funnel_stages_order(self, client: TestClient, db: Session, auth_headers: dict):
        """Test that funnel stages are in correct order."""
        response = client.get(
            "/api/v2/enhanced-analytics/engagement-funnel",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        stages = data["funnel_stages"]
        expected_stages = [
            "enrolled",
            "first_quiz_sent",
            "first_quiz_completed",
            "consistent_engagement",
            "high_engagement"
        ]

        actual_stages = [s["stage"] for s in stages]
        assert actual_stages == expected_stages

    def test_engagement_funnel_with_treatment_filter(self, client: TestClient, db: Session, auth_headers: dict):
        """Test funnel with treatment type filter."""
        response = client.get(
            "/api/v2/enhanced-analytics/engagement-funnel?treatment_type=Radioterapia",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("treatment_type") == "Radioterapia"

    def test_engagement_funnel_conversion_logic(self, client: TestClient, db: Session, auth_headers: dict):
        """Test that conversion rates decrease through funnel."""
        response = client.get(
            "/api/v2/enhanced-analytics/engagement-funnel",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        stages = data["funnel_stages"]
        # First stage should be 100%
        assert stages[0]["conversion_rate"] == 100.0

        # Counts should generally decrease
        for i in range(len(stages) - 1):
            assert stages[i]["count"] >= stages[i+1]["count"]


class TestPredictiveAnalytics:
    """Test suite for predictive analytics endpoint."""

    def test_get_predictive_analytics(self, client: TestClient, db: Session, auth_headers: dict):
        """Test predictive analytics generation."""
        response = client.get(
            "/api/v2/enhanced-analytics/predictive-analytics?metric_type=patients&forecast_days=30",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "metric_type" in data
        assert "forecast_period_days" in data
        assert "predictions" in data
        assert "trend_direction" in data
        assert "model_accuracy" in data

        # Verify predictions structure
        predictions = data["predictions"]
        assert isinstance(predictions, list)

        for pred in predictions:
            assert "date" in pred
            assert "predicted_value" in pred
            assert "confidence_score" in pred
            assert "lower_bound" in pred
            assert "upper_bound" in pred

            # Verify confidence is between 0 and 1
            assert 0 <= pred["confidence_score"] <= 1

    def test_predictive_analytics_different_metrics(self, client: TestClient, db: Session, auth_headers: dict):
        """Test predictions for different metric types."""
        metric_types = ["patients", "quiz", "engagement"]

        for metric_type in metric_types:
            response = client.get(
                f"/api/v2/enhanced-analytics/predictive-analytics?metric_type={metric_type}",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["metric_type"] == metric_type

    def test_predictive_analytics_forecast_periods(self, client: TestClient, db: Session, auth_headers: dict):
        """Test different forecast periods."""
        periods = [7, 30, 60, 90]

        for days in periods:
            response = client.get(
                f"/api/v2/enhanced-analytics/predictive-analytics?forecast_days={days}",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["forecast_period_days"] == days

    def test_predictive_analytics_confidence_filter(self, client: TestClient, db: Session, auth_headers: dict):
        """Test confidence threshold filtering."""
        response = client.get(
            "/api/v2/enhanced-analytics/predictive-analytics?confidence_threshold=0.8",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # All predictions should meet confidence threshold
        for pred in data["predictions"]:
            assert pred["confidence_score"] >= 0.8


class TestCustomMetrics:
    """Test suite for custom metrics endpoint."""

    def test_create_custom_metric(self, client: TestClient, db: Session, auth_headers: dict):
        """Test custom metric creation."""
        metric_def = {
            "name": "Test Metric",
            "description": "A test metric",
            "metric_type": "patients",
            "aggregation": "count",
            "filters": {}
        }

        response = client.post(
            "/api/v2/enhanced-analytics/custom-metrics",
            headers=auth_headers,
            json=metric_def
        )

        assert response.status_code == 200
        data = response.json()

        assert "metric_id" in data
        assert "name" in data
        assert "value" in data
        assert "status" in data
        assert data["status"] == "success"

    def test_custom_metric_validation(self, client: TestClient, db: Session, auth_headers: dict):
        """Test custom metric validation."""
        # Missing required fields
        invalid_metric = {
            "description": "Invalid metric"
        }

        response = client.post(
            "/api/v2/enhanced-analytics/custom-metrics",
            headers=auth_headers,
            json=invalid_metric
        )

        assert response.status_code == 422  # Validation error


class TestRealtimeStream:
    """Test suite for real-time analytics stream."""

    def test_get_realtime_stream(self, client: TestClient, db: Session, auth_headers: dict):
        """Test real-time stream retrieval."""
        response = client.get(
            "/api/v2/enhanced-analytics/realtime-stream",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "timestamp" in data
        assert "active_sessions" in data
        assert "recent_activity_1h" in data
        assert "system_health" in data
        assert "metrics" in data

        # Verify system health
        health = data["system_health"]
        assert "status" in health
        assert "response_time_ms" in health
        assert "error_rate" in health


class TestAnalyticsExport:
    """Test suite for analytics export endpoint."""

    def test_export_csv(self, client: TestClient, db: Session, auth_headers: dict):
        """Test CSV export."""
        response = client.get(
            "/api/v2/enhanced-analytics/export?metric_type=patients&export_format=csv",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

    def test_export_json(self, client: TestClient, db: Session, auth_headers: dict):
        """Test JSON export."""
        response = client.get(
            "/api/v2/enhanced-analytics/export?metric_type=patients&export_format=json",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_export_excel(self, client: TestClient, db: Session, auth_headers: dict):
        """Test Excel export."""
        response = client.get(
            "/api/v2/enhanced-analytics/export?metric_type=quiz&export_format=excel",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "spreadsheet" in response.headers["content-type"]

    def test_export_with_date_range(self, client: TestClient, db: Session, auth_headers: dict):
        """Test export with custom date range."""
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        end_date = datetime.utcnow().isoformat()

        response = client.get(
            f"/api/v2/enhanced-analytics/export?metric_type=patients&time_range=custom&start_date={start_date}&end_date={end_date}",
            headers=auth_headers
        )

        assert response.status_code == 200


class TestComparativeAnalytics:
    """Test suite for comparative analytics endpoint."""

    def test_get_comparative_analytics(self, client: TestClient, db: Session, auth_headers: dict):
        """Test comparative analytics retrieval."""
        current_start = (datetime.utcnow() - timedelta(days=30)).isoformat()
        current_end = datetime.utcnow().isoformat()
        compare_start = (datetime.utcnow() - timedelta(days=60)).isoformat()
        compare_end = (datetime.utcnow() - timedelta(days=30)).isoformat()

        response = client.get(
            f"/api/v2/enhanced-analytics/comparative?metric_type=patients&current_start={current_start}&current_end={current_end}&compare_start={compare_start}&compare_end={compare_end}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "metric_type" in data
        assert "current_period" in data
        assert "comparison_period" in data
        assert "change_metrics" in data

        # Verify change metrics
        changes = data["change_metrics"]
        assert "absolute_change" in changes
        assert "percent_change" in changes
        assert "trend" in changes
        assert changes["trend"] in ["up", "down", "stable"]

    def test_comparative_analytics_trend_calculation(self, client: TestClient, db: Session, auth_headers: dict):
        """Test trend direction calculation."""
        current_start = datetime.utcnow().isoformat()
        current_end = (datetime.utcnow() + timedelta(days=1)).isoformat()
        compare_start = (datetime.utcnow() - timedelta(days=2)).isoformat()
        compare_end = (datetime.utcnow() - timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v2/enhanced-analytics/comparative?metric_type=patients&current_start={current_start}&current_end={current_end}&compare_start={compare_start}&compare_end={compare_end}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify trend matches absolute change
        changes = data["change_metrics"]
        if changes["absolute_change"] > 0:
            assert changes["trend"] == "up"
        elif changes["absolute_change"] < 0:
            assert changes["trend"] == "down"
        else:
            assert changes["trend"] == "stable"


class TestEnhancedAnalyticsAuth:
    """Test suite for authentication and authorization."""

    def test_endpoints_require_authentication(self, client: TestClient, db: Session):
        """Test that all endpoints require authentication."""
        endpoints = [
            "/api/v2/enhanced-analytics/dashboard-enhanced",
            "/api/v2/enhanced-analytics/cohort-analysis",
            "/api/v2/enhanced-analytics/engagement-funnel",
            "/api/v2/enhanced-analytics/predictive-analytics",
            "/api/v2/enhanced-analytics/realtime-stream",
            "/api/v2/enhanced-analytics/export",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403], f"Endpoint {endpoint} should require auth"


class TestEnhancedAnalyticsPerformance:
    """Test suite for performance and caching."""

    @patch('app.api.v2.enhanced_analytics._get_cached_result')
    def test_cache_hit_performance(self, mock_cache, client: TestClient, db: Session, auth_headers: dict):
        """Test cache hit improves performance."""
        # Mock cache hit
        mock_cache.return_value = {
            "time_range": "30d",
            "metrics": {},
            "generated_at": datetime.utcnow().isoformat()
        }

        response = client.get(
            "/api/v2/enhanced-analytics/dashboard-enhanced",
            headers=auth_headers
        )

        assert response.status_code == 200
        # Cache should have been checked
        mock_cache.assert_called_once()

    def test_query_performance_with_filters(self, client: TestClient, db: Session, auth_headers: dict):
        """Test query performance with various filters."""
        # This test ensures queries complete in reasonable time
        import time

        start = time.time()
        response = client.get(
            "/api/v2/enhanced-analytics/cohort-analysis?cohort_filter=high_engagement&limit=50",
            headers=auth_headers
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        # Should complete in under 5 seconds even with complex filters
        assert elapsed < 5.0
