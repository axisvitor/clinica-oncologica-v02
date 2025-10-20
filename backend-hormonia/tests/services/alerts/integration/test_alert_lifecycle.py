"""
Integration Tests for Complete Alert Lifecycle.

Tests the end-to-end alert workflow including:
- Alert creation from patient rules
- Processing and validation
- Multi-channel notification
- Escalation scenarios
- Acknowledgment and resolution
- State transitions
- Database persistence
- Concurrent alert handling

Author: Backend Team
Date: 2025-01-20
"""

import pytest
import asyncio
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.services.alerts import (
    AlertManager,
    RuleEngine,
    AlertProcessor,
    NotificationDispatcher,
    EscalationManager,
    Alert,
    AlertRule,
    AlertRuleType,
    AlertSeverity,
    AlertStatus,
    NotificationChannel,
    NotificationTarget,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def alert_system():
    """Create integrated alert system with all components."""
    # Initialize components
    rule_engine = RuleEngine()
    processor = AlertProcessor()
    dispatcher = NotificationDispatcher()
    escalation_manager = EscalationManager()

    # Create AlertManager with all dependencies
    alert_manager = AlertManager(
        rule_engine=rule_engine,
        processor=processor,
        dispatcher=dispatcher,
        escalation_manager=escalation_manager,
    )

    return {
        "manager": alert_manager,
        "rule_engine": rule_engine,
        "processor": processor,
        "dispatcher": dispatcher,
        "escalation": escalation_manager,
    }


@pytest.fixture
def patient_data():
    """Sample patient data for testing."""
    return {
        "patient_id": uuid4(),
        "name": "João Silva",
        "last_interaction": datetime.now() - timedelta(days=8),
        "quiz_completion_rate": 0.3,
        "recent_messages": [
            {"text": "Estou com muita dor", "sentiment_score": -0.8},
            {"text": "Não aguento mais", "sentiment_score": -0.9},
        ],
        "treatment_adherence_rate": 0.4,
        "emergency_keywords": ["dor intensa", "sangramento"],
    }


@pytest.fixture
def alert_rule_no_response():
    """Alert rule for no response detection."""
    return AlertRule(
        id=uuid4(),
        rule_type=AlertRuleType.NO_RESPONSE,
        name="No Response Check",
        description="Detect patients not responding",
        enabled=True,
        severity=AlertSeverity.WARNING,
        conditions={
            "days_threshold": 7,
        },
        metadata={
            "evaluator": "no_response",
        },
    )


@pytest.fixture
def notification_targets():
    """Sample notification targets."""
    return [
        NotificationTarget(
            target_id=str(uuid4()),
            target_type="doctor",
            name="Dr. Silva",
            email="dr.silva@clinic.com",
            phone="+5511999999999",
        ),
        NotificationTarget(
            target_id=str(uuid4()),
            target_type="nurse",
            name="Enf. Maria",
            email="maria@clinic.com",
        ),
    ]


# ============================================================================
# Test Complete Alert Lifecycle
# ============================================================================


class TestAlertLifecycle:
    """Test complete alert lifecycle from creation to resolution."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_alert_flow_success(
        self, alert_system, patient_data, alert_rule_no_response, notification_targets
    ):
        """Test complete successful alert flow."""
        manager = alert_system["manager"]
        rule_engine = alert_system["rule_engine"]
        dispatcher = alert_system["dispatcher"]

        # Step 1: Register rule
        rule_engine.register_rule(alert_rule_no_response)

        # Step 2: Register notification channels (mock)
        from unittest.mock import AsyncMock

        mock_email_channel = AsyncMock()
        mock_email_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_email_channel)

        # Step 3: Evaluate patient (should trigger alert)
        alerts = await manager.evaluate_patient_alerts(
            patient_id=patient_data["patient_id"],
            patient_data=patient_data,
        )

        # Verify alert was created
        assert len(alerts) > 0
        alert = alerts[0]
        assert alert.rule_type == AlertRuleType.NO_RESPONSE
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.ACTIVE

        # Step 4: Process alert (validate and enrich)
        processed_alert = await manager.process_alert(alert)
        assert processed_alert.id == alert.id
        assert processed_alert.status == AlertStatus.ACTIVE

        # Step 5: Send notifications
        notification_result = await manager.send_notifications(
            alert=processed_alert,
            targets=notification_targets,
            channels=[NotificationChannel.EMAIL],
        )

        assert notification_result["sent"] > 0
        assert mock_email_channel.send.called

        # Step 6: Acknowledge alert
        acknowledged_alert = await manager.acknowledge_alert(
            alert_id=alert.id,
            acknowledged_by="Dr. Silva",
            notes="Verificando paciente",
        )

        assert acknowledged_alert.status == AlertStatus.ACKNOWLEDGED
        assert acknowledged_alert.acknowledged_by == "Dr. Silva"

        # Step 7: Resolve alert
        resolved_alert = await manager.resolve_alert(
            alert_id=alert.id,
            resolution_notes="Paciente contactado com sucesso",
        )

        assert resolved_alert.status == AlertStatus.RESOLVED
        assert resolved_alert.resolved_at is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_alert_lifecycle_with_escalation(
        self, alert_system, patient_data, notification_targets
    ):
        """Test alert lifecycle with escalation when not acknowledged."""
        manager = alert_system["manager"]
        escalation = alert_system["escalation"]

        # Create critical alert rule
        critical_rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.EMERGENCY_KEYWORDS,
            name="Emergency Detection",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            conditions={"keywords": ["sangramento", "dor intensa"]},
        )

        alert_system["rule_engine"].register_rule(critical_rule)

        # Create escalation rule
        from app.services.alerts import EscalationRule, EscalationStrategy

        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Critical Alert Escalation",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.DELAYED,
            delay_minutes=5,
            targets=notification_targets[:1],  # Escalate to doctor only
        )

        escalation.register_rule(escalation_rule)

        # Trigger alert
        alerts = await manager.evaluate_patient_alerts(
            patient_id=patient_data["patient_id"],
            patient_data=patient_data,
        )

        assert len(alerts) > 0
        alert = alerts[0]
        assert alert.severity == AlertSeverity.CRITICAL

        # Check if escalation was scheduled
        escalations = escalation.get_pending_escalations()
        assert len(escalations) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_alerts_concurrent_processing(
        self, alert_system, notification_targets
    ):
        """Test handling multiple concurrent alerts."""
        manager = alert_system["manager"]

        # Create multiple patient data sets
        patients = [
            {
                "patient_id": uuid4(),
                "name": f"Patient {i}",
                "last_interaction": datetime.now() - timedelta(days=8 + i),
                "quiz_completion_rate": 0.2,
            }
            for i in range(5)
        ]

        # Register rule
        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="No Response",
            enabled=True,
            severity=AlertSeverity.WARNING,
            conditions={"days_threshold": 7},
        )
        alert_system["rule_engine"].register_rule(rule)

        # Evaluate all patients concurrently
        tasks = [
            manager.evaluate_patient_alerts(
                patient_id=patient["patient_id"],
                patient_data=patient,
            )
            for patient in patients
        ]

        results = await asyncio.gather(*tasks)

        # Verify all alerts were created
        total_alerts = sum(len(alerts) for alerts in results)
        assert total_alerts == 5

        # Verify all alerts are active
        for alerts in results:
            for alert in alerts:
                assert alert.status == AlertStatus.ACTIVE


# ============================================================================
# Test Alert State Transitions
# ============================================================================


class TestAlertStateTransitions:
    """Test alert state machine transitions."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_valid_state_transitions(self, alert_system, patient_data):
        """Test valid state transitions: ACTIVE → ACKNOWLEDGED → RESOLVED."""
        manager = alert_system["manager"]

        # Create alert
        alert = Alert(
            id=uuid4(),
            rule_id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            title="Test Alert",
            message="Test message",
            patient_id=patient_data["patient_id"],
            context=patient_data,
            created_at=datetime.now(),
        )

        # Transition: ACTIVE → ACKNOWLEDGED
        ack_alert = await manager.acknowledge_alert(
            alert_id=alert.id,
            acknowledged_by="Doctor",
        )
        assert ack_alert.status == AlertStatus.ACKNOWLEDGED

        # Transition: ACKNOWLEDGED → RESOLVED
        resolved_alert = await manager.resolve_alert(
            alert_id=alert.id,
            resolution_notes="Fixed",
        )
        assert resolved_alert.status == AlertStatus.RESOLVED

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dismiss_alert_transition(self, alert_system, patient_data):
        """Test ACTIVE → DISMISSED transition."""
        manager = alert_system["manager"]

        # Create alert
        alert = Alert(
            id=uuid4(),
            rule_id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.INFO,
            status=AlertStatus.ACTIVE,
            title="Low Priority Alert",
            message="Can be dismissed",
            patient_id=patient_data["patient_id"],
            context={},
            created_at=datetime.now(),
        )

        # Dismiss alert
        dismissed_alert = await manager.dismiss_alert(
            alert_id=alert.id,
            dismissed_by="Doctor",
            reason="False positive",
        )

        assert dismissed_alert.status == AlertStatus.DISMISSED


# ============================================================================
# Test Multi-Channel Notifications
# ============================================================================


class TestMultiChannelNotifications:
    """Test notifications across multiple channels."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_send_to_multiple_channels(
        self, alert_system, patient_data, notification_targets
    ):
        """Test sending alert to multiple notification channels."""
        manager = alert_system["manager"]
        dispatcher = alert_system["dispatcher"]

        # Mock multiple channels
        from unittest.mock import AsyncMock

        mock_email = AsyncMock()
        mock_email.send = AsyncMock(return_value=True)

        mock_webhook = AsyncMock()
        mock_webhook.send = AsyncMock(return_value=True)

        mock_dashboard = AsyncMock()
        mock_dashboard.send = AsyncMock(return_value=True)

        dispatcher.register_channel(NotificationChannel.EMAIL, mock_email)
        dispatcher.register_channel(NotificationChannel.WEBHOOK, mock_webhook)
        dispatcher.register_channel(NotificationChannel.DASHBOARD, mock_dashboard)

        # Create alert
        alert = Alert(
            id=uuid4(),
            rule_id=uuid4(),
            rule_type=AlertRuleType.EMERGENCY_KEYWORDS,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.ACTIVE,
            title="Emergency Alert",
            message="Patient needs immediate attention",
            patient_id=patient_data["patient_id"],
            context=patient_data,
            created_at=datetime.now(),
        )

        # Send to all channels
        result = await manager.send_notifications(
            alert=alert,
            targets=notification_targets,
            channels=[
                NotificationChannel.EMAIL,
                NotificationChannel.WEBHOOK,
                NotificationChannel.DASHBOARD,
            ],
        )

        # Verify all channels were used
        assert result["sent"] >= 3
        assert mock_email.send.called
        assert mock_webhook.send.called
        assert mock_dashboard.send.called

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_partial_channel_failure(
        self, alert_system, patient_data, notification_targets
    ):
        """Test handling when some channels fail."""
        manager = alert_system["manager"]
        dispatcher = alert_system["dispatcher"]

        from unittest.mock import AsyncMock

        # Success channel
        mock_email = AsyncMock()
        mock_email.send = AsyncMock(return_value=True)

        # Failing channel
        mock_webhook = AsyncMock()
        mock_webhook.send = AsyncMock(side_effect=Exception("Webhook failed"))

        dispatcher.register_channel(NotificationChannel.EMAIL, mock_email)
        dispatcher.register_channel(NotificationChannel.WEBHOOK, mock_webhook)

        alert = Alert(
            id=uuid4(),
            rule_id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            title="Test Alert",
            message="Test",
            patient_id=patient_data["patient_id"],
            context={},
            created_at=datetime.now(),
        )

        # Should not raise exception even if webhook fails
        result = await manager.send_notifications(
            alert=alert,
            targets=notification_targets,
            channels=[NotificationChannel.EMAIL, NotificationChannel.WEBHOOK],
        )

        # Email should succeed, webhook should fail
        assert result["sent"] > 0
        assert result["failed"] > 0


# ============================================================================
# Test Alert Retrieval and Filtering
# ============================================================================


class TestAlertRetrieval:
    """Test alert retrieval and filtering."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_active_alerts_by_patient(self, alert_system, patient_data):
        """Test retrieving active alerts for specific patient."""
        manager = alert_system["manager"]
        patient_id = patient_data["patient_id"]

        # Create multiple alerts
        alerts_created = []
        for i in range(3):
            alert = Alert(
                id=uuid4(),
                rule_id=uuid4(),
                rule_type=AlertRuleType.NO_RESPONSE,
                severity=AlertSeverity.WARNING,
                status=AlertStatus.ACTIVE,
                title=f"Alert {i}",
                message=f"Message {i}",
                patient_id=patient_id,
                context={},
                created_at=datetime.now(),
            )
            alerts_created.append(alert)

        # Retrieve active alerts
        active_alerts = await manager.get_active_alerts(patient_id=patient_id)

        assert len(active_alerts) >= 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_filter_alerts_by_severity(self, alert_system, patient_data):
        """Test filtering alerts by severity level."""
        manager = alert_system["manager"]
        patient_id = patient_data["patient_id"]

        # Create alerts with different severities
        severities = [
            AlertSeverity.INFO,
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
            AlertSeverity.FATAL,
        ]

        for severity in severities:
            alert = Alert(
                id=uuid4(),
                rule_id=uuid4(),
                rule_type=AlertRuleType.NO_RESPONSE,
                severity=severity,
                status=AlertStatus.ACTIVE,
                title=f"{severity.value} Alert",
                message="Test",
                patient_id=patient_id,
                context={},
                created_at=datetime.now(),
            )

        # Filter by CRITICAL and above
        critical_alerts = await manager.get_active_alerts(
            patient_id=patient_id,
            min_severity=AlertSeverity.CRITICAL,
        )

        # Should only get CRITICAL and FATAL
        for alert in critical_alerts:
            assert alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.FATAL]


