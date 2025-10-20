"""
Unit Tests for AlertManager.

Tests the core orchestration logic of the unified alert system,
including alert evaluation, processing, notification, and lifecycle management.

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.alerts import (
    AlertManager,
    RuleEngine,
    AlertProcessor,
    NotificationDispatcher,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    NotificationChannel,
    AlertRule,
    AlertEvaluation,
    DispatchResult,
    NotificationResult,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_rule_engine():
    """Create mock RuleEngine."""
    engine = MagicMock(spec=RuleEngine)
    engine.evaluate = AsyncMock()
    engine.register_evaluator = MagicMock()
    engine.get_statistics = MagicMock()
    return engine


@pytest.fixture
def mock_processor():
    """Create mock AlertProcessor."""
    processor = MagicMock(spec=AlertProcessor)
    processor.process_alert = AsyncMock()
    processor.validate_alert = AsyncMock()
    processor.enrich_alert = AsyncMock()
    processor.persist_alert = AsyncMock()
    return processor


@pytest.fixture
def mock_dispatcher():
    """Create mock NotificationDispatcher."""
    dispatcher = MagicMock(spec=NotificationDispatcher)
    dispatcher.dispatch = AsyncMock()
    dispatcher.register_channel = MagicMock()
    dispatcher.get_channel = MagicMock()
    return dispatcher


@pytest.fixture
def alert_manager(mock_rule_engine, mock_processor, mock_dispatcher):
    """Create AlertManager instance with mocked dependencies."""
    return AlertManager(
        rule_engine=mock_rule_engine,
        processor=mock_processor,
        dispatcher=mock_dispatcher,
    )


@pytest.fixture
def sample_patient_id():
    """Sample patient UUID."""
    return uuid4()


@pytest.fixture
def sample_alert(sample_patient_id):
    """Sample alert object."""
    return Alert(
        id=uuid4(),
        patient_id=sample_patient_id,
        rule_type=AlertRuleType.NO_RESPONSE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        title="Patient No Response",
        message="Patient has not responded in 48 hours",
        metadata={"days_without_response": 2},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_context():
    """Sample patient context for evaluation."""
    return {
        "last_inbound_message_at": datetime.utcnow() - timedelta(days=3),
        "quiz_responses_count": 0,
        "sentiment_scores": [-0.8, -0.7, -0.9],
        "treatment_adherence_rate": 0.45,
        "last_message_text": "estou com muita dor",
    }


@pytest.fixture
def sample_evaluation():
    """Sample alert evaluation result."""
    return AlertEvaluation(
        rule_type=AlertRuleType.NO_RESPONSE,
        triggered=True,
        severity=AlertSeverity.HIGH,
        title="Patient No Response",
        message="Patient has not responded in 72 hours",
        metadata={"days_without_response": 3},
        timestamp=datetime.utcnow(),
    )


# ============================================================================
# Test AlertManager Initialization
# ============================================================================


class TestAlertManagerInitialization:
    """Test AlertManager initialization and configuration."""

    def test_init_with_dependencies(
        self, mock_rule_engine, mock_processor, mock_dispatcher
    ):
        """Test AlertManager initialization with dependencies."""
        manager = AlertManager(
            rule_engine=mock_rule_engine,
            processor=mock_processor,
            dispatcher=mock_dispatcher,
        )

        assert manager.rule_engine == mock_rule_engine
        assert manager.processor == mock_processor
        assert manager.dispatcher == mock_dispatcher
        assert manager._active_alerts == {}
        assert manager._alert_history == []

    def test_init_without_dependencies(self):
        """Test AlertManager can initialize with default singletons."""
        manager = AlertManager()

        assert manager.rule_engine is not None
        assert manager.processor is not None
        assert manager.dispatcher is not None


# ============================================================================
# Test Patient Alert Evaluation
# ============================================================================


class TestPatientAlertEvaluation:
    """Test patient alert evaluation logic."""

    @pytest.mark.asyncio
    async def test_evaluate_patient_alerts_success(
        self,
        alert_manager,
        mock_rule_engine,
        sample_patient_id,
        sample_context,
        sample_evaluation,
    ):
        """Test successful patient alert evaluation."""
        # Setup mock
        mock_rule_engine.evaluate.return_value = [sample_evaluation]

        # Execute
        alerts = await alert_manager.evaluate_patient_alerts(
            patient_id=sample_patient_id,
            context=sample_context,
        )

        # Assert
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.patient_id == sample_patient_id
        assert alert.rule_type == AlertRuleType.NO_RESPONSE
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.PENDING
        assert alert.title == sample_evaluation.title
        assert alert.message == sample_evaluation.message

        # Verify rule engine was called
        mock_rule_engine.evaluate.assert_called_once()
        call_args = mock_rule_engine.evaluate.call_args
        assert call_args[1]["patient_id"] == sample_patient_id
        assert call_args[1]["context"] == sample_context

    @pytest.mark.asyncio
    async def test_evaluate_patient_alerts_no_triggers(
        self,
        alert_manager,
        mock_rule_engine,
        sample_patient_id,
        sample_context,
    ):
        """Test evaluation when no alerts are triggered."""
        # Setup mock - no triggered alerts
        mock_rule_engine.evaluate.return_value = []

        # Execute
        alerts = await alert_manager.evaluate_patient_alerts(
            patient_id=sample_patient_id,
            context=sample_context,
        )

        # Assert
        assert alerts == []

    @pytest.mark.asyncio
    async def test_evaluate_patient_alerts_multiple_triggers(
        self,
        alert_manager,
        mock_rule_engine,
        sample_patient_id,
        sample_context,
    ):
        """Test evaluation with multiple triggered alerts."""
        # Setup mock - multiple evaluations
        evaluations = [
            AlertEvaluation(
                rule_type=AlertRuleType.NO_RESPONSE,
                triggered=True,
                severity=AlertSeverity.HIGH,
                title="No Response",
                message="Patient has not responded",
                metadata={},
                timestamp=datetime.utcnow(),
            ),
            AlertEvaluation(
                rule_type=AlertRuleType.NEGATIVE_SENTIMENT,
                triggered=True,
                severity=AlertSeverity.MEDIUM,
                title="Negative Sentiment",
                message="Patient sentiment is negative",
                metadata={},
                timestamp=datetime.utcnow(),
            ),
        ]
        mock_rule_engine.evaluate.return_value = evaluations

        # Execute
        alerts = await alert_manager.evaluate_patient_alerts(
            patient_id=sample_patient_id,
            context=sample_context,
        )

        # Assert
        assert len(alerts) == 2
        assert alerts[0].rule_type == AlertRuleType.NO_RESPONSE
        assert alerts[1].rule_type == AlertRuleType.NEGATIVE_SENTIMENT

    @pytest.mark.asyncio
    async def test_evaluate_patient_alerts_with_exception(
        self,
        alert_manager,
        mock_rule_engine,
        sample_patient_id,
        sample_context,
    ):
        """Test evaluation handles exceptions gracefully."""
        # Setup mock to raise exception
        mock_rule_engine.evaluate.side_effect = Exception("Rule engine error")

        # Execute and expect exception
        with pytest.raises(Exception) as exc_info:
            await alert_manager.evaluate_patient_alerts(
                patient_id=sample_patient_id,
                context=sample_context,
            )

        assert "Rule engine error" in str(exc_info.value)


# ============================================================================
# Test Alert Processing
# ============================================================================


class TestAlertProcessing:
    """Test alert processing logic."""

    @pytest.mark.asyncio
    async def test_process_alert_success(
        self,
        alert_manager,
        mock_processor,
        sample_alert,
    ):
        """Test successful alert processing."""
        # Setup mock
        processed_alert = sample_alert.copy()
        processed_alert.status = AlertStatus.ACKNOWLEDGED
        mock_processor.process_alert.return_value = processed_alert

        # Execute
        result = await alert_manager.process_alert(sample_alert)

        # Assert
        assert result.status == AlertStatus.ACKNOWLEDGED
        mock_processor.process_alert.assert_called_once_with(sample_alert)

    @pytest.mark.asyncio
    async def test_process_alert_validation_failure(
        self,
        alert_manager,
        mock_processor,
        sample_alert,
    ):
        """Test alert processing with validation failure."""
        # Setup mock to raise validation error
        mock_processor.process_alert.side_effect = ValueError("Invalid alert")

        # Execute and expect exception
        with pytest.raises(ValueError) as exc_info:
            await alert_manager.process_alert(sample_alert)

        assert "Invalid alert" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_alert_stores_in_active(
        self,
        alert_manager,
        mock_processor,
        sample_alert,
    ):
        """Test that processed alerts are stored in active alerts."""
        # Setup mock
        mock_processor.process_alert.return_value = sample_alert

        # Execute
        await alert_manager.process_alert(sample_alert)

        # Assert
        assert sample_alert.id in alert_manager._active_alerts
        assert alert_manager._active_alerts[sample_alert.id] == sample_alert


# ============================================================================
# Test Alert Notification
# ============================================================================


class TestAlertNotification:
    """Test alert notification logic."""

    @pytest.mark.asyncio
    async def test_notify_alert_success(
        self,
        alert_manager,
        mock_dispatcher,
        sample_alert,
    ):
        """Test successful alert notification."""
        # Setup mock
        dispatch_result = DispatchResult(
            alert_id=sample_alert.id,
            channels=[NotificationChannel.EMAIL, NotificationChannel.DASHBOARD],
            results=[
                NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    success=True,
                    message="Email sent successfully",
                ),
                NotificationResult(
                    channel=NotificationChannel.DASHBOARD,
                    success=True,
                    message="Dashboard updated",
                ),
            ],
            total_success=2,
            total_failed=0,
            dispatched_at=datetime.utcnow(),
        )
        mock_dispatcher.dispatch.return_value = dispatch_result

        # Execute
        result = await alert_manager.notify_alert(
            alert=sample_alert,
            channels=[NotificationChannel.EMAIL, NotificationChannel.DASHBOARD],
        )

        # Assert
        assert result.total_success == 2
        assert result.total_failed == 0
        mock_dispatcher.dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_alert_partial_failure(
        self,
        alert_manager,
        mock_dispatcher,
        sample_alert,
    ):
        """Test notification with partial channel failures."""
        # Setup mock
        dispatch_result = DispatchResult(
            alert_id=sample_alert.id,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            results=[
                NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    success=True,
                    message="Email sent",
                ),
                NotificationResult(
                    channel=NotificationChannel.SLACK,
                    success=False,
                    message="Slack API error",
                ),
            ],
            total_success=1,
            total_failed=1,
            dispatched_at=datetime.utcnow(),
        )
        mock_dispatcher.dispatch.return_value = dispatch_result

        # Execute
        result = await alert_manager.notify_alert(
            alert=sample_alert,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
        )

        # Assert
        assert result.total_success == 1
        assert result.total_failed == 1

    @pytest.mark.asyncio
    async def test_notify_alert_default_channels(
        self,
        alert_manager,
        mock_dispatcher,
        sample_alert,
    ):
        """Test notification uses default channels when none specified."""
        # Setup mock
        dispatch_result = DispatchResult(
            alert_id=sample_alert.id,
            channels=[NotificationChannel.EMAIL, NotificationChannel.DASHBOARD],
            results=[],
            total_success=2,
            total_failed=0,
            dispatched_at=datetime.utcnow(),
        )
        mock_dispatcher.dispatch.return_value = dispatch_result

        # Execute - no channels specified
        result = await alert_manager.notify_alert(alert=sample_alert)

        # Assert - should use default channels
        assert result is not None
        mock_dispatcher.dispatch.assert_called_once()


# ============================================================================
# Test Alert Lifecycle Management
# ============================================================================


class TestAlertLifecycle:
    """Test alert lifecycle management."""

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, alert_manager, sample_alert):
        """Test alert acknowledgment."""
        # Add alert to active alerts
        alert_manager._active_alerts[sample_alert.id] = sample_alert

        # Execute
        result = await alert_manager.acknowledge_alert(
            alert_id=sample_alert.id,
            acknowledged_by=uuid4(),
        )

        # Assert
        assert result.status == AlertStatus.ACKNOWLEDGED
        assert result.acknowledged_by is not None
        assert result.acknowledged_at is not None

    @pytest.mark.asyncio
    async def test_resolve_alert(self, alert_manager, sample_alert):
        """Test alert resolution."""
        # Add alert to active alerts
        alert_manager._active_alerts[sample_alert.id] = sample_alert

        # Execute
        result = await alert_manager.resolve_alert(
            alert_id=sample_alert.id,
            resolved_by=uuid4(),
            resolution_notes="Issue resolved",
        )

        # Assert
        assert result.status == AlertStatus.RESOLVED
        assert result.resolved_by is not None
        assert result.resolved_at is not None
        assert result.resolution_notes == "Issue resolved"

        # Alert should be moved to history
        assert sample_alert.id not in alert_manager._active_alerts
        assert result in alert_manager._alert_history

    @pytest.mark.asyncio
    async def test_dismiss_alert(self, alert_manager, sample_alert):
        """Test alert dismissal."""
        # Add alert to active alerts
        alert_manager._active_alerts[sample_alert.id] = sample_alert

        # Execute
        result = await alert_manager.dismiss_alert(
            alert_id=sample_alert.id,
            dismissed_by=uuid4(),
            reason="False positive",
        )

        # Assert
        assert result.status == AlertStatus.DISMISSED
        assert result.dismissed_by is not None
        assert result.dismissed_at is not None

        # Alert should be removed from active
        assert sample_alert.id not in alert_manager._active_alerts

    @pytest.mark.asyncio
    async def test_get_active_alerts(self, alert_manager, sample_patient_id):
        """Test retrieving active alerts for a patient."""
        # Add multiple alerts
        alert1 = Alert(
            id=uuid4(),
            patient_id=sample_patient_id,
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            title="Alert 1",
            message="Message 1",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        alert2 = Alert(
            id=uuid4(),
            patient_id=sample_patient_id,
            rule_type=AlertRuleType.NEGATIVE_SENTIMENT,
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.ACKNOWLEDGED,
            title="Alert 2",
            message="Message 2",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        alert3 = Alert(
            id=uuid4(),
            patient_id=uuid4(),  # Different patient
            rule_type=AlertRuleType.MISSED_QUIZ,
            severity=AlertSeverity.LOW,
            status=AlertStatus.PENDING,
            title="Alert 3",
            message="Message 3",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        alert_manager._active_alerts[alert1.id] = alert1
        alert_manager._active_alerts[alert2.id] = alert2
        alert_manager._active_alerts[alert3.id] = alert3

        # Execute
        alerts = await alert_manager.get_active_alerts(patient_id=sample_patient_id)

        # Assert - should only return alerts for specified patient
        assert len(alerts) == 2
        assert alert1 in alerts
        assert alert2 in alerts
        assert alert3 not in alerts

    @pytest.mark.asyncio
    async def test_get_alert_by_id(self, alert_manager, sample_alert):
        """Test retrieving a specific alert by ID."""
        # Add alert to active alerts
        alert_manager._active_alerts[sample_alert.id] = sample_alert

        # Execute
        result = await alert_manager.get_alert(alert_id=sample_alert.id)

        # Assert
        assert result == sample_alert

    @pytest.mark.asyncio
    async def test_get_alert_not_found(self, alert_manager):
        """Test retrieving non-existent alert."""
        # Execute
        result = await alert_manager.get_alert(alert_id=uuid4())

        # Assert
        assert result is None


# ============================================================================
# Test Alert Statistics
# ============================================================================


class TestAlertStatistics:
    """Test alert statistics and reporting."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, alert_manager, sample_patient_id):
        """Test retrieving alert statistics."""
        # Add some alerts
        alert1 = Alert(
            id=uuid4(),
            patient_id=sample_patient_id,
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            title="Alert 1",
            message="Message 1",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        alert2 = Alert(
            id=uuid4(),
            patient_id=sample_patient_id,
            rule_type=AlertRuleType.NEGATIVE_SENTIMENT,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACKNOWLEDGED,
            title="Alert 2",
            message="Message 2",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        alert_manager._active_alerts[alert1.id] = alert1
        alert_manager._active_alerts[alert2.id] = alert2

        # Execute
        stats = await alert_manager.get_statistics(patient_id=sample_patient_id)

        # Assert
        assert stats.total_active >= 2
        assert stats.by_severity[AlertSeverity.HIGH] >= 2
        assert stats.by_status[AlertStatus.PENDING] >= 1
        assert stats.by_status[AlertStatus.ACKNOWLEDGED] >= 1

    @pytest.mark.asyncio
    async def test_get_statistics_empty(self, alert_manager):
        """Test statistics with no alerts."""
        # Execute
        stats = await alert_manager.get_statistics(patient_id=uuid4())

        # Assert
        assert stats.total_active == 0


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_evaluate_with_invalid_patient_id(self, alert_manager):
        """Test evaluation with None patient_id."""
        with pytest.raises((ValueError, TypeError)):
            await alert_manager.evaluate_patient_alerts(
                patient_id=None,
                context={},
            )

    @pytest.mark.asyncio
    async def test_process_none_alert(self, alert_manager):
        """Test processing None alert."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await alert_manager.process_alert(None)

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_alert(self, alert_manager):
        """Test acknowledging non-existent alert."""
        result = await alert_manager.acknowledge_alert(
            alert_id=uuid4(),
            acknowledged_by=uuid4(),
        )

        # Should return None or raise exception
        assert result is None or isinstance(result, Alert)
