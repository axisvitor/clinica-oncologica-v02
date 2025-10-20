"""
Unit Tests for EscalationManager.

Tests the alert escalation management system including:
- Escalation rule registration and management
- Escalation scheduling (IMMEDIATE, DELAYED, PROGRESSIVE)
- Escalation execution and notification
- Escalation cancellation
- Multi-level escalation paths
- Escalation history and tracking
- Statistics and metrics

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, List, Optional

from app.services.alerts import (
    EscalationManager,
    Escalation,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    EscalationRule,
    EscalationStrategy,
    NotificationTarget,
    NotificationChannel,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def escalation_manager():
    """Create EscalationManager instance."""
    return EscalationManager()


@pytest.fixture
def sample_alert():
    """Sample alert object."""
    return Alert(
        id=uuid4(),
        patient_id=uuid4(),
        rule_type=AlertRuleType.NO_RESPONSE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        title="Patient No Response",
        message="Patient has not responded in 48 hours",
        escalation_level=0,
        metadata={"days_without_response": 2},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def critical_alert():
    """Critical severity alert."""
    return Alert(
        id=uuid4(),
        patient_id=uuid4(),
        rule_type=AlertRuleType.EMERGENCY_KEYWORDS,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.PENDING,
        title="Emergency Keywords Detected",
        message="Patient mentioned emergency keywords",
        escalation_level=0,
        metadata={"keywords": ["dor", "sangue"]},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def immediate_rule():
    """Escalation rule with IMMEDIATE strategy."""
    return EscalationRule(
        id=uuid4(),
        alert_type=AlertRuleType.EMERGENCY_KEYWORDS,
        escalation_strategy=EscalationStrategy.IMMEDIATE,
        escalation_target="oncology_team",
        escalation_channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        delay_minutes=0,
        enabled=True,
        metadata={"priority": "critical"},
    )


@pytest.fixture
def delayed_rule():
    """Escalation rule with DELAYED strategy."""
    return EscalationRule(
        id=uuid4(),
        alert_type=AlertRuleType.NO_RESPONSE,
        escalation_strategy=EscalationStrategy.DELAYED,
        escalation_target="supervisor",
        escalation_channels=[NotificationChannel.EMAIL],
        delay_minutes=30,
        enabled=True,
        metadata={},
    )


@pytest.fixture
def progressive_rule():
    """Escalation rule with PROGRESSIVE strategy."""
    return EscalationRule(
        id=uuid4(),
        alert_type=AlertRuleType.MISSED_QUIZ,
        escalation_strategy=EscalationStrategy.PROGRESSIVE,
        escalation_target="team_lead",
        escalation_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
        delay_minutes=60,
        escalation_levels=[
            {"level": 1, "delay_minutes": 30, "target": "team_lead"},
            {"level": 2, "delay_minutes": 60, "target": "manager"},
            {"level": 3, "delay_minutes": 120, "target": "director"},
        ],
        enabled=True,
        metadata={},
    )


@pytest.fixture
def sample_escalation(sample_alert, immediate_rule):
    """Sample escalation instance."""
    return Escalation(
        id=uuid4(),
        alert_id=sample_alert.id,
        rule_id=immediate_rule.id,
        level=1,
        scheduled_at=datetime.utcnow(),
        status="scheduled",
        metadata={"strategy": "immediate"},
    )


@pytest.fixture
def mock_dispatcher():
    """Mock NotificationDispatcher."""
    dispatcher = MagicMock()
    dispatcher.dispatch = AsyncMock()
    return dispatcher


# ============================================================================
# Test EscalationManager Initialization
# ============================================================================


class TestEscalationManagerInitialization:
    """Test EscalationManager initialization."""

    def test_init_default(self):
        """Test initialization with defaults."""
        manager = EscalationManager()

        assert manager._escalations == {}
        assert manager._escalation_rules == {}
        assert manager._alert_escalations == {}
        assert manager._total_scheduled == 0
        assert manager._total_executed == 0
        assert manager._total_cancelled == 0

    def test_init_loads_config(self):
        """Test that initialization loads configuration."""
        manager = EscalationManager()

        assert manager.config is not None


# ============================================================================
# Test Escalation Rule Management
# ============================================================================


class TestEscalationRuleManagement:
    """Test escalation rule registration and management."""

    def test_register_rule(self, escalation_manager, immediate_rule):
        """Test registering an escalation rule."""
        # Execute
        escalation_manager.register_escalation_rule(immediate_rule)

        # Assert
        assert immediate_rule.id in escalation_manager._escalation_rules
        assert escalation_manager._escalation_rules[immediate_rule.id] == immediate_rule

    def test_register_multiple_rules(
        self, escalation_manager, immediate_rule, delayed_rule
    ):
        """Test registering multiple escalation rules."""
        # Execute
        escalation_manager.register_escalation_rule(immediate_rule)
        escalation_manager.register_escalation_rule(delayed_rule)

        # Assert
        assert len(escalation_manager._escalation_rules) == 2
        assert immediate_rule.id in escalation_manager._escalation_rules
        assert delayed_rule.id in escalation_manager._escalation_rules

    def test_register_rule_overwrites_existing(
        self, escalation_manager, immediate_rule
    ):
        """Test that registering same rule ID overwrites."""
        # Register first
        escalation_manager.register_escalation_rule(immediate_rule)
        first_rule = escalation_manager._escalation_rules[immediate_rule.id]

        # Register again with same ID
        modified_rule = immediate_rule
        modified_rule.delay_minutes = 10
        escalation_manager.register_escalation_rule(modified_rule)

        # Assert - should be overwritten
        assert (
            escalation_manager._escalation_rules[immediate_rule.id].delay_minutes == 10
        )

    def test_unregister_rule(self, escalation_manager, immediate_rule):
        """Test unregistering an escalation rule."""
        # Setup
        escalation_manager.register_escalation_rule(immediate_rule)
        assert immediate_rule.id in escalation_manager._escalation_rules

        # Execute
        escalation_manager.unregister_escalation_rule(immediate_rule.id)

        # Assert
        assert immediate_rule.id not in escalation_manager._escalation_rules

    def test_unregister_rule_not_found(self, escalation_manager):
        """Test unregistering non-existent rule raises error."""
        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            escalation_manager.unregister_escalation_rule(uuid4())

        assert "not found" in str(exc_info.value).lower()

    def test_get_escalation_rule_found(
        self, escalation_manager, sample_alert, immediate_rule
    ):
        """Test getting escalation rule for an alert."""
        # Setup
        immediate_rule.alert_type = sample_alert.rule_type
        escalation_manager.register_escalation_rule(immediate_rule)

        # Execute
        rule = escalation_manager.get_escalation_rule(sample_alert)

        # Assert
        assert rule == immediate_rule

    def test_get_escalation_rule_not_found(self, escalation_manager, sample_alert):
        """Test getting escalation rule when none matches."""
        # Execute
        rule = escalation_manager.get_escalation_rule(sample_alert)

        # Assert
        assert rule is None

    def test_get_escalation_rule_respects_enabled_flag(
        self, escalation_manager, sample_alert, immediate_rule
    ):
        """Test that disabled rules are not returned."""
        # Setup
        immediate_rule.alert_type = sample_alert.rule_type
        immediate_rule.enabled = False
        escalation_manager.register_escalation_rule(immediate_rule)

        # Execute
        rule = escalation_manager.get_escalation_rule(sample_alert)

        # Assert - should not return disabled rule
        assert rule is None


# ============================================================================
# Test Escalation Scheduling
# ============================================================================


class TestEscalationScheduling:
    """Test escalation scheduling logic."""

    @pytest.mark.asyncio
    async def test_schedule_escalation_immediate(
        self, escalation_manager, critical_alert, immediate_rule
    ):
        """Test scheduling escalation with IMMEDIATE strategy."""
        # Setup
        escalation_manager.register_escalation_rule(immediate_rule)

        # Execute
        escalation = await escalation_manager.schedule_escalation(
            alert=critical_alert, rule=immediate_rule
        )

        # Assert
        assert isinstance(escalation, Escalation)
        assert escalation.alert_id == critical_alert.id
        assert escalation.rule_id == immediate_rule.id
        assert escalation.level == 1
        assert escalation.status == "scheduled"
        # IMMEDIATE should schedule for now
        assert escalation.scheduled_at <= datetime.utcnow()

    @pytest.mark.asyncio
    async def test_schedule_escalation_delayed(
        self, escalation_manager, sample_alert, delayed_rule
    ):
        """Test scheduling escalation with DELAYED strategy."""
        # Setup
        escalation_manager.register_escalation_rule(delayed_rule)

        # Execute
        escalation = await escalation_manager.schedule_escalation(
            alert=sample_alert, rule=delayed_rule
        )

        # Assert
        assert escalation.level == 1
        # DELAYED should schedule for future (30 minutes)
        expected_time = datetime.utcnow() + timedelta(minutes=30)
        assert escalation.scheduled_at >= datetime.utcnow()
        # Allow 1 minute tolerance
        assert abs((escalation.scheduled_at - expected_time).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_schedule_escalation_auto_detects_rule(
        self, escalation_manager, sample_alert, delayed_rule
    ):
        """Test that escalation auto-detects rule if not provided."""
        # Setup
        delayed_rule.alert_type = sample_alert.rule_type
        escalation_manager.register_escalation_rule(delayed_rule)

        # Execute - no rule provided
        escalation = await escalation_manager.schedule_escalation(alert=sample_alert)

        # Assert
        assert escalation.rule_id == delayed_rule.id

    @pytest.mark.asyncio
    async def test_schedule_escalation_no_rule_found(
        self, escalation_manager, sample_alert
    ):
        """Test scheduling escalation when no rule found."""
        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            await escalation_manager.schedule_escalation(alert=sample_alert)

        assert "no escalation rule" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_schedule_escalation_max_level_reached(
        self, escalation_manager, sample_alert, immediate_rule
    ):
        """Test scheduling escalation when max level reached."""
        # Setup
        sample_alert.escalation_level = 5  # At max level
        escalation_manager.register_escalation_rule(immediate_rule)

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            await escalation_manager.schedule_escalation(
                alert=sample_alert, rule=immediate_rule
            )

        assert "max escalation level" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_schedule_escalation_increments_level(
        self, escalation_manager, sample_alert, immediate_rule
    ):
        """Test that scheduling increments escalation level."""
        # Setup
        sample_alert.escalation_level = 1
        escalation_manager.register_escalation_rule(immediate_rule)

        # Execute
        escalation = await escalation_manager.schedule_escalation(
            alert=sample_alert, rule=immediate_rule
        )

        # Assert - should be level 2 (1 + 1)
        assert escalation.level == 2

    @pytest.mark.asyncio
    async def test_schedule_escalation_updates_statistics(
        self, escalation_manager, sample_alert, immediate_rule
    ):
        """Test that scheduling updates statistics."""
        # Setup
        escalation_manager.register_escalation_rule(immediate_rule)
        initial_scheduled = escalation_manager._total_scheduled

        # Execute
        await escalation_manager.schedule_escalation(
            alert=sample_alert, rule=immediate_rule
        )

        # Assert
        assert escalation_manager._total_scheduled == initial_scheduled + 1

    @pytest.mark.asyncio
    async def test_schedule_escalation_tracks_by_alert(
        self, escalation_manager, sample_alert, immediate_rule
    ):
        """Test that escalations are tracked by alert ID."""
        # Setup
        escalation_manager.register_escalation_rule(immediate_rule)

        # Execute
        escalation = await escalation_manager.schedule_escalation(
            alert=sample_alert, rule=immediate_rule
        )

        # Assert
        assert sample_alert.id in escalation_manager._alert_escalations
        assert escalation.id in escalation_manager._alert_escalations[sample_alert.id]


# ============================================================================
# Test Escalation Execution
# ============================================================================


class TestEscalationExecution:
    """Test escalation execution logic."""

    @pytest.mark.asyncio
    async def test_execute_escalation_success(
        self, escalation_manager, sample_escalation, immediate_rule, mock_dispatcher
    ):
        """Test successful escalation execution."""
        # Setup
        escalation_manager._escalations[sample_escalation.id] = sample_escalation
        escalation_manager._escalation_rules[immediate_rule.id] = immediate_rule

        # Execute
        result = await escalation_manager.execute_escalation(
            escalation_id=sample_escalation.id, dispatcher=mock_dispatcher
        )

        # Assert
        assert result is True
        assert sample_escalation.status == "executed"
        assert sample_escalation.executed_at is not None

    @pytest.mark.asyncio
    async def test_execute_escalation_not_found(self, escalation_manager):
        """Test executing non-existent escalation."""
        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            await escalation_manager.execute_escalation(escalation_id=uuid4())

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_escalation_already_executed(
        self, escalation_manager, sample_escalation
    ):
        """Test executing already executed escalation."""
        # Setup
        sample_escalation.status = "executed"
        escalation_manager._escalations[sample_escalation.id] = sample_escalation

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            await escalation_manager.execute_escalation(
                escalation_id=sample_escalation.id
            )

        assert "already executed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_escalation_cancelled(
        self, escalation_manager, sample_escalation
    ):
        """Test executing cancelled escalation."""
        # Setup
        sample_escalation.status = "cancelled"
        escalation_manager._escalations[sample_escalation.id] = sample_escalation

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            await escalation_manager.execute_escalation(
                escalation_id=sample_escalation.id
            )

        assert "cancelled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_escalation_updates_statistics(
        self, escalation_manager, sample_escalation, immediate_rule, mock_dispatcher
    ):
        """Test that execution updates statistics."""
        # Setup
        escalation_manager._escalations[sample_escalation.id] = sample_escalation
        escalation_manager._escalation_rules[immediate_rule.id] = immediate_rule
        initial_executed = escalation_manager._total_executed

        # Execute
        await escalation_manager.execute_escalation(
            escalation_id=sample_escalation.id, dispatcher=mock_dispatcher
        )

        # Assert
        assert escalation_manager._total_executed == initial_executed + 1

    @pytest.mark.asyncio
    async def test_execute_escalation_calls_dispatcher(
        self, escalation_manager, sample_escalation, immediate_rule, mock_dispatcher
    ):
        """Test that execution calls notification dispatcher."""
        # Setup
        escalation_manager._escalations[sample_escalation.id] = sample_escalation
        escalation_manager._escalation_rules[immediate_rule.id] = immediate_rule

        # Execute
        await escalation_manager.execute_escalation(
            escalation_id=sample_escalation.id, dispatcher=mock_dispatcher
        )

        # Assert - dispatcher should be called
        assert mock_dispatcher.dispatch.called or mock_dispatcher.dispatch_batch.called


# ============================================================================
# Test Escalation Cancellation
# ============================================================================


class TestEscalationCancellation:
    """Test escalation cancellation logic."""

    @pytest.mark.asyncio
    async def test_cancel_escalation_success(
        self, escalation_manager, sample_escalation
    ):
        """Test successful escalation cancellation."""
        # Setup
        escalation_manager._escalations[sample_escalation.id] = sample_escalation

        # Execute
        result = await escalation_manager.cancel_escalation(
            escalation_id=sample_escalation.id, reason="Alert acknowledged"
        )

        # Assert
        assert result is True
        assert sample_escalation.status == "cancelled"
        assert sample_escalation.cancelled_at is not None

    @pytest.mark.asyncio
    async def test_cancel_escalation_not_found(self, escalation_manager):
        """Test cancelling non-existent escalation."""
        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            await escalation_manager.cancel_escalation(escalation_id=uuid4())

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cancel_escalation_already_executed(
        self, escalation_manager, sample_escalation
    ):
        """Test cancelling already executed escalation."""
        # Setup
        sample_escalation.status = "executed"
        escalation_manager._escalations[sample_escalation.id] = sample_escalation

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            await escalation_manager.cancel_escalation(
                escalation_id=sample_escalation.id
            )

        assert "already executed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cancel_escalation_updates_statistics(
        self, escalation_manager, sample_escalation
    ):
        """Test that cancellation updates statistics."""
        # Setup
        escalation_manager._escalations[sample_escalation.id] = sample_escalation
        initial_cancelled = escalation_manager._total_cancelled

        # Execute
        await escalation_manager.cancel_escalation(escalation_id=sample_escalation.id)

        # Assert
        assert escalation_manager._total_cancelled == initial_cancelled + 1

    @pytest.mark.asyncio
    async def test_cancel_all_escalations_for_alert(
        self, escalation_manager, sample_alert
    ):
        """Test cancelling all escalations for an alert."""
        # Setup - create multiple escalations
        escalation1 = Escalation(
            id=uuid4(),
            alert_id=sample_alert.id,
            rule_id=uuid4(),
            level=1,
            scheduled_at=datetime.utcnow(),
            status="scheduled",
        )
        escalation2 = Escalation(
            id=uuid4(),
            alert_id=sample_alert.id,
            rule_id=uuid4(),
            level=2,
            scheduled_at=datetime.utcnow(),
            status="scheduled",
        )

        escalation_manager._escalations[escalation1.id] = escalation1
        escalation_manager._escalations[escalation2.id] = escalation2
        escalation_manager._alert_escalations[sample_alert.id] = [
            escalation1.id,
            escalation2.id,
        ]

        # Execute
        count = await escalation_manager.cancel_alert_escalations(
            alert_id=sample_alert.id, reason="Alert resolved"
        )

        # Assert
        assert count == 2
        assert escalation1.status == "cancelled"
        assert escalation2.status == "cancelled"


# ============================================================================
# Test Progressive Escalation
# ============================================================================


class TestProgressiveEscalation:
    """Test progressive multi-level escalation."""

    @pytest.mark.asyncio
    async def test_schedule_progressive_escalation_level_1(
        self, escalation_manager, sample_alert, progressive_rule
    ):
        """Test scheduling progressive escalation at level 1."""
        # Setup
        sample_alert.escalation_level = 0
        escalation_manager.register_escalation_rule(progressive_rule)

        # Execute
        escalation = await escalation_manager.schedule_escalation(
            alert=sample_alert, rule=progressive_rule
        )

        # Assert
        assert escalation.level == 1
        # Level 1 should use 30 minute delay
        expected_time = datetime.utcnow() + timedelta(minutes=30)
        assert abs((escalation.scheduled_at - expected_time).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_schedule_progressive_escalation_level_2(
        self, escalation_manager, sample_alert, progressive_rule
    ):
        """Test scheduling progressive escalation at level 2."""
        # Setup
        sample_alert.escalation_level = 1  # Already at level 1
        escalation_manager.register_escalation_rule(progressive_rule)

        # Execute
        escalation = await escalation_manager.schedule_escalation(
            alert=sample_alert, rule=progressive_rule
        )

        # Assert
        assert escalation.level == 2
        # Level 2 should use 60 minute delay
        expected_time = datetime.utcnow() + timedelta(minutes=60)
        assert abs((escalation.scheduled_at - expected_time).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_progressive_escalation_changes_target(
        self, escalation_manager, sample_alert, progressive_rule
    ):
        """Test that progressive escalation changes target per level."""
        # Setup
        escalation_manager.register_escalation_rule(progressive_rule)

        # Level 1
        sample_alert.escalation_level = 0
        esc1 = await escalation_manager.schedule_escalation(
            alert=sample_alert, rule=progressive_rule
        )

        # Level 2
        sample_alert.escalation_level = 1
        esc2 = await escalation_manager.schedule_escalation(
            alert=sample_alert, rule=progressive_rule
        )

        # Assert - targets should be different
        assert esc1.metadata.get("target") != esc2.metadata.get("target")


# ============================================================================
# Test Escalation History
# ============================================================================


class TestEscalationHistory:
    """Test escalation history tracking."""

    @pytest.mark.asyncio
    async def test_get_escalation_history_for_alert(
        self, escalation_manager, sample_alert
    ):
        """Test retrieving escalation history for an alert."""
        # Setup
        escalation1 = Escalation(
            id=uuid4(),
            alert_id=sample_alert.id,
            rule_id=uuid4(),
            level=1,
            scheduled_at=datetime.utcnow(),
            status="executed",
            executed_at=datetime.utcnow(),
        )
        escalation2 = Escalation(
            id=uuid4(),
            alert_id=sample_alert.id,
            rule_id=uuid4(),
            level=2,
            scheduled_at=datetime.utcnow(),
            status="executed",
            executed_at=datetime.utcnow(),
        )

        escalation_manager._escalations[escalation1.id] = escalation1
        escalation_manager._escalations[escalation2.id] = escalation2
        escalation_manager._alert_escalations[sample_alert.id] = [
            escalation1.id,
            escalation2.id,
        ]

        # Execute
        history = await escalation_manager.get_escalation_history(
            alert_id=sample_alert.id
        )

        # Assert
        assert len(history) == 2
        assert escalation1 in history
        assert escalation2 in history

    @pytest.mark.asyncio
    async def test_get_escalation_history_empty(self, escalation_manager):
        """Test retrieving history for alert with no escalations."""
        # Execute
        history = await escalation_manager.get_escalation_history(alert_id=uuid4())

        # Assert
        assert history == []


# ============================================================================
# Test Statistics
# ============================================================================


class TestEscalationStatistics:
    """Test escalation statistics tracking."""

    def test_get_statistics(self, escalation_manager):
        """Test retrieving escalation statistics."""
        # Setup
        escalation_manager._total_scheduled = 10
        escalation_manager._total_executed = 7
        escalation_manager._total_cancelled = 2

        # Execute
        stats = escalation_manager.get_statistics()

        # Assert
        assert stats["total_scheduled"] == 10
        assert stats["total_executed"] == 7
        assert stats["total_cancelled"] == 2
        assert "success_rate" in stats

    def test_statistics_calculate_success_rate(self, escalation_manager):
        """Test that statistics calculate success rate correctly."""
        # Setup
        escalation_manager._total_scheduled = 10
        escalation_manager._total_executed = 8

        # Execute
        stats = escalation_manager.get_statistics()

        # Assert
        assert stats["success_rate"] == 0.8  # 8/10


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_schedule_escalation_with_none_alert(
        self, escalation_manager, immediate_rule
    ):
        """Test scheduling escalation with None alert."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await escalation_manager.schedule_escalation(
                alert=None, rule=immediate_rule
            )

    @pytest.mark.asyncio
    async def test_execute_escalation_with_none_id(self, escalation_manager):
        """Test executing escalation with None ID."""
        with pytest.raises((ValueError, TypeError)):
            await escalation_manager.execute_escalation(escalation_id=None)

    @pytest.mark.asyncio
    async def test_cancel_escalation_with_none_id(self, escalation_manager):
        """Test cancelling escalation with None ID."""
        with pytest.raises((ValueError, TypeError)):
            await escalation_manager.cancel_escalation(escalation_id=None)

    def test_register_rule_with_none(self, escalation_manager):
        """Test registering None rule."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            escalation_manager.register_escalation_rule(None)
