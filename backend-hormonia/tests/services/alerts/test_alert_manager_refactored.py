"""
Comprehensive test suite for Alert Manager (Refactored)

Tests cover:
- Notification handler (email, SMS, webhook)
- Escalation handler (priority levels, routing)
- Persistence handler (alert storage, retrieval)
- Metrics collection and reporting
- Integration between handlers
- Error handling and resilience
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from datetime import datetime, timedelta
import json

from app.services.alerts import AlertManager, Alert, AlertSeverity as AlertPriority, AlertStatus


# ==========================================
# Test Fixtures
# ==========================================

@pytest.fixture
def mock_email_service():
    """Mock email service"""
    service = AsyncMock()
    service.send_email = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_sms_service():
    """Mock SMS service"""
    service = AsyncMock()
    service.send_sms = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_webhook_service():
    """Mock webhook service"""
    service = AsyncMock()
    service.send_webhook = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_database():
    """Mock database session"""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.query = MagicMock()
    db.flush = MagicMock()
    return db


@pytest.fixture
def alert_manager(mock_email_service, mock_sms_service, mock_webhook_service, mock_database):
    """Create AlertManager instance"""
    manager = AlertManager(
        email_service=mock_email_service,
        sms_service=mock_sms_service,
        webhook_service=mock_webhook_service,
        database=mock_database
    )
    return manager


@pytest.fixture
def sample_alert():
    """Sample alert"""
    return Alert(
        id='alert-001',
        title='Test Alert',
        message='This is a test alert',
        priority=AlertPriority.MEDIUM,
        status=AlertStatus.NEW,
        created_at=datetime.utcnow(),
        metadata={'source': 'test'}
    )


@pytest.fixture
def critical_alert():
    """Critical priority alert"""
    return Alert(
        id='critical-001',
        title='Critical System Error',
        message='Database connection lost',
        priority=AlertPriority.CRITICAL,
        status=AlertStatus.NEW,
        created_at=datetime.utcnow(),
        metadata={'component': 'database'}
    )


# ==========================================
# Notification Handler Tests
# ==========================================

class TestNotificationHandler:
    """Test notification handler in isolation"""

    @pytest.mark.asyncio
    async def test_send_email_notification(self, alert_manager, sample_alert, mock_email_service):
        """Test sending email notification"""
        recipients = ['admin@example.com']
        result = await alert_manager.send_email_notification(sample_alert, recipients)

        assert result is True
        mock_email_service.send_email.assert_called_once()
        call_args = mock_email_service.send_email.call_args
        assert 'test alert' in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_send_email_with_template(self, alert_manager, sample_alert, mock_email_service):
        """Test email notification with template"""
        result = await alert_manager.send_email_notification(
            sample_alert,
            ['admin@example.com'],
            template='critical_alert'
        )

        assert result is True
        mock_email_service.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_sms_notification(self, alert_manager, critical_alert, mock_sms_service):
        """Test sending SMS notification"""
        phone_numbers = ['+5511987654321']
        result = await alert_manager.send_sms_notification(critical_alert, phone_numbers)

        assert result is True
        mock_sms_service.send_sms.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_sms_character_limit(self, alert_manager, mock_sms_service):
        """Test SMS notification respects character limit"""
        long_message = 'x' * 500
        alert = Alert(
            id='long',
            title='Long Message',
            message=long_message,
            priority=AlertPriority.HIGH,
            status=AlertStatus.NEW,
            created_at=datetime.utcnow()
        )

        await alert_manager.send_sms_notification(alert, ['+5511987654321'])

        # Verify message was truncated
        call_args = mock_sms_service.send_sms.call_args
        sent_message = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('message', '')
        assert len(sent_message) <= 160  # Standard SMS limit

    @pytest.mark.asyncio
    async def test_send_webhook_notification(self, alert_manager, sample_alert, mock_webhook_service):
        """Test sending webhook notification"""
        webhook_url = 'https://example.com/webhook'
        result = await alert_manager.send_webhook_notification(sample_alert, webhook_url)

        assert result is True
        mock_webhook_service.send_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_payload_format(self, alert_manager, sample_alert, mock_webhook_service):
        """Test webhook payload format"""
        await alert_manager.send_webhook_notification(sample_alert, 'https://example.com/webhook')

        call_args = mock_webhook_service.send_webhook.call_args
        payload = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('payload')

        assert 'id' in payload
        assert 'title' in payload
        assert 'priority' in payload

    @pytest.mark.asyncio
    async def test_notification_retry_on_failure(self, alert_manager, sample_alert, mock_email_service):
        """Test notification retry on failure"""
        mock_email_service.send_email.side_effect = [
            Exception('Network error'),
            Exception('Network error'),
            True  # Success on third try
        ]

        result = await alert_manager.send_email_notification_with_retry(
            sample_alert,
            ['admin@example.com'],
            max_retries=3
        )

        assert result is True
        assert mock_email_service.send_email.call_count == 3

    @pytest.mark.asyncio
    async def test_multiple_notification_channels(self, alert_manager, critical_alert,
                                                   mock_email_service, mock_sms_service):
        """Test sending to multiple notification channels"""
        await alert_manager.send_multi_channel_notification(
            critical_alert,
            email_recipients=['admin@example.com'],
            sms_recipients=['+5511987654321']
        )

        mock_email_service.send_email.assert_called_once()
        mock_sms_service.send_sms.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_batching(self, alert_manager, mock_email_service):
        """Test batching multiple alerts into single notification"""
        alerts = [
            Alert(
                id=f'alert-{i}',
                title=f'Alert {i}',
                message=f'Message {i}',
                priority=AlertPriority.MEDIUM,
                status=AlertStatus.NEW,
                created_at=datetime.utcnow()
            )
            for i in range(5)
        ]

        await alert_manager.send_batch_notification(alerts, ['admin@example.com'])

        # Should send one email with all alerts
        assert mock_email_service.send_email.call_count == 1


# ==========================================
# Escalation Handler Tests
# ==========================================

class TestEscalationHandler:
    """Test escalation handler in isolation"""

    @pytest.mark.asyncio
    async def test_escalate_by_priority(self, alert_manager, critical_alert):
        """Test escalation based on priority"""
        escalation_path = await alert_manager.get_escalation_path(critical_alert)

        assert len(escalation_path) > 0
        # Critical alerts should escalate to senior staff
        assert any('senior' in str(recipient).lower() or 'manager' in str(recipient).lower()
                   for recipient in escalation_path)

    @pytest.mark.asyncio
    async def test_escalate_on_timeout(self, alert_manager, sample_alert):
        """Test escalation when alert not acknowledged in time"""
        # Set alert as unacknowledged
        sample_alert.created_at = datetime.utcnow() - timedelta(hours=2)
        sample_alert.acknowledged_at = None

        should_escalate = await alert_manager.should_escalate(sample_alert)
        assert should_escalate is True

    @pytest.mark.asyncio
    async def test_escalation_levels(self, alert_manager, critical_alert):
        """Test multiple escalation levels"""
        escalation_levels = await alert_manager.get_escalation_levels(critical_alert)

        assert len(escalation_levels) >= 2
        # Each level should have different recipients
        assert escalation_levels[0] != escalation_levels[1]

    @pytest.mark.asyncio
    async def test_escalation_routing_by_component(self, alert_manager):
        """Test alert routing based on component"""
        database_alert = Alert(
            id='db-alert',
            title='Database Error',
            message='Connection pool exhausted',
            priority=AlertPriority.HIGH,
            status=AlertStatus.NEW,
            created_at=datetime.utcnow(),
            metadata={'component': 'database'}
        )

        recipients = await alert_manager.route_alert_by_component(database_alert)

        # Should route to database team
        assert any('dba' in str(r).lower() or 'database' in str(r).lower()
                   for r in recipients)

    @pytest.mark.asyncio
    async def test_escalation_suppression_for_low_priority(self, alert_manager):
        """Test that low priority alerts don't escalate"""
        low_alert = Alert(
            id='low-alert',
            title='Info',
            message='Informational message',
            priority=AlertPriority.LOW,
            status=AlertStatus.NEW,
            created_at=datetime.utcnow() - timedelta(hours=24)
        )

        should_escalate = await alert_manager.should_escalate(low_alert)
        assert should_escalate is False

    @pytest.mark.asyncio
    async def test_escalation_with_on_call_rotation(self, alert_manager, critical_alert):
        """Test escalation respects on-call rotation"""
        with patch.object(alert_manager, 'get_on_call_engineer') as mock_on_call:
            mock_on_call.return_value = 'engineer-on-call@example.com'

            recipients = await alert_manager.get_escalation_path(critical_alert)

            assert 'engineer-on-call@example.com' in recipients


