"""
Tests for Enhanced Reports API v2
Comprehensive test coverage for advanced reporting features.

Tests cover:
- Custom report builder with drag-and-drop fields
- Advanced data visualization
- Scheduled delivery (email, webhook)
- Report sharing and permissions
- Multi-format export (PDF, Excel, PowerPoint)
- Report versioning and history
- Interactive dashboards
"""

import json

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi import status
from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch("app.core.redis_manager.get_async_redis_client") as mock, \
         patch("app.services.cache.json_cache_mixin.get_async_redis") as cache_get_redis, \
         patch("app.services.reporting.enhanced_reports_service.get_async_redis") as service_get_redis:
        redis_mock = AsyncMock()
        async def _empty_scan_iter(*args, **kwargs):
            _ = args, kwargs
            if False:
                yield None

        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.setex = AsyncMock()
        redis_mock.delete = AsyncMock()
        redis_mock.scan_iter = _empty_scan_iter
        mock.return_value = redis_mock
        cache_get_redis.return_value = redis_mock
        service_get_redis.return_value = redis_mock
        yield redis_mock


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.scalar.return_value = 0
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


# ============================================================================
# Report Builder Tests
# ============================================================================

class TestReportBuilder:
    """Tests for custom report builder endpoints."""

    def test_build_custom_report_success(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test successful custom report building."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            request_data = {
                "name": "Custom Patient Report",
                "description": "Patient data with custom fields",
                "fields": [
                    {
                        "field_name": "patient_count",
                        "display_name": "Total Patients",
                        "field_type": "number",
                        "data_source": "patients",
                        "aggregation": "count"
                    },
                    {
                        "field_name": "treatment_type",
                        "display_name": "Treatment",
                        "field_type": "text",
                        "data_source": "patients"
                    }
                ],
                "filters": {"active": True},
                "include_totals": True
            }

            response = client.post("/api/v2/enhanced-reports/builder", json=request_data)

            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert data["name"] == "Custom Patient Report"
            assert len(data["fields"]) == 2
            assert "id" in data

    def test_build_report_invalid_data_source(self, client, mock_current_user_doctor):
        """Test report builder with invalid data source."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            request_data = {
                "name": "Invalid Report",
                "fields": [
                    {
                        "field_name": "test_field",
                        "display_name": "Test",
                        "field_type": "text",
                        "data_source": "invalid_source"  # Invalid
                    }
                ]
            }

            response = client.post("/api/v2/enhanced-reports/builder", json=request_data)

            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_build_report_with_grouping_and_sorting(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test report builder with grouping and sorting."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            request_data = {
                "name": "Grouped Report",
                "fields": [
                    {
                        "field_name": "treatment_type",
                        "display_name": "Treatment",
                        "field_type": "text",
                        "data_source": "patients"
                    }
                ],
                "group_by": ["treatment_type"],
                "sort_by": [{"treatment_type": "asc"}],
                "include_subtotals": True
            }

            response = client.post("/api/v2/enhanced-reports/builder", json=request_data)

            assert response.status_code == status.HTTP_202_ACCEPTED

    def test_get_builder_report_success(self, client, mock_redis, mock_current_user_doctor):
        """Test getting builder report status."""
        builder_id = uuid4()
        cached_report = {
            "id": str(builder_id),
            "report_id": str(builder_id),
            "created_by": str(mock_current_user_doctor["id"]),
            "name": "Test Report",
            "fields": [],
            "row_count": 100,
            "generation_time_seconds": 2.0
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_report):

            response = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == str(builder_id)
            assert data["row_count"] == 100

    def test_download_builder_report_csv(self, client, mock_redis, mock_current_user_doctor):
        """Test downloading builder report as CSV."""
        builder_id = uuid4()
        cached_report = {
            "id": str(builder_id),
            "report_id": str(builder_id),
            "created_by": str(mock_current_user_doctor["id"]),
            "name": "Test Report",
            "data": [
                {"patient_id": "1", "name": "John"},
                {"patient_id": "2", "name": "Jane"}
            ]
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_report):

            response = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}/download?format=csv")

            assert response.status_code == status.HTTP_200_OK
            assert "text/csv" in response.headers["content-type"]


# ============================================================================
# Visualization Tests
# ============================================================================

class TestVisualizations:
    """Tests for data visualization endpoints."""

    def test_create_line_chart_visualization(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test creating line chart visualization."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            request_data = {
                "report_id": str(uuid4()),
                "visualization": {
                    "type": "line_chart",
                    "title": "Patient Trends Over Time",
                    "data_field_x": "date",
                    "data_field_y": "patient_count",
                    "show_legend": True,
                    "show_grid": True
                },
                "aggregation_method": "count"
            }

            response = client.post("/api/v2/enhanced-reports/visualizations", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["config"]["type"] == "line_chart"
            assert "data" in data

    def test_create_pie_chart_visualization(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test creating pie chart visualization."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            request_data = {
                "report_id": str(uuid4()),
                "visualization": {
                    "type": "pie_chart",
                    "title": "Treatment Distribution",
                    "data_fields": ["treatment_type"],
                    "colors": ["#FF6384", "#36A2EB", "#FFCE56"],
                    "show_labels": True
                }
            }

            response = client.post("/api/v2/enhanced-reports/visualizations", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["config"]["type"] == "pie_chart"

    def test_create_visualization_access_denied(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test visualization creation with access denied."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=False):

            request_data = {
                "report_id": str(uuid4()),
                "visualization": {
                    "type": "bar_chart",
                    "title": "Test Chart"
                }
            }

            response = client.post("/api/v2/enhanced-reports/visualizations", json=request_data)

            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_visualization_success(self, client, mock_redis, mock_current_user_doctor):
        """Test getting visualization details."""
        viz_id = uuid4()
        cached_viz = {
            "id": str(viz_id),
            "report_id": str(viz_id),
            "created_by": str(mock_current_user_doctor["id"]),
            "config": {"type": "bar_chart", "title": "Test"},
            "data": {"labels": [], "data": []}
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_viz):

            response = client.get(f"/api/v2/enhanced-reports/visualizations/{viz_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == str(viz_id)

    def test_delete_visualization(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test deleting visualization."""
        viz_id = uuid4()

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            response = client.delete(f"/api/v2/enhanced-reports/visualizations/{viz_id}")

            assert response.status_code == status.HTTP_204_NO_CONTENT


