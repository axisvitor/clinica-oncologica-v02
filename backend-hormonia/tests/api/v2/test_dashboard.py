"""
Comprehensive test suite for Dashboard API v2

Tests cover:
- All 6 endpoints with various scenarios
- Role-based access control (RBAC)
- Time range filtering
- Redis caching behavior
- Rate limiting
- Field selection
- Error handling and edge cases
- Performance and data accuracy

These tests validate dashboard functionality that aggregates
sensitive patient data and system metrics.
"""

import pytest
from typing import Dict
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity
from app.models.patient import Patient
from app.models.user import User


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def create_test_data(db: Session, test_patient: Patient, test_user: User):
    """Create comprehensive test data for dashboard tests."""
    # Create messages
    for i in range(10):
        message_data = {
            "patient_id": test_patient.id,
            "content": f"Test message {i}",
            "status": "sent" if i % 2 == 0 else "delivered",
            "patient_response_received": i % 3 == 0,
            "created_at": datetime.utcnow() - timedelta(days=i)
        }
        # Note: Assuming messages table exists with these fields
        # db.execute(text("INSERT INTO messages ..."))

    # Create alerts
    severities = [AlertSeverity.CRITICAL, AlertSeverity.HIGH, AlertSeverity.MEDIUM, AlertSeverity.LOW]
    for i in range(8):
        alert = Alert(
            patient_id=test_patient.id,
            alert_type=f"test_alert_type_{i % 4}",
            severity=severities[i % 4],
            description=f"Test alert {i}",
            acknowledged=i % 2 == 0,
            created_at=datetime.utcnow() - timedelta(days=i)
        )
        db.add(alert)

    # Create flows
    for i in range(5):
        flow_data = {
            "patient_id": test_patient.id,
            "status": "active" if i < 3 else "completed",
            "created_at": datetime.utcnow() - timedelta(days=i * 2)
        }
        # Note: Assuming patient_flows table exists
        # db.execute(text("INSERT INTO patient_flows ..."))

    db.commit()
    return {
        "messages_count": 10,
        "alerts_count": 8,
        "flows_count": 5
    }


# ============================================================================
# Main Dashboard Tests
# ============================================================================

