"""
Tests for NotificationService - Patient onboarding notification orchestration.

ISSUE-005 PHASE 2: NotificationService Extraction

Test Coverage:
- Initialization and dependency injection
- Welcome message sending
- WebSocket event publishing
- Conditional message sending (send_welcome_if_needed)
- Error handling and edge cases
- Service shutdown

Target: 100% code coverage
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.domain.patient.onboarding.notification_service import NotificationService
from app.models.patient import Patient
from app.models.user import User


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_message_service():
    """Create mock MessageService."""
    service = Mock()
    service.db = Mock()
    service.schedule_message = Mock()
    return service


@pytest.fixture
def mock_whatsapp_service():
    """Create mock UnifiedWhatsAppService."""
    service = AsyncMock()
    service.send_message = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_websocket_service():
    """Create mock WebSocketEventService."""
    service = AsyncMock()
    service.publish_patient_event = AsyncMock()
    return service


@pytest.fixture
def mock_executor():
    """Create mock ThreadPoolExecutor."""
    executor = Mock()
    return executor


@pytest.fixture
def notification_service(
    mock_message_service, mock_whatsapp_service, mock_websocket_service, mock_executor
):
    """Create NotificationService instance with all dependencies."""
    return NotificationService(
        message_service=mock_message_service,
        whatsapp_service=mock_whatsapp_service,
        websocket_service=mock_websocket_service,
        executor=mock_executor,
    )


@pytest.fixture
def sample_patient():
    """Create sample patient for testing."""
    patient = Mock(spec=Patient)
    patient.id = uuid4()
    patient.name = "Test Patient"
    patient.phone = "+5511999999999"
    patient.treatment_type = "hormonal"
    patient.doctor_id = uuid4()
    return patient


@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "doctor@clinic.com"
    return user


# ============================================================================
# Initialization Tests
# ============================================================================


class TestNotificationServiceInitialization:
    """Test NotificationService initialization and dependency injection."""

    def test_init_with_all_dependencies(
        self,
        mock_message_service,
        mock_whatsapp_service,
        mock_websocket_service,
        mock_executor,
    ):
        """Test initialization with all dependencies provided."""
        service = NotificationService(
            message_service=mock_message_service,
            whatsapp_service=mock_whatsapp_service,
            websocket_service=mock_websocket_service,
            executor=mock_executor,
        )

        assert service.message_service == mock_message_service
        assert service.whatsapp_service == mock_whatsapp_service
        assert service.websocket_service == mock_websocket_service
        assert service._executor == mock_executor

    def test_init_creates_default_executor(
        self, mock_message_service, mock_whatsapp_service
    ):
        """Test that default executor is created if not provided."""
        with patch(
            "app.domain.patient.onboarding.notification_service.get_notification_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_get_executor.return_value = mock_executor
            service = NotificationService(
                message_service=mock_message_service,
                whatsapp_service=mock_whatsapp_service,
            )

            mock_get_executor.assert_called_once_with()
            assert service._executor == mock_executor

    def test_init_without_websocket_service(
        self, mock_message_service, mock_whatsapp_service
    ):
        """Test initialization without WebSocket service (optional dependency)."""
        service = NotificationService(
            message_service=mock_message_service,
            whatsapp_service=mock_whatsapp_service,
            websocket_service=None,
        )

        assert service.websocket_service is None
        assert service.message_service is not None
        assert service.whatsapp_service is not None


# ============================================================================
# Welcome Message Tests
# ============================================================================


class TestSendWelcomeMessage:
    """Test send_welcome_message method."""

    @pytest.mark.asyncio
    async def test_send_welcome_message_success(
        self, notification_service, sample_patient, sample_user, mock_executor
    ):
        """Test successful welcome message sending."""
        # Mock settings
        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = True
            mock_settings.WHATSAPP_CLINIC_NAME = "Test Clinic"
            mock_settings.WHATSAPP_CLINIC_SUPPORT_PHONE = "+5511888888888"

            # Mock get_welcome_message
            with patch(
                "app.domain.patient.onboarding.notification_service.get_welcome_message"
            ) as mock_get_welcome:
                mock_get_welcome.return_value = "Welcome to Test Clinic!"

                # Mock message object
                mock_message = Mock()
                notification_service.message_service.schedule_message.return_value = (
                    mock_message
                )

                # Mock asyncio.get_event_loop and run_in_executor
                with patch(
                    "app.domain.patient.onboarding.notification_service.asyncio.get_event_loop"
                ) as mock_get_loop:
                    mock_loop = AsyncMock()
                    mock_loop.run_in_executor = AsyncMock(
                        return_value=mock_message
                    )
                    mock_get_loop.return_value = mock_loop

                    # Execute
                    result = await notification_service.send_welcome_message(
                        sample_patient, sample_user
                    )

                    # Verify
                    assert result is True
                    notification_service.whatsapp_service.send_message.assert_called_once_with(
                        mock_message
                    )
                    mock_get_welcome.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_welcome_message_whatsapp_disabled(
        self, notification_service, sample_patient, sample_user
    ):
        """Test welcome message skipped when WhatsApp is disabled."""
        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = False

            result = await notification_service.send_welcome_message(
                sample_patient, sample_user
            )

            assert result is False
            notification_service.whatsapp_service.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_welcome_message_welcome_disabled(
        self, notification_service, sample_patient, sample_user
    ):
        """Test welcome message skipped when welcome messages are disabled."""
        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = False

            result = await notification_service.send_welcome_message(
                sample_patient, sample_user
            )

            assert result is False
            notification_service.whatsapp_service.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_welcome_message_whatsapp_failure(
        self, notification_service, sample_patient, sample_user, mock_executor
    ):
        """Test handling of WhatsApp sending failure."""
        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = True
            mock_settings.WHATSAPP_CLINIC_NAME = "Test Clinic"
            mock_settings.WHATSAPP_CLINIC_SUPPORT_PHONE = "+5511888888888"

            with patch(
                "app.domain.patient.onboarding.notification_service.get_welcome_message"
            ) as mock_get_welcome:
                mock_get_welcome.return_value = "Welcome to Test Clinic!"

                # Mock WhatsApp service to return False (failure)
                notification_service.whatsapp_service.send_message.return_value = False

                mock_message = Mock()
                notification_service.message_service.schedule_message.return_value = (
                    mock_message
                )

                with patch(
                    "app.domain.patient.onboarding.notification_service.asyncio.get_event_loop"
                ) as mock_get_loop:
                    mock_loop = AsyncMock()
                    mock_loop.run_in_executor = AsyncMock(
                        return_value=mock_message
                    )
                    mock_get_loop.return_value = mock_loop

                    result = await notification_service.send_welcome_message(
                        sample_patient, sample_user
                    )

                    # Verify failure is returned
                    assert result is False

    @pytest.mark.asyncio
    async def test_send_welcome_message_exception_handling(
        self, notification_service, sample_patient, sample_user
    ):
        """Test exception handling during message sending."""
        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = True

            with patch(
                "app.domain.patient.onboarding.notification_service.get_welcome_message"
            ) as mock_get_welcome:
                mock_get_welcome.side_effect = Exception("Template error")

                result = await notification_service.send_welcome_message(
                    sample_patient, sample_user
                )

                # Should return False on exception
                assert result is False

    @pytest.mark.asyncio
    async def test_send_welcome_message_import_error(
        self, notification_service, sample_patient, sample_user
    ):
        """Test handling of ImportError (WhatsApp service not available)."""
        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = True

            with patch(
                "app.domain.patient.onboarding.notification_service.get_welcome_message"
            ) as mock_get_welcome:
                mock_get_welcome.side_effect = ImportError("Module not found")

                result = await notification_service.send_welcome_message(
                    sample_patient, sample_user
                )

                # Should return False on ImportError
                assert result is False


# ============================================================================
# WebSocket Event Tests
# ============================================================================


class TestPublishPatientCreatedEvent:
    """Test publish_patient_created_event method."""

    @pytest.mark.asyncio
    async def test_publish_event_success(self, notification_service, sample_patient):
        """Test successful WebSocket event publishing."""
        doctor_id = uuid4()

        with patch(
            "app.services.websocket_events.websocket_events"
        ) as mock_ws_events:
            mock_ws_events.publish_patient_event = AsyncMock()

            result = await notification_service.publish_patient_created_event(
                sample_patient, doctor_id, action="created"
            )

            assert result is True
            mock_ws_events.publish_patient_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event_no_websocket_service(
        self, mock_message_service, mock_whatsapp_service, sample_patient
    ):
        """Test event publishing when WebSocket service is not configured."""
        # Create service without WebSocket
        service = NotificationService(
            message_service=mock_message_service,
            whatsapp_service=mock_whatsapp_service,
            websocket_service=None,
        )

        doctor_id = uuid4()
        result = await service.publish_patient_created_event(
            sample_patient, doctor_id
        )

        # Should return False when no WebSocket service
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_event_websocket_not_initialized(
        self, notification_service, sample_patient
    ):
        """Test handling when websocket_events is not initialized."""
        doctor_id = uuid4()

        with patch(
            "app.services.websocket_events.websocket_events",
            None,
        ):
            result = await notification_service.publish_patient_created_event(
                sample_patient, doctor_id
            )

            # Should return False and log warning
            assert result is False

    @pytest.mark.asyncio
    async def test_publish_event_exception_handling(
        self, notification_service, sample_patient
    ):
        """Test exception handling during event publishing."""
        doctor_id = uuid4()

        with patch(
            "app.services.websocket_events.websocket_events"
        ) as mock_ws_events:
            mock_ws_events.publish_patient_event = AsyncMock(
                side_effect=Exception("WebSocket error")
            )

            result = await notification_service.publish_patient_created_event(
                sample_patient, doctor_id
            )

            # Should return False on exception
            assert result is False

    @pytest.mark.asyncio
    async def test_publish_event_custom_action(
        self, notification_service, sample_patient
    ):
        """Test event publishing with custom action."""
        doctor_id = uuid4()

        with patch(
            "app.services.websocket_events.websocket_events"
        ) as mock_ws_events:
            mock_ws_events.publish_patient_event = AsyncMock()

            result = await notification_service.publish_patient_created_event(
                sample_patient, doctor_id, action="onboarding_completed"
            )

            assert result is True
            # Verify the action was passed correctly
            call_args = mock_ws_events.publish_patient_event.call_args
            assert call_args.kwargs["data"]["action"] == "onboarding_completed"


# ============================================================================
# Conditional Message Sending Tests
# ============================================================================


class TestSendWelcomeIfNeeded:
    """Test send_welcome_if_needed method."""

    @pytest.mark.asyncio
    async def test_send_if_no_existing_messages(
        self, notification_service, sample_patient, sample_user
    ):
        """Test sending welcome message when no messages exist."""
        # Mock database query to return 0 messages
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.count.return_value = 0
        notification_service.message_service.db.query.return_value = mock_query

        with patch(
            "app.domain.patient.onboarding.notification_service.asyncio.get_event_loop"
        ) as mock_get_loop:
            mock_loop = AsyncMock()
            mock_loop.run_in_executor = AsyncMock(return_value=0)
            mock_get_loop.return_value = mock_loop

            # Mock send_welcome_message to return True
            with patch.object(
                notification_service, "send_welcome_message", return_value=True
            ) as mock_send:
                result = await notification_service.send_welcome_if_needed(
                    sample_patient, sample_user
                )

                assert result is True
                mock_send.assert_called_once_with(sample_patient, sample_user)

    @pytest.mark.asyncio
    async def test_skip_if_messages_exist(
        self, notification_service, sample_patient, sample_user
    ):
        """Test skipping welcome message when messages already exist."""
        # Mock database query to return 1 message
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.count.return_value = 1
        notification_service.message_service.db.query.return_value = mock_query

        with patch(
            "app.domain.patient.onboarding.notification_service.asyncio.get_event_loop"
        ) as mock_get_loop:
            mock_loop = AsyncMock()
            mock_loop.run_in_executor = AsyncMock(return_value=1)
            mock_get_loop.return_value = mock_loop

            # Mock send_welcome_message to ensure it's not called
            with patch.object(
                notification_service, "send_welcome_message"
            ) as mock_send:
                result = await notification_service.send_welcome_if_needed(
                    sample_patient, sample_user
                )

                assert result is True
                mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_handling(
        self, notification_service, sample_patient, sample_user
    ):
        """Test exception handling during message check."""
        # Mock database query to raise exception
        notification_service.message_service.db.query.side_effect = Exception(
            "Database error"
        )

        result = await notification_service.send_welcome_if_needed(
            sample_patient, sample_user
        )

        # Should return False on exception
        assert result is False


# ============================================================================
# Service Shutdown Tests
# ============================================================================


class TestNotificationServiceShutdown:
    """Test NotificationService shutdown method."""

    def test_shutdown_graceful(self, notification_service):
        """Test graceful shutdown with wait=True."""
        notification_service.shutdown(wait=True)

        notification_service._executor.shutdown.assert_called_once_with(wait=True)

    def test_shutdown_no_wait(self, notification_service):
        """Test shutdown without waiting."""
        notification_service.shutdown(wait=False)

        notification_service._executor.shutdown.assert_called_once_with(wait=False)

    def test_shutdown_default_wait(self, notification_service):
        """Test shutdown with default wait parameter."""
        notification_service.shutdown()

        # Default should be wait=True
        notification_service._executor.shutdown.assert_called_once_with(wait=True)


# ============================================================================
# Integration Tests
# ============================================================================


class TestNotificationServiceIntegration:
    """Integration tests for NotificationService."""

    @pytest.mark.asyncio
    async def test_full_onboarding_notification_flow(
        self, notification_service, sample_patient, sample_user
    ):
        """Test complete onboarding notification flow."""
        doctor_id = uuid4()

        # Mock all settings
        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = True
            mock_settings.WHATSAPP_CLINIC_NAME = "Test Clinic"
            mock_settings.WHATSAPP_CLINIC_SUPPORT_PHONE = "+5511888888888"

            with patch(
                "app.domain.patient.onboarding.notification_service.get_welcome_message"
            ) as mock_get_welcome:
                mock_get_welcome.return_value = "Welcome!"

                mock_message = Mock()
                notification_service.message_service.schedule_message.return_value = (
                    mock_message
                )

                with patch(
                    "app.domain.patient.onboarding.notification_service.asyncio.get_event_loop"
                ) as mock_get_loop:
                    mock_loop = AsyncMock()
                    mock_loop.run_in_executor = AsyncMock(
                        return_value=mock_message
                    )
                    mock_get_loop.return_value = mock_loop

                    with patch(
                        "app.services.websocket_events.websocket_events"
                    ) as mock_ws_events:
                        mock_ws_events.publish_patient_event = AsyncMock()

                        # Step 1: Send welcome message
                        welcome_result = (
                            await notification_service.send_welcome_message(
                                sample_patient, sample_user
                            )
                        )

                        # Step 2: Publish WebSocket event
                        event_result = (
                            await notification_service.publish_patient_created_event(
                                sample_patient, doctor_id
                            )
                        )

                        # Verify both steps succeeded
                        assert welcome_result is True
                        assert event_result is True
                        notification_service.whatsapp_service.send_message.assert_called_once()
                        mock_ws_events.publish_patient_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_failure_handling(
        self, notification_service, sample_patient, sample_user
    ):
        """Test handling when WhatsApp succeeds but WebSocket fails."""
        doctor_id = uuid4()

        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = True
            mock_settings.WHATSAPP_CLINIC_NAME = "Test Clinic"
            mock_settings.WHATSAPP_CLINIC_SUPPORT_PHONE = "+5511888888888"

            with patch(
                "app.domain.patient.onboarding.notification_service.get_welcome_message"
            ) as mock_get_welcome:
                mock_get_welcome.return_value = "Welcome!"

                mock_message = Mock()
                notification_service.message_service.schedule_message.return_value = (
                    mock_message
                )

                with patch(
                    "app.domain.patient.onboarding.notification_service.asyncio.get_event_loop"
                ) as mock_get_loop:
                    mock_loop = AsyncMock()
                    mock_loop.run_in_executor = AsyncMock(
                        return_value=mock_message
                    )
                    mock_get_loop.return_value = mock_loop

                    with patch(
                        "app.services.websocket_events.websocket_events"
                    ) as mock_ws_events:
                        # Make WebSocket fail
                        mock_ws_events.publish_patient_event = AsyncMock(
                            side_effect=Exception("WebSocket error")
                        )

                        # Send welcome (should succeed)
                        welcome_result = (
                            await notification_service.send_welcome_message(
                                sample_patient, sample_user
                            )
                        )

                        # Publish event (should fail gracefully)
                        event_result = (
                            await notification_service.publish_patient_created_event(
                                sample_patient, doctor_id
                            )
                        )

                        # WhatsApp should succeed, WebSocket should fail gracefully
                        assert welcome_result is True
                        assert event_result is False


# ============================================================================
# Edge Cases and Error Scenarios
# ============================================================================


class TestNotificationServiceEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_send_message_with_none_user(
        self, notification_service, sample_patient
    ):
        """Test sending message with current_user=None."""
        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = True
            mock_settings.WHATSAPP_CLINIC_NAME = "Test Clinic"
            mock_settings.WHATSAPP_CLINIC_SUPPORT_PHONE = "+5511888888888"

            with patch(
                "app.domain.patient.onboarding.notification_service.get_welcome_message"
            ) as mock_get_welcome:
                mock_get_welcome.return_value = "Welcome!"

                mock_message = Mock()
                notification_service.message_service.schedule_message.return_value = (
                    mock_message
                )

                with patch(
                    "app.domain.patient.onboarding.notification_service.asyncio.get_event_loop"
                ) as mock_get_loop:
                    mock_loop = AsyncMock()
                    mock_loop.run_in_executor = AsyncMock(
                        return_value=mock_message
                    )
                    mock_get_loop.return_value = mock_loop

                    # Send with None user
                    result = await notification_service.send_welcome_message(
                        sample_patient, current_user=None
                    )

                    # Should handle None user gracefully
                    assert result is True

    @pytest.mark.asyncio
    async def test_multiple_concurrent_notifications(
        self, notification_service, sample_patient, sample_user
    ):
        """Test handling multiple concurrent notification requests."""
        import asyncio

        with patch(
            "app.domain.patient.onboarding.notification_service.settings"
        ) as mock_settings:
            mock_settings.WHATSAPP_ENABLE_ON_REGISTRATION = True
            mock_settings.WHATSAPP_ENABLE_WELCOME_MESSAGE = True
            mock_settings.WHATSAPP_CLINIC_NAME = "Test Clinic"
            mock_settings.WHATSAPP_CLINIC_SUPPORT_PHONE = "+5511888888888"

            with patch(
                "app.domain.patient.onboarding.notification_service.get_welcome_message"
            ) as mock_get_welcome:
                mock_get_welcome.return_value = "Welcome!"

                mock_message = Mock()
                notification_service.message_service.schedule_message.return_value = (
                    mock_message
                )

                with patch(
                    "app.domain.patient.onboarding.notification_service.asyncio.get_event_loop"
                ) as mock_get_loop:
                    mock_loop = AsyncMock()
                    mock_loop.run_in_executor = AsyncMock(
                        return_value=mock_message
                    )
                    mock_get_loop.return_value = mock_loop

                    # Send multiple concurrent messages
                    tasks = [
                        notification_service.send_welcome_message(
                            sample_patient, sample_user
                        )
                        for _ in range(3)
                    ]

                    results = await asyncio.gather(*tasks)

                    # All should succeed
                    assert all(results)
