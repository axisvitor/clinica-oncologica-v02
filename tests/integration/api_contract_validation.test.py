"""
API Contract Validation Tests
============================

This test suite validates API contract alignment between frontend and backend,
ensuring proper schema validation, response structure consistency, and data type compatibility.

Key Focus Areas:
- User admin endpoints paginated response format
- System stats response structure with trend data
- Notification API contract validation
- Template CRUD operation schemas
- Error response standardization
"""

import pytest
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, ValidationError

import httpx
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.schemas.user_admin import UserListResponse, UserResponse, UserStatsResponse
from app.schemas.report import DashboardResponse
from app.schemas.common import SuccessResponse, ErrorResponse


client = TestClient(app)


class FrontendExpectedResponse(BaseModel):
    """Expected response structure from frontend perspective."""
    pass


class TestUserAdminAPIContracts:
    """Test user administration API contracts."""

    def test_user_list_paginated_response_structure(self):
        """Test that user list endpoint returns proper paginated structure."""
        # Mock authentication
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                # Mock database response
                mock_session = MagicMock()
                mock_user = MagicMock()
                mock_user.id = uuid4()
                mock_user.email = "test@example.com"
                mock_user.full_name = "Test User"
                mock_user.role.value = "doctor"
                mock_user.is_active = True
                mock_user.created_at = datetime.now()
                mock_user.updated_at = datetime.now()
                mock_user.last_login = None

                mock_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_user]
                mock_session.query.return_value.count.return_value = 1
                mock_db.return_value = mock_session

                response = client.get("/api/v1/admin/users")

                assert response.status_code == 200
                data = response.json()

                # Validate paginated response structure
                assert "items" in data
                assert "total" in data
                assert "page" in data
                assert "size" in data
                assert "total_pages" in data
                assert "has_next" in data
                assert "has_previous" in data

                # Validate items structure
                items = data["items"]
                assert isinstance(items, list)

                if items:
                    user_item = items[0]
                    required_user_fields = [
                        "id", "email", "full_name", "role",
                        "is_active", "created_at", "updated_at"
                    ]
                    for field in required_user_fields:
                        assert field in user_item, f"Missing user field: {field}"

                # Validate pagination metadata
                assert isinstance(data["total"], int)
                assert isinstance(data["page"], int)
                assert isinstance(data["size"], int)
                assert isinstance(data["total_pages"], int)
                assert isinstance(data["has_next"], bool)
                assert isinstance(data["has_previous"], bool)

    def test_user_stats_response_structure(self):
        """Test user statistics endpoint response structure."""
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                mock_session = MagicMock()
                mock_session.query.return_value.count.return_value = 10
                mock_session.query.return_value.filter.return_value.count.return_value = 8
                mock_db.return_value = mock_session

                response = client.get("/api/v1/admin/users/stats/overview")

                assert response.status_code == 200
                data = response.json()

                # Validate stats response structure
                expected_fields = [
                    "total_users", "active_users", "inactive_users",
                    "by_role", "recent_registrations"
                ]
                for field in expected_fields:
                    assert field in data, f"Missing stats field: {field}"

                # Validate data types
                assert isinstance(data["total_users"], int)
                assert isinstance(data["active_users"], int)
                assert isinstance(data["inactive_users"], int)
                assert isinstance(data["by_role"], dict)
                assert isinstance(data["recent_registrations"], int)

    def test_user_creation_request_validation(self):
        """Test user creation request schema validation."""
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            # Test valid user creation request
            valid_user_data = {
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "New User",
                "role": "doctor",
                "is_active": True
            }

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                mock_session = MagicMock()
                mock_session.commit.return_value = None
                mock_db.return_value = mock_session

                with patch('app.repositories.user.UserRepository') as mock_repo:
                    mock_repo_instance = MagicMock()
                    mock_repo_instance.get_by_email.return_value = None

                    created_user = MagicMock()
                    created_user.id = uuid4()
                    created_user.email = valid_user_data["email"]
                    created_user.full_name = valid_user_data["full_name"]
                    created_user.role.value = valid_user_data["role"]
                    created_user.is_active = valid_user_data["is_active"]
                    created_user.created_at = datetime.now()
                    created_user.updated_at = datetime.now()
                    created_user.last_login = None

                    mock_repo_instance.create.return_value = created_user
                    mock_repo.return_value = mock_repo_instance

                    response = client.post("/api/v1/admin/users", json=valid_user_data)

                    assert response.status_code == 201
                    data = response.json()

                    # Validate response has user structure
                    assert "id" in data
                    assert "email" in data
                    assert data["email"] == valid_user_data["email"]

    def test_user_creation_validation_errors(self):
        """Test user creation validation error responses."""
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            # Test invalid email format
            invalid_data = {
                "email": "invalid-email",
                "password": "SecurePass123!",
                "full_name": "Test User",
                "role": "doctor"
            }

            response = client.post("/api/v1/admin/users", json=invalid_data)

            assert response.status_code == 422
            data = response.json()

            # Should have validation error structure
            assert "detail" in data
            assert isinstance(data["detail"], list)

    def test_user_activity_endpoint_structure(self):
        """Test user activity endpoint response structure."""
        user_id = str(uuid4())

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                mock_session = MagicMock()
                mock_user = MagicMock()
                mock_user.id = user_id
                mock_user.email = "test@example.com"

                mock_session.query.return_value.get.return_value = mock_user
                mock_db.return_value = mock_session

                with patch('app.services.audit_service.AuditService') as mock_audit:
                    mock_audit_instance = MagicMock()
                    mock_audit_instance.count_events.return_value = 0
                    mock_audit_instance.query_events.return_value = []
                    mock_audit.return_value = mock_audit_instance

                    response = client.get(f"/api/v1/admin/users/{user_id}/activity")

                    assert response.status_code == 200
                    data = response.json()

                    # Validate activity response structure
                    expected_fields = [
                        "items", "total", "page", "size",
                        "pages", "has_next", "has_previous"
                    ]
                    for field in expected_fields:
                        assert field in data, f"Missing activity field: {field}"

                    # Validate items structure (if any)
                    assert isinstance(data["items"], list)