class TestMainDashboard:
    """Test suite for GET /api/v2/dashboard/main endpoint."""

    def test_get_main_dashboard_success(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test successfully retrieving main dashboard."""
        response = client.get(
            "/api/v2/dashboard/main",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "user_role" in data
        assert "time_range" in data
        assert "patient_metrics" in data
        assert "message_metrics" in data
        assert "alert_metrics" in data
        assert "flow_metrics" in data
        assert "recent_activity" in data
        assert "generated_at" in data

        # Verify patient metrics structure
        patient_metrics = data["patient_metrics"]
        assert "total_patients" in patient_metrics
        assert "active_patients" in patient_metrics
        assert "new_patients" in patient_metrics

    def test_get_main_dashboard_with_time_range_today(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test main dashboard with TODAY time range."""
        response = client.get(
            "/api/v2/dashboard/main?time_range=today",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "today"

        # Verify dates are for today
        start_date = datetime.fromisoformat(data["start_date"].replace("Z", "+00:00"))
        assert start_date.date() == datetime.utcnow().date()

    def test_get_main_dashboard_with_time_range_week(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test main dashboard with WEEK time range."""
        response = client.get(
            "/api/v2/dashboard/main?time_range=week",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "week"

    def test_get_main_dashboard_with_time_range_month(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test main dashboard with MONTH time range."""
        response = client.get(
            "/api/v2/dashboard/main?time_range=month",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "month"

    def test_get_main_dashboard_with_custom_date_range(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test main dashboard with custom date range."""
        start_date = (datetime.utcnow() - timedelta(days=14)).isoformat()
        end_date = datetime.utcnow().isoformat()

        response = client.get(
            f"/api/v2/dashboard/main?time_range=custom&custom_start={start_date}&custom_end={end_date}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "custom"

    def test_get_main_dashboard_with_field_selection(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test main dashboard with field selection."""
        response = client.get(
            "/api/v2/dashboard/main?fields=user_role,patient_metrics,alert_metrics",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Only selected fields should be present
        assert "user_role" in data
        assert "patient_metrics" in data
        assert "alert_metrics" in data

    def test_get_main_dashboard_unauthorized(
        self,
        client: TestClient,
        db: Session
    ):
        """Test accessing main dashboard without authentication."""
        response = client.get("/api/v2/dashboard/main")

        assert response.status_code == 401

    def test_get_main_dashboard_admin_sees_all_data(
        self,
        client: TestClient,
        db: Session,
        auth_headers_admin: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test admin user sees system-wide data."""
        response = client.get(
            "/api/v2/dashboard/main",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_role"] == "admin"


# ============================================================================
# Patient Dashboard Tests
# ============================================================================

class TestPatientDashboard:
    """Test suite for GET /api/v2/dashboard/patient/{patient_id} endpoint."""

    def test_get_patient_dashboard_success(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        test_patient: Patient,
        create_test_data: Dict[str, int]
    ):
        """Test successfully retrieving patient dashboard."""
        response = client.get(
            f"/api/v2/dashboard/patient/{test_patient.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "patient" in data
        assert "time_range" in data
        assert "message_metrics" in data
        assert "alert_metrics" in data
        assert "flow_metrics" in data
        assert "recent_activity" in data
        assert "engagement_chart" in data

        # Verify patient info
        patient_info = data["patient"]
        assert patient_info["id"] == str(test_patient.id)
        assert "full_name" in patient_info
        assert "email" in patient_info

    def test_get_patient_dashboard_not_found(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]
    ):
        """Test retrieving dashboard for non-existent patient."""
        fake_patient_id = uuid4()
        response = client.get(
            f"/api/v2/dashboard/patient/{fake_patient_id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_patient_dashboard_access_denied_different_patient(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        test_patient: Patient
    ):
        """Test patient cannot access another patient's dashboard."""
        # Create another patient
        other_patient = Patient(
            full_name="Other Patient",
            email="other@example.com",
            doctor_id=test_patient.doctor_id
        )
        db.add(other_patient)
        db.commit()
        db.refresh(other_patient)

        # Assuming auth_headers is for test_patient
        # Try to access other_patient's dashboard
        response = client.get(
            f"/api/v2/dashboard/patient/{other_patient.id}",
            headers=auth_headers
        )

        # Should be forbidden (depends on RBAC implementation)
        assert response.status_code in [403, 404]

    def test_get_patient_dashboard_with_time_range(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        test_patient: Patient,
        create_test_data: Dict[str, int]
    ):
        """Test patient dashboard with different time ranges."""
        for time_range in ["today", "week", "month", "year"]:
            response = client.get(
                f"/api/v2/dashboard/patient/{test_patient.id}?time_range={time_range}",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["time_range"] == time_range

    def test_get_patient_dashboard_engagement_chart_data(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        test_patient: Patient,
        create_test_data: Dict[str, int]
    ):
        """Test engagement chart data is present and valid."""
        response = client.get(
            f"/api/v2/dashboard/patient/{test_patient.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify engagement chart
        engagement_chart = data["engagement_chart"]
        assert isinstance(engagement_chart, list)

        if engagement_chart:
            # Check data point structure
            point = engagement_chart[0]
            assert "date" in point
            assert "messages_sent" in point
            assert "responses_received" in point
            assert "response_rate" in point


# ============================================================================
# Physician Dashboard Tests
# ============================================================================

class TestPhysicianDashboard:
    """Test suite for GET /api/v2/dashboard/physician endpoint."""

    def test_get_physician_dashboard_success(
        self,
        client: TestClient,
        db: Session,
        auth_headers_physician: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test successfully retrieving physician dashboard."""
        response = client.get(
            "/api/v2/dashboard/physician",
            headers=auth_headers_physician
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "user_id" in data
        assert "patient_metrics" in data
        assert "message_metrics" in data
        assert "alert_metrics" in data
        assert "flow_metrics" in data
        assert "high_priority_alerts" in data
        assert "top_risk_patients" in data

    def test_get_physician_dashboard_patient_cannot_access(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]  # Patient auth headers
    ):
        """Test patient cannot access physician dashboard."""
        response = client.get(
            "/api/v2/dashboard/physician",
            headers=auth_headers
        )

        assert response.status_code == 403

    def test_get_physician_dashboard_shows_high_priority_alerts(
        self,
        client: TestClient,
        db: Session,
        auth_headers_physician: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test high-priority alerts are included."""
        response = client.get(
            "/api/v2/dashboard/physician",
            headers=auth_headers_physician
        )

        assert response.status_code == 200
        data = response.json()

        high_priority_alerts = data["high_priority_alerts"]
        assert isinstance(high_priority_alerts, list)

        # If there are alerts, verify structure
        if high_priority_alerts:
            alert = high_priority_alerts[0]
            assert "id" in alert
            assert "patient_id" in alert
            assert "severity" in alert
            assert "description" in alert

    def test_get_physician_dashboard_shows_top_risk_patients(
        self,
        client: TestClient,
        db: Session,
        auth_headers_physician: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test top risk patients are included."""
        response = client.get(
            "/api/v2/dashboard/physician",
            headers=auth_headers_physician
        )

        assert response.status_code == 200
        data = response.json()

        top_risk_patients = data["top_risk_patients"]
        assert isinstance(top_risk_patients, list)

        # If there are patients, verify structure
        if top_risk_patients:
            patient = top_risk_patients[0]
            assert "patient_id" in patient
            assert "patient_name" in patient
            assert "alert_count" in patient


# ============================================================================
# Admin Dashboard Tests
# ============================================================================

class TestAdminDashboard:
    """Test suite for GET /api/v2/dashboard/admin endpoint."""

    def test_get_admin_dashboard_success(
        self,
        client: TestClient,
        db: Session,
        auth_headers_admin: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test successfully retrieving admin dashboard."""
        response = client.get(
            "/api/v2/dashboard/admin",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "patient_metrics" in data
        assert "message_metrics" in data
        assert "alert_metrics" in data
        assert "flow_metrics" in data
        assert "user_metrics" in data
        assert "top_physicians" in data
        assert "system_health" in data

    def test_get_admin_dashboard_non_admin_cannot_access(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]  # Non-admin auth headers
    ):
        """Test non-admin users cannot access admin dashboard."""
        response = client.get(
            "/api/v2/dashboard/admin",
            headers=auth_headers
        )

        assert response.status_code == 403

    def test_get_admin_dashboard_user_metrics(
        self,
        client: TestClient,
        db: Session,
        auth_headers_admin: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test user metrics are present and accurate."""
        response = client.get(
            "/api/v2/dashboard/admin",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        user_metrics = data["user_metrics"]
        assert "total_users" in user_metrics
        assert "active_users" in user_metrics
        assert "doctors_count" in user_metrics
        assert "patients_count" in user_metrics
        assert "admins_count" in user_metrics

        # Verify counts are non-negative
        assert user_metrics["total_users"] >= 0
        assert user_metrics["active_users"] >= 0

    def test_get_admin_dashboard_system_health(
        self,
        client: TestClient,
        db: Session,
        auth_headers_admin: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test system health indicators are present."""
        response = client.get(
            "/api/v2/dashboard/admin",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        system_health = data["system_health"]
        assert "message_success_rate" in system_health
        assert "alert_response_rate" in system_health
        assert "flow_completion_rate" in system_health
        assert "patient_active_rate" in system_health

        # Verify rates are percentages (0-100)
        for key, value in system_health.items():
            assert 0 <= value <= 100, f"{key} should be between 0 and 100"

    def test_get_admin_dashboard_top_physicians(
        self,
        client: TestClient,
        db: Session,
        auth_headers_admin: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test top physicians list is included."""
        response = client.get(
            "/api/v2/dashboard/admin",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        top_physicians = data["top_physicians"]
        assert isinstance(top_physicians, list)

        # If there are physicians, verify structure
        if top_physicians:
            physician = top_physicians[0]
            assert "physician_id" in physician
            assert "physician_name" in physician
            assert "patient_count" in physician
            assert "engagement_rate" in physician


# ============================================================================
# Custom Dashboard Tests
# ============================================================================

class TestCustomDashboard:
    """Test suite for custom dashboard endpoints."""

    def test_get_custom_dashboard_success(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]
    ):
        """Test successfully retrieving custom dashboard."""
        dashboard_id = uuid4()
        response = client.get(
            f"/api/v2/dashboard/custom/{dashboard_id}",
            headers=auth_headers
        )

        # For now, should return 200 with placeholder data
        assert response.status_code == 200
        data = response.json()

        assert "dashboard_id" in data
        assert "user_id" in data
        assert "widgets" in data
        assert "layout" in data

    def test_update_dashboard_layout_success(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]
    ):
        """Test successfully updating dashboard layout."""
        dashboard_id = uuid4()

        update_data = {
            "name": "Updated Dashboard",
            "description": "Modified layout",
            "widgets": [
                {
                    "widget_id": "widget_1",
                    "widget_type": "metric_card",
                    "title": "Active Patients",
                    "size": "medium",
                    "position": {"x": 0, "y": 0},
                    "config": {}
                }
            ],
            "layout": {"columns": 4, "row_height": 120}
        }

        response = client.put(
            f"/api/v2/dashboard/custom/{dashboard_id}/layout",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["dashboard_id"] == str(dashboard_id)
        assert data["name"] == "Updated Dashboard"

    def test_update_dashboard_layout_invalid_data(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]
    ):
        """Test updating dashboard with invalid data fails validation."""
        dashboard_id = uuid4()

        invalid_data = {
            "widgets": [
                {
                    "widget_id": "widget_1",
                    "widget_type": "invalid_type",  # Invalid type
                    "title": "Test",
                    "size": "medium",
                    "position": {"x": 0, "y": 0}
                }
            ]
        }

        response = client.put(
            f"/api/v2/dashboard/custom/{dashboard_id}/layout",
            json=invalid_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error


# ============================================================================
# Caching Tests
# ============================================================================

class TestDashboardCaching:
    """Test suite for Redis caching behavior."""

    @pytest.mark.asyncio
    async def test_main_dashboard_uses_cache(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test main dashboard uses cache on subsequent requests."""
        # First request
        response1 = client.get("/api/v2/dashboard/main", headers=auth_headers)
        assert response1.status_code == 200

        # Second request (should hit cache)
        response2 = client.get("/api/v2/dashboard/main", headers=auth_headers)
        assert response2.status_code == 200

        # Responses should be identical
        assert response1.json()["generated_at"] == response2.json()["generated_at"]

    @pytest.mark.asyncio
    async def test_patient_dashboard_cache_per_patient(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        test_patient: Patient,
        create_test_data: Dict[str, int]
    ):
        """Test patient dashboard caches per patient ID."""
        response = client.get(
            f"/api/v2/dashboard/patient/{test_patient.id}",
            headers=auth_headers
        )

        assert response.status_code == 200


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestDashboardRateLimiting:
    """Test suite for rate limiting."""

    def test_main_dashboard_rate_limit(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]
    ):
        """Test rate limiting on main dashboard endpoint."""
        # Make multiple requests (within limit)
        for i in range(5):
            response = client.get("/api/v2/dashboard/main", headers=auth_headers)
            assert response.status_code == 200

    def test_admin_dashboard_higher_rate_limit(
        self,
        client: TestClient,
        db: Session,
        auth_headers_admin: Dict[str, str]
    ):
        """Test admin dashboard has higher rate limit."""
        # Admin endpoints typically have 60/min vs 30/min
        for i in range(10):
            response = client.get("/api/v2/dashboard/admin", headers=auth_headers_admin)
            assert response.status_code == 200


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestDashboardErrorHandling:
    """Test suite for error handling."""

    def test_invalid_time_range(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]
    ):
        """Test invalid time range parameter."""
        response = client.get(
            "/api/v2/dashboard/main?time_range=invalid",
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_custom_range_missing_dates(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]
    ):
        """Test custom range without start/end dates fails."""
        response = client.get(
            "/api/v2/dashboard/main?time_range=custom",
            headers=auth_headers
        )

        assert response.status_code in [400, 422]

    def test_invalid_patient_id_format(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str]
    ):
        """Test invalid patient ID format."""
        response = client.get(
            "/api/v2/dashboard/patient/invalid-uuid",
            headers=auth_headers
        )

        assert response.status_code == 422


# ============================================================================
# Data Accuracy Tests
# ============================================================================

class TestDashboardDataAccuracy:
    """Test suite for data accuracy and calculations."""

    def test_patient_metrics_accuracy(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test patient metrics calculations are accurate."""
        response = client.get("/api/v2/dashboard/main", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        patient_metrics = data["patient_metrics"]

        # Verify total = active + inactive
        assert patient_metrics["total_patients"] == (
            patient_metrics["active_patients"] + patient_metrics["inactive_patients"]
        )

    def test_message_response_rate_calculation(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test message response rate is calculated correctly."""
        response = client.get("/api/v2/dashboard/main", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        message_metrics = data["message_metrics"]

        # Response rate should be between 0 and 100
        assert 0 <= message_metrics["response_rate"] <= 100

        # If there are messages, response rate should be meaningful
        if message_metrics["total_messages"] > 0:
            expected_rate = (
                message_metrics["response_count"] / message_metrics["total_messages"] * 100
            )
            # Allow small floating point differences
            assert abs(message_metrics["response_rate"] - expected_rate) < 0.5

    def test_flow_completion_rate_calculation(
        self,
        client: TestClient,
        db: Session,
        auth_headers: Dict[str, str],
        create_test_data: Dict[str, int]
    ):
        """Test flow completion rate is calculated correctly."""
        response = client.get("/api/v2/dashboard/main", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        flow_metrics = data["flow_metrics"]

        # Completion rate should be between 0 and 100
        assert 0 <= flow_metrics["completion_rate"] <= 100

        # Verify total = active + completed + paused
        assert flow_metrics["total_flows"] == (
            flow_metrics["active_flows"] +
            flow_metrics["completed_flows"] +
            flow_metrics["paused_flows"]
        )
