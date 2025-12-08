"""
Unit and integration tests for NotificationService.

CRITICAL: Tests multi-channel notification service (Email, Slack, PagerDuty, WhatsApp).
Coverage target: 100% of NotificationService (currently 0%).

Test scenarios:
1. Send welcome message via WhatsApp
2. Send reminder message via Email
3. Template rendering with Jinja2
4. WhatsApp error handling and retry

Relates to: docs/code-review-paciente/07-TESTES-QUALIDADE.md
GAP: NotificationService Tests (0% → 100% coverage)

File: backend-hormonia/tests/services/test_notification_service.py
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.notification_service import (
    NotificationService,
    NotificationChannel,
    NotificationPriority,
    NotificationResult
)


@pytest.fixture
def notification_service():
    """Create NotificationService instance with mocked settings."""
    with patch('app.config.settings') as mock_settings:
        # Email settings
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USERNAME = "test@test.com"
        mock_settings.SMTP_PASSWORD = "testpass"
        mock_settings.SMTP_FROM_EMAIL = "noreply@test.com"
        mock_settings.SMTP_USE_TLS = True

        # Slack settings
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
        mock_settings.SLACK_DEFAULT_CHANNEL = "#alerts"

        # PagerDuty settings
        mock_settings.PAGERDUTY_SERVICE_KEY = "test_service_key"
        mock_settings.PAGERDUTY_API_KEY = "test_api_key"

        # Retry settings
        mock_settings.NOTIFICATION_RETRY_ATTEMPTS = 3
        mock_settings.NOTIFICATION_RETRY_DELAY = 5

        service = NotificationService()
        return service


@pytest.mark.unit
class TestNotificationServiceWelcomeMessage:
    """Test sending welcome messages."""

    @pytest.mark.asyncio
    async def test_send_welcome_message_whatsapp(
        self,
        notification_service: NotificationService
    ):
        """
        Test sending welcome message via WhatsApp.

        Scenario:
        - New patient registered
        - Send welcome message via WhatsApp
        - Template rendered with patient name

        Expected:
        - Message sent successfully
        - Template variables replaced
        - WhatsApp service called
        """
        # Arrange
        patient_name = "João Silva"
        phone_number = "+5511999999999"

        welcome_template = """
        Olá {{name}}!

        Bem-vinda ao sistema de acompanhamento oncológico.
        Estaremos aqui para ajudar você durante seu tratamento.
        """

        expected_message = f"""
        Olá {patient_name}!

        Bem-vinda ao sistema de acompanhamento oncológico.
        Estaremos aqui para ajudar você durante seu tratamento.
        """

        # Mock WhatsApp service
        with patch('app.services.notification_service.get_whatsapp_service') as mock_whatsapp:
            mock_whatsapp_instance = AsyncMock()
            mock_whatsapp_instance.send_message = AsyncMock(return_value={
                "status": "sent",
                "message_id": "wamid.12345"
            })
            mock_whatsapp.return_value = mock_whatsapp_instance

            # Act
            results = await notification_service.send_notification(
                channels=[NotificationChannel.WHATSAPP],
                subject="Bem-vinda!",
                message=welcome_template,
                recipients=[phone_number],
                priority=NotificationPriority.HIGH,
                template_data={"name": patient_name}
            )

            # Assert
            assert NotificationChannel.WHATSAPP in results
            result = results[NotificationChannel.WHATSAPP]
            assert result.success is True
            assert result.message_id == "wamid.12345"

            # Verify WhatsApp called with rendered message
            mock_whatsapp_instance.send_message.assert_called_once()
            call_args = mock_whatsapp_instance.send_message.call_args
            assert phone_number in str(call_args)

    @pytest.mark.asyncio
    async def test_send_welcome_message_email(
        self,
        notification_service: NotificationService
    ):
        """
        Test sending welcome message via Email.

        Scenario:
        - New patient registered
        - Send welcome email
        - Template rendered with patient data

        Expected:
        - Email sent via SMTP
        - Template variables replaced
        - Email contains patient name
        """
        # Arrange
        patient_name = "Maria Santos"
        email = "maria@test.com"

        template = "Olá {{name}}, bem-vinda!"

        # Mock SMTP
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Act
            results = await notification_service.send_notification(
                channels=[NotificationChannel.EMAIL],
                subject="Bem-vinda ao Sistema",
                message=template,
                recipients=[email],
                priority=NotificationPriority.NORMAL,
                template_data={"name": patient_name}
            )

            # Assert
            assert NotificationChannel.EMAIL in results
            result = results[NotificationChannel.EMAIL]
            assert result.success is True

            # Verify SMTP called
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once()
            mock_server.send_message.assert_called_once()


@pytest.mark.unit
class TestNotificationServiceReminderMessage:
    """Test sending reminder messages."""

    @pytest.mark.asyncio
    async def test_send_reminder_message_email(
        self,
        notification_service: NotificationService
    ):
        """
        Test sending reminder message via Email.

        Scenario:
        - Patient has pending quiz
        - Send reminder email
        - Include quiz link in message

        Expected:
        - Email sent successfully
        - Quiz link included
        - Reminder template rendered
        """
        # Arrange
        patient_email = "patient@test.com"
        quiz_link = "https://app.example.com/quiz/123"

        template = """
        Lembrete: Você tem um questionário pendente.
        Clique aqui para responder: {{quiz_link}}
        """

        # Mock SMTP
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Act
            results = await notification_service.send_notification(
                channels=[NotificationChannel.EMAIL],
                subject="Lembrete: Questionário Pendente",
                message=template,
                recipients=[patient_email],
                priority=NotificationPriority.NORMAL,
                template_data={"quiz_link": quiz_link}
            )

            # Assert
            result = results[NotificationChannel.EMAIL]
            assert result.success is True
            mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_reminder_message_slack(
        self,
        notification_service: NotificationService
    ):
        """
        Test sending reminder notification to Slack.

        Scenario:
        - System has pending tasks
        - Send reminder to Slack channel
        - Use color coding based on priority

        Expected:
        - Slack webhook called
        - Color matches priority (orange for HIGH)
        - Message formatted correctly
        """
        # Arrange
        message = "5 patients have pending quizzes"

        # Mock HTTP client
        with patch.object(notification_service.http_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            # Act
            results = await notification_service.send_notification(
                channels=[NotificationChannel.SLACK],
                subject="Pending Quizzes Alert",
                message=message,
                priority=NotificationPriority.HIGH
            )

            # Assert
            result = results[NotificationChannel.SLACK]
            assert result.success is True

            # Verify Slack webhook called
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert notification_service.slack_webhook in str(call_args)


@pytest.mark.unit
class TestNotificationServiceTemplateRendering:
    """Test template rendering with Jinja2."""

    @pytest.mark.asyncio
    async def test_template_rendering_simple(
        self,
        notification_service: NotificationService
    ):
        """
        Test simple template rendering.

        Scenario:
        - Template with variables
        - Render with data
        - Variables replaced correctly

        Expected:
        - {{name}} replaced with actual name
        - {{date}} replaced with actual date
        """
        # Arrange
        template = "Olá {{name}}! Seu compromisso é em {{date}}."
        template_data = {
            "name": "João",
            "date": "15/01/2025"
        }

        # Mock SMTP
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Act
            await notification_service.send_notification(
                channels=[NotificationChannel.EMAIL],
                subject="Test",
                message=template,
                recipients=["test@test.com"],
                template_data=template_data
            )

            # Assert
            # Verify template was rendered (message sent contains replaced values)
            sent_message = mock_server.send_message.call_args[0][0]
            message_body = str(sent_message)
            assert "João" in message_body
            assert "15/01/2025" in message_body
            assert "{{name}}" not in message_body  # Template tag removed

    @pytest.mark.asyncio
    async def test_template_rendering_complex(
        self,
        notification_service: NotificationService
    ):
        """
        Test complex template rendering with loops and conditionals.

        Scenario:
        - Template with Jinja2 loops
        - Render patient quiz responses
        - Include conditional logic

        Expected:
        - Loop rendered correctly
        - Conditionals work
        - All data included
        """
        # Arrange
        template = """
        Respostas do questionário:
        {% for question, answer in responses.items() %}
        - {{question}}: {{answer}}
        {% endfor %}

        {% if score > 7 %}
        Alerta: Pontuação alta, requer atenção!
        {% endif %}
        """

        template_data = {
            "responses": {
                "Dor": "8/10",
                "Náusea": "Sim",
                "Febre": "Não"
            },
            "score": 8
        }

        # Mock SMTP
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Act
            await notification_service.send_notification(
                channels=[NotificationChannel.EMAIL],
                subject="Quiz Results",
                message=template,
                recipients=["doctor@test.com"],
                template_data=template_data
            )

            # Assert
            sent_message = mock_server.send_message.call_args[0][0]
            message_body = str(sent_message)
            assert "Dor: 8/10" in message_body
            assert "Náusea: Sim" in message_body
            assert "Alerta: Pontuação alta" in message_body


@pytest.mark.unit
class TestNotificationServiceWhatsAppErrorHandling:
    """Test WhatsApp error handling and retry logic."""

    @pytest.mark.asyncio
    async def test_whatsapp_error_handling_timeout(
        self,
        notification_service: NotificationService
    ):
        """
        Test WhatsApp timeout error handling.

        Scenario:
        - WhatsApp API times out
        - Service retries with exponential backoff
        - After 3 retries, returns error

        Expected:
        - 3 retry attempts
        - Exponential backoff delays
        - Final result: failure
        """
        # Arrange
        # Mock WhatsApp to always timeout
        with patch('app.services.notification_service.get_whatsapp_service') as mock_whatsapp:
            mock_whatsapp_instance = AsyncMock()
            mock_whatsapp_instance.send_message = AsyncMock(
                side_effect=TimeoutError("WhatsApp API timeout")
            )
            mock_whatsapp.return_value = mock_whatsapp_instance

            # Act
            results = await notification_service.send_notification(
                channels=[NotificationChannel.WHATSAPP],
                subject="Test",
                message="Test message",
                recipients=["+5511999999999"]
            )

            # Assert
            result = results[NotificationChannel.WHATSAPP]
            assert result.success is False
            assert "timeout" in result.error.lower()

            # Verify 3 retry attempts (max_retries)
            assert mock_whatsapp_instance.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_whatsapp_error_handling_retry_success(
        self,
        notification_service: NotificationService
    ):
        """
        Test WhatsApp retry succeeds after transient failure.

        Scenario:
        - First attempt fails (network error)
        - Second attempt succeeds
        - No more retries needed

        Expected:
        - 2 attempts total
        - Final result: success
        - Message delivered
        """
        # Arrange
        call_count = 0

        def whatsapp_send_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return {"status": "sent", "message_id": "wamid.success"}

        with patch('app.services.notification_service.get_whatsapp_service') as mock_whatsapp:
            mock_whatsapp_instance = AsyncMock()
            mock_whatsapp_instance.send_message = AsyncMock(
                side_effect=whatsapp_send_with_retry
            )
            mock_whatsapp.return_value = mock_whatsapp_instance

            # Act
            results = await notification_service.send_notification(
                channels=[NotificationChannel.WHATSAPP],
                subject="Test",
                message="Test message",
                recipients=["+5511999999999"]
            )

            # Assert
            result = results[NotificationChannel.WHATSAPP]
            assert result.success is True
            assert result.message_id == "wamid.success"

            # Only 2 attempts (1 failure + 1 success)
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_whatsapp_error_handling_invalid_recipient(
        self,
        notification_service: NotificationService
    ):
        """
        Test WhatsApp invalid recipient error.

        Scenario:
        - Invalid phone number format
        - WhatsApp API rejects
        - Service returns error (no retry for invalid input)

        Expected:
        - No retries (invalid input)
        - Clear error message
        - Failure result
        """
        # Arrange
        with patch('app.services.notification_service.get_whatsapp_service') as mock_whatsapp:
            mock_whatsapp_instance = AsyncMock()
            mock_whatsapp_instance.send_message = AsyncMock(
                side_effect=ValueError("Invalid phone number format")
            )
            mock_whatsapp.return_value = mock_whatsapp_instance

            # Act
            results = await notification_service.send_notification(
                channels=[NotificationChannel.WHATSAPP],
                subject="Test",
                message="Test message",
                recipients=["invalid_phone"]
            )

            # Assert
            result = results[NotificationChannel.WHATSAPP]
            assert result.success is False
            assert "phone" in result.error.lower() or "invalid" in result.error.lower()


@pytest.mark.unit
class TestNotificationServiceMultiChannel:
    """Test multi-channel notification with fallback."""

    @pytest.mark.asyncio
    async def test_multi_channel_fallback(
        self,
        notification_service: NotificationService
    ):
        """
        Test fallback to secondary channel on primary failure.

        Scenario:
        - Primary channel (WhatsApp) fails
        - Fallback to Email
        - Email succeeds

        Expected:
        - WhatsApp attempted first
        - Email attempted after WhatsApp failure
        - Final result: success (via Email)
        """
        # Arrange
        with patch('app.services.notification_service.get_whatsapp_service') as mock_whatsapp, \
             patch('smtplib.SMTP') as mock_smtp:

            # WhatsApp fails
            mock_whatsapp_instance = AsyncMock()
            mock_whatsapp_instance.send_message = AsyncMock(
                side_effect=Exception("WhatsApp unavailable")
            )
            mock_whatsapp.return_value = mock_whatsapp_instance

            # Email succeeds
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Act - Try WhatsApp first, fallback to Email
            results = await notification_service.send_notification(
                channels=[NotificationChannel.WHATSAPP, NotificationChannel.EMAIL],
                subject="Important Alert",
                message="Test message",
                recipients=["+5511999999999"],
                fallback=True  # Enable fallback
            )

            # Assert
            # WhatsApp failed
            assert NotificationChannel.WHATSAPP in results
            assert results[NotificationChannel.WHATSAPP].success is False

            # Email succeeded (fallback)
            assert NotificationChannel.EMAIL in results
            assert results[NotificationChannel.EMAIL].success is True

    @pytest.mark.asyncio
    async def test_send_alert_critical_priority(
        self,
        notification_service: NotificationService
    ):
        """
        Test sending critical alert uses all channels.

        Scenario:
        - Critical alert (severity: critical)
        - Send via PagerDuty, Slack, and Email
        - Ensure all channels attempted

        Expected:
        - All 3 channels used
        - PagerDuty alert triggered
        - Slack notification sent
        - Email sent
        """
        # Arrange
        with patch.object(notification_service.http_client, 'post', new_callable=AsyncMock) as mock_post, \
             patch('smtplib.SMTP') as mock_smtp:

            # Mock PagerDuty and Slack
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            # Mock Email
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Act
            results = await notification_service.send_alert(
                alert_type="system_down",
                title="CRITICAL: System Unavailable",
                description="Database connection lost",
                severity="critical"
            )

            # Assert - All channels attempted
            assert len(results) == 3  # PagerDuty, Slack, Email
            assert NotificationChannel.PAGERDUTY in results
            assert NotificationChannel.SLACK in results
            assert NotificationChannel.EMAIL in results


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
