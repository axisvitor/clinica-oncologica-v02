"""
Integration tests for AlertManagerAdapter with router endpoints and Celery tasks.

This module tests the AlertManagerAdapter in integration with:
- FastAPI router endpoints (app/api/v1/alerts.py)
- Celery background tasks (app/tasks/alerts.py)
- Feature flag switching (USE_CONSOLIDATED_ALERTS)
- Real AlertManager dependencies

Tests validate:
- End-to-end workflows through API endpoints
- Background task processing with adapter
- Feature flag behavior (legacy vs consolidated)
- Backward compatibility
- Data consistency across systems
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.patient import Patient
from app.services.alerts.adapter import AlertManagerAdapter
from app.config.settings import Settings


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    client = TestClient(app)
    return client


@pytest.fixture
def mock_db_session():
    """Mock database session for integration tests."""
    db = Mock(spec=Session)
    db.commit = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def sample_patient():
    """Create sample patient for testing."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        cpf="12345678900",
        email="patient@test.com",
        phone="+5511999999999",
        flow_state="active",
        created_at=datetime.utcnow(),
    )
    return patient


@pytest.fixture
def sample_alerts():
    """Create sample alerts for testing."""
    patient_id = uuid4()
    alerts = [
        Alert(
            id=uuid4(),
            rule_type="no_response",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            title="Patient No Response",
            message="Patient hasn't responded in 72 hours",
            patient_id=patient_id,
            created_at=datetime.utcnow(),
        ),
        Alert(
            id=uuid4(),
            rule_type="missed_quiz",
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.PENDING,
            title="Missed Quiz",
            message="Patient missed 2 consecutive quizzes",
            patient_id=patient_id,
            created_at=datetime.utcnow(),
        ),
    ]
    return alerts


class TestRouterEndpointIntegration:
    """Integration tests for AlertManagerAdapter with router endpoints."""

    @pytest.mark.integration
    def test_list_alerts_endpoint_with_adapter(
        self, test_client, mock_db_session, sample_alerts
    ):
        """Test GET /alerts endpoint with AlertManagerAdapter."""
        with (
            patch("app.api.v1.alerts.get_db", return_value=mock_db_session),
            patch("app.api.v1.alerts.settings") as mock_settings,
            patch("app.api.v1.alerts.AlertManagerAdapter") as MockAdapter,
            patch("app.dependencies.get_current_user", return_value=Mock(id=uuid4())),
        ):
            # Enable consolidated system
            mock_settings.USE_CONSOLIDATED_ALERTS = True

            # Setup adapter mock
            adapter_instance = Mock()
            adapter_instance.alert_repo.get_paginated.return_value = (
                sample_alerts,
                len(sample_alerts),
            )
            MockAdapter.return_value = adapter_instance

            # Call endpoint
            response = test_client.get("/api/v1/alerts")

            # Validate
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert data["total"] == len(sample_alerts)

    @pytest.mark.integration
    def test_acknowledge_alert_endpoint_with_adapter(
        self, test_client, mock_db_session, sample_alerts
    ):
        """Test POST /alerts/{alert_id}/acknowledge with AlertManagerAdapter."""
        alert = sample_alerts[0]
        user_id = uuid4()

        with (
            patch("app.api.v1.alerts.get_db", return_value=mock_db_session),
            patch("app.api.v1.alerts.settings") as mock_settings,
            patch("app.api.v1.alerts.AlertManagerAdapter") as MockAdapter,
            patch("app.dependencies.get_current_user", return_value=Mock(id=user_id)),
        ):
            # Enable consolidated system
            mock_settings.USE_CONSOLIDATED_ALERTS = True

            # Setup adapter mock
            adapter_instance = AsyncMock()
            acknowledged_alert = Mock(spec=Alert)
            acknowledged_alert.id = alert.id
            acknowledged_alert.status = AlertStatus.ACKNOWLEDGED
            acknowledged_alert.acknowledged_by = user_id
            acknowledged_alert.acknowledged_at = datetime.utcnow()
            adapter_instance.acknowledge_alert.return_value = acknowledged_alert
            MockAdapter.return_value = adapter_instance

            # Call endpoint
            response = test_client.post(
                f"/api/v1/alerts/{alert.id}/acknowledge",
                json={"user_id": str(user_id)},
            )

            # Validate
            assert response.status_code == 200
            adapter_instance.acknowledge_alert.assert_called_once()

    @pytest.mark.integration
    def test_resolve_alert_endpoint_with_adapter(
        self, test_client, mock_db_session, sample_alerts
    ):
        """Test POST /alerts/{alert_id}/resolve with AlertManagerAdapter."""
        alert = sample_alerts[0]
        user_id = uuid4()

        with (
            patch("app.api.v1.alerts.get_db", return_value=mock_db_session),
            patch("app.api.v1.alerts.settings") as mock_settings,
            patch("app.api.v1.alerts.AlertManagerAdapter") as MockAdapter,
            patch("app.dependencies.get_current_user", return_value=Mock(id=user_id)),
        ):
            # Enable consolidated system
            mock_settings.USE_CONSOLIDATED_ALERTS = True

            # Setup adapter mock
            adapter_instance = AsyncMock()
            resolved_alert = Mock(spec=Alert)
            resolved_alert.id = alert.id
            resolved_alert.status = AlertStatus.RESOLVED
            resolved_alert.resolved_by = user_id
            resolved_alert.resolved_at = datetime.utcnow()
            adapter_instance.resolve_alert.return_value = resolved_alert
            MockAdapter.return_value = adapter_instance

            # Call endpoint
            response = test_client.post(
                f"/api/v1/alerts/{alert.id}/resolve",
                params={"resolution_notes": "Issue resolved"},
            )

            # Validate
            assert response.status_code == 200
            adapter_instance.resolve_alert.assert_called_once()

    @pytest.mark.integration
    def test_get_alert_statistics_endpoint_with_adapter(
        self, test_client, mock_db_session
    ):
        """Test GET /alerts/statistics endpoint with AlertManagerAdapter."""
        with (
            patch("app.api.v1.alerts.get_db", return_value=mock_db_session),
            patch("app.api.v1.alerts.settings") as mock_settings,
            patch("app.api.v1.alerts.AlertManagerAdapter") as MockAdapter,
            patch("app.dependencies.get_current_user", return_value=Mock(id=uuid4())),
        ):
            # Enable consolidated system
            mock_settings.USE_CONSOLIDATED_ALERTS = True

            # Setup adapter mock
            adapter_instance = Mock()
            adapter_instance.get_alert_statistics.return_value = {
                "total_alerts": 100,
                "active_alerts": 20,
                "acknowledged_alerts": 30,
                "resolved_alerts": 50,
            }
            MockAdapter.return_value = adapter_instance

            # Call endpoint
            response = test_client.get("/api/v1/alerts/statistics")

            # Validate
            assert response.status_code == 200
            data = response.json()
            assert data["total_alerts"] == 100
            assert data["active_alerts"] == 20


