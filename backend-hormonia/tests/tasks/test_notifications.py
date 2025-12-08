"""
Comprehensive Multi-Channel Notification Tests

Tests P2 Implementation: Multi-channel notifications (Email, Slack, PagerDuty)
Tests notification dispatch, channel fallback, retry logic, and external service mocking.
Priority: P2 - High (Alert System)
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock, call
import json

from app.tasks.notifications import (
    send_email_notification,
    send_slack_notification,
    send_pagerduty_notification,
    send_multi_channel_notification,
    NotificationChannel,
    NotificationPriority
)


class TestEmailNotifications:
    """Test email notification sending"""

    @pytest.mark.asyncio
    async def test_send_email_success(self, mocker):
        """Test successful email sending"""
        # Mock SMTP
        mock_smtp = mocker.MagicMock()
        mock_smtp.sendmail = mocker.MagicMock(return_value={})
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        result = await send_email_notification(
            to="doctor@example.com",
            subject="Test Alert",
            body="This is a test notification",
            priority=NotificationPriority.HIGH
        )

        assert result.success is True
        assert result.channel == NotificationChannel.EMAIL
        mock_smtp.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_with_html_template(self, mocker):
        """Test email sending with HTML template"""
        mock_smtp = mocker.MagicMock()
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        result = await send_email_notification(
            to="doctor@example.com",
            subject="Patient Alert",
            body="Patient requires immediate attention",
            html_template="alert_email.html",
            template_vars={"patient_name": "John Doe"}
        )

        assert result.success is True
        # Verify HTML was rendered
        assert mock_smtp.sendmail.called

    @pytest.mark.asyncio
    async def test_send_email_failure_smtp_error(self, mocker):
        """Test email failure handling"""
        import smtplib

        # Mock SMTP failure
        mock_smtp = mocker.MagicMock()
        mock_smtp.sendmail.side_effect = smtplib.SMTPException("Connection refused")
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        result = await send_email_notification(
            to="doctor@example.com",
            subject="Test",
            body="Test"
        )

        assert result.success is False
        assert "SMTP" in result.error or "refused" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_email_invalid_address(self, mocker):
        """Test email with invalid address"""
        result = await send_email_notification(
            to="invalid-email",
            subject="Test",
            body="Test"
        )

        assert result.success is False
        assert "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_email_with_attachments(self, mocker):
        """Test email with file attachments"""
        mock_smtp = mocker.MagicMock()
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        result = await send_email_notification(
            to="doctor@example.com",
            subject="Report",
            body="Please find attached report",
            attachments=[
                {"filename": "report.pdf", "content": b"PDF content"}
            ]
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_bulk_email(self, mocker):
        """Test sending to multiple recipients"""
        mock_smtp = mocker.MagicMock()
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        recipients = [
            "doctor1@example.com",
            "doctor2@example.com",
            "admin@example.com"
        ]

        result = await send_email_notification(
            to=recipients,
            subject="Team Alert",
            body="Urgent: System maintenance"
        )

        assert result.success is True
        assert mock_smtp.sendmail.call_count == len(recipients)


class TestSlackNotifications:
    """Test Slack notification sending"""

    @pytest.mark.asyncio
    async def test_send_slack_message_success(self, mocker):
        """Test successful Slack message sending"""
        # Mock Slack API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "ts": "1234567890.123456"}

        mocker.patch('requests.post', return_value=mock_response)

        result = await send_slack_notification(
            channel="#alerts",
            message="Patient alert: High risk detected",
            priority=NotificationPriority.CRITICAL
        )

        assert result.success is True
        assert result.channel == NotificationChannel.SLACK
        assert result.message_id is not None

    @pytest.mark.asyncio
    async def test_send_slack_with_blocks(self, mocker):
        """Test Slack message with rich formatting (blocks)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}

        mocker.patch('requests.post', return_value=mock_response)

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Alert*: Patient requires attention"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": "*Patient:*\nJohn Doe"},
                    {"type": "mrkdwn", "text": "*Risk:*\nHigh"}
                ]
            }
        ]

        result = await send_slack_notification(
            channel="#alerts",
            message="Patient alert",
            blocks=blocks
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_slack_failure_invalid_token(self, mocker):
        """Test Slack failure with invalid token"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}

        mocker.patch('requests.post', return_value=mock_response)

        result = await send_slack_notification(
            channel="#alerts",
            message="Test"
        )

        assert result.success is False
        assert "auth" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_slack_with_thread(self, mocker):
        """Test Slack threaded message"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}

        mocker.patch('requests.post', return_value=mock_response)

        result = await send_slack_notification(
            channel="#alerts",
            message="Follow-up on alert",
            thread_ts="1234567890.123456"  # Reply to thread
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_slack_mention_users(self, mocker):
        """Test Slack message with user mentions"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}

        mocker.patch('requests.post', return_value=mock_response)

        result = await send_slack_notification(
            channel="#alerts",
            message="<@U123456> <@U789012> Please check this alert",
            priority=NotificationPriority.URGENT
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_slack_rate_limit_handling(self, mocker):
        """Test Slack rate limit handling"""
        mock_response = Mock()
        mock_response.status_code = 429  # Too Many Requests
        mock_response.headers = {"Retry-After": "60"}

        mocker.patch('requests.post', return_value=mock_response)

        result = await send_slack_notification(
            channel="#alerts",
            message="Test"
        )

        assert result.success is False
        assert "rate limit" in result.error.lower()


class TestPagerDutyNotifications:
    """Test PagerDuty incident creation"""

    @pytest.mark.asyncio
    async def test_create_pagerduty_incident_success(self, mocker):
        """Test successful PagerDuty incident creation"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "incident": {
                "id": "PT4KHLK",
                "status": "triggered",
                "incident_number": 123
            }
        }

        mocker.patch('requests.post', return_value=mock_response)

        result = await send_pagerduty_notification(
            summary="Critical: Patient vital signs abnormal",
            severity="critical",
            source="Oncology Clinic System",
            component="Patient Monitoring"
        )

        assert result.success is True
        assert result.channel == NotificationChannel.PAGERDUTY
        assert result.incident_id == "PT4KHLK"

    @pytest.mark.asyncio
    async def test_pagerduty_with_custom_details(self, mocker):
        """Test PagerDuty incident with custom details"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"incident": {"id": "TEST123"}}

        mocker.patch('requests.post', return_value=mock_response)

        custom_details = {
            "patient_id": "PAT-12345",
            "vital_signs": {
                "heart_rate": 150,
                "blood_pressure": "180/110"
            },
            "alert_type": "vital_signs_abnormal"
        }

        result = await send_pagerduty_notification(
            summary="Patient alert",
            severity="high",
            custom_details=custom_details
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_pagerduty_deduplication(self, mocker):
        """Test PagerDuty alert deduplication"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"incident": {"id": "DEDUP123"}}

        mocker.patch('requests.post', return_value=mock_response)

        dedup_key = "patient-123-vitals-alert"

        result = await send_pagerduty_notification(
            summary="Alert",
            severity="high",
            dedup_key=dedup_key
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_pagerduty_failure_invalid_routing_key(self, mocker):
        """Test PagerDuty failure with invalid routing key"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Invalid routing key"}

        mocker.patch('requests.post', return_value=mock_response)

        result = await send_pagerduty_notification(
            summary="Test",
            severity="low"
        )

        assert result.success is False
        assert "routing key" in result.error.lower()

    @pytest.mark.asyncio
    async def test_pagerduty_resolve_incident(self, mocker):
        """Test resolving a PagerDuty incident"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "resolved"}

        mocker.patch('requests.put', return_value=mock_response)

        from app.tasks.notifications import resolve_pagerduty_incident

        result = await resolve_pagerduty_incident(
            incident_id="PT4KHLK",
            resolution_note="Patient stabilized"
        )

        assert result.success is True


class TestMultiChannelNotifications:
    """Test multi-channel notification dispatch"""

    @pytest.mark.asyncio
    async def test_send_to_all_channels(self, mocker):
        """Test sending notification to all channels"""
        # Mock all services
        mocker.patch('smtplib.SMTP', return_value=mocker.MagicMock())

        mock_slack = Mock()
        mock_slack.status_code = 200
        mock_slack.json.return_value = {"ok": True}

        mock_pagerduty = Mock()
        mock_pagerduty.status_code = 201
        mock_pagerduty.json.return_value = {"incident": {"id": "TEST"}}

        mocker.patch('requests.post', side_effect=[mock_slack, mock_pagerduty])

        result = await send_multi_channel_notification(
            message="Critical system alert",
            channels=[
                NotificationChannel.EMAIL,
                NotificationChannel.SLACK,
                NotificationChannel.PAGERDUTY
            ],
            priority=NotificationPriority.CRITICAL,
            email_to="admin@example.com",
            slack_channel="#alerts"
        )

        assert result.success is True
        assert len(result.channel_results) == 3
        assert all(r.success for r in result.channel_results)

    @pytest.mark.asyncio
    async def test_channel_fallback_on_failure(self, mocker):
        """Test fallback to next channel when primary fails"""
        # Mock email failure
        mock_smtp = mocker.MagicMock()
        mock_smtp.sendmail.side_effect = Exception("SMTP error")
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        # Mock Slack success
        mock_slack = Mock()
        mock_slack.status_code = 200
        mock_slack.json.return_value = {"ok": True}
        mocker.patch('requests.post', return_value=mock_slack)

        result = await send_multi_channel_notification(
            message="Alert",
            channels=[
                NotificationChannel.EMAIL,  # Will fail
                NotificationChannel.SLACK   # Fallback
            ],
            email_to="admin@example.com",
            slack_channel="#alerts",
            enable_fallback=True
        )

        # Should succeed via Slack fallback
        assert result.success is True
        assert any(r.channel == NotificationChannel.SLACK and r.success
                  for r in result.channel_results)

    @pytest.mark.asyncio
    async def test_all_channels_fail(self, mocker):
        """Test handling when all channels fail"""
        # Mock all failures
        mocker.patch('smtplib.SMTP', side_effect=Exception("SMTP error"))

        mock_failure = Mock()
        mock_failure.status_code = 500
        mocker.patch('requests.post', return_value=mock_failure)

        result = await send_multi_channel_notification(
            message="Alert",
            channels=[
                NotificationChannel.EMAIL,
                NotificationChannel.SLACK,
                NotificationChannel.PAGERDUTY
            ],
            email_to="admin@example.com",
            slack_channel="#alerts"
        )

        assert result.success is False
        assert all(not r.success for r in result.channel_results)

    @pytest.mark.asyncio
    async def test_priority_based_channel_selection(self, mocker):
        """Test channel selection based on priority level"""
        mocker.patch('smtplib.SMTP', return_value=mocker.MagicMock())
        mocker.patch('requests.post', return_value=Mock(status_code=200, json=lambda: {"ok": True}))

        # Low priority - email only
        result_low = await send_multi_channel_notification(
            message="Info: System update",
            priority=NotificationPriority.LOW,
            auto_select_channels=True
        )

        assert NotificationChannel.EMAIL in [r.channel for r in result_low.channel_results]
        assert NotificationChannel.PAGERDUTY not in [r.channel for r in result_low.channel_results]

        # Critical priority - all channels
        result_critical = await send_multi_channel_notification(
            message="Critical: System failure",
            priority=NotificationPriority.CRITICAL,
            auto_select_channels=True
        )

        assert len(result_critical.channel_results) >= 2


class TestNotificationRetry:
    """Test notification retry logic"""

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self, mocker):
        """Test retry logic for transient failures"""
        call_count = 0

        def mock_send(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return Mock(status_code=200, json=lambda: {"ok": True})

        mocker.patch('requests.post', side_effect=mock_send)

        result = await send_slack_notification(
            channel="#alerts",
            message="Test",
            max_retries=3,
            retry_delay=0.1
        )

        assert result.success is True
        assert call_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, mocker):
        """Test exponential backoff between retries"""
        import time

        call_times = []

        def mock_send(*args, **kwargs):
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("Error")
            return Mock(status_code=200, json=lambda: {"ok": True})

        mocker.patch('requests.post', side_effect=mock_send)

        result = await send_slack_notification(
            channel="#alerts",
            message="Test",
            max_retries=3,
            retry_strategy="exponential"
        )

        # Verify increasing delays
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            assert delay2 > delay1  # Exponential increase

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, mocker):
        """Test behavior when max retries exhausted"""
        mocker.patch('requests.post', side_effect=Exception("Permanent error"))

        result = await send_slack_notification(
            channel="#alerts",
            message="Test",
            max_retries=2,
            retry_delay=0.1
        )

        assert result.success is False
        assert "retry" in result.error.lower() or "exhausted" in result.error.lower()