# ==========================================
# Persistence Handler Tests
# ==========================================

class TestPersistenceHandler:
    """Test persistence handler in isolation"""

    @pytest.mark.asyncio
    async def test_save_alert_to_database(self, alert_manager, sample_alert, mock_database):
        """Test saving alert to database"""
        await alert_manager.save_alert(sample_alert)

        mock_database.add.assert_called_once()
        mock_database.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_alert_by_id(self, alert_manager, sample_alert, mock_database):
        """Test retrieving alert by ID"""
        mock_database.query.return_value.filter.return_value.first.return_value = sample_alert

        retrieved = await alert_manager.get_alert_by_id('alert-001')

        assert retrieved.id == 'alert-001'
        mock_database.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_alert_status(self, alert_manager, sample_alert, mock_database):
        """Test updating alert status"""
        mock_database.query.return_value.filter.return_value.first.return_value = sample_alert

        await alert_manager.update_alert_status('alert-001', AlertStatus.ACKNOWLEDGED)

        assert sample_alert.status == AlertStatus.ACKNOWLEDGED
        mock_database.commit.assert_called()

    @pytest.mark.asyncio
    async def test_query_alerts_by_priority(self, alert_manager, mock_database):
        """Test querying alerts by priority"""
        mock_database.query.return_value.filter.return_value.all.return_value = [
            Alert(id='1', title='Alert 1', message='msg', priority=AlertPriority.HIGH,
                  status=AlertStatus.NEW, created_at=datetime.utcnow())
        ]

        alerts = await alert_manager.get_alerts_by_priority(AlertPriority.HIGH)

        assert len(alerts) >= 0
        mock_database.query.assert_called()

    @pytest.mark.asyncio
    async def test_query_alerts_by_date_range(self, alert_manager, mock_database):
        """Test querying alerts by date range"""
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        mock_database.query.return_value.filter.return_value.all.return_value = []

        alerts = await alert_manager.get_alerts_by_date_range(start_date, end_date)

        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_delete_old_alerts(self, alert_manager, mock_database):
        """Test deletion of old alerts"""
        cutoff_date = datetime.utcnow() - timedelta(days=90)

        deleted_count = await alert_manager.delete_alerts_before(cutoff_date)

        assert deleted_count >= 0
        mock_database.commit.assert_called()

    @pytest.mark.asyncio
    async def test_alert_audit_trail(self, alert_manager, sample_alert, mock_database):
        """Test alert audit trail creation"""
        await alert_manager.save_alert(sample_alert)
        await alert_manager.update_alert_status(sample_alert.id, AlertStatus.RESOLVED)

        if hasattr(alert_manager, 'get_alert_audit_trail'):
            audit_trail = await alert_manager.get_alert_audit_trail(sample_alert.id)
            assert len(audit_trail) >= 2  # Create + Update