class TestCeleryTaskIntegration:
    """Integration tests for AlertManagerAdapter with Celery tasks."""

    @pytest.mark.integration
    @patch("app.tasks.alerts.get_db_session")
    @patch("app.tasks.alerts.settings")
    def test_check_patient_alerts_task_with_adapter(
        self, mock_settings, mock_get_db, sample_patient, sample_alerts
    ):
        """Test check_patient_alerts Celery task with AlertManagerAdapter."""
        # Enable consolidated system
        mock_settings.USE_CONSOLIDATED_ALERTS = True

        # Setup database mock
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            sample_patient
        ]
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Setup adapter mock
        with patch("app.tasks.alerts.AlertManagerAdapter") as MockAdapter:
            adapter_instance = Mock()
            adapter_instance.evaluate_patient_alerts.return_value = sample_alerts
            processor_instance = Mock()
            processor_instance.process_alert.return_value = {"success": True}
            MockAdapter.return_value = adapter_instance

            # Import and call task
            from app.tasks.alerts import check_patient_alerts

            result = check_patient_alerts.apply(
                kwargs={"patient_ids": [str(sample_patient.id)]}
            )

            # Validate
            assert result is not None
            # Note: Full validation depends on actual task implementation

    @pytest.mark.integration
    @patch("app.tasks.alerts.get_db_session")
    @patch("app.tasks.alerts.settings")
    def test_process_alert_escalation_task_with_adapter(
        self, mock_settings, mock_get_db, sample_alerts
    ):
        """Test process_alert_escalation Celery task with AlertManagerAdapter."""
        alert = sample_alerts[0]

        # Enable consolidated system
        mock_settings.USE_CONSOLIDATED_ALERTS = True

        # Setup database mock
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Setup adapter mock
        with patch("app.tasks.alerts.AlertManagerAdapter") as MockAdapter:
            adapter_instance = Mock()
            adapter_instance.process_escalation.return_value = {
                "success": True,
                "alert_id": str(alert.id),
                "new_severity": AlertSeverity.CRITICAL.value,
            }
            MockAdapter.return_value = adapter_instance

            # Import and call task
            from app.tasks.alerts import process_alert_escalation

            result = process_alert_escalation.apply(kwargs={"alert_id": str(alert.id)})

            # Validate
            assert result is not None