# ============================================================================
# Scheduled Delivery Tests
# ============================================================================

class TestScheduledDelivery:
    """Tests for scheduled report delivery."""

    def test_create_email_delivery_schedule(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test creating email delivery schedule."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            request_data = {
                "report_id": str(uuid4()),
                "name": "Weekly Email Report",
                "description": "Weekly patient summary via email",
                "method": "email",
                "schedule": {
                    "frequency": "weekly",
                    "start_date": "2024-01-01",
                    "time_of_day": "09:00",
                    "timezone": "America/Sao_Paulo",
                    "day_of_week": 1  # Monday
                },
                "email_config": {
                    "recipients": ["doctor@example.com"],
                    "subject": "Weekly Patient Report",
                    "attach_report": True
                },
                "export_format": "pdf"
            }

            response = client.post("/api/v2/enhanced-reports/delivery/schedules", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Weekly Email Report"
            assert data["method"] == "email"
            assert "next_run" in data

    def test_create_webhook_delivery_schedule(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test creating webhook delivery schedule."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            request_data = {
                "report_id": str(uuid4()),
                "name": "Daily Webhook Report",
                "method": "webhook",
                "schedule": {
                    "frequency": "daily",
                    "start_date": "2024-01-01",
                    "time_of_day": "03:00"
                },
                "webhook_config": {
                    "url": "https://api.example.com/reports",
                    "method": "POST",
                    "auth_type": "bearer",
                    "retry_count": 3
                },
                "export_format": "json"
            }

            response = client.post("/api/v2/enhanced-reports/delivery/schedules", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["method"] == "webhook"

    def test_create_delivery_missing_email_config(self, client, mock_current_user_doctor):
        """Test creating email delivery without email config."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            request_data = {
                "report_id": str(uuid4()),
                "name": "Test",
                "method": "email",
                "schedule": {
                    "frequency": "daily",
                    "start_date": "2024-01-01",
                    "time_of_day": "09:00"
                }
                # Missing email_config
            }

            response = client.post("/api/v2/enhanced-reports/delivery/schedules", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_delivery_schedule(self, client, mock_redis, mock_current_user_doctor):
        """Test getting delivery schedule details."""
        schedule_id = uuid4()
        cached_schedule = {
            "id": str(schedule_id),
            "report_id": str(schedule_id),
            "created_by": str(mock_current_user_doctor["id"]),
            "name": "Test Schedule",
            "method": "email",
            "is_active": True
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_schedule):

            response = client.get(f"/api/v2/enhanced-reports/delivery/schedules/{schedule_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == str(schedule_id)

    def test_delete_delivery_schedule(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test deleting delivery schedule."""
        schedule_id = uuid4()

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            response = client.delete(f"/api/v2/enhanced-reports/delivery/schedules/{schedule_id}")

            assert response.status_code == status.HTTP_204_NO_CONTENT


# ============================================================================
# Report Sharing Tests
# ============================================================================

class TestReportSharing:
    """Tests for report sharing and permissions."""

    def test_share_report_with_users(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test sharing report with multiple users."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            user_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
            request_data = {
                "report_id": str(uuid4()),
                "user_ids": user_ids,
                "permission_level": "view",
                "message": "Sharing this report with you"
            }

            response = client.post("/api/v2/enhanced-reports/sharing", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert len(data) == 3
            assert data[0]["permission_level"] == "view"

    def test_share_report_with_expiration(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test sharing report with expiration date."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            expires_at = (now_sao_paulo_naive() + timedelta(days=7)).isoformat()
            request_data = {
                "report_id": str(uuid4()),
                "user_ids": [str(uuid4())],
                "permission_level": "edit",
                "expires_at": expires_at
            }

            response = client.post("/api/v2/enhanced-reports/sharing", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data[0]["expires_at"] == expires_at

    def test_create_public_link(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test creating public shareable link."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            request_data = {
                "report_id": str(uuid4()),
                "password_protected": True,
                "password": "SecurePassword123",
                "max_views": 100
            }

            response = client.post("/api/v2/enhanced-reports/sharing/public-link", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert "token" in data
            assert "url" in data
            assert data["password_protected"] is True
            assert data["max_views"] == 100

    def test_create_public_link_without_password(self, client, mock_current_user_doctor):
        """Test creating password-protected link without password."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor):

            request_data = {
                "report_id": str(uuid4()),
                "password_protected": True
                # Missing password
            }

            response = client.post("/api/v2/enhanced-reports/sharing/public-link", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# Multi-Format Export Tests
# ============================================================================

class TestMultiFormatExport:
    """Tests for multi-format export functionality."""

    def test_export_multiple_formats(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test exporting report in multiple formats."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            request_data = {
                "report_id": str(uuid4()),
                "formats": ["pdf", "excel", "powerpoint"],
                "zip_results": True,
                "options": {
                    "pdf_page_size": "A4",
                    "pdf_orientation": "landscape",
                    "excel_freeze_header": True
                }
            }

            response = client.post("/api/v2/enhanced-reports/export", json=request_data)

            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert len(data["formats"]) == 3
            assert data["status"] == "pending"
            assert "export_id" in data

            cached_exports = [
                json.loads(call.args[2])
                for call in mock_redis.setex.await_args_list
                if len(call.args) >= 3
            ]
            matching_exports = [
                payload
                for payload in cached_exports
                if payload.get("export_id") == data["export_id"]
            ]
            assert matching_exports
            assert all(
                payload["created_by"] == mock_current_user_doctor["id"]
                for payload in matching_exports
            )
            assert all(
                payload["report_id"] == request_data["report_id"]
                for payload in matching_exports
            )
            assert all(payload["formats"] == request_data["formats"] for payload in matching_exports)
            assert all(payload["status"] == "pending" for payload in matching_exports)
            assert all("created_at" in payload and "updated_at" in payload for payload in matching_exports)

    def test_export_single_format(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test exporting report in single format."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            request_data = {
                "report_id": str(uuid4()),
                "formats": ["csv"],
                "zip_results": False
            }

            response = client.post("/api/v2/enhanced-reports/export", json=request_data)

            assert response.status_code == status.HTTP_202_ACCEPTED

    def test_get_export_status(self, client, mock_redis, mock_current_user_doctor):
        """Test getting export status."""
        export_id = uuid4()
        cached_export = {
            "export_id": str(export_id),
            "report_id": str(uuid4()),
            "created_by": str(mock_current_user_doctor["id"]),
            "status": "completed",
            "formats": ["pdf", "excel"],
            "download_urls": {
                "pdf": "/download?format=pdf",
                "excel": "/download?format=excel"
            }
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_export):

            response = client.get(f"/api/v2/enhanced-reports/export/{export_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "completed"
            assert len(data["download_urls"]) == 2

    def test_download_export_file(self, client, mock_redis, mock_current_user_doctor):
        """Test downloading exported file."""
        export_id = uuid4()
        cached_export = {
            "export_id": str(export_id),
            "report_id": str(uuid4()),
            "created_by": str(mock_current_user_doctor["id"]),
            "status": "completed",
            "formats": ["pdf"]
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_export):

            response = client.get(f"/api/v2/enhanced-reports/export/{export_id}/download?format=pdf")

            assert response.status_code == status.HTTP_200_OK
            assert "application/pdf" in response.headers["content-type"]


# ============================================================================
# Report Versioning Tests
# ============================================================================

class TestReportVersioning:
    """Tests for report versioning and history."""

    def test_get_report_history(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test getting report version history."""
        report_id = uuid4()

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            response = client.get(f"/api/v2/enhanced-reports/reports/{report_id}/history")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "versions" in data
            assert data["current_version"] >= 1
            assert data["total_versions"] >= 1

    def test_restore_report_version(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test restoring previous report version."""
        report_id = uuid4()

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=True):

            request_data = {
                "report_id": str(report_id),
                "version": 2,
                "create_backup": True
            }

            response = client.post(f"/api/v2/enhanced-reports/reports/{report_id}/restore", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "id" in data
            assert "restored to v2" in data["name"].lower()


# ============================================================================
# Dashboard Tests
# ============================================================================

class TestDashboards:
    """Tests for interactive dashboard functionality."""

    def test_create_dashboard(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test creating interactive dashboard."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            request_data = {
                "name": "Patient Overview Dashboard",
                "description": "Main patient monitoring dashboard",
                "layout": "grid",
                "widgets": [
                    {
                        "type": "metric",
                        "x": 0,
                        "y": 0,
                        "width": 3,
                        "height": 2,
                        "title": "Total Patients"
                    },
                    {
                        "type": "chart",
                        "x": 3,
                        "y": 0,
                        "width": 6,
                        "height": 4,
                        "title": "Patient Trends"
                    }
                ],
                "auto_refresh": True,
                "refresh_interval_seconds": 300,
                "theme": "light"
            }

            response = client.post("/api/v2/enhanced-reports/dashboards", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Patient Overview Dashboard"
            assert len(data["widgets"]) == 2
            assert data["auto_refresh"] is True

    def test_create_public_dashboard(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test creating public dashboard."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            request_data = {
                "name": "Public Metrics Dashboard",
                "layout": "rows",
                "widgets": [
                    {
                        "type": "card",
                        "x": 0,
                        "y": 0,
                        "width": 12,
                        "height": 2
                    }
                ],
                "is_public": True,
                "theme": "dark"
            }

            response = client.post("/api/v2/enhanced-reports/dashboards", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["is_public"] is True
            assert data["theme"] == "dark"

    def test_get_dashboard(self, client, mock_redis, mock_current_user_doctor):
        """Test getting dashboard details."""
        dashboard_id = uuid4()
        cached_dashboard = {
            "id": str(dashboard_id),
            "report_id": str(dashboard_id),
            "created_by": str(mock_current_user_doctor["id"]),
            "name": "Test Dashboard",
            "layout": "grid",
            "widgets": [],
            "view_count": 10
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_dashboard):

            response = client.get(f"/api/v2/enhanced-reports/dashboards/{dashboard_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == str(dashboard_id)
            assert data["view_count"] == 10

    def test_update_dashboard(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test updating dashboard configuration."""
        dashboard_id = uuid4()
        existing_dashboard = {
            "id": str(dashboard_id),
            "report_id": str(dashboard_id),
            "created_by": str(mock_current_user_doctor["id"]),
            "name": "Old Name",
            "widgets": []
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=existing_dashboard):

            update_data = {
                "name": "Updated Dashboard Name",
                "auto_refresh": True,
                "refresh_interval_seconds": 60
            }

            response = client.put(f"/api/v2/enhanced-reports/dashboards/{dashboard_id}", json=update_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == "Updated Dashboard Name"

    def test_delete_dashboard(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test deleting dashboard."""
        dashboard_id = uuid4()

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            response = client.delete(f"/api/v2/enhanced-reports/dashboards/{dashboard_id}")

            assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_create_dashboard_snapshot(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test creating dashboard snapshot."""
        dashboard_id = uuid4()

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            request_data = {
                "dashboard_id": str(dashboard_id),
                "name": "Monthly Snapshot",
                "description": "End of month dashboard state",
                "capture_data": True
            }

            response = client.post(f"/api/v2/enhanced-reports/dashboards/{dashboard_id}/snapshots", json=request_data)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Monthly Snapshot"
            assert "snapshot_data" in data


# ============================================================================
# Caching Tests
# ============================================================================

class TestCaching:
    """Tests for Redis caching functionality."""

    def test_builder_report_cached(self, client, mock_redis, mock_current_user_doctor):
        """Test that builder reports are cached."""
        builder_id = uuid4()
        cached_report = {
            "id": str(builder_id),
            "report_id": str(builder_id),
            "created_by": str(mock_current_user_doctor["id"]),
            "name": "Cached Report",
            "row_count": 50
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_report):

            response = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}")

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["name"] == "Cached Report"

    def test_visualization_cached(self, client, mock_redis, mock_current_user_doctor):
        """Test that visualizations are cached."""
        viz_id = uuid4()
        cached_viz = {
            "id": str(viz_id),
            "report_id": str(viz_id),
            "created_by": str(mock_current_user_doctor["id"]),
            "config": {"type": "line_chart"},
            "data": {}
        }

        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports._get_cached_result", return_value=cached_viz):

            response = client.get(f"/api/v2/enhanced-reports/visualizations/{viz_id}")

            assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Permission Tests
# ============================================================================

class TestPermissions:
    """Tests for access control and permissions."""

    def test_doctor_cannot_access_other_reports(self, client, mock_redis, mock_db, mock_current_user_doctor):
        """Test that doctors cannot access other doctors' reports."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_doctor), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db), \
             patch("app.api.v2.routers.enhanced_reports._check_report_access", return_value=False):

            request_data = {
                "report_id": str(uuid4()),
                "visualization": {
                    "type": "bar_chart",
                    "title": "Test"
                }
            }

            response = client.post("/api/v2/enhanced-reports/visualizations", json=request_data)

            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_has_full_access(self, client, mock_redis, mock_db, mock_current_user_admin):
        """Test that admin has access to all reports."""
        with patch("app.api.v2.routers.enhanced_reports.get_current_user_from_session", return_value=mock_current_user_admin), \
             patch("app.api.v2.routers.enhanced_reports.get_db", return_value=mock_db):

            # Admin should have access automatically
            response = client.get(f"/api/v2/enhanced-reports/reports/{uuid4()}/history")

            # May return 200 if report exists or would check permissions correctly
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
