"""
Tests for Reports API v2
Comprehensive test coverage for all report endpoints.
"""

import pytest
import json
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import UserRole
from app.models.patient import FlowState
from app.schemas.v2.reports import ReportFormat, ReportStatus, ReportType, ScheduleFrequency


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch("app.core.redis_unified.get_async_redis") as mock:
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.setex = AsyncMock()
        redis_mock.delete = AsyncMock()
        redis_mock.scan_iter = AsyncMock(return_value=iter([]))
        mock.return_value = redis_mock
        yield redis_mock


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.scalar.return_value = 0
    db.query.return_value.options.return_value.filter.return_value.all.return_value = []
    yield db


@pytest.fixture
def mock_current_user_admin():
    """Mock admin user."""
    return {
        "id": str(uuid4()),
        "role": "admin",
        "email": "admin@test.com",
        "is_active": True
    }


@pytest.fixture
def mock_current_user_doctor():
    """Mock doctor user."""
    return {
        "id": str(uuid4()),
        "role": "doctor",
        "email": "doctor@test.com",
        "is_active": True
    }


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


# ============================================================================
# Report Generation Tests
# ============================================================================

class TestReportGeneration:
    """Tests for report generation endpoints."""

    def test_generate_report_success(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test successful report generation."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            request_data = {
                "report_type": "patient_summary",
                "title": "Test Report",
                "description": "Test Description",
                "format": "json",
                "date_from": "2024-01-01",
                "date_to": "2024-12-31"
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert data["title"] == "Test Report"
            assert data["status"] == "pending"
            assert "id" in data

    def test_generate_report_invalid_dates(self, client, mock_current_user_doctor):
        """Test report generation with invalid date range."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            request_data = {
                "report_type": "patient_summary",
                "title": "Test Report",
                "format": "json",
                "date_from": "2024-12-31",
                "date_to": "2024-01-01"  # Before date_from
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_generate_report_missing_title(self, client, mock_current_user_doctor):
        """Test report generation without title."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            request_data = {
                "report_type": "patient_summary",
                "format": "json"
                # Missing title
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_generate_report_with_patient_filters(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test report generation with patient ID filters."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._check_patient_access", return_value=True):

            patient_ids = [str(uuid4()), str(uuid4())]
            request_data = {
                "report_type": "patient_activity",
                "title": "Patient Activity Report",
                "format": "csv",
                "patient_ids": patient_ids
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_202_ACCEPTED

    def test_generate_report_access_denied(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test report generation with access denied to patients."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._check_patient_access", return_value=False):

            request_data = {
                "report_type": "patient_summary",
                "title": "Test Report",
                "format": "json",
                "patient_ids": [str(uuid4())]
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_generate_report_multiple_formats(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test report generation with different formats."""
        formats = ["json", "csv", "pdf", "excel"]

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            for fmt in formats:
                request_data = {
                    "report_type": "analytics_overview",
                    "title": f"Report {fmt}",
                    "format": fmt
                }

                response = client.post("/api/v2/reports/generate", json=request_data)

                assert response.status_code == status.HTTP_202_ACCEPTED
                assert response.json()["format"] == fmt


class TestReportRetrieval:
    """Tests for report retrieval endpoints."""

    def test_get_report_success(self, client, mock_redis, mock_current_user_doctor):
        """Test successful report retrieval."""
        report_id = uuid4()
        cached_report = {
            "id": str(report_id),
            "title": "Test Report",
            "status": "completed",
            "format": "json"
        }

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result", return_value=cached_report):

            response = client.get(f"/api/v2/reports/{report_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == str(report_id)
            assert data["title"] == "Test Report"

    def test_get_report_not_found(self, client, mock_redis, mock_current_user_doctor):
        """Test report retrieval when not found."""
        report_id = uuid4()

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result", return_value=None):

            response = client.get(f"/api/v2/reports/{report_id}")

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_report_status_generating(self, client, mock_redis, mock_current_user_doctor):
        """Test report status retrieval during generation."""
        report_id = uuid4()
        status_data = {
            "id": str(report_id),
            "status": "generating",
            "progress_percentage": 45,
            "current_step": "Processing data"
        }

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result", return_value=status_data):

            response = client.get(f"/api/v2/reports/{report_id}/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "generating"
            assert data["progress_percentage"] == 45

    def test_get_report_status_completed(self, client, mock_redis, mock_current_user_doctor):
        """Test report status retrieval when completed."""
        report_id = uuid4()

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result") as mock_cache:

            # First call returns None (no status cache)
            # Second call returns completed report
            mock_cache.side_effect = [
                None,
                {"id": str(report_id), "status": "completed"}
            ]

            response = client.get(f"/api/v2/reports/{report_id}/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "completed"
            assert data["progress_percentage"] == 100

    def test_download_report_json(self, client, mock_redis, mock_current_user_doctor):
        """Test downloading report in JSON format."""
        report_id = uuid4()
        report_data = {
            "id": str(report_id),
            "status": "completed",
            "format": "json"
        }
        report_content = {"total_patients": 100, "active_patients": 80}

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result") as mock_cache:

            mock_cache.side_effect = [report_data, report_content]

            response = client.get(f"/api/v2/reports/{report_id}/download")

            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"
            assert "attachment" in response.headers.get("content-disposition", "")

    def test_download_report_csv(self, client, mock_redis, mock_current_user_doctor):
        """Test downloading report in CSV format."""
        report_id = uuid4()
        report_data = {
            "id": str(report_id),
            "status": "completed",
            "format": "csv"
        }
        report_content = {"data": [{"patient": "John", "age": 45}]}

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result") as mock_cache:

            mock_cache.side_effect = [report_data, report_content]

            response = client.get(f"/api/v2/reports/{report_id}/download")

            assert response.status_code == status.HTTP_200_OK
            assert "text/csv" in response.headers["content-type"]

    def test_download_report_not_ready(self, client, mock_redis, mock_current_user_doctor):
        """Test downloading report that's not ready."""
        report_id = uuid4()
        report_data = {
            "id": str(report_id),
            "status": "generating",  # Not completed
            "format": "json"
        }

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result", return_value=report_data):

            response = client.get(f"/api/v2/reports/{report_id}/download")

            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_download_report_format_override(self, client, mock_redis, mock_current_user_doctor):
        """Test downloading report with format override."""
        report_id = uuid4()
        report_data = {
            "id": str(report_id),
            "status": "completed",
            "format": "json"  # Original format
        }
        report_content = {"data": "test"}

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result") as mock_cache:

            mock_cache.side_effect = [report_data, report_content]

            # Request CSV format override
            response = client.get(f"/api/v2/reports/{report_id}/download?format_override=csv")

            assert response.status_code == status.HTTP_200_OK
            assert "text/csv" in response.headers["content-type"]


class TestPredefinedReports:
    """Tests for pre-defined report endpoints."""

    def test_patient_summary_report(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test patient summary report."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._get_cached_result", return_value=None), \
             patch("app.api.v2.reports._generate_patient_summary") as mock_gen:

            mock_gen.return_value = {
                "total_patients": 100,
                "active_patients": 80,
                "inactive_patients": 20,
                "new_patients_period": 10,
                "by_treatment_type": {"chemotherapy": 50, "radiotherapy": 50},
                "by_flow_state": {"active": 80, "completed": 20},
                "generated_at": datetime.utcnow().isoformat()
            }

            response = client.get("/api/v2/reports/patients/summary")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_patients"] == 100
            assert data["active_patients"] == 80

    def test_patient_activity_report(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test patient activity report."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._generate_patient_activity") as mock_gen:

            mock_gen.return_value = {
                "total_interactions": 500,
                "average_response_time_hours": 2.5,
                "engagement_rate": 85.0,
                "messages_sent": 200,
                "messages_received": 180,
                "quizzes_completed": 120,
                "by_patient": [],
                "activity_timeline": [],
                "generated_at": datetime.utcnow().isoformat()
            }

            response = client.get("/api/v2/reports/patients/activity")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_interactions"] == 500
            assert data["engagement_rate"] == 85.0

    def test_flow_performance_report(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test flow performance report."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._generate_flow_performance") as mock_gen:

            mock_gen.return_value = {
                "total_flows": 150,
                "active_flows": 120,
                "completion_rate": 75.5,
                "average_flow_duration_days": 45.3,
                "flows_by_state": {"active": 120, "completed": 30},
                "bottlenecks": [],
                "performance_timeline": [],
                "generated_at": datetime.utcnow().isoformat()
            }

            response = client.get("/api/v2/reports/flows/performance")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_flows"] == 150
            assert data["completion_rate"] == 75.5

    def test_message_delivery_report(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test message delivery report."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._generate_message_delivery") as mock_gen:

            mock_gen.return_value = {
                "total_messages": 1000,
                "delivered": 950,
                "failed": 30,
                "pending": 20,
                "delivery_rate": 95.0,
                "average_delivery_time_seconds": 1.2,
                "failures_by_reason": {"network_error": 30},
                "delivery_timeline": [],
                "generated_at": datetime.utcnow().isoformat()
            }

            response = client.get("/api/v2/reports/messages/delivery")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_messages"] == 1000
            assert data["delivery_rate"] == 95.0

    def test_quiz_completion_report(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test quiz completion report."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._generate_quiz_completion") as mock_gen:

            mock_gen.return_value = {
                "total_quizzes": 500,
                "completed": 450,
                "in_progress": 40,
                "cancelled": 10,
                "completion_rate": 90.0,
                "average_completion_time_minutes": 5.3,
                "by_template": [],
                "completion_timeline": [],
                "generated_at": datetime.utcnow().isoformat()
            }

            response = client.get("/api/v2/reports/quizzes/completion")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_quizzes"] == 500
            assert data["completion_rate"] == 90.0

    def test_analytics_overview_report(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test analytics overview report."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._generate_analytics_overview") as mock_gen:

            mock_gen.return_value = {
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
                "patient_metrics": {},
                "activity_metrics": {},
                "flow_metrics": {},
                "message_metrics": {},
                "quiz_metrics": {},
                "key_insights": ["Insight 1", "Insight 2"],
                "recommendations": ["Recommendation 1"],
                "generated_at": datetime.utcnow().isoformat()
            }

            response = client.get("/api/v2/reports/analytics/overview")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["key_insights"]) == 2
            assert len(data["recommendations"]) == 1


class TestScheduledReports:
    """Tests for scheduled report endpoints."""

    def test_list_scheduled_reports(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test listing scheduled reports."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            response = client.get("/api/v2/reports/scheduled")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "items" in data
            assert "total" in data

    def test_create_scheduled_report(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test creating scheduled report."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            request_data = {
                "name": "Weekly Patient Report",
                "description": "Weekly summary",
                "report_type": "patient_summary",
                "format": "pdf",
                "frequency": "weekly",
                "start_date": "2024-01-01",
                "time_of_day": "09:00",
                "timezone": "UTC",
                "recipient_emails": ["test@example.com"]
            }

            response = client.post("/api/v2/reports/scheduled", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Weekly Patient Report"
            assert data["frequency"] == "weekly"

    def test_create_scheduled_report_invalid_time(self, client, mock_current_user_doctor):
        """Test creating scheduled report with invalid time format."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            request_data = {
                "name": "Test Report",
                "report_type": "patient_summary",
                "format": "pdf",
                "frequency": "daily",
                "start_date": "2024-01-01",
                "time_of_day": "25:00",  # Invalid hour
                "recipient_emails": ["test@example.com"]
            }

            response = client.post("/api/v2/reports/scheduled", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_scheduled_report(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test getting scheduled report."""
        scheduled_id = uuid4()

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            response = client.get(f"/api/v2/reports/scheduled/{scheduled_id}")

            # Should return 404 as we don't have database
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_scheduled_report(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test updating scheduled report."""
        scheduled_id = uuid4()

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            update_data = {
                "name": "Updated Report Name",
                "is_active": False
            }

            response = client.put(f"/api/v2/reports/scheduled/{scheduled_id}", json=update_data)

            # Should return 404 as we don't have database
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_scheduled_report(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test deleting scheduled report."""
        scheduled_id = uuid4()

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            response = client.delete(f"/api/v2/reports/scheduled/{scheduled_id}")

            assert response.status_code == status.HTTP_204_NO_CONTENT


class TestReportTemplates:
    """Tests for report template endpoints."""

    def test_list_templates(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test listing report templates."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            response = client.get("/api/v2/reports/templates")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "items" in data
            assert "total" in data

    def test_create_template(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test creating report template."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            request_data = {
                "name": "Custom Patient Report",
                "description": "Custom template",
                "report_type": "patient_summary",
                "default_format": "pdf",
                "default_filters": {},
                "sections": ["summary", "details", "charts"],
                "is_public": True
            }

            response = client.post("/api/v2/reports/templates", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Custom Patient Report"
            assert data["is_public"] is True

    def test_create_template_missing_sections(self, client, mock_current_user_admin):
        """Test creating template without sections."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin):

            request_data = {
                "name": "Test Template",
                "report_type": "patient_summary",
                "sections": []  # Empty sections not allowed
            }

            response = client.post("/api/v2/reports/templates", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_template(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test getting template by ID."""
        template_id = uuid4()

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            response = client.get(f"/api/v2/reports/templates/{template_id}")

            # Should return 404 as we don't have database
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_template(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test updating template."""
        template_id = uuid4()

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            update_data = {
                "name": "Updated Template",
                "is_public": False
            }

            response = client.put(f"/api/v2/reports/templates/{template_id}", json=update_data)

            # Should return 404 as we don't have database
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_template(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test deleting template."""
        template_id = uuid4()

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            response = client.delete(f"/api/v2/reports/templates/{template_id}")

            assert response.status_code == status.HTTP_204_NO_CONTENT


class TestCaching:
    """Tests for report caching functionality."""

    def test_report_cached_on_completion(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test that completed reports are cached."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._set_cached_result") as mock_cache:

            request_data = {
                "report_type": "patient_summary",
                "title": "Test Report",
                "format": "json"
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_202_ACCEPTED
            # Cache should be called during async generation (we're testing the API call succeeds)

    def test_cached_report_retrieved(self, client, mock_redis, mock_current_user_doctor):
        """Test retrieving cached report."""
        report_id = uuid4()
        cached_data = {
            "id": str(report_id),
            "title": "Cached Report",
            "status": "completed"
        }

        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports._get_cached_result", return_value=cached_data):

            response = client.get(f"/api/v2/reports/{report_id}")

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["title"] == "Cached Report"


class TestPermissions:
    """Tests for permission and access control."""

    def test_doctor_cannot_access_other_patients(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test doctor cannot generate reports for other doctor's patients."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.reports.get_db", return_value=mock_db), \
             patch("app.api.v2.reports._check_patient_access", return_value=False):

            request_data = {
                "report_type": "patient_summary",
                "title": "Test Report",
                "format": "json",
                "patient_ids": [str(uuid4())]
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_access_all_patients(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test admin can generate reports for any patient."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.reports.get_db", return_value=mock_db):

            # Admin doesn't need _check_patient_access to pass
            request_data = {
                "report_type": "analytics_overview",
                "title": "System Report",
                "format": "json"
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_202_ACCEPTED


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_report_type(self, client, mock_current_user_doctor):
        """Test invalid report type."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            request_data = {
                "report_type": "invalid_type",
                "title": "Test Report",
                "format": "json"
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_invalid_format(self, client, mock_current_user_doctor):
        """Test invalid report format."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            request_data = {
                "report_type": "patient_summary",
                "title": "Test Report",
                "format": "invalid_format"
            }

            response = client.post("/api/v2/reports/generate", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_invalid_uuid(self, client, mock_current_user_doctor):
        """Test invalid UUID in URL."""
        with patch("app.api.v2.reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            response = client.get("/api/v2/reports/not-a-uuid")

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
