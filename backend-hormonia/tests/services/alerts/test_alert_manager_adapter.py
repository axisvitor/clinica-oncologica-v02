"""
Unit tests for AlertManagerAdapter.

This module tests the AlertManagerAdapter compatibility layer that bridges
the consolidated AlertManager with legacy API expectations.

Tests cover:
- Adapter initialization
- Repository access
- AlertManager delegation methods
- Database-backed operations (acknowledge, resolve)
- Statistics and dashboard data generation
- Escalation processing
- Error handling and edge cases
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch

from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.services.alerts.adapter import AlertManagerAdapter
from app.services.alerts import AlertManager


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.commit = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_alert_manager():
    """Mock AlertManager instance."""
    manager = Mock(spec=AlertManager)
    manager.evaluate_patient_alerts = AsyncMock(return_value=[])
    manager.evaluate_infrastructure_alerts = AsyncMock(return_value=[])
    manager.process_alert = AsyncMock(return_value=Mock())
    return manager


@pytest.fixture
def mock_alert_repo():
    """Mock AlertRepository."""
    repo = Mock()
    repo.get = Mock()
    repo.get_by_patient = Mock(return_value=[])
    repo.get_by_severity = Mock(return_value=[])
    repo.get_paginated = Mock(return_value=([], 0))
    repo.count = Mock(return_value=0)
    repo.count_by_severity = Mock(return_value=0)
    repo.count_unacknowledged = Mock(return_value=0)
    return repo


@pytest.fixture
def mock_patient_repo():
    """Mock PatientRepository."""
    return Mock()


@pytest.fixture
def mock_message_repo():
    """Mock MessageRepository."""
    return Mock()


@pytest.fixture
def mock_quiz_repo():
    """Mock QuizResponseRepository."""
    return Mock()


@pytest.fixture
def sample_alert():
    """Sample alert for testing."""
    alert = Alert(
        id=uuid4(),
        rule_type="no_response",
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        title="Patient No Response",
        message="Patient hasn't responded in 72 hours",
        patient_id=uuid4(),
        created_at=datetime.utcnow(),
    )
    return alert


@pytest.fixture
def adapter(mock_db, mock_alert_manager):
    """Create AlertManagerAdapter instance with mocks."""
    with (
        patch("app.services.alerts.adapter.AlertRepository") as mock_alert_repo_class,
        patch(
            "app.services.alerts.adapter.PatientRepository"
        ) as mock_patient_repo_class,
        patch(
            "app.services.alerts.adapter.MessageRepository"
        ) as mock_message_repo_class,
        patch(
            "app.services.alerts.adapter.QuizResponseRepository"
        ) as mock_quiz_repo_class,
    ):
        adapter = AlertManagerAdapter(db=mock_db, alert_manager=mock_alert_manager)

        # Set up repository mocks
        adapter.alert_repo = Mock()
        adapter.patient_repo = Mock()
        adapter.message_repo = Mock()
        adapter.quiz_repo = Mock()

        return adapter


class TestAlertManagerAdapterInitialization:
    """Test AlertManagerAdapter initialization."""

    def test_adapter_initialization_with_alert_manager(
        self, mock_db, mock_alert_manager
    ):
        """Test that adapter initializes correctly with provided AlertManager."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
        ):
            adapter = AlertManagerAdapter(db=mock_db, alert_manager=mock_alert_manager)

            assert adapter.db == mock_db
            assert adapter.alert_manager == mock_alert_manager
            assert adapter.alert_repo is not None
            assert adapter.patient_repo is not None
            assert adapter.message_repo is not None
            assert adapter.quiz_repo is not None

    def test_adapter_initialization_without_alert_manager(self, mock_db):
        """Test that adapter creates AlertManager if not provided."""
        with (
            patch("app.services.alerts.adapter.AlertRepository"),
            patch("app.services.alerts.adapter.PatientRepository"),
            patch("app.services.alerts.adapter.MessageRepository"),
            patch("app.services.alerts.adapter.QuizResponseRepository"),
            patch(
                "app.services.alerts.adapter.AlertManagerAdapter._create_alert_manager"
            ) as mock_create,
        ):
            mock_manager = Mock()
            mock_create.return_value = mock_manager

            adapter = AlertManagerAdapter(db=mock_db)

            mock_create.assert_called_once()
            assert adapter.alert_manager == mock_manager

    def test_adapter_exposes_repositories(self, adapter):
        """Test that adapter exposes all required repositories."""
        assert hasattr(adapter, "alert_repo")
        assert hasattr(adapter, "patient_repo")
        assert hasattr(adapter, "message_repo")
        assert hasattr(adapter, "quiz_repo")


