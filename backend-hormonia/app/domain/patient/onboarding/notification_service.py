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
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from app.models.patient import Patient
from app.models.user import User
from app.models.message import MessageType
from app.schemas.websocket import WebSocketEventType
from app.templates.whatsapp import get_welcome_message
from app.config import settings
import logging

if TYPE_CHECKING:
    from app.domain.messaging.core import MessageService
    from app.services.unified_whatsapp_service import UnifiedWhatsAppService
    from app.services.websocket_events import WebSocketEventService

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for patient onboarding notifications.

    SINGLE RESPONSIBILITY: Deliver onboarding notifications via WhatsApp and WebSocket.

    This service orchestrates notification delivery during patient onboarding,
    delegating to specialized messaging services for actual delivery.
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
            message_service: Service for message scheduling and persistence
            whatsapp_service: Service for WhatsApp message delivery
            websocket_service: Optional WebSocket event broadcasting service
            executor: Optional ThreadPoolExecutor for sync operations
        """
        self.message_service = message_service
        self.whatsapp_service = whatsapp_service
        self.websocket_service = websocket_service
        self._executor = executor or ThreadPoolExecutor(
            max_workers=5, thread_name_prefix="notification_sync"
        )

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
            patient: The newly created patient
            current_user: The user who created the patient (for logging)

        Returns:
            True if message sent successfully, False otherwise

        Raises:
            Exception: If message sending fails critically
        """
        try:
            # Check if welcome messages are enabled
            if not settings.ENABLE_WHATSAPP_ON_REGISTRATION:
                logger.info(
                    f"WhatsApp welcome messages disabled, skipping for patient {patient.id}"
                )
                return False

            if not settings.WHATSAPP_WELCOME_MESSAGE_ENABLED:
                logger.info(
                    f"Welcome messages disabled, skipping for patient {patient.id}"
                )
                return False

            # Generate welcome message content
            welcome_text = get_welcome_message(
                patient_name=patient.name,
                clinic_name=settings.CLINIC_NAME,
                support_phone=settings.CLINIC_SUPPORT_PHONE,
            )

            # Schedule message for immediate sending
            loop = asyncio.get_event_loop()
            try:
                message = await loop.run_in_executor(
                    self._executor,
                    lambda: self.message_service.schedule_message(
                        patient_id=patient.id,
                        content=welcome_text,
                        scheduled_for=datetime.utcnow(),
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
                logger.error(
                    f"Failed to schedule welcome message in executor: {e}",
                    exc_info=True,
                )
                raise

            # Send message via WhatsApp
            try:
                success = await self.whatsapp_service.send_message(message)
            except Exception as e:
                logger.error(
                    f"Failed to send WhatsApp message: {e}", exc_info=True
                )
                raise

            logger.info(
                f"Welcome message {'sent' if success else 'failed'} to patient {patient.id} "
                f"({patient.name}): phone={patient.phone}"
            )
            return success

        except ImportError as e:
            logger.error(f"WhatsApp service not available: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Error sending welcome message to {patient.phone}: {e}",
                exc_info=True,
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
            patient: The newly created patient
            doctor_id: Doctor ID for event routing
            action: Action type (default: "created")

        Returns:
            True if event published successfully, False otherwise
        """
        if not self.websocket_service:
            logger.debug("WebSocket service not configured, skipping event publication")
            return False

        try:
            # Import here to avoid circular dependency
            from app.services.websocket_events import websocket_events

            if not websocket_events:
                logger.warning("WebSocket events service not initialized")
                return False

            # Publish patient updated event
            await websocket_events.publish_patient_event(
                event_type=WebSocketEventType.PATIENT_UPDATED,
                patient_id=patient.id,
                patient_name=patient.name,
                doctor_id=doctor_id,
                changes={"action": action},
                metadata={"treatment_type": patient.treatment_type},
            )

            logger.info(
                f"Published WebSocket event for patient {patient.id} ({action})"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to publish WebSocket event: {e}")
            return False

    async def send_welcome_if_needed(
        self, patient: Patient, current_user: Optional[User] = None
    ) -> bool:
        """
        Send welcome message only if not already sent.

        This method checks if a welcome message has already been sent
        to the patient before attempting to send one.

        Args:
            patient: The patient to check
            current_user: Current authenticated user

        Returns:
            True if message sent or not needed, False if sending failed
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
                        Message.message_type == MessageType.TEXT,
                        Message.message_metadata['message_type'].astext == 'welcome',
                    )
                    .count()
                ),
            )

            if message_count > 0:
                logger.info(
                    f"Welcome message already sent to patient {patient.id}, skipping"
                )
                return True

            # Send welcome message
            return await self.send_welcome_message(patient, current_user)

        except Exception as e:
            logger.error(
                f"Error checking/sending welcome message for patient {patient.id}: {e}",
                exc_info=True,
            )
            return False

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the notification service gracefully.

        Args:
            wait: Whether to wait for pending notifications to complete
        """
        if self._executor:
            self._executor.shutdown(wait=wait)
            logger.info(f"NotificationService executor shutdown (wait={wait})")