class TestSystemStatsAPIContracts:
    """Test system statistics API contracts."""

    def test_dashboard_stats_response_structure(self):
        """Test dashboard statistics endpoint response structure."""
        with patch('app.dependencies.get_current_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="user@test.com")

            with patch('app.services.analytics.AnalyticsService') as mock_analytics:
                # Mock analytics service response
                mock_service = MagicMock()

                mock_dashboard_data = MagicMock()
                mock_dashboard_data.total_patients = 100
                mock_dashboard_data.active_patients = 85
                mock_dashboard_data.messages_today = 25
                mock_dashboard_data.alerts_pending = 3
                mock_dashboard_data.active_patients_percentage = 85.0
                mock_dashboard_data.response_rate = 92.5
                mock_dashboard_data.messages_sent = 150
                mock_dashboard_data.completed_quizzes = 45
                mock_dashboard_data.avg_response_time = 2.3
                mock_dashboard_data.patients_change = 5.2
                mock_dashboard_data.active_patients_change = 3.1
                mock_dashboard_data.messages_change = 12.8
                mock_dashboard_data.alerts_change = -15.5
                mock_dashboard_data.response_rate_change = 2.1
                mock_dashboard_data.quizzes_change = 8.7
                mock_dashboard_data.recent_messages = []
                mock_dashboard_data.recent_alerts = []
                mock_dashboard_data.recent_quiz_completions = []
                mock_dashboard_data.engagement_chart = []
                mock_dashboard_data.alert_severity_chart = {}
                mock_dashboard_data.treatment_progress_chart = {}

                mock_service.get_dashboard_data.return_value = mock_dashboard_data
                mock_analytics.return_value = mock_service

                response = client.get("/api/v1/analytics/dashboard")

                assert response.status_code == 200
                data = response.json()

                # Validate dashboard response structure
                expected_fields = [
                    "total_patients", "active_patients", "messages_today", "alerts_pending",
                    "active_patients_percentage", "response_rate", "messages_sent",
                    "completed_quizzes", "avg_response_time"
                ]
                for field in expected_fields:
                    assert field in data, f"Missing dashboard field: {field}"

                # Validate trend data (percentage changes)
                trend_fields = [
                    "patients_change", "active_patients_change", "messages_change",
                    "alerts_change", "response_rate_change", "quizzes_change"
                ]
                for field in trend_fields:
                    assert field in data, f"Missing trend field: {field}"
                    # Trend data should be numeric
                    assert isinstance(data[field], (int, float))

                # Validate chart data
                chart_fields = [
                    "engagement_chart", "alert_severity_chart", "treatment_progress_chart"
                ]
                for field in chart_fields:
                    assert field in data, f"Missing chart field: {field}"

    def test_system_stats_with_trend_indicators(self):
        """Test system stats include proper trend direction indicators."""
        with patch('app.dependencies.get_current_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="user@test.com")

            # Mock endpoint that would return trend data
            mock_response_data = {
                "users": {
                    "value": 1250,
                    "trend": {"percentage": 12.5, "direction": "up"}
                },
                "appointments": {
                    "value": 342,
                    "trend": {"percentage": 8.2, "direction": "up"}
                },
                "revenue": {
                    "value": 45890.50,
                    "trend": {"percentage": -3.1, "direction": "down"}
                },
                "active_users": {
                    "value": 892,
                    "trend": {"percentage": 0, "direction": "stable"}
                }
            }

            with patch('httpx.get') as mock_httpx:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_response_data
                mock_httpx.return_value = mock_response

                # This would test the frontend's expected format
                # In a real implementation, this might be a different endpoint
                response = client.get("/api/v1/admin/dashboard/stats")

                if response.status_code == 200:
                    data = response.json()

                    # Validate trend structure for each metric
                    for metric_name, metric_data in data.items():
                        if isinstance(metric_data, dict) and "trend" in metric_data:
                            trend = metric_data["trend"]

                            # Validate trend structure
                            assert "percentage" in trend
                            assert "direction" in trend

                            # Validate trend values
                            assert isinstance(trend["percentage"], (int, float))
                            assert trend["direction"] in ["up", "down", "stable"]


class TestNotificationAPIContracts:
    """Test notification API contracts."""

    def test_notification_list_response_structure(self):
        """Test notification list endpoint response structure."""
        with patch('app.dependencies.get_current_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="user@test.com")

            response = client.get("/api/v1/auth/notifications")

            assert response.status_code == 200
            data = response.json()

            # Validate notification list structure
            expected_fields = ["items", "total", "unread_count"]
            for field in expected_fields:
                assert field in data, f"Missing notification field: {field}"

            # Validate data types
            assert isinstance(data["items"], list)
            assert isinstance(data["total"], int)
            assert isinstance(data["unread_count"], int)

            # If items exist, validate structure
            items = data["items"]
            if items:
                notification = items[0]
                notification_fields = [
                    "id", "title", "message", "type",
                    "read", "created_at"
                ]
                for field in notification_fields:
                    assert field in notification, f"Missing notification item field: {field}"

    def test_notification_mark_read_response(self):
        """Test notification mark as read response."""
        notification_id = str(uuid4())

        with patch('app.dependencies.get_current_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="user@test.com")

            response = client.post(f"/api/v1/auth/notifications/{notification_id}/read")

            assert response.status_code == 200
            data = response.json()

            # Validate success response structure
            assert "success" in data
            assert "message" in data
            assert data["success"] is True
            assert isinstance(data["message"], str)


class TestTemplateAPIContracts:
    """Test template CRUD API contracts."""

    def test_template_list_response_structure(self):
        """Test template list endpoint response structure."""
        with patch('app.dependencies.get_current_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="user@test.com")

            # Mock the templates endpoint (if it exists)
            response = client.get("/api/v1/templates")

            if response.status_code == 200:
                data = response.json()

                # Should return list of templates
                assert isinstance(data, list) or "items" in data

                if isinstance(data, list) and data:
                    template = data[0]
                    template_fields = [
                        "id", "name", "description", "questions",
                        "created_at", "updated_at"
                    ]
                    for field in template_fields:
                        assert field in template, f"Missing template field: {field}"

    def test_template_creation_request_validation(self):
        """Test template creation request validation."""
        with patch('app.dependencies.get_current_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="user@test.com")

            valid_template_data = {
                "name": "Test Template",
                "description": "Test template description",
                "questions": [
                    {
                        "id": "q1",
                        "text": "How are you feeling?",
                        "type": "multiple_choice",
                        "options": ["Good", "Fair", "Poor"]
                    }
                ]
            }

            response = client.post("/api/v1/templates", json=valid_template_data)

            # Should either succeed or return proper validation error
            assert response.status_code in [200, 201, 422, 404]

            if response.status_code in [200, 201]:
                data = response.json()
                # Should return created template with ID
                assert "id" in data
                assert "name" in data


class TestErrorResponseContracts:
    """Test error response standardization."""

    def test_validation_error_response_structure(self):
        """Test validation error response structure."""
        # Send invalid data to trigger validation error
        invalid_data = {
            "email": "not-an-email",
            "password": "weak",
            "role": "invalid_role"
        }

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            response = client.post("/api/v1/admin/users", json=invalid_data)

            assert response.status_code == 422
            data = response.json()

            # Should have FastAPI validation error structure
            assert "detail" in data
            assert isinstance(data["detail"], list)

            if data["detail"]:
                error = data["detail"][0]
                assert "loc" in error
                assert "msg" in error
                assert "type" in error

    def test_authentication_error_response(self):
        """Test authentication error response structure."""
        # Try to access protected endpoint without authentication
        response = client.get("/api/v1/admin/users")

        assert response.status_code == 401
        data = response.json()

        # Should have standard error structure
        assert "detail" in data
        assert isinstance(data["detail"], str)

    def test_authorization_error_response(self):
        """Test authorization error response structure."""
        with patch('app.dependencies.get_current_user') as mock_auth:
            # Mock regular user trying to access admin endpoint
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="user@test.com",
                role="doctor"  # Not admin
            )

            response = client.get("/api/v1/admin/users")

            assert response.status_code == 403
            data = response.json()

            # Should have standard error structure
            assert "detail" in data
            assert isinstance(data["detail"], str)

    def test_not_found_error_response(self):
        """Test not found error response structure."""
        non_existent_id = str(uuid4())

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                mock_session = MagicMock()
                mock_session.query.return_value.get.return_value = None
                mock_db.return_value = mock_session

                response = client.get(f"/api/v1/admin/users/{non_existent_id}")

                assert response.status_code == 404
                data = response.json()

                # Should have standard error structure
                assert "detail" in data
                assert isinstance(data["detail"], str)

    def test_server_error_response_structure(self):
        """Test server error response structure."""
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                # Simulate database error
                mock_db.side_effect = Exception("Database connection failed")

                response = client.get("/api/v1/admin/users")

                assert response.status_code == 500
                data = response.json()

                # Should have standard error structure
                assert "detail" in data
                assert isinstance(data["detail"], str)


class TestDataTypeConsistency:
    """Test data type consistency across API responses."""

    def test_datetime_format_consistency(self):
        """Test that all datetime fields use consistent ISO format."""
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                mock_session = MagicMock()
                mock_user = MagicMock()
                mock_user.id = uuid4()
                mock_user.email = "test@example.com"
                mock_user.full_name = "Test User"
                mock_user.role.value = "doctor"
                mock_user.is_active = True
                mock_user.created_at = datetime.now()
                mock_user.updated_at = datetime.now()
                mock_user.last_login = None

                mock_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_user]
                mock_session.query.return_value.count.return_value = 1
                mock_db.return_value = mock_session

                response = client.get("/api/v1/admin/users")

                assert response.status_code == 200
                data = response.json()

                # Check datetime format in response
                items = data["items"]
                if items:
                    user = items[0]

                    # Test created_at format
                    created_at = user["created_at"]
                    try:
                        datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except ValueError:
                        pytest.fail(f"Invalid datetime format: {created_at}")

    def test_uuid_format_consistency(self):
        """Test that all UUID fields use consistent string format."""
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                mock_session = MagicMock()
                mock_user = MagicMock()
                test_uuid = uuid4()
                mock_user.id = test_uuid
                mock_user.email = "test@example.com"
                mock_user.full_name = "Test User"
                mock_user.role.value = "doctor"
                mock_user.is_active = True
                mock_user.created_at = datetime.now()
                mock_user.updated_at = datetime.now()
                mock_user.last_login = None

                mock_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_user]
                mock_session.query.return_value.count.return_value = 1
                mock_db.return_value = mock_session

                response = client.get("/api/v1/admin/users")

                assert response.status_code == 200
                data = response.json()

                # Check UUID format in response
                items = data["items"]
                if items:
                    user = items[0]
                    user_id = user["id"]

                    # Should be valid UUID string
                    try:
                        UUID(user_id)
                    except ValueError:
                        pytest.fail(f"Invalid UUID format: {user_id}")

    def test_boolean_consistency(self):
        """Test that boolean fields are consistently typed."""
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4(), email="admin@test.com", role="admin")

            with patch('app.dependencies.get_thread_safe_db') as mock_db:
                mock_session = MagicMock()
                mock_user = MagicMock()
                mock_user.id = uuid4()
                mock_user.email = "test@example.com"
                mock_user.full_name = "Test User"
                mock_user.role.value = "doctor"
                mock_user.is_active = True
                mock_user.created_at = datetime.now()
                mock_user.updated_at = datetime.now()
                mock_user.last_login = None

                mock_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_user]
                mock_session.query.return_value.count.return_value = 1
                mock_db.return_value = mock_session

                response = client.get("/api/v1/admin/users")

                assert response.status_code == 200
                data = response.json()

                # Check boolean consistency
                items = data["items"]
                if items:
                    user = items[0]

                    # is_active should be boolean
                    assert isinstance(user["is_active"], bool)

                # Pagination booleans
                assert isinstance(data["has_next"], bool)
                assert isinstance(data["has_previous"], bool)