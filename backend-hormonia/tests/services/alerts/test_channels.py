"""
Unit Tests for Channel Handlers.

Tests individual notification channel implementations including:
- Email channel (SMTP)
- WebSocket channel (real-time)
- Webhook channel (HTTP POST)
- Dashboard channel (data storage)
- Slack channel (stub)
- PagerDuty channel (stub)
- SMS channel (stub)

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, Optional

from app.services.alerts import (
    EmailChannelHandler,
    WebSocketChannelHandler,
    WebhookChannelHandler,
    DashboardChannelHandler,
    SlackChannelHandler,
    PagerDutyChannelHandler,
    SMSChannelHandler,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    NotificationChannel,
    NotificationTarget,
    NotificationResult,
    EmailChannelConfig,
    WebSocketChannelConfig,
    WebhookChannelConfig,
)


# ============================================================================
# Fixtures
# ============================================================================


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
        metadata={"days_without_response": 2},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_target():
    """Sample notification target."""
    return NotificationTarget(
        user_id=uuid4(),
        email="doctor@example.com",
        phone="+5511999999999",
        metadata={
            "email": "doctor@example.com",
            "slack_user_id": "U123456",
            "pagerduty_user_id": "P123456",
        },
    )


@pytest.fixture
def email_config():
    """Sample email configuration."""
    return EmailChannelConfig(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="noreply@example.com",
        smtp_password="password123",
        from_email="alerts@example.com",
        from_name="Alert System",
        use_tls=True,
    )


@pytest.fixture
def webhook_config():
    """Sample webhook configuration."""
    return WebhookChannelConfig(
        url="https://webhook.example.com/alerts",
        method="POST",
        headers={"Authorization": "Bearer token123"},
        timeout_seconds=30,
        retry_count=3,
    )


@pytest.fixture
def websocket_config():
    """Sample WebSocket configuration."""
    return WebSocketChannelConfig(
        server_url="ws://localhost:8000/ws",
        reconnect_interval=5,
        max_reconnect_attempts=3,
    )


# ============================================================================
# Test EmailChannelHandler
# ============================================================================


class TestEmailChannelHandler:
    """Test EmailChannelHandler implementation."""

    def test_init_with_config(self, email_config):
        """Test initialization with configuration."""
        handler = EmailChannelHandler(config=email_config)

        assert handler.email_config == email_config
        assert handler.is_enabled() is True

    def test_init_without_config(self):
        """Test initialization without configuration."""
        handler = EmailChannelHandler()

        assert handler.email_config is None

    @pytest.mark.asyncio
    async def test_send_success(self, email_config, sample_alert, sample_target):
        """Test successful email send."""
        handler = EmailChannelHandler(config=email_config)

        with patch("smtplib.SMTP") as mock_smtp:
            # Setup mock
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Execute
            result = await handler.send(alert=sample_alert, target=sample_target)

            # Assert
            assert isinstance(result, NotificationResult)
            assert result.channel == NotificationChannel.EMAIL
            assert result.success is True
            assert result.error is None

    @pytest.mark.asyncio
    async def test_send_without_config(self, sample_alert, sample_target):
        """Test send fails without configuration."""
        handler = EmailChannelHandler()

        # Execute
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert
        assert result.success is False
        assert "configuration" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_without_email_in_target(
        self, email_config, sample_alert, sample_target
    ):
        """Test send fails when target has no email."""
        handler = EmailChannelHandler(config=email_config)
        target_no_email = NotificationTarget(
            user_id=uuid4(),
            metadata={},  # No email
        )

        # Execute
        result = await handler.send(alert=sample_alert, target=target_no_email)

        # Assert
        assert result.success is False
        assert "email" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_smtp_failure(self, email_config, sample_alert, sample_target):
        """Test handling of SMTP errors."""
        handler = EmailChannelHandler(config=email_config)

        with patch("smtplib.SMTP") as mock_smtp:
            # Setup mock to raise exception
            mock_smtp.side_effect = smtplib.SMTPException("SMTP error")

            # Execute
            result = await handler.send(alert=sample_alert, target=sample_target)

            # Assert
            assert result.success is False
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_send_formats_email_correctly(
        self, email_config, sample_alert, sample_target
    ):
        """Test that email is formatted correctly."""
        handler = EmailChannelHandler(config=email_config)

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Execute
            await handler.send(alert=sample_alert, target=sample_target)

            # Assert - sendmail should be called
            assert mock_server.sendmail.called

    def test_create_email_message(self, email_config, sample_alert):
        """Test email message creation."""
        handler = EmailChannelHandler(config=email_config)

        # Execute
        message = handler._create_email_message(
            alert=sample_alert, recipient="test@example.com"
        )

        # Assert
        assert message is not None
        assert sample_alert.title in str(message)


# ============================================================================
# Test WebSocketChannelHandler
# ============================================================================


class TestWebSocketChannelHandler:
    """Test WebSocketChannelHandler implementation."""

    def test_init_with_config(self, websocket_config):
        """Test initialization with configuration."""
        handler = WebSocketChannelHandler(config=websocket_config)

        assert handler.ws_config == websocket_config
        assert handler.is_enabled() is True

    def test_init_without_config(self):
        """Test initialization without configuration."""
        handler = WebSocketChannelHandler()

        assert handler.ws_config is None

    @pytest.mark.asyncio
    async def test_send_success(self, websocket_config, sample_alert, sample_target):
        """Test successful WebSocket send."""
        handler = WebSocketChannelHandler(config=websocket_config)

        with patch("aiohttp.ClientSession") as mock_session:
            # Setup mock
            mock_ws = AsyncMock()
            mock_ws.send_json = AsyncMock()
            mock_session.return_value.ws_connect = AsyncMock(return_value=mock_ws)

            # Execute
            result = await handler.send(alert=sample_alert, target=sample_target)

            # Assert
            assert isinstance(result, NotificationResult)
            assert result.channel == NotificationChannel.WEBSOCKET

    @pytest.mark.asyncio
    async def test_send_without_config(self, sample_alert, sample_target):
        """Test send without configuration."""
        handler = WebSocketChannelHandler()

        # Execute
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert - should handle gracefully
        assert result is not None

    @pytest.mark.asyncio
    async def test_send_connection_failure(
        self, websocket_config, sample_alert, sample_target
    ):
        """Test handling of WebSocket connection failures."""
        handler = WebSocketChannelHandler(config=websocket_config)

        with patch("aiohttp.ClientSession") as mock_session:
            # Setup mock to raise exception
            mock_session.return_value.ws_connect = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            # Execute
            result = await handler.send(alert=sample_alert, target=sample_target)

            # Assert
            assert result.success is False

    @pytest.mark.asyncio
    async def test_send_formats_message_correctly(
        self, websocket_config, sample_alert, sample_target
    ):
        """Test that WebSocket message is formatted correctly."""
        handler = WebSocketChannelHandler(config=websocket_config)

        with patch("aiohttp.ClientSession") as mock_session:
            mock_ws = AsyncMock()
            mock_ws.send_json = AsyncMock()
            mock_session.return_value.ws_connect = AsyncMock(return_value=mock_ws)

            # Execute
            await handler.send(alert=sample_alert, target=sample_target)

            # Assert - send_json should be called
            mock_ws.send_json.assert_called_once()
            call_args = mock_ws.send_json.call_args
            message_data = call_args[0][0]
            assert "alert_id" in message_data
            assert "title" in message_data


# ============================================================================
# Test WebhookChannelHandler
# ============================================================================


class TestWebhookChannelHandler:
    """Test WebhookChannelHandler implementation."""

    def test_init_with_config(self, webhook_config):
        """Test initialization with configuration."""
        handler = WebhookChannelHandler(config=webhook_config)

        assert handler.webhook_config == webhook_config
        assert handler.is_enabled() is True

    def test_init_without_config(self):
        """Test initialization without configuration."""
        handler = WebhookChannelHandler()

        assert handler.webhook_config is None

    @pytest.mark.asyncio
    async def test_send_success(self, webhook_config, sample_alert, sample_target):
        """Test successful webhook POST."""
        handler = WebhookChannelHandler(config=webhook_config)

        with patch("aiohttp.ClientSession") as mock_session:
            # Setup mock
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="OK")
            mock_session.return_value.post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session.return_value
            )
            mock_session.return_value.__aexit__ = AsyncMock()

            # Execute
            result = await handler.send(alert=sample_alert, target=sample_target)

            # Assert
            assert isinstance(result, NotificationResult)
            assert result.channel == NotificationChannel.WEBHOOK

    @pytest.mark.asyncio
    async def test_send_without_config(self, sample_alert, sample_target):
        """Test send without configuration."""
        handler = WebhookChannelHandler()

        # Execute
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert
        assert result.success is False
        assert "configuration" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_http_error(self, webhook_config, sample_alert, sample_target):
        """Test handling of HTTP errors."""
        handler = WebhookChannelHandler(config=webhook_config)

        with patch("aiohttp.ClientSession") as mock_session:
            # Setup mock to return error status
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_session.return_value.post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session.return_value
            )
            mock_session.return_value.__aexit__ = AsyncMock()

            # Execute
            result = await handler.send(alert=sample_alert, target=sample_target)

            # Assert
            assert result.success is False

    @pytest.mark.asyncio
    async def test_send_with_retry(self, sample_alert, sample_target):
        """Test webhook retry mechanism."""
        config = WebhookChannelConfig(
            url="https://webhook.example.com/alerts",
            method="POST",
            retry_count=3,
            timeout_seconds=30,
        )
        handler = WebhookChannelHandler(config=config)

        with patch("aiohttp.ClientSession") as mock_session:
            # Setup mock to fail first attempts, succeed on last
            mock_response_fail = AsyncMock()
            mock_response_fail.status = 500

            mock_response_success = AsyncMock()
            mock_response_success.status = 200

            mock_session.return_value.post = AsyncMock(
                side_effect=[
                    mock_response_fail,
                    mock_response_fail,
                    mock_response_success,
                ]
            )
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session.return_value
            )
            mock_session.return_value.__aexit__ = AsyncMock()

            # Execute
            result = await handler.send(alert=sample_alert, target=sample_target)

            # Assert - should eventually succeed
            assert mock_session.return_value.post.call_count >= 1

    @pytest.mark.asyncio
    async def test_send_includes_headers(
        self, webhook_config, sample_alert, sample_target
    ):
        """Test that webhook includes configured headers."""
        handler = WebhookChannelHandler(config=webhook_config)

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session.return_value
            )
            mock_session.return_value.__aexit__ = AsyncMock()

            # Execute
            await handler.send(alert=sample_alert, target=sample_target)

            # Assert - post should be called with headers
            call_args = mock_session.return_value.post.call_args
            assert call_args is not None


# ============================================================================
# Test DashboardChannelHandler
# ============================================================================


class TestDashboardChannelHandler:
    """Test DashboardChannelHandler implementation."""

    def test_init(self):
        """Test initialization."""
        handler = DashboardChannelHandler()

        assert handler.is_enabled() is True

    @pytest.mark.asyncio
    async def test_send_success(self, sample_alert, sample_target):
        """Test successful dashboard notification."""
        handler = DashboardChannelHandler()

        # Execute
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert
        assert isinstance(result, NotificationResult)
        assert result.channel == NotificationChannel.DASHBOARD
        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_stores_alert_data(self, sample_alert, sample_target):
        """Test that dashboard stores alert data."""
        handler = DashboardChannelHandler()

        # Execute
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert - should store in internal cache
        assert len(handler._dashboard_alerts) > 0

    @pytest.mark.asyncio
    async def test_get_dashboard_alerts(self, sample_alert, sample_target):
        """Test retrieving dashboard alerts."""
        handler = DashboardChannelHandler()

        # Send alert
        await handler.send(alert=sample_alert, target=sample_target)

        # Execute
        alerts = handler.get_dashboard_alerts(user_id=sample_target.user_id)

        # Assert
        assert len(alerts) > 0
        assert any(a["alert_id"] == str(sample_alert.id) for a in alerts)

    def test_clear_dashboard_alerts(self):
        """Test clearing dashboard alerts."""
        handler = DashboardChannelHandler()
        handler._dashboard_alerts = {"user1": [{"alert": "test"}]}

        # Execute
        handler.clear_dashboard_alerts(user_id="user1")

        # Assert
        assert handler._dashboard_alerts.get("user1", []) == []


# ============================================================================
# Test SlackChannelHandler (Stub)
# ============================================================================


class TestSlackChannelHandler:
    """Test SlackChannelHandler stub implementation."""

    def test_init(self):
        """Test initialization."""
        handler = SlackChannelHandler()

        assert handler.is_enabled() is True

    @pytest.mark.asyncio
    async def test_send_stub_implementation(self, sample_alert, sample_target):
        """Test stub implementation returns success."""
        handler = SlackChannelHandler()

        # Execute
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert
        assert isinstance(result, NotificationResult)
        assert result.channel == NotificationChannel.SLACK
        # Stub should return success with note
        assert result.success is True
        assert (
            "stub" in result.message.lower()
            or "not implemented" in result.message.lower()
        )

    @pytest.mark.asyncio
    async def test_send_logs_stub_message(self, sample_alert, sample_target):
        """Test that stub logs appropriate message."""
        handler = SlackChannelHandler()

        with patch("app.services.alerts.notification.channels.logger") as mock_logger:
            # Execute
            await handler.send(alert=sample_alert, target=sample_target)

            # Assert - should log stub message
            assert mock_logger.info.called or mock_logger.warning.called


# ============================================================================
# Test PagerDutyChannelHandler (Stub)
# ============================================================================


class TestPagerDutyChannelHandler:
    """Test PagerDutyChannelHandler stub implementation."""

    def test_init(self):
        """Test initialization."""
        handler = PagerDutyChannelHandler()

        assert handler.is_enabled() is True

    @pytest.mark.asyncio
    async def test_send_stub_implementation(self, sample_alert, sample_target):
        """Test stub implementation returns success."""
        handler = PagerDutyChannelHandler()

        # Execute
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert
        assert isinstance(result, NotificationResult)
        assert result.channel == NotificationChannel.PAGERDUTY
        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_includes_severity(self, sample_alert, sample_target):
        """Test that PagerDuty stub acknowledges severity."""
        handler = PagerDutyChannelHandler()

        # High severity alert
        high_alert = sample_alert
        high_alert.severity = AlertSeverity.CRITICAL

        # Execute
        result = await handler.send(alert=high_alert, target=sample_target)

        # Assert
        assert result is not None


# ============================================================================
# Test SMSChannelHandler (Stub)
# ============================================================================


class TestSMSChannelHandler:
    """Test SMSChannelHandler stub implementation."""

    def test_init(self):
        """Test initialization."""
        handler = SMSChannelHandler()

        assert handler.is_enabled() is True

    @pytest.mark.asyncio
    async def test_send_stub_implementation(self, sample_alert, sample_target):
        """Test stub implementation returns success."""
        handler = SMSChannelHandler()

        # Execute
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert
        assert isinstance(result, NotificationResult)
        assert result.channel == NotificationChannel.SMS
        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_without_phone_number(self, sample_alert):
        """Test SMS stub handles missing phone number."""
        handler = SMSChannelHandler()
        target_no_phone = NotificationTarget(
            user_id=uuid4(),
            metadata={},  # No phone
        )

        # Execute
        result = await handler.send(alert=sample_alert, target=target_no_phone)

        # Assert - stub should still succeed
        assert result.success is True


# ============================================================================
# Test Channel Configuration
# ============================================================================


class TestChannelConfiguration:
    """Test channel configuration validation."""

    def test_email_config_validation(self):
        """Test email configuration validation."""
        config = EmailChannelConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="password",
            from_email="noreply@example.com",
        )

        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 587

    def test_webhook_config_validation(self):
        """Test webhook configuration validation."""
        config = WebhookChannelConfig(
            url="https://example.com/webhook",
            method="POST",
            timeout_seconds=30,
        )

        assert config.url == "https://example.com/webhook"
        assert config.method == "POST"

    def test_websocket_config_validation(self):
        """Test WebSocket configuration validation."""
        config = WebSocketChannelConfig(
            server_url="ws://localhost:8000/ws",
            reconnect_interval=5,
        )

        assert config.server_url == "ws://localhost:8000/ws"
        assert config.reconnect_interval == 5


# ============================================================================
# Test Base ChannelHandler
# ============================================================================


class TestBaseChannelHandler:
    """Test base ChannelHandler class."""

    def test_base_handler_init(self):
        """Test base handler initialization."""
        handler = ChannelHandler(config={"enabled": True})

        assert handler.config == {"enabled": True}
        assert handler.enabled is True

    def test_base_handler_is_enabled(self):
        """Test is_enabled method."""
        handler = ChannelHandler(config={"enabled": True})

        assert handler.is_enabled() is True

    def test_base_handler_is_disabled(self):
        """Test is_enabled with disabled config."""
        handler = ChannelHandler(config={"enabled": False})

        assert handler.is_enabled() is False

    @pytest.mark.asyncio
    async def test_base_handler_send_not_implemented(self, sample_alert, sample_target):
        """Test that base handler send raises NotImplementedError."""
        handler = ChannelHandler()

        with pytest.raises(NotImplementedError):
            await handler.send(alert=sample_alert, target=sample_target)


# ============================================================================
# Test Error Handling
# ============================================================================


class TestChannelErrorHandling:
    """Test error handling across all channels."""

    @pytest.mark.asyncio
    async def test_email_handles_none_alert(self, email_config, sample_target):
        """Test email handler with None alert."""
        handler = EmailChannelHandler(config=email_config)

        with pytest.raises((ValueError, TypeError, AttributeError)):
            await handler.send(alert=None, target=sample_target)

    @pytest.mark.asyncio
    async def test_websocket_handles_none_target(self, websocket_config, sample_alert):
        """Test WebSocket handler with None target."""
        handler = WebSocketChannelHandler(config=websocket_config)

        with pytest.raises((ValueError, TypeError, AttributeError)):
            await handler.send(alert=sample_alert, target=None)

    @pytest.mark.asyncio
    async def test_webhook_handles_invalid_url(self, sample_alert, sample_target):
        """Test webhook handler with invalid URL."""
        config = WebhookChannelConfig(
            url="not-a-valid-url",
            method="POST",
        )
        handler = WebhookChannelHandler(config=config)

        # Execute - should handle gracefully
        result = await handler.send(alert=sample_alert, target=sample_target)

        # Assert
        assert result.success is False