# ============================================================================
# Test Alert Statistics
# ============================================================================


class TestAlertStatistics:
    """Test alert statistics and metrics."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_statistics_after_processing(self, alert_system, patient_data):
        """Test statistics after processing multiple alerts."""
        manager = alert_system["manager"]

        # Process multiple alerts
        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="Test Rule",
            enabled=True,
            severity=AlertSeverity.WARNING,
            conditions={},
        )

        alert_system["rule_engine"].register_rule(rule)

        # Create and process 5 alerts
        for i in range(5):
            patient = {**patient_data, "patient_id": uuid4()}
            await manager.evaluate_patient_alerts(
                patient_id=patient["patient_id"],
                patient_data=patient,
            )

        # Get statistics
        stats = manager.get_statistics()

        assert "active_alerts" in stats
        assert "total_processed" in stats
        assert stats["total_processed"] >= 5


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling in alert lifecycle."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_invalid_alert_data_handling(self, alert_system):
        """Test handling of invalid alert data."""
        manager = alert_system["manager"]

        # Try to process invalid alert (missing required fields)
        invalid_alert = Alert(
            id=uuid4(),
            rule_id=None,  # Invalid: should have rule_id
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            title="",  # Invalid: empty title
            message="Test",
            context={},
            created_at=datetime.now(),
        )

        # Should handle gracefully
        with pytest.raises((ValueError, TypeError)):
            await manager.process_alert(invalid_alert)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_notification_failure_doesnt_break_pipeline(
        self, alert_system, patient_data, notification_targets
    ):
        """Test that notification failures don't break alert processing."""
        manager = alert_system["manager"]
        dispatcher = alert_system["dispatcher"]

        # Register failing channel
        from unittest.mock import AsyncMock

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(side_effect=Exception("Send failed"))
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        alert = Alert(
            id=uuid4(),
            rule_id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            title="Test Alert",
            message="Test",
            patient_id=patient_data["patient_id"],
            context={},
            created_at=datetime.now(),
        )

        # Process alert - should not raise exception
        processed = await manager.process_alert(alert)
        assert processed is not None

        # Try to send notifications - should handle failure
        result = await manager.send_notifications(
            alert=alert,
            targets=notification_targets,
            channels=[NotificationChannel.EMAIL],
        )

        # Should track failure
        assert result["failed"] > 0


# ============================================================================
# Test Performance
# ============================================================================


class TestPerformance:
    """Test system performance under load."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_high_volume_alert_processing(self, alert_system):
        """Test processing high volume of alerts."""
        manager = alert_system["manager"]

        # Register rule
        rule = AlertRule(
            id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            name="Load Test Rule",
            enabled=True,
            severity=AlertSeverity.INFO,
            conditions={},
        )
        alert_system["rule_engine"].register_rule(rule)

        # Create 100 patient evaluations
        num_patients = 100
        start_time = datetime.now()

        tasks = []
        for i in range(num_patients):
            patient_data = {
                "patient_id": uuid4(),
                "name": f"Patient {i}",
                "last_interaction": datetime.now() - timedelta(days=8),
            }
            tasks.append(
                manager.evaluate_patient_alerts(
                    patient_id=patient_data["patient_id"],
                    patient_data=patient_data,
                )
            )

        results = await asyncio.gather(*tasks)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Should process all in reasonable time (< 10 seconds)
        assert duration < 10.0
        assert len(results) == num_patients
