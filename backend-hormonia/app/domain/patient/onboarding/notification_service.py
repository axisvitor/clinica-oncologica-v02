"""
NotificationService - Patient onboarding notification orchestration.

This service handles all notification delivery for patient onboarding:
- WhatsApp welcome messages
- WebSocket real-time events
- Notification status tracking

File: app/domain/patient/onboarding/notification_service.py
LOC: ~100
Responsibility: Notification delivery for onboarding events

ISSUE-005 PHASE 2:
- Extracted from PatientOnboardingService
- Follows Single Responsibility Principle (SRP)
- 100% dependency injection for testability
"""

from __future__ import annotations

# Standard library imports
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID

# Local application imports
from app.config import settings
from app.models.message import MessageType
from app.models.patient import Patient
from app.models.user import User
from app.schemas.websocket import WebSocketEventType
from app.templates.whatsapp import get_welcome_message

if TYPE_CHECKING:
    from app.domain.messaging.core import MessageService
    from app.services.unified_whatsapp_service import UnifiedWhatsAppService
    from app.services.websocket_events import WebSocketEventService


class NotificationService:
    """
    Service for patient onboarding notifications.

    SINGLE RESPONSIBILITY: Deliver onboarding notifications via WhatsApp and WebSocket.

    This service orchestrates notification delivery during patient onboarding,
    delegating to specialized messaging services for actual delivery.

    Attributes:
        message_service: Service for message scheduling and persistence.
        whatsapp_service: Service for WhatsApp message delivery.
        websocket_service: Optional WebSocket event broadcasting service.
        _logger: Service logger (private).
        _executor: Thread pool executor for sync operations.
    """

    def __init__(
        self,
        message_service: "MessageService",
        whatsapp_service: "UnifiedWhatsAppService",
        websocket_service: Optional["WebSocketEventService"] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """
        Initialize NotificationService with dependency injection.

        DEPENDENCY INJECTION PATTERN (ISSUE-005):
        All services are injected via constructor to:
        - Enable testability (mock dependencies)
        - Reduce coupling between components
        - Follow Dependency Inversion Principle

        Args:
            message_service: Service for message scheduling and persistence.
            whatsapp_service: Service for WhatsApp message delivery.
            websocket_service: Optional WebSocket event broadcasting service.
            executor: Optional ThreadPoolExecutor for sync operations.
        """
        self.message_service = message_service
        self.whatsapp_service = whatsapp_service
        self.websocket_service = websocket_service
        # Use centralized executor from app.core.executors
        self._executor = executor or get_notification_executor()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def send_welcome_message(
        self, patient: Patient, current_user: Optional[User] = None
    ) -> bool:
        """
        Send WhatsApp welcome message to newly registered patient.

        This method:
        1. Generates welcome message content
        2. Schedules message via MessageService
        3. Sends message via WhatsAppService
        4. Returns success status

        Args:
            patient: The newly created patient.
            current_user: The user who created the patient (for logging).

        Returns:
            True if message sent successfully, False otherwise.

        Raises:
            Exception: If message sending fails critically.
        """
        try:
            # Check if welcome messages are enabled
            if not settings.WHATSAPP_ENABLE_ON_REGISTRATION:
                self._logger.info(
                    "WhatsApp welcome messages disabled, skipping",
                    extra={"patient_id": str(patient.id)}
                )
                return False

            if not settings.WHATSAPP_ENABLE_WELCOME_MESSAGE:
                self._logger.info(
                    "Welcome messages disabled, skipping",
                    extra={"patient_id": str(patient.id)}
                )
                return False

            # Generate welcome message content
            welcome_text = get_welcome_message(
                patient_name=patient.name,
                clinic_name=settings.WHATSAPP_CLINIC_NAME,
                support_phone=settings.WHATSAPP_CLINIC_SUPPORT_PHONE,
            )

            # Schedule message for immediate sending
            loop = asyncio.get_event_loop()
            try:
                message = await loop.run_in_executor(
                    self._executor,
                    lambda: self.message_service.schedule_message(
                        patient_id=patient.id,
                        content=welcome_text,
                        scheduled_for=datetime.now(timezone.utc),
                        message_type=MessageType.TEXT,
                        message_metadata={
                            "patient_id": str(patient.id),
                            "patient_name": patient.name,
                            "message_type": "welcome",
                            "created_by": getattr(current_user, "email", None)
                            if current_user
                            else "system",
                            "treatment_type": patient.treatment_type,
                        },
                    ),
                )
            except Exception as e:
                self._logger.error("Failed to schedule welcome message in executor", exc_info=True)
                raise

            # Send message via WhatsApp
            try:
                success = await self.whatsapp_service.send_message(message)
            except Exception as e:
                self._logger.error("Failed to send WhatsApp message", exc_info=True)
                raise

            self._logger.info(
                f"Welcome message {'sent' if success else 'failed'}",
                extra={"patient_id": str(patient.id)}
            )
            return success

        except ImportError as e:
            self._logger.error("WhatsApp service not available", extra={"error": str(e)})
            return False
        except Exception as e:
            self._logger.error(
                "Error sending welcome message",
                exc_info=True,
                extra={"patient_id": str(patient.id), "exception_type": type(e).__name__}
            )
            return False

    async def publish_patient_created_event(
        self, patient: Patient, doctor_id: UUID, action: str = "created"
    ) -> bool:
        """
        Publish WebSocket event for patient creation.

        This method broadcasts a real-time event to connected clients
        notifying them that a new patient has been created.

        Args:
            patient: The newly created patient.
            doctor_id: Doctor ID for event routing.
            action: Action type (default: "created").

        Returns:
            True if event published successfully, False otherwise.
        """
        if not self.websocket_service:
            self._logger.debug("WebSocket service not configured, skipping event publication")
            return False

        try:
            # Import here to avoid circular dependency
            from app.services.websocket_events import websocket_events

            if not websocket_events:
                self._logger.warning("WebSocket events service not initialized")
                return False

            # Publish patient updated event
            # FIX: Pack all data into single dict to match method signature
            await websocket_events.publish_patient_event(
                event_type=WebSocketEventType.PATIENT_UPDATED,
                patient_id=patient.id,
                data={
                    "patient_name": patient.name,
                    "doctor_id": str(doctor_id) if doctor_id else None,
                    "action": action,
                    "treatment_type": patient.treatment_type,
                },
            )

            self._logger.info(
                "Published WebSocket event",
                extra={"patient_id": str(patient.id), "action": action}
            )
            return True

        except Exception as e:
            self._logger.warning("Failed to publish WebSocket event", extra={"error": str(e)})
            return False

    async def send_welcome_if_needed(
        self, patient: Patient, current_user: Optional[User] = None
    ) -> bool:
        """
        Send welcome message only if not already sent.

        This method checks if a welcome message has already been sent
        to the patient before attempting to send one.

        Args:
            patient: The patient to check.
            current_user: Current authenticated user.

        Returns:
            True if message sent or not needed, False if sending failed.
        """
        try:
            # Check if messages already exist for this patient
            from app.models.message import Message

            loop = asyncio.get_event_loop()
            # FIX: Filter specifically for welcome messages using message_metadata
            # instead of counting any TEXT message (which would incorrectly skip
            # welcome if patient received any other text message like quiz intro)
            message_count = await loop.run_in_executor(
                self._executor,
                lambda: (
                    self.message_service.db.query(Message)
                    .filter(
                        Message.patient_id == patient.id,
                        Message.type == MessageType.TEXT,
                        Message.message_metadata["message_type"].astext == "welcome",
                    )
                    .count()
                ),
            )

            if message_count > 0:
                self._logger.info(
                    "Welcome message already sent, skipping",
                    extra={"patient_id": str(patient.id)}
                )
                return True

            # Send welcome message
            return await self.send_welcome_message(patient, current_user)

        except Exception as e:
            self._logger.error(
                "Error checking/sending welcome message",
                exc_info=True,
                extra={"patient_id": str(patient.id)}
            )
            return False

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the notification service gracefully.

        Args:
            wait: Whether to wait for pending notifications to complete.
        """
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._logger.info(
                "NotificationService executor shutdown",
                extra={"wait": wait}
            )