class TestAlertManagerDelegation:
    """Test AlertManager method delegation."""

    @pytest.mark.asyncio
    async def test_evaluate_patient_alerts_delegates_to_manager(self, adapter):
        """Test that evaluate_patient_alerts delegates to AlertManager."""
        patient_id = uuid4()
        context = {"last_message_at": datetime.utcnow()}

        expected_alerts = [Mock(), Mock()]
        adapter.alert_manager.evaluate_patient_alerts.return_value = expected_alerts

        result = await adapter.evaluate_patient_alerts(patient_id, context)

        adapter.alert_manager.evaluate_patient_alerts.assert_called_once_with(
            patient_id, context
        )
        assert result == expected_alerts

    @pytest.mark.asyncio
    async def test_evaluate_infrastructure_alerts_delegates_to_manager(self, adapter):
        """Test that evaluate_infrastructure_alerts delegates to AlertManager."""
        context = {"pool_utilization": 0.85}

        expected_alerts = [Mock()]
        adapter.alert_manager.evaluate_infrastructure_alerts.return_value = (
            expected_alerts
        )

        result = await adapter.evaluate_infrastructure_alerts(context)

        adapter.alert_manager.evaluate_infrastructure_alerts.assert_called_once_with(
            context
        )
        assert result == expected_alerts

    @pytest.mark.asyncio
    async def test_process_alert_delegates_to_manager(self, adapter, sample_alert):
        """Test that process_alert delegates to AlertManager."""
        expected_result = Mock()
        adapter.alert_manager.process_alert.return_value = expected_result

        result = await adapter.process_alert(sample_alert)

        adapter.alert_manager.process_alert.assert_called_once_with(sample_alert)
        assert result == expected_result


class TestAcknowledgeAlert:
    """Test acknowledge_alert method."""

    @pytest.mark.asyncio
    async def test_acknowledge_alert_success(self, adapter, sample_alert, mock_db):
        """Test successful alert acknowledgment."""
        alert_id = sample_alert.id
        user_id = uuid4()
        notes = "Acknowledged by doctor"

        adapter.alert_repo.get.return_value = sample_alert

        result = await adapter.acknowledge_alert(alert_id, user_id, notes)

        adapter.alert_repo.get.assert_called_once_with(alert_id)
        assert result.status == AlertStatus.ACKNOWLEDGED
        assert result.acknowledged_by == user_id
        assert result.acknowledged_at is not None
        assert result.metadata.get("acknowledgment_notes") == notes
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_alert)

    @pytest.mark.asyncio
    async def test_acknowledge_alert_without_notes(
        self, adapter, sample_alert, mock_db
    ):
        """Test alert acknowledgment without notes."""
        alert_id = sample_alert.id
        user_id = uuid4()

        adapter.alert_repo.get.return_value = sample_alert

        result = await adapter.acknowledge_alert(alert_id, user_id, notes=None)

        assert result.status == AlertStatus.ACKNOWLEDGED
        assert result.acknowledged_by == user_id
        assert "acknowledgment_notes" not in result.metadata
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_alert_not_found(self, adapter):
        """Test acknowledging non-existent alert."""
        alert_id = uuid4()
        user_id = uuid4()

        adapter.alert_repo.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await adapter.acknowledge_alert(alert_id, user_id)

    @pytest.mark.asyncio
    async def test_acknowledge_alert_already_acknowledged(self, adapter, sample_alert):
        """Test acknowledging already acknowledged alert."""
        sample_alert.status = AlertStatus.ACKNOWLEDGED
        alert_id = sample_alert.id
        user_id = uuid4()

        adapter.alert_repo.get.return_value = sample_alert

        with pytest.raises(ValueError, match="already acknowledged"):
            await adapter.acknowledge_alert(alert_id, user_id)

    @pytest.mark.asyncio
    async def test_acknowledge_alert_already_resolved(self, adapter, sample_alert):
        """Test acknowledging already resolved alert."""
        sample_alert.status = AlertStatus.RESOLVED
        alert_id = sample_alert.id
        user_id = uuid4()

        adapter.alert_repo.get.return_value = sample_alert

        with pytest.raises(ValueError, match="already resolved"):
            await adapter.acknowledge_alert(alert_id, user_id)