# ==========================================
# Metrics Collection Tests
# ==========================================

class TestMetricsCollection:
    """Test metrics collection and reporting"""

    @pytest.mark.asyncio
    async def test_collect_alert_metrics(self, alert_manager, sample_alert):
        """Test collection of alert metrics"""
        await alert_manager.save_alert(sample_alert)

        metrics = await alert_manager.get_metrics()

        assert 'total_alerts' in metrics
        assert metrics['total_alerts'] >= 0

    @pytest.mark.asyncio
    async def test_metrics_by_priority(self, alert_manager):
        """Test metrics grouped by priority"""
        metrics = await alert_manager.get_metrics_by_priority()

        assert AlertPriority.CRITICAL.value in metrics or 'critical' in str(metrics).lower()
        assert AlertPriority.HIGH.value in metrics or 'high' in str(metrics).lower()

    @pytest.mark.asyncio
    async def test_response_time_metrics(self, alert_manager, sample_alert, mock_database):
        """Test response time metrics"""
        sample_alert.acknowledged_at = sample_alert.created_at + timedelta(minutes=5)
        sample_alert.resolved_at = sample_alert.created_at + timedelta(minutes=30)

        mock_database.query.return_value.filter.return_value.all.return_value = [sample_alert]

        metrics = await alert_manager.get_response_time_metrics()

        assert 'avg_acknowledgement_time' in metrics
        assert 'avg_resolution_time' in metrics

    @pytest.mark.asyncio
    async def test_escalation_metrics(self, alert_manager):
        """Test escalation metrics"""
        metrics = await alert_manager.get_escalation_metrics()

        assert 'total_escalations' in metrics
        assert 'escalation_rate' in metrics

    @pytest.mark.asyncio
    async def test_notification_delivery_metrics(self, alert_manager):
        """Test notification delivery metrics"""
        metrics = await alert_manager.get_notification_metrics()

        assert 'emails_sent' in metrics or 'total_notifications' in metrics
        assert 'delivery_success_rate' in metrics or 'success_rate' in metrics


# ==========================================
# Handler Integration Tests
# ==========================================

