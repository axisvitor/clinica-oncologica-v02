"""
Integration Tests for Alert Escalation Flow.

Tests the complete escalation workflow including:
- Immediate escalation on critical alerts
- Delayed escalation with timeout
- Progressive multi-level escalation
- Escalation cancellation on acknowledgment
- Multiple concurrent escalations
- Escalation notification delivery
- Escalation history tracking
- Cross-component integration (AlertManager + EscalationManager + Dispatcher)

Author: Backend Team
Date: 2025-01-20
"""

import pytest
import asyncio
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from app.services.alerts import (
    AlertManager,
    EscalationManager,
    NotificationDispatcher,
    Alert,
    AlertRule,
    AlertRuleType,
    AlertSeverity,
    AlertStatus,
    EscalationRule,
    EscalationStrategy,
    Escalation,
    NotificationChannel,
    NotificationTarget,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def escalation_system():
    """Create integrated escalation system."""
    dispatcher = NotificationDispatcher()
    escalation_manager = EscalationManager(dispatcher=dispatcher)
    alert_manager = AlertManager(escalation_manager=escalation_manager)

    return {
        "alert_manager": alert_manager,
        "escalation_manager": escalation_manager,
        "dispatcher": dispatcher,
    }


@pytest.fixture
def escalation_targets():
    """Multi-level escalation targets."""
    return {
        "level_1": [
            NotificationTarget(
                target_id=str(uuid4()),
                target_type="nurse",
                name="Enf. Maria",
                email="maria@clinic.com",
                phone="+5511999991111",
            )
        ],
        "level_2": [
            NotificationTarget(
                target_id=str(uuid4()),
                target_type="doctor",
                name="Dr. Silva",
                email="dr.silva@clinic.com",
                phone="+5511999992222",
            )
        ],
        "level_3": [
            NotificationTarget(
                target_id=str(uuid4()),
                target_type="coordinator",
                name="Coord. João",
                email="joao@clinic.com",
                phone="+5511999993333",
            )
        ],
    }


@pytest.fixture
def critical_alert():
    """Critical alert that should trigger escalation."""
    return Alert(
        id=uuid4(),
        rule_id=uuid4(),
        rule_type=AlertRuleType.EMERGENCY_KEYWORDS,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.ACTIVE,
        title="Emergency: Patient in Distress",
        message="Patient reported severe symptoms",
        patient_id=uuid4(),
        context={
            "keywords_found": ["dor intensa", "sangramento"],
            "patient_name": "João Silva",
        },
        metadata={
            "urgency": "high",
            "requires_immediate_attention": True,
        },
        created_at=datetime.now(),
    )


@pytest.fixture
def warning_alert():
    """Warning alert for delayed escalation testing."""
    return Alert(
        id=uuid4(),
        rule_id=uuid4(),
        rule_type=AlertRuleType.NO_RESPONSE,
        severity=AlertSeverity.WARNING,
        status=AlertStatus.ACTIVE,
        title="Patient Not Responding",
        message="No response for 7 days",
        patient_id=uuid4(),
        context={"days_no_response": 7},
        created_at=datetime.now(),
    )


# ============================================================================
# Test Immediate Escalation
# ============================================================================


class TestImmediateEscalation:
    """Test immediate escalation strategy."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_immediate_escalation_on_critical_alert(
        self, escalation_system, critical_alert, escalation_targets
    ):
        """Test that critical alerts trigger immediate escalation."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        # Register mock notification channel
        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        # Create immediate escalation rule
        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Critical Alert Immediate Escalation",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.IMMEDIATE,
            delay_minutes=0,
            targets=escalation_targets["level_2"],  # Escalate to doctor
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Trigger escalation
        escalations = await escalation_manager.evaluate_alert(critical_alert)

        # Verify immediate escalation created
        assert len(escalations) > 0
        escalation = escalations[0]
        assert escalation.strategy == EscalationStrategy.IMMEDIATE
        assert escalation.alert_id == critical_alert.id

        # Execute escalation
        await escalation_manager.execute_escalation(escalation.id)

        # Verify notification sent
        assert mock_channel.send.called
        call_args = mock_channel.send.call_args
        assert "Emergency" in str(call_args)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_immediate_escalation_multiple_targets(
        self, escalation_system, critical_alert, escalation_targets
    ):
        """Test immediate escalation to multiple targets."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        # Escalate to multiple levels immediately
        all_targets = (
            escalation_targets["level_1"]
            + escalation_targets["level_2"]
            + escalation_targets["level_3"]
        )

        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Multi-Target Immediate Escalation",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.IMMEDIATE,
            targets=all_targets,
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Trigger and execute
        escalations = await escalation_manager.evaluate_alert(critical_alert)
        assert len(escalations) > 0

        await escalation_manager.execute_escalation(escalations[0].id)

        # Should have sent to all 3 targets
        assert mock_channel.send.call_count == 3


# ============================================================================
# Test Delayed Escalation
# ============================================================================


class TestDelayedEscalation:
    """Test delayed escalation strategy with timeouts."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delayed_escalation_not_executed_immediately(
        self, escalation_system, warning_alert, escalation_targets
    ):
        """Test that delayed escalation is scheduled, not executed immediately."""
        escalation_manager = escalation_system["escalation_manager"]

        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Delayed Escalation",
            alert_types=[AlertRuleType.NO_RESPONSE],
            min_severity=AlertSeverity.WARNING,
            strategy=EscalationStrategy.DELAYED,
            delay_minutes=30,
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Create escalation
        escalations = await escalation_manager.evaluate_alert(warning_alert)

        assert len(escalations) > 0
        escalation = escalations[0]

        # Should be scheduled for future
        assert escalation.scheduled_for > datetime.now()
        assert escalation.status == "pending"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delayed_escalation_executes_after_timeout(
        self, escalation_system, warning_alert, escalation_targets
    ):
        """Test that delayed escalation executes after timeout period."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        # Short delay for testing (1 second)
        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Short Delayed Escalation",
            alert_types=[AlertRuleType.NO_RESPONSE],
            min_severity=AlertSeverity.WARNING,
            strategy=EscalationStrategy.DELAYED,
            delay_minutes=0.02,  # ~1 second
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Create escalation
        escalations = await escalation_manager.evaluate_alert(warning_alert)
        escalation = escalations[0]

        # Manually set scheduled time to past (simulate time passing)
        escalation.scheduled_for = datetime.now() - timedelta(seconds=1)

        # Execute pending escalations
        await escalation_manager.execute_pending_escalations()

        # Should have been executed
        assert mock_channel.send.called

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delayed_escalation_cancelled_on_acknowledgment(
        self, escalation_system, warning_alert, escalation_targets
    ):
        """Test that delayed escalation is cancelled when alert is acknowledged."""
        escalation_manager = escalation_system["escalation_manager"]
        alert_manager = escalation_system["alert_manager"]

        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Cancellable Delayed Escalation",
            alert_types=[AlertRuleType.NO_RESPONSE],
            min_severity=AlertSeverity.WARNING,
            strategy=EscalationStrategy.DELAYED,
            delay_minutes=30,
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Create escalation
        escalations = await escalation_manager.evaluate_alert(warning_alert)
        assert len(escalations) > 0
        escalation = escalations[0]

        # Acknowledge alert
        warning_alert.status = AlertStatus.ACKNOWLEDGED
        warning_alert.acknowledged_by = "Dr. Silva"
        warning_alert.acknowledged_at = datetime.now()

        # Cancel escalations for acknowledged alert
        await escalation_manager.cancel_escalations_for_alert(warning_alert.id)

        # Verify escalation was cancelled
        cancelled_escalation = escalation_manager.get_escalation(escalation.id)
        assert cancelled_escalation.status == "cancelled"


# ============================================================================
# Test Progressive Escalation
# ============================================================================


class TestProgressiveEscalation:
    """Test progressive multi-level escalation."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_progressive_escalation_multiple_levels(
        self, escalation_system, critical_alert, escalation_targets
    ):
        """Test progressive escalation through multiple levels."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        # Create 3-level progressive escalation
        level_1_rule = EscalationRule(
            id=uuid4(),
            name="Level 1: Nurse",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.PROGRESSIVE,
            level=1,
            delay_minutes=0,
            targets=escalation_targets["level_1"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        level_2_rule = EscalationRule(
            id=uuid4(),
            name="Level 2: Doctor",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.PROGRESSIVE,
            level=2,
            delay_minutes=5,
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        level_3_rule = EscalationRule(
            id=uuid4(),
            name="Level 3: Coordinator",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.PROGRESSIVE,
            level=3,
            delay_minutes=10,
            targets=escalation_targets["level_3"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(level_1_rule)
        escalation_manager.register_rule(level_2_rule)
        escalation_manager.register_rule(level_3_rule)

        # Trigger escalation
        escalations = await escalation_manager.evaluate_alert(critical_alert)

        # Should create 3 escalations (one per level)
        assert len(escalations) == 3

        # Verify escalation levels
        levels = [esc.level for esc in escalations]
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_progressive_escalation_stops_on_acknowledgment(
        self, escalation_system, critical_alert, escalation_targets
    ):
        """Test that progressive escalation stops when alert is acknowledged."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        # 2-level progressive
        level_1_rule = EscalationRule(
            id=uuid4(),
            name="Level 1",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.PROGRESSIVE,
            level=1,
            delay_minutes=0,
            targets=escalation_targets["level_1"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        level_2_rule = EscalationRule(
            id=uuid4(),
            name="Level 2",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.PROGRESSIVE,
            level=2,
            delay_minutes=10,
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(level_1_rule)
        escalation_manager.register_rule(level_2_rule)

        # Create escalations
        escalations = await escalation_manager.evaluate_alert(critical_alert)
        assert len(escalations) == 2

        # Execute level 1 (immediate)
        level_1_escalation = [e for e in escalations if e.level == 1][0]
        await escalation_manager.execute_escalation(level_1_escalation.id)

        # Acknowledge alert before level 2 executes
        critical_alert.status = AlertStatus.ACKNOWLEDGED
        await escalation_manager.cancel_escalations_for_alert(critical_alert.id)

        # Level 2 should be cancelled
        level_2_escalation = [e for e in escalations if e.level == 2][0]
        updated_escalation = escalation_manager.get_escalation(level_2_escalation.id)
        assert updated_escalation.status == "cancelled"


# ============================================================================
# Test Concurrent Escalations
# ============================================================================


class TestConcurrentEscalations:
    """Test handling of multiple concurrent escalations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_alerts_escalating_simultaneously(
        self, escalation_system, escalation_targets
    ):
        """Test multiple alerts escalating at the same time."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Concurrent Escalation Rule",
            alert_types=[
                AlertRuleType.EMERGENCY_KEYWORDS,
                AlertRuleType.TREATMENT_ADHERENCE,
                AlertRuleType.NEGATIVE_SENTIMENT,
            ],
            min_severity=AlertSeverity.WARNING,
            strategy=EscalationStrategy.IMMEDIATE,
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Create 5 different alerts
        alerts = [
            Alert(
                id=uuid4(),
                rule_id=uuid4(),
                rule_type=alert_type,
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.ACTIVE,
                title=f"Alert {i}",
                message=f"Message {i}",
                patient_id=uuid4(),
                context={},
                created_at=datetime.now(),
            )
            for i, alert_type in enumerate(
                [
                    AlertRuleType.EMERGENCY_KEYWORDS,
                    AlertRuleType.TREATMENT_ADHERENCE,
                    AlertRuleType.NEGATIVE_SENTIMENT,
                    AlertRuleType.EMERGENCY_KEYWORDS,
                    AlertRuleType.TREATMENT_ADHERENCE,
                ]
            )
        ]

        # Evaluate all alerts concurrently
        tasks = [escalation_manager.evaluate_alert(alert) for alert in alerts]
        results = await asyncio.gather(*tasks)

        # All should create escalations
        total_escalations = sum(len(escalations) for escalations in results)
        assert total_escalations >= 5

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_escalation_queue_processing(
        self, escalation_system, escalation_targets
    ):
        """Test processing escalation queue with multiple pending items."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        # Create delayed escalation rule
        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Queue Processing Test",
            alert_types=[AlertRuleType.NO_RESPONSE],
            min_severity=AlertSeverity.WARNING,
            strategy=EscalationStrategy.DELAYED,
            delay_minutes=0.01,  # Very short delay
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Create 10 alerts with delayed escalations
        alerts = [
            Alert(
                id=uuid4(),
                rule_id=uuid4(),
                rule_type=AlertRuleType.NO_RESPONSE,
                severity=AlertSeverity.WARNING,
                status=AlertStatus.ACTIVE,
                title=f"Queued Alert {i}",
                message=f"Message {i}",
                patient_id=uuid4(),
                context={},
                created_at=datetime.now(),
            )
            for i in range(10)
        ]

        # Create all escalations
        for alert in alerts:
            await escalation_manager.evaluate_alert(alert)

        # Simulate time passing
        for escalation in escalation_manager.get_pending_escalations():
            escalation.scheduled_for = datetime.now() - timedelta(seconds=1)

        # Process queue
        await escalation_manager.execute_pending_escalations()

        # Should have processed all
        assert mock_channel.send.call_count >= 10


# ============================================================================
# Test Escalation History
# ============================================================================


class TestEscalationHistory:
    """Test escalation history tracking."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_escalation_history_recorded(
        self, escalation_system, critical_alert, escalation_targets
    ):
        """Test that escalation history is properly recorded."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        escalation_rule = EscalationRule(
            id=uuid4(),
            name="History Tracking Test",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.IMMEDIATE,
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Create and execute escalation
        escalations = await escalation_manager.evaluate_alert(critical_alert)
        escalation = escalations[0]

        await escalation_manager.execute_escalation(escalation.id)

        # Get history
        history = escalation_manager.get_escalation_history(critical_alert.id)

        assert len(history) > 0
        assert history[0].alert_id == critical_alert.id
        assert history[0].executed_at is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_level_escalation_history(
        self, escalation_system, critical_alert, escalation_targets
    ):
        """Test history for multi-level progressive escalation."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        # 2-level progressive
        for level in [1, 2]:
            rule = EscalationRule(
                id=uuid4(),
                name=f"Level {level}",
                alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
                min_severity=AlertSeverity.CRITICAL,
                strategy=EscalationStrategy.PROGRESSIVE,
                level=level,
                delay_minutes=0 if level == 1 else 5,
                targets=escalation_targets[f"level_{level}"],
                channels=[NotificationChannel.EMAIL],
                enabled=True,
            )
            escalation_manager.register_rule(rule)

        # Create escalations
        escalations = await escalation_manager.evaluate_alert(critical_alert)

        # Execute level 1
        level_1 = [e for e in escalations if e.level == 1][0]
        await escalation_manager.execute_escalation(level_1.id)

        # Get history (should show level 1 executed)
        history = escalation_manager.get_escalation_history(critical_alert.id)
        executed = [h for h in history if h.executed_at is not None]
        assert len(executed) >= 1


# ============================================================================
# Test Escalation Statistics
# ============================================================================


class TestEscalationStatistics:
    """Test escalation statistics and metrics."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_escalation_statistics_tracking(
        self, escalation_system, critical_alert, escalation_targets
    ):
        """Test that escalation statistics are tracked correctly."""
        escalation_manager = escalation_system["escalation_manager"]
        dispatcher = escalation_system["dispatcher"]

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel)

        escalation_rule = EscalationRule(
            id=uuid4(),
            name="Stats Test",
            alert_types=[AlertRuleType.EMERGENCY_KEYWORDS],
            min_severity=AlertSeverity.CRITICAL,
            strategy=EscalationStrategy.IMMEDIATE,
            targets=escalation_targets["level_2"],
            channels=[NotificationChannel.EMAIL],
            enabled=True,
        )

        escalation_manager.register_rule(escalation_rule)

        # Initial stats
        initial_stats = escalation_manager.get_statistics()

        # Create and execute escalation
        escalations = await escalation_manager.evaluate_alert(critical_alert)
        await escalation_manager.execute_escalation(escalations[0].id)

        # Get updated stats
        updated_stats = escalation_manager.get_statistics()

        # Should have increased
        assert updated_stats["total_escalations"] > initial_stats.get(
            "total_escalations", 0
        )
        assert updated_stats["executed_escalations"] > initial_stats.get(
            "executed_escalations", 0
        )