class TestResolveAlert:
    """Test resolve_alert method."""

    @pytest.mark.asyncio
    async def test_resolve_alert_success(self, adapter, sample_alert, mock_db):
        """Test successful alert resolution."""
        alert_id = sample_alert.id
        user_id = uuid4()
        resolution_notes = "Issue resolved - patient contacted"

        adapter.alert_repo.get.return_value = sample_alert

        result = await adapter.resolve_alert(alert_id, user_id, resolution_notes)

        adapter.alert_repo.get.assert_called_once_with(alert_id)
        assert result.status == AlertStatus.RESOLVED
        assert result.resolved_by == user_id
        assert result.resolved_at is not None
        assert result.metadata.get("resolution") == resolution_notes
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_alert)

    @pytest.mark.asyncio
    async def test_resolve_alert_not_found(self, adapter):
        """Test resolving non-existent alert."""
        alert_id = uuid4()
        user_id = uuid4()

        adapter.alert_repo.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await adapter.resolve_alert(alert_id, user_id, "resolution")

    @pytest.mark.asyncio
    async def test_resolve_alert_already_resolved(self, adapter, sample_alert):
        """Test resolving already resolved alert."""
        sample_alert.status = AlertStatus.RESOLVED
        alert_id = sample_alert.id
        user_id = uuid4()

        adapter.alert_repo.get.return_value = sample_alert

        with pytest.raises(ValueError, match="already resolved"):
            await adapter.resolve_alert(alert_id, user_id, "resolution")


class TestGetAlertStatistics:
    """Test get_alert_statistics method."""

    def test_get_alert_statistics_basic(self, adapter):
        """Test basic statistics generation."""
        # Create sample alerts
        alerts = [
            Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="no_response",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            ),
            Alert(
                id=uuid4(),
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.ACKNOWLEDGED,
                rule_type="emergency_keywords",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            ),
        ]

        adapter.alert_repo.get_paginated.return_value = (alerts, len(alerts))

        stats = adapter.get_alert_statistics()

        assert stats["total_alerts"] == 2
        assert stats["active_alerts"] == 0  # None are ACTIVE status
        assert stats["acknowledged_alerts"] == 1
        assert stats["by_severity"][AlertSeverity.HIGH.value] == 1
        assert stats["by_severity"][AlertSeverity.CRITICAL.value] == 1

    def test_get_alert_statistics_empty(self, adapter):
        """Test statistics with no alerts."""
        adapter.alert_repo.get_paginated.return_value = ([], 0)

        stats = adapter.get_alert_statistics()

        assert stats["total_alerts"] == 0
        assert stats["active_alerts"] == 0
        assert stats["acknowledged_alerts"] == 0
        assert stats["resolved_alerts"] == 0

    def test_get_alert_statistics_with_filters(self, adapter):
        """Test statistics with filters applied."""
        alerts = [
            Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="no_response",
                title="Test",
                message="Test",
                patient_id=uuid4(),
                created_at=datetime.utcnow(),
            ),
        ]

        adapter.alert_repo.get_paginated.return_value = (alerts, len(alerts))

        filters = {"severity": AlertSeverity.HIGH}
        stats = adapter.get_alert_statistics(filters)

        assert stats["total_alerts"] == 1