class TestNotificationTemplates:
    """Test notification templates"""

    @pytest.mark.asyncio
    async def test_email_template_rendering(self, mocker):
        """Test email template rendering"""
        mock_smtp = mocker.MagicMock()
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        template_vars = {
            "patient_name": "John Doe",
            "alert_type": "Vital Signs Abnormal",
            "severity": "High",
            "timestamp": datetime.utcnow().isoformat()
        }

        result = await send_email_notification(
            to="doctor@example.com",
            subject="Patient Alert",
            template="patient_alert",
            template_vars=template_vars
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_slack_block_template(self, mocker):
        """Test Slack block template"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mocker.patch('requests.post', return_value=mock_response)

        from app.tasks.notifications import build_slack_blocks

        blocks = build_slack_blocks(
            template="patient_alert",
            patient_name="John Doe",
            risk_level="High",
            details="Vital signs abnormal"
        )

        result = await send_slack_notification(
            channel="#alerts",
            message="Patient Alert",
            blocks=blocks
        )

        assert result.success is True


class TestNotificationLogging:
    """Test notification logging and audit trail"""

    @pytest.mark.asyncio
    async def test_notification_logged_to_database(self, db_session, mocker):
        """Test notifications are logged to database"""
        mocker.patch('smtplib.SMTP', return_value=mocker.MagicMock())

        result = await send_email_notification(
            to="doctor@example.com",
            subject="Test",
            body="Test",
            log_to_database=True,
            db=db_session
        )

        assert result.success is True

        # Verify database record
        from app.models.notification import NotificationLog
        log = db_session.query(NotificationLog).filter_by(
            notification_id=result.notification_id
        ).first()

        assert log is not None
        assert log.channel == "email"
        assert log.status == "sent"

    @pytest.mark.asyncio
    async def test_failed_notification_logged(self, db_session, mocker):
        """Test failed notifications are also logged"""
        mocker.patch('smtplib.SMTP', side_effect=Exception("SMTP error"))

        result = await send_email_notification(
            to="doctor@example.com",
            subject="Test",
            body="Test",
            log_to_database=True,
            db=db_session
        )

        assert result.success is False

        # Verify failure logged
        from app.models.notification import NotificationLog
        log = db_session.query(NotificationLog).filter_by(
            notification_id=result.notification_id
        ).first()

        assert log is not None
        assert log.status == "failed"
        assert log.error_message is not None


class TestNotificationRateLimiting:
    """Test notification rate limiting"""

    @pytest.mark.asyncio
    async def test_rate_limit_per_channel(self, mocker):
        """Test rate limiting per notification channel"""
        mock_smtp = mocker.MagicMock()
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        mock_redis = mocker.MagicMock()
        mock_redis.incr.return_value = 1
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Send multiple notifications rapidly
        for i in range(10):
            result = await send_email_notification(
                to="doctor@example.com",
                subject=f"Alert {i}",
                body="Test",
                rate_limit=True,
                max_per_minute=5
            )

            if i < 5:
                assert result.success is True
            else:
                # Should be rate limited
                assert result.success is False or result.rate_limited is True

    @pytest.mark.asyncio
    async def test_rate_limit_bypass_for_critical(self, mocker):
        """Test critical priority bypasses rate limiting"""
        mock_smtp = mocker.MagicMock()
        mocker.patch('smtplib.SMTP', return_value=mock_smtp)

        # Even if rate limited, critical should go through
        result = await send_email_notification(
            to="doctor@example.com",
            subject="CRITICAL ALERT",
            body="Patient emergency",
            priority=NotificationPriority.CRITICAL,
            rate_limit=True
        )

        assert result.success is True


class TestNotificationIntegration:
    """Integration tests for notification system"""

    @pytest.mark.asyncio
    async def test_patient_alert_workflow(self, db_session, test_patient, mocker):
        """Test complete patient alert notification workflow"""
        # Mock all channels
        mocker.patch('smtplib.SMTP', return_value=mocker.MagicMock())
        mock_http = Mock()
        mock_http.status_code = 200
        mock_http.json.return_value = {"ok": True}
        mocker.patch('requests.post', return_value=mock_http)

        # Trigger alert
        from app.tasks.notifications import send_patient_alert

        result = await send_patient_alert(
            patient_id=str(test_patient.id),
            alert_type="vital_signs_abnormal",
            severity="high",
            details={
                "heart_rate": 150,
                "blood_pressure": "180/110"
            },
            db=db_session
        )

        assert result.success is True
        # Verify all channels were attempted
        assert len(result.channel_results) >= 1
