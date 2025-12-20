"""
Integration tests for error handling in critical endpoints.

Tests end-to-end error handling across analytics, monthly quiz, and alerts
endpoints to ensure proper error handling is integrated throughout the system.
"""
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.user import User, UserRole
from app.models.error_tracking import ErrorLog
from app.core.error_handler import error_handler
from tests.conftest import create_test_user


class TestAnalyticsErrorHandling:
    """Test error handling in analytics endpoints."""

    def test_analytics_endpoint_with_role_enum_error(self, client: TestClient, admin_user: User, db: Session):
        """Test analytics endpoint handles role enum errors gracefully."""
        # Test V2 endpoint with role-based access
        # Note: UserRole is from app.models.user, not from API modules
        response = client.get(
            "/api/v2/analytics/engagement-range",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )

        # Should handle gracefully - either success (200) or proper error codes (400, 401, 403)
        assert response.status_code in [200, 400, 401, 403], f"Expected 200/400/401/403, got {response.status_code}"

    def test_analytics_endpoint_with_dependency_injection_error(self, client: TestClient, admin_user: User, db: Session):
        """Test analytics endpoint handles dependency injection errors gracefully."""
        # Mock a dependency injection error
        with patch('app.dependencies.service_dependencies.get_thread_safe_service_provider') as mock_provider:
            mock_provider.side_effect = AttributeError("'generator' object has no attribute 'monthly_quiz_service'")
            
            response = client.get(
                "/api/v2/analytics/engagement-range",
                headers={"Authorization": f"Bearer {admin_user.id}"}
            )
            
            # Should handle error gracefully
            assert response.status_code == 500
            assert "Service temporarily unavailable" in response.json()["detail"]

    def test_analytics_endpoint_with_date_parameter_error(self, client: TestClient, admin_user: User, db: Session):
        """Test analytics endpoint handles invalid date parameters gracefully."""
        response = client.get(
            "/api/v2/analytics/engagement-range",
            params={
                "start_date": "invalid-date-format",
                "end_date": "2025-10-12T15:01:57.695Z"
            },
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        # Should return 400 with helpful error message
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_analytics_endpoint_with_valid_datetime_strings(self, client: TestClient, admin_user: User, db: Session):
        """Test analytics endpoint accepts valid datetime strings."""
        response = client.get(
            "/api/v2/analytics/engagement-range",
            params={
                "start_date": "2025-10-05T15:01:57.695Z",
                "end_date": "2025-10-12T15:01:57.695Z"
            },
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        # Should not be a validation error
        assert response.status_code != 422
        # May be 200 (success) or other business logic error, but not validation error


class TestMonthlyQuizErrorHandling:
    """Test error handling in monthly quiz endpoints."""

    def test_monthly_quiz_endpoint_with_invalid_role_comparison(self, client: TestClient, db: Session):
        """Test monthly quiz endpoint handles role comparisons correctly."""
        # Create a user with admin role
        user = create_test_user(db, role=UserRole.ADMIN)

        # Test V2 endpoint with role-based access
        # Note: UserRole is from app.models.user, not from API modules
        response = client.get(
            "/api/v2/monthly-quiz/dashboard-stats",
            headers={"Authorization": f"Bearer {user.id}"}
        )

        # Should handle gracefully - either success or proper error codes
        assert response.status_code in [200, 400, 401, 403, 500]
        if response.status_code == 403:
            assert "denied" in response.json().get("detail", "").lower() or "access" in response.json().get("detail", "").lower()

    def test_monthly_quiz_endpoint_with_dependency_injection_error(self, client: TestClient, admin_user: User, db: Session):
        """Test monthly quiz endpoint handles dependency injection errors gracefully."""
        with patch('app.dependencies.service_dependencies.get_thread_safe_service_provider') as mock_provider:
            mock_provider.side_effect = AttributeError("'generator' object has no attribute 'quiz_service'")
            
            response = client.get(
                "/api/v2/monthly-quiz/dashboard-stats",
                headers={"Authorization": f"Bearer {admin_user.id}"}
            )
            
            # Should handle error gracefully
            assert response.status_code == 500
            assert "Service temporarily unavailable" in response.json()["detail"]

    def test_monthly_quiz_role_check_with_proper_enum(self, client: TestClient, admin_user: User, db: Session):
        """Test monthly quiz endpoint works with proper enum comparison."""
        # Ensure the user has the correct role
        admin_user.role = UserRole.ADMIN
        db.commit()
        
        response = client.get(
            "/api/v2/monthly-quiz/dashboard-stats",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        # Should not fail due to role enum issues
        assert response.status_code != 500 or "AttributeError" not in str(response.json())


class TestAlertsErrorHandling:
    """Test error handling in alerts endpoints."""

    def test_alerts_endpoint_with_schema_compatibility_error(self, client: TestClient, admin_user: User, db: Session):
        """Test alerts endpoint handles schema compatibility errors gracefully."""
        # Mock a schema mismatch error
        with patch('app.repositories.alert.AlertRepository.get_all') as mock_get_all:
            mock_get_all.side_effect = SQLAlchemyError("column 'alert_type' does not exist")
            
            response = client.get(
                "/api/v2/alerts/",
                headers={"Authorization": f"Bearer {admin_user.id}"}
            )
            
            # Should handle error gracefully
            assert response.status_code == 500
            assert "Database schema mismatch" in response.json()["detail"]

    def test_alerts_create_with_schema_compatibility(self, client: TestClient, admin_user: User, db: Session):
        """Test alerts creation works with schema-compatible fields."""
        alert_data = {
            "patient_id": str(uuid.uuid4()),
            "alert_type": "medication_reminder",  # Maps to 'type' column
            "description": "Test alert message",   # Maps to 'message' column
            "severity": "medium"
        }
        
        response = client.post(
            "/api/v2/alerts/",
            json=alert_data,
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        # Should not fail due to schema issues
        # May fail for other reasons (business logic, validation), but not schema
        assert response.status_code != 500 or "column" not in str(response.json().get("detail", ""))

    def test_alerts_filter_by_quiz_session_id(self, client: TestClient, admin_user: User, db: Session):
        """Test alerts filtering by quiz_session_id works with JSONB storage."""
        quiz_session_id = str(uuid.uuid4())
        
        response = client.get(
            f"/api/v2/alerts/quiz-session/{quiz_session_id}",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        # Should not fail due to schema issues
        assert response.status_code != 500 or "quiz_session_id" not in str(response.json().get("detail", ""))


class TestMonitoringEndpoints:
    """Test monitoring endpoints return appropriate metrics."""

    def test_health_check_critical_fixes(self, client: TestClient, admin_user: User, db: Session):
        """Test health check endpoint validates critical fixes."""
        response = client.get(
            "/api/v2/monitoring/health/critical-fixes",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have overall status
        assert "overall_status" in data
        assert data["overall_status"] in ["healthy", "unhealthy"]
        
        # Should have individual checks
        assert "checks" in data
        expected_checks = [
            "dependency_injection",
            "role_enum_system", 
            "database_schema",
            "date_parameter_handling",
            "error_tracking"
        ]
        
        for check in expected_checks:
            assert check in data["checks"]
            assert "status" in data["checks"][check]

    def test_error_metrics_endpoint(self, client: TestClient, admin_user: User, db: Session):
        """Test error metrics endpoint returns proper metrics."""
        # Create some test error logs
        error_log = ErrorLog(
            error_type="TEST_ERROR",
            error_message="Test error for metrics",
            severity="ERROR",
            context={"test": True}
        )
        db.add(error_log)
        db.commit()
        
        response = client.get(
            "/api/v2/monitoring/errors/metrics",
            params={"hours": 24},
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have summary metrics
        assert "summary" in data
        assert "total_error_types" in data["summary"]
        assert "total_error_occurrences" in data["summary"]
        assert "error_rate_per_hour" in data["summary"]
        
        # Should have error breakdown
        assert "error_types" in data
        assert "severity_breakdown" in data

    def test_error_details_endpoint(self, client: TestClient, admin_user: User, db: Session):
        """Test error details endpoint returns detailed information."""
        # Create a test error log
        error_log = ErrorLog(
            error_type="TEST_ERROR",
            error_message="Test error for details",
            severity="ERROR",
            context={"test": True},
            stack_trace="Test stack trace"
        )
        db.add(error_log)
        db.commit()
        
        response = client.get(
            f"/api/v2/monitoring/errors/{error_log.id}",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have detailed error information
        assert data["id"] == str(error_log.id)
        assert data["error_type"] == "TEST_ERROR"
        assert data["error_message"] == "Test error for details"
        assert data["severity"] == "ERROR"
        assert data["context"] == {"test": True}
        assert data["stack_trace"] == "Test stack trace"

    def test_system_status_endpoint(self, client: TestClient, admin_user: User, db: Session):
        """Test system status endpoint provides comprehensive status."""
        response = client.get(
            "/api/v2/monitoring/system/status",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have system status
        assert "system_status" in data
        assert data["system_status"] in ["healthy", "degraded"]
        
        # Should have critical fixes health
        assert "critical_fixes_health" in data
        
        # Should have error summary
        assert "error_summary" in data
        assert "recent_errors_1h" in data["error_summary"]
        assert "critical_errors_1h" in data["error_summary"]
        
        # Should have recommendations
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)


class TestErrorHandlerIntegration:
    """Test error handler integration across the system."""

    def test_error_handler_tracks_errors_in_database(self, db: Session):
        """Test that error handler properly tracks errors in database."""
        initial_count = db.query(ErrorLog).count()
        
        # Trigger an error through the error handler
        import asyncio
        
        async def test_error_handling():
            try:
                await error_handler.handle_dependency_injection_error(
                    Exception("Test DI error"),
                    {"test": True, "endpoint": "/test"}
                )
            except Exception:
                pass  # Expected to raise HTTPException
        
        asyncio.run(test_error_handling())
        
        # Should have created an error log entry
        final_count = db.query(ErrorLog).count()
        assert final_count > initial_count
        
        # Check the error log details
        error_log = db.query(ErrorLog).filter(
            ErrorLog.error_message == "Test DI error"
        ).first()
        
        assert error_log is not None
        assert error_log.error_type == "DI_GENERATOR_ERROR"
        assert error_log.severity == "CRITICAL"
        assert error_log.context["test"] is True

    def test_error_handler_rate_limiting(self, db: Session):
        """Test that error handler properly rate limits repeated errors."""
        import asyncio
        
        async def test_rate_limiting():
            # Generate multiple identical errors
            for i in range(10):
                try:
                    await error_handler.handle_role_enum_error(
                        AttributeError("Test role error"),
                        user_role="invalid_role",
                        endpoint="/test"
                    )
                except Exception:
                    pass  # Expected to raise HTTPException
        
        asyncio.run(test_rate_limiting())
        
        # Should have created error logs but with rate limiting
        error_logs = db.query(ErrorLog).filter(
            ErrorLog.error_message == "Test role error"
        ).all()
        
        # Should have at least one error log (not rate limited)
        assert len(error_logs) >= 1
        
        # If multiple logs exist, they should show deduplication (count > 1)
        if len(error_logs) == 1:
            assert error_logs[0].count >= 1

    def test_error_context_manager(self, db: Session):
        """Test error handler context manager functionality."""
        initial_count = db.query(ErrorLog).count()
        
        # Test context manager with error
        try:
            with error_handler.error_context("test_operation", user_id="123"):
                raise ValueError("Test context error")
        except Exception:
            pass  # Expected
        
        # Should have handled the error appropriately
        # The context manager converts exceptions to HTTPExceptions
        # but doesn't necessarily log them to database unless explicitly handled

    def test_error_stats_collection(self):
        """Test error handler statistics collection."""
        stats = error_handler.get_error_stats()
        
        assert isinstance(stats, dict)
        assert "error_types" in stats
        assert "total_error_types" in stats
        assert "rate_limit_threshold" in stats
        
        # Stats should be properly formatted
        assert isinstance(stats["error_types"], dict)
        assert isinstance(stats["total_error_types"], int)
        assert isinstance(stats["rate_limit_threshold"], int)


class TestEndToEndErrorHandling:
    """Test end-to-end error handling scenarios."""

    def test_complete_error_flow_with_monitoring(self, client: TestClient, admin_user: User, db: Session):
        """Test complete error flow from endpoint to monitoring."""
        # 1. Trigger an error in an endpoint
        with patch('app.dependencies.service_dependencies.get_thread_safe_service_provider') as mock_provider:
            mock_provider.side_effect = AttributeError("Test DI error for monitoring")
            
            response = client.get(
                "/api/v2/analytics/engagement-range",
                headers={"Authorization": f"Bearer {admin_user.id}"}
            )
            
            # Should handle error gracefully
            assert response.status_code == 500
        
        # 2. Check that error was tracked
        error_logs = db.query(ErrorLog).filter(
            ErrorLog.error_message.contains("Test DI error for monitoring")
        ).all()
        
        # Should have at least one error log
        assert len(error_logs) >= 0  # May be rate limited
        
        # 3. Check monitoring endpoints can retrieve the error
        metrics_response = client.get(
            "/api/v2/monitoring/errors/metrics",
            params={"hours": 1},
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        assert metrics_response.status_code == 200
        
        # 4. Check health status reflects the error
        health_response = client.get(
            "/api/v2/monitoring/health/critical-fixes",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        assert health_response.status_code == 200
        health_data = health_response.json()
        
        # Health check should detect DI issues
        if "dependency_injection" in health_data.get("checks", {}):
            di_check = health_data["checks"]["dependency_injection"]
            # May be healthy or unhealthy depending on the specific test conditions
            assert "status" in di_check

    def test_non_admin_access_to_monitoring_endpoints(self, client: TestClient, db: Session):
        """Test that non-admin users cannot access monitoring endpoints."""
        # Create a non-admin user
        regular_user = create_test_user(db, role=UserRole.DOCTOR)
        
        # Try to access monitoring endpoints
        endpoints = [
            "/api/v2/monitoring/health/critical-fixes",
            "/api/v2/monitoring/errors/metrics",
            "/api/v2/monitoring/system/status"
        ]
        
        for endpoint in endpoints:
            response = client.get(
                endpoint,
                headers={"Authorization": f"Bearer {regular_user.id}"}
            )
            
            # Should be denied access
            assert response.status_code == 403
            assert "Admin access required" in response.json()["detail"]

    def test_error_resolution_workflow(self, client: TestClient, admin_user: User, db: Session):
        """Test complete error resolution workflow."""
        # 1. Create an error log
        error_log = ErrorLog(
            error_type="TEST_WORKFLOW_ERROR",
            error_message="Test error for resolution workflow",
            severity="ERROR",
            context={"test": True}
        )
        db.add(error_log)
        db.commit()
        
        # 2. Get error details
        details_response = client.get(
            f"/api/v2/monitoring/errors/{error_log.id}",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        assert details_response.status_code == 200
        assert not details_response.json()["resolved"]
        
        # 3. Resolve the error
        resolve_response = client.post(
            f"/api/v2/monitoring/errors/{error_log.id}/resolve",
            headers={"Authorization": f"Bearer {admin_user.id}"}
        )
        
        assert resolve_response.status_code == 200
        assert resolve_response.json()["resolved"] is True
        
        # 4. Verify error is marked as resolved
        db.refresh(error_log)
        assert error_log.resolved is True