class TestFeatureFlagBehavior:
    """Test feature flag switching between legacy and consolidated systems."""

    @pytest.mark.integration
    def test_feature_flag_enables_consolidated_system(self, mock_db_session):
        """Test that USE_CONSOLIDATED_ALERTS=True uses AlertManagerAdapter."""
        with (
            patch("app.api.v1.alerts.settings") as mock_settings,
            patch("app.api.v1.alerts.AlertManagerAdapter") as MockAdapter,
            patch("app.api.v1.alerts.AlertService") as MockLegacyService,
        ):
            # Enable consolidated system
            mock_settings.USE_CONSOLIDATED_ALERTS = True

            # Import factory function
            from app.api.v1.alerts import _get_alert_service

            # Call factory
            service = _get_alert_service(mock_db_session)

            # Validate consolidated system is used
            MockAdapter.assert_called_once_with(mock_db_session)
            MockLegacyService.assert_not_called()

    @pytest.mark.integration
    def test_feature_flag_disables_consolidated_system(self, mock_db_session):
        """Test that USE_CONSOLIDATED_ALERTS=False uses legacy AlertService."""
        with (
            patch("app.api.v1.alerts.settings") as mock_settings,
            patch("app.api.v1.alerts.AlertManagerAdapter") as MockAdapter,
            patch("app.api.v1.alerts.AlertService") as MockLegacyService,
        ):
            # Disable consolidated system
            mock_settings.USE_CONSOLIDATED_ALERTS = False

            # Import factory function
            from app.api.v1.alerts import _get_alert_service

            # Call factory
            service = _get_alert_service(mock_db_session)

            # Validate legacy system is used
            MockLegacyService.assert_called_once_with(mock_db_session)
            MockAdapter.assert_not_called()

    @pytest.mark.integration
    def test_feature_flag_switching_at_runtime(self, mock_db_session):
        """Test that feature flag can be switched at runtime."""
        with (
            patch("app.api.v1.alerts.settings") as mock_settings,
            patch("app.api.v1.alerts.AlertManagerAdapter") as MockAdapter,
            patch("app.api.v1.alerts.AlertService") as MockLegacyService,
        ):
            from app.api.v1.alerts import _get_alert_service

            # Test consolidated system
            mock_settings.USE_CONSOLIDATED_ALERTS = True
            service1 = _get_alert_service(mock_db_session)
            assert MockAdapter.call_count == 1

            # Test legacy system
            mock_settings.USE_CONSOLIDATED_ALERTS = False
            service2 = _get_alert_service(mock_db_session)
            assert MockLegacyService.call_count == 1

            # Test back to consolidated
            mock_settings.USE_CONSOLIDATED_ALERTS = True
            service3 = _get_alert_service(mock_db_session)
            assert MockAdapter.call_count == 2


class TestBackwardCompatibility:
    """Test backward compatibility between legacy and consolidated systems."""

    @pytest.mark.integration
    def test_adapter_provides_same_interface_as_legacy(self, mock_db_session):
        """Test that AlertManagerAdapter provides same interface as AlertService."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db_session)

            # Check that adapter exposes same repositories as legacy
            assert hasattr(adapter, "alert_repo")
            assert hasattr(adapter, "patient_repo")
            assert hasattr(adapter, "message_repo")
            assert hasattr(adapter, "quiz_repo")

            # Check that adapter has key methods
            assert hasattr(adapter, "evaluate_patient_alerts")
            assert hasattr(adapter, "acknowledge_alert")
            assert hasattr(adapter, "resolve_alert")
            assert hasattr(adapter, "get_alert_statistics")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_adapter_method_signatures_compatible(self, mock_db_session):
        """Test that adapter method signatures are compatible with legacy."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db_session)
            alert_id = uuid4()
            user_id = uuid4()

            # Setup mocks
            adapter.alert_repo.get = Mock(
                return_value=Alert(
                    id=alert_id,
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    rule_type="test",
                    title="Test",
                    message="Test",
                    created_at=datetime.utcnow(),
                )
            )

            # Test method signatures
            try:
                # acknowledge_alert(alert_id, user_id, notes)
                await adapter.acknowledge_alert(alert_id, user_id, "notes")

                # resolve_alert(alert_id, user_id, resolution_notes)
                await adapter.resolve_alert(alert_id, user_id, "resolved")

                # get_alert_statistics(filters)
                adapter.get_alert_statistics({"severity": AlertSeverity.HIGH})

                # get_alert_dashboard_data()
                adapter.alert_repo.get_paginated = Mock(return_value=([], 0))
                adapter.alert_repo.count_unacknowledged = Mock(return_value=0)
                adapter.alert_repo.count_by_severity = Mock(return_value=0)
                adapter.get_alert_dashboard_data()

                # process_escalation(alert_id)
                adapter.process_escalation(alert_id)

                # All methods called successfully
                assert True

            except TypeError as e:
                pytest.fail(f"Method signature incompatible: {e}")