class TestGetAlertDashboardData:
    """Test get_alert_dashboard_data method."""

    def test_get_alert_dashboard_data_basic(self, adapter):
        """Test dashboard data generation."""
        alerts = [
            Alert(
                id=uuid4(),
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.PENDING,
                rule_type="no_response",
                title="Critical Alert",
                message="Test",
                created_at=datetime.utcnow(),
            ),
        ]

        adapter.alert_repo.get_paginated.return_value = (alerts, len(alerts))
        adapter.alert_repo.count_unacknowledged.return_value = 5
        adapter.alert_repo.count_by_severity.return_value = 2

        dashboard = adapter.get_alert_dashboard_data()

        assert "statistics" in dashboard
        assert "recent_alerts" in dashboard
        assert "unacknowledged_count" in dashboard
        assert "critical_count" in dashboard
        assert "timestamp" in dashboard

        assert dashboard["unacknowledged_count"] == 5
        assert dashboard["critical_count"] == 2
        assert len(dashboard["recent_alerts"]) <= 20

    def test_get_alert_dashboard_data_empty(self, adapter):
        """Test dashboard data with no alerts."""
        adapter.alert_repo.get_paginated.return_value = ([], 0)
        adapter.alert_repo.count_unacknowledged.return_value = 0
        adapter.alert_repo.count_by_severity.return_value = 0

        dashboard = adapter.get_alert_dashboard_data()

        assert dashboard["statistics"]["total_alerts"] == 0
        assert len(dashboard["recent_alerts"]) == 0
        assert dashboard["unacknowledged_count"] == 0


class TestProcessEscalation:
    """Test process_escalation method."""

    def test_process_escalation_low_to_medium(self, adapter, sample_alert, mock_db):
        """Test escalating alert from LOW to MEDIUM."""
        sample_alert.severity = AlertSeverity.LOW
        alert_id = sample_alert.id

        adapter.alert_repo.get.return_value = sample_alert

        result = adapter.process_escalation(alert_id)

        assert result["success"] is True
        assert sample_alert.severity == AlertSeverity.MEDIUM
        assert sample_alert.metadata.get("manually_escalated") is True
        assert result["new_severity"] == AlertSeverity.MEDIUM.value
        mock_db.commit.assert_called_once()

    def test_process_escalation_medium_to_high(self, adapter, sample_alert, mock_db):
        """Test escalating alert from MEDIUM to HIGH."""
        sample_alert.severity = AlertSeverity.MEDIUM
        alert_id = sample_alert.id

        adapter.alert_repo.get.return_value = sample_alert

        result = adapter.process_escalation(alert_id)

        assert result["success"] is True
        assert sample_alert.severity == AlertSeverity.HIGH
        assert result["previous_severity"] == AlertSeverity.MEDIUM.value

    def test_process_escalation_high_to_critical(self, adapter, sample_alert, mock_db):
        """Test escalating alert from HIGH to CRITICAL."""
        sample_alert.severity = AlertSeverity.HIGH
        alert_id = sample_alert.id

        adapter.alert_repo.get.return_value = sample_alert

        result = adapter.process_escalation(alert_id)

        assert result["success"] is True
        assert sample_alert.severity == AlertSeverity.CRITICAL

    def test_process_escalation_already_critical(self, adapter, sample_alert):
        """Test escalating alert that's already at CRITICAL."""
        sample_alert.severity = AlertSeverity.CRITICAL
        alert_id = sample_alert.id

        adapter.alert_repo.get.return_value = sample_alert

        result = adapter.process_escalation(alert_id)

        assert result["success"] is False
        assert "maximum severity" in result["message"]

    def test_process_escalation_alert_not_found(self, adapter):
        """Test escalating non-existent alert."""
        alert_id = uuid4()

        adapter.alert_repo.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            adapter.process_escalation(alert_id)