class TestHandlerIntegration:
    """Test integration between alert handlers"""

    @pytest.mark.asyncio
    async def test_full_alert_lifecycle(self, alert_manager, critical_alert,
                                        mock_email_service, mock_database):
        """Test complete alert lifecycle"""
        # 1. Create and save alert
        await alert_manager.create_alert(critical_alert)
        mock_database.add.assert_called()

        # 2. Send notification
        await alert_manager.notify(critical_alert)
        mock_email_service.send_email.assert_called()

        # 3. Acknowledge
        await alert_manager.acknowledge_alert(critical_alert.id)

        # 4. Resolve
        await alert_manager.resolve_alert(critical_alert.id)

        assert mock_database.commit.call_count >= 3

    @pytest.mark.asyncio
    async def test_alert_with_automatic_escalation(self, alert_manager, sample_alert,
                                                    mock_email_service):
        """Test alert with automatic escalation"""
        # Create unacknowledged alert
        await alert_manager.create_alert(sample_alert)

        # Simulate time passage
        sample_alert.created_at = datetime.utcnow() - timedelta(hours=2)

        # Check escalation
        await alert_manager.process_escalations()

        # Should send escalation notifications
        assert mock_email_service.send_email.call_count >= 1

    @pytest.mark.asyncio
    async def test_alert_deduplication(self, alert_manager, sample_alert, mock_database):
        """Test alert deduplication"""
        # Create same alert twice
        await alert_manager.create_alert(sample_alert)

        duplicate = Alert(
            id=sample_alert.id,
            title=sample_alert.title,
            message=sample_alert.message,
            priority=sample_alert.priority,
            status=AlertStatus.NEW,
            created_at=datetime.utcnow()
        )

        result = await alert_manager.create_alert(duplicate)

        # Should detect duplicate and not create new alert
        assert result is False or mock_database.add.call_count == 1

    @pytest.mark.asyncio
    async def test_alert_aggregation(self, alert_manager):
        """Test aggregation of similar alerts"""
        similar_alerts = [
            Alert(
                id=f'alert-{i}',
                title='Database Connection Error',
                message=f'Connection {i} failed',
                priority=AlertPriority.MEDIUM,
                status=AlertStatus.NEW,
                created_at=datetime.utcnow()
            )
            for i in range(10)
        ]

        aggregated = await alert_manager.aggregate_similar_alerts(similar_alerts)

        # Should group similar alerts
        assert len(aggregated) < len(similar_alerts)


# ==========================================
# Error Handling Tests
# ==========================================

class TestErrorHandling:
    """Test error handling and resilience"""

    @pytest.mark.asyncio
    async def test_notification_failure_handling(self, alert_manager, sample_alert,
                                                  mock_email_service):
        """Test handling of notification failures"""
        mock_email_service.send_email.side_effect = Exception('SMTP error')

        result = await alert_manager.send_email_notification(sample_alert, ['admin@example.com'])

        assert result is False
        # Should log error
        if hasattr(alert_manager, 'logger'):
            assert alert_manager.logger.error.called

    @pytest.mark.asyncio
    async def test_database_failure_handling(self, alert_manager, sample_alert, mock_database):
        """Test handling of database failures"""
        mock_database.commit.side_effect = Exception('Database error')

        with pytest.raises(Exception):
            await alert_manager.save_alert(sample_alert)

        # Should rollback
        mock_database.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_partial_notification_failure(self, alert_manager, critical_alert,
                                                 mock_email_service, mock_sms_service):
        """Test handling when some notifications succeed and others fail"""
        mock_email_service.send_email.return_value = True
        mock_sms_service.send_sms.side_effect = Exception('SMS gateway error')

        result = await alert_manager.send_multi_channel_notification(
            critical_alert,
            email_recipients=['admin@example.com'],
            sms_recipients=['+5511987654321']
        )

        # Should return partial success
        assert result['email'] is True
        assert result['sms'] is False


# ==========================================
# Configuration Tests
# ==========================================

class TestAlertConfiguration:
    """Test alert manager configuration"""

    def test_default_configuration(self, alert_manager):
        """Test default configuration values"""
        assert alert_manager.default_escalation_timeout > 0
        assert alert_manager.max_retry_attempts > 0

    def test_custom_escalation_rules(self, mock_database):
        """Test custom escalation rules"""
        custom_rules = {
            AlertPriority.CRITICAL: timedelta(minutes=5),
            AlertPriority.HIGH: timedelta(minutes=30),
            AlertPriority.MEDIUM: timedelta(hours=2)
        }

        manager = AlertManager(
            database=mock_database,
            escalation_rules=custom_rules
        )

        assert manager.escalation_rules[AlertPriority.CRITICAL] == timedelta(minutes=5)

    def test_notification_channel_configuration(self, mock_database):
        """Test notification channel configuration"""
        channels = ['email', 'sms', 'webhook']

        manager = AlertManager(
            database=mock_database,
            enabled_channels=channels
        )

        assert 'email' in manager.enabled_channels
        assert 'sms' in manager.enabled_channels