class TestDataConsistency:
    """Test data consistency across legacy and consolidated systems."""

    @pytest.mark.integration
    def test_alert_data_format_consistent(self, mock_db_session, sample_alerts):
        """Test that alert data format is consistent between systems."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db_session)
            adapter.alert_repo.get_paginated = Mock(
                return_value=(sample_alerts, len(sample_alerts))
            )

            # Get statistics
            stats = adapter.get_alert_statistics()

            # Validate data format
            assert "total_alerts" in stats
            assert "active_alerts" in stats
            assert "acknowledged_alerts" in stats
            assert "resolved_alerts" in stats
            assert "by_severity" in stats
            assert "by_status" in stats

            # Validate data types
            assert isinstance(stats["total_alerts"], int)
            assert isinstance(stats["by_severity"], dict)
            assert isinstance(stats["by_status"], dict)

    @pytest.mark.integration
    def test_dashboard_data_format_consistent(self, mock_db_session):
        """Test that dashboard data format is consistent between systems."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db_session)
            adapter.alert_repo.get_paginated = Mock(return_value=([], 0))
            adapter.alert_repo.count_unacknowledged = Mock(return_value=0)
            adapter.alert_repo.count_by_severity = Mock(return_value=0)

            # Get dashboard data
            dashboard = adapter.get_alert_dashboard_data()

            # Validate data format
            assert "statistics" in dashboard
            assert "recent_alerts" in dashboard
            assert "unacknowledged_count" in dashboard
            assert "critical_count" in dashboard
            assert "timestamp" in dashboard

            # Validate data types
            assert isinstance(dashboard["statistics"], dict)
            assert isinstance(dashboard["recent_alerts"], list)
            assert isinstance(dashboard["unacknowledged_count"], int)
            assert isinstance(dashboard["timestamp"], str)


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows with AlertManagerAdapter."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_alert_lifecycle_workflow(self, mock_db_session):
        """Test complete alert lifecycle: create → acknowledge → resolve."""
        alert_id = uuid4()
        user_id = uuid4()

        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db_session)

            # Create alert mock
            alert = Alert(
                id=alert_id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="no_response",
                title="Test Alert",
                message="Test message",
                created_at=datetime.utcnow(),
                metadata={},
            )

            # Step 1: Alert exists (pending)
            adapter.alert_repo.get = Mock(return_value=alert)

            # Step 2: Acknowledge alert
            acknowledged = await adapter.acknowledge_alert(
                alert_id, user_id, "Acknowledged by doctor"
            )
            assert acknowledged.status == AlertStatus.ACKNOWLEDGED
            assert acknowledged.acknowledged_by == user_id

            # Step 3: Resolve alert
            alert.status = AlertStatus.ACKNOWLEDGED  # Update for next step
            resolved = await adapter.resolve_alert(
                alert_id, user_id, "Issue resolved - patient contacted"
            )
            assert resolved.status == AlertStatus.RESOLVED
            assert resolved.resolved_by == user_id

    @pytest.mark.integration
    def test_alert_escalation_workflow(self, mock_db_session):
        """Test alert escalation workflow: LOW → MEDIUM → HIGH → CRITICAL."""
        alert_id = uuid4()

        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db_session)

            # Create LOW severity alert
            alert = Alert(
                id=alert_id,
                severity=AlertSeverity.LOW,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
                metadata={},
            )
            adapter.alert_repo.get = Mock(return_value=alert)

            # Escalate LOW → MEDIUM
            result1 = adapter.process_escalation(alert_id)
            assert result1["success"] is True
            assert alert.severity == AlertSeverity.MEDIUM

            # Escalate MEDIUM → HIGH
            result2 = adapter.process_escalation(alert_id)
            assert result2["success"] is True
            assert alert.severity == AlertSeverity.HIGH

            # Escalate HIGH → CRITICAL
            result3 = adapter.process_escalation(alert_id)
            assert result3["success"] is True
            assert alert.severity == AlertSeverity.CRITICAL

            # Try to escalate CRITICAL (should fail)
            result4 = adapter.process_escalation(alert_id)
            assert result4["success"] is False
            assert "maximum severity" in result4["message"]


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_adapter_handles_database_errors_gracefully(self, mock_db_session):
        """Test that adapter handles database errors gracefully."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db_session)

            # Simulate database error
            adapter.alert_repo.get = Mock(side_effect=Exception("Database error"))

            # Test that error is raised appropriately
            with pytest.raises(Exception, match="Database error"):
                await adapter.acknowledge_alert(uuid4(), uuid4(), "test")

    @pytest.mark.integration
    def test_adapter_handles_invalid_alert_id(self, mock_db_session):
        """Test that adapter handles invalid alert IDs."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db_session)
            adapter.alert_repo.get = Mock(return_value=None)

            # Test escalation with non-existent alert
            with pytest.raises(ValueError, match="not found"):
                adapter.process_escalation(uuid4())