class TestStubMethods:
    """Test stub methods for future implementation."""

    def test_update_alert_rule_stub(self, adapter):
        """Test update_alert_rule stub returns success."""
        result = adapter.update_alert_rule(
            rule_type="no_response",
            severity=AlertSeverity.HIGH,
            threshold=72.0,
        )

        assert result is True

    def test_update_notification_channel_stub(self, adapter):
        """Test update_notification_channel stub returns success."""
        result = adapter.update_notification_channel("email", enabled=True)

        assert result is True


class TestHelperMethods:
    """Test adapter helper methods."""

    def test_apply_filters_severity(self, adapter):
        """Test _apply_filters with severity filter."""
        alerts = [
            Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            ),
            Alert(
                id=uuid4(),
                severity=AlertSeverity.LOW,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            ),
        ]

        filters = {"severity": AlertSeverity.HIGH}
        filtered = adapter._apply_filters(alerts, filters)

        assert len(filtered) == 1
        assert filtered[0].severity == AlertSeverity.HIGH

    def test_apply_filters_status(self, adapter):
        """Test _apply_filters with status filter."""
        alerts = [
            Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            ),
            Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.RESOLVED,
                rule_type="test",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            ),
        ]

        filters = {"status": AlertStatus.PENDING}
        filtered = adapter._apply_filters(alerts, filters)

        assert len(filtered) == 1
        assert filtered[0].status == AlertStatus.PENDING

    def test_apply_filters_patient_id(self, adapter):
        """Test _apply_filters with patient_id filter."""
        patient_id_1 = uuid4()
        patient_id_2 = uuid4()

        alerts = [
            Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                patient_id=patient_id_1,
                created_at=datetime.utcnow(),
            ),
            Alert(
                id=uuid4(),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                rule_type="test",
                title="Test",
                message="Test",
                patient_id=patient_id_2,
                created_at=datetime.utcnow(),
            ),
        ]

        filters = {"patient_id": patient_id_1}
        filtered = adapter._apply_filters(alerts, filters)

        assert len(filtered) == 1
        assert filtered[0].patient_id == patient_id_1

    def test_alert_to_dict(self, adapter, sample_alert):
        """Test _alert_to_dict conversion."""
        result = adapter._alert_to_dict(sample_alert)

        assert result["id"] == str(sample_alert.id)
        assert result["rule_type"] == sample_alert.rule_type
        assert result["severity"] == sample_alert.severity.value
        assert result["status"] == sample_alert.status.value
        assert result["title"] == sample_alert.title
        assert result["message"] == sample_alert.message


class TestAdapterIntegration:
    """Integration tests for adapter."""

    @pytest.mark.asyncio
    async def test_full_alert_lifecycle(self, adapter, sample_alert, mock_db):
        """Test complete alert lifecycle through adapter."""
        alert_id = sample_alert.id
        user_id = uuid4()

        # 1. Alert exists (pending)
        adapter.alert_repo.get.return_value = sample_alert

        # 2. Acknowledge alert
        acknowledged = await adapter.acknowledge_alert(
            alert_id, user_id, "acknowledged"
        )
        assert acknowledged.status == AlertStatus.ACKNOWLEDGED

        # 3. Resolve alert
        sample_alert.status = AlertStatus.ACKNOWLEDGED  # Update for next call
        resolved = await adapter.resolve_alert(alert_id, user_id, "resolved")
        assert resolved.status == AlertStatus.RESOLVED

    def test_adapter_repr(self, adapter):
        """Test adapter string representation."""
        repr_str = repr(adapter)

        assert "AlertManagerAdapter" in repr_str
        assert "repositories=4" in repr_str
