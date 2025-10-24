"""
Message Service - Consolidated Message Management Core (QW-022).

This module consolidates core message functionality:
- Message CRUD operations (from message.py)
- Message factory and templates (from message_factory.py)
- Message scheduling (from message_scheduler.py)

Consolidation: 3 files → 1 file

Legacy Files:
    - app/services/message.py (MessageService)
    - app/services/message_factory.py (MessageFactory)
    - app/services/message_scheduler.py (MessageScheduler)
"""

from typing import List, Optional, Any, Dict, Callable, Tuple
from uuid import UUID
from datetime import datetime, timedelta, time
from dataclasses import dataclass
from enum import Enum
import logging
import pytz

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.models.message import (
    Message,
    MessageDirection,
    MessageType,
    MessageStatus,
    DeliveryStatus,
)
from app.models.patient import Patient
from app.models.quiz import QuizTemplate
from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.schemas.message import MessageCreate, MessageUpdate
from app.schemas.quiz import QuizQuestion
from app.utils.db_retry import with_db_retry
from app.exceptions import ValidationError, NotFoundError


logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================


class MessageTemplate(Enum):
    """Pre-defined message templates."""

    QUIZ_INTRODUCTION = "quiz_introduction"
    QUIZ_QUESTION = "quiz_question"
    QUIZ_COMPLETION = "quiz_completion"
    QUIZ_CLARIFICATION = "quiz_clarification"
    QUIZ_PAUSED = "quiz_paused"
    FLOW_MESSAGE = "flow_message"
    ALERT_MESSAGE = "alert_message"
    REMINDER = "reminder"
    FOLLOW_UP = "follow_up"
    MONTHLY_QUIZ_LINK_INVITATION = "monthly_quiz_link_invitation"
    MONTHLY_QUIZ_LINK_REMINDER = "monthly_quiz_link_reminder"
    MONTHLY_QUIZ_LINK_EXPIRED = "monthly_quiz_link_expired"
    MONTHLY_QUIZ_LINK_COMPLETED = "monthly_quiz_link_completed"


class SchedulingWindow(Enum):
    """Predefined scheduling windows for message delivery."""

    MORNING = "morning"  # 9:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 17:00
    EVENING = "evening"  # 17:00 - 20:00
    BUSINESS_HOURS = "business_hours"  # 9:00 - 18:00
    EXTENDED_HOURS = "extended_hours"  # 8:00 - 21:00


class MessageSchedulerConfig:
    """Configuration constants for MessageScheduler."""

    # Scheduling windows (start_time, end_time)
    SCHEDULING_WINDOWS = {
        SchedulingWindow.MORNING: (time(9, 0), time(12, 0)),
        SchedulingWindow.AFTERNOON: (time(12, 0), time(17, 0)),
        SchedulingWindow.EVENING: (time(17, 0), time(20, 0)),
        SchedulingWindow.BUSINESS_HOURS: (time(9, 0), time(18, 0)),
        SchedulingWindow.EXTENDED_HOURS: (time(8, 0), time(21, 0)),
    }

    # Message constraints
    MAX_MESSAGE_LENGTH = 4096  # WhatsApp message limit
    MIN_SCHEDULING_BUFFER_MINUTES = 15  # Minimum time before sending
    FALLBACK_DELAY_MINUTES = 30  # Fallback delay when calculation fails

    # Default timezone
    DEFAULT_TIMEZONE = "America/Sao_Paulo"

    # Retry configuration
    MAX_TASK_RETRIES = 3
    RETRY_DELAY_SECONDS = 60


# ============================================================================
# Exceptions
# ============================================================================


class MessageSchedulingError(Exception):
    """Base exception for message scheduling errors."""

    pass


class TimezoneError(MessageSchedulingError):
    """Exception for timezone-related errors."""

    pass


class TaskSchedulingError(MessageSchedulingError):
    """Exception for task scheduling errors."""

    pass


# ============================================================================
# MessageService - CRUD Operations
# ============================================================================


class MessageService:
    """
    Service layer for message CRUD operations.

    Consolidated from: app/services/message.py
    """

    def __init__(self, db: Session):
        """
        Initialize MessageService.

        Args:
            db: Database session
        """
        self.db = db
        self.repository = MessageRepository(db)

    @with_db_retry(max_retries=3)
    def create_message(self, message_data: MessageCreate) -> Message:
        """
        Create a new message.

        Args:
            message_data: Message creation data

        Returns:
            Created Message object
        """
        message_dict = message_data.dict()
        return self.repository.create(message_dict)

    @with_db_retry(max_retries=3)
    def get_message(self, message_id: UUID) -> Optional[Message]:
        """
        Get message by ID.

        Args:
            message_id: Message UUID

        Returns:
            Message object or None
        """
        return self.repository.get_by_id(message_id)

    @with_db_retry(max_retries=3)
    def get_message_by_whatsapp_id(self, whatsapp_id: str) -> Optional[Message]:
        """
        Get message by WhatsApp ID.

        Args:
            whatsapp_id: WhatsApp message ID

        Returns:
            Message object or None
        """
        return self.repository.get_by_whatsapp_id(whatsapp_id)

    @with_db_retry(max_retries=3)
    def update_message(
        self, message_id: UUID, message_data: MessageUpdate
    ) -> Optional[Message]:
        """
        Update message information.

        Args:
            message_id: Message UUID
            message_data: Update data

        Returns:
            Updated Message object or None
        """
        message = self.repository.get_by_id(message_id)
        if not message:
            return None

        update_data = message_data.dict(exclude_unset=True)
        return self.repository.update(message, update_data)

    @with_db_retry(max_retries=3)
    def get_patient_messages(
        self, patient_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Message]:
        """
        Get all messages for a patient.

        Args:
            patient_id: Patient UUID
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of Message objects
        """
        return self.repository.get_by_patient(patient_id, skip, limit)

    @with_db_retry(max_retries=3)
    def get_conversation_history(
        self, patient_id: UUID, skip: int = 0, limit: int = 50
    ) -> List[Message]:
        """
        Get conversation history for a patient.

        Args:
            patient_id: Patient UUID
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of Message objects
        """
        return self.repository.get_conversation_history(patient_id, skip, limit)

    @with_db_retry(max_retries=3)
    def get_pending_messages(
        self, skip: int = 0, limit: int = 100, patient_id: Optional[UUID] = None
    ) -> List[Message]:
        """
        Get pending messages for sending.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records
            patient_id: Optional patient filter

        Returns:
            List of pending Message objects
        """
        return self.repository.get_pending_messages(skip, limit, patient_id)

    @with_db_retry(max_retries=3)
    def get_scheduled_messages(
        self, before_time: datetime, skip: int = 0, limit: int = 100
    ) -> List[Message]:
        """
        Get messages scheduled before a specific time.

        Args:
            before_time: Time threshold
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of scheduled Message objects
        """
        return self.repository.get_scheduled_messages(before_time, skip, limit)

    @with_db_retry(max_retries=3)
    def schedule_message(
        self,
        patient_id: UUID,
        content: str,
        scheduled_for: datetime,
        message_type: MessageType = MessageType.TEXT,
        message_metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Schedule a message for later delivery.

        Args:
            patient_id: Patient UUID
            content: Message content
            scheduled_for: Scheduled delivery time
            message_type: Type of message
            message_metadata: Optional metadata

        Returns:
            Scheduled Message object
        """
        message_data = {
            "patient_id": patient_id,
            "direction": MessageDirection.OUTBOUND,
            "type": message_type,
            "content": content,
            "scheduled_for": scheduled_for,
            "message_metadata": message_metadata or {},
            "status": MessageStatus.PENDING,
        }
        return self.repository.create(message_data)

    @with_db_retry(max_retries=3)
    def mark_as_sent(
        self, message_id: UUID, whatsapp_id: Optional[str] = None
    ) -> Optional[Message]:
        """
        Mark message as sent.

        Args:
            message_id: Message UUID
            whatsapp_id: Optional WhatsApp message ID

        Returns:
            Updated Message object or None
        """
        message = self.repository.get_by_id(message_id)
        if not message:
            return None

        update_data = {"status": MessageStatus.SENT, "sent_at": datetime.utcnow()}
        if whatsapp_id:
            update_data["whatsapp_id"] = whatsapp_id

        return self.repository.update(message, update_data)

    @with_db_retry(max_retries=3)
    def mark_as_failed(self, message_id: UUID, error_message: str) -> Optional[Message]:
        """
        Mark message as failed.

        Args:
            message_id: Message UUID
            error_message: Error description

        Returns:
            Updated Message object or None
        """
        message = self.repository.get_by_id(message_id)
        if not message:
            return None

        update_data = {
            "status": MessageStatus.FAILED,
            "delivery_status": DeliveryStatus.FAILED,
            "message_metadata": {
                **message.message_metadata,
                "error": error_message,
                "failed_at": datetime.utcnow().isoformat(),
            },
        }

        return self.repository.update(message, update_data)


# ============================================================================
# MessageFactory - Template-based Message Creation
# ============================================================================


class MessageFactory:
    """
    Factory class for creating standardized messages.
    Eliminates code duplication across services.

    Consolidated from: app/services/message_factory.py
    """

    def __init__(self, db: Session):
        """
        Initialize MessageFactory.

        Args:
            db: Database session
        """
        self.db = db

        # Message templates for monthly quiz links
        self.monthly_quiz_templates = {
            "invitation": (
                "Olá {patient_name}! 😊\n\n"
                "Chegou o momento do seu questionário mensal de bem-estar!\n\n"
                "Acesse pelo link: {link}\n\n"
                "➡️ Válido por {expiry_hours} horas\n\n"
                "Sua participação é muito importante para acompanharmos seu progresso."
            ),
            "reminder": (
                "Oi {patient_name}! 💬\n\n"
                "Lembrete: você ainda não respondeu ao questionário mensal.\n\n"
                "Por favor, acesse: {link}\n\n"
                "⏳ Expira em {hours_remaining} horas\n\n"
                "Contamos com você!"
            ),
            "expired": (
                "Olá {patient_name}! ⏰\n\n"
                "O link do seu questionário expirou.\n\n"
                "Um novo link será enviado em breve. Fique atenta(o)!"
            ),
            "completed": (
                "Obrigada, {patient_name}! 🙌\n\n"
                "Recebemos suas respostas do questionário mensal.\n\n"
                "Nossa equipe médica irá analisá-las em breve.\n\n"
                "Continue cuidando bem da sua saúde! 🌷"
            ),
        }

    def create_outbound_message(
        self,
        patient_id: UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        template_type: Optional[MessageTemplate] = None,
        scheduled_for: Optional[datetime] = None,
    ) -> Message:
        """
        Create an outbound message.

        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Type of message
            metadata: Optional metadata
            template_type: Optional template type
            scheduled_for: Optional scheduled time

        Returns:
            Created Message object
        """
        message_data = {
            "patient_id": patient_id,
            "direction": MessageDirection.OUTBOUND,
            "type": message_type,
            "content": content,
            "message_metadata": metadata or {},
            "status": MessageStatus.PENDING
            if not scheduled_for
            else MessageStatus.SCHEDULED,
        }

        if template_type:
            message_data["message_metadata"]["template_type"] = template_type.value

        if scheduled_for:
            message_data["scheduled_for"] = scheduled_for

        message = Message(**message_data)
        return self._save_message(message)

    def create_quiz_question_message(
        self,
        patient_id: UUID,
        question: QuizQuestion,
        quiz_session_id: str,
        question_number: int,
        total_questions: int,
    ) -> Message:
        """
        Create quiz question message.

        Args:
            patient_id: Patient UUID
            question: Quiz question object
            quiz_session_id: Quiz session ID
            question_number: Current question number
            total_questions: Total number of questions

        Returns:
            Created Message object
        """
        content = (
            f"Questão {question_number}/{total_questions}:\n\n{question.question_text}"
        )

        if question.options:
            content += "\n\nOpções:"
            for idx, option in enumerate(question.options, 1):
                content += f"\n{idx}. {option}"

        metadata = {
            "quiz_session_id": quiz_session_id,
            "question_id": str(question.id) if hasattr(question, "id") else None,
            "question_number": question_number,
            "total_questions": total_questions,
            "template_type": MessageTemplate.QUIZ_QUESTION.value,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.QUIZ_QUESTION,
            metadata=metadata,
            template_type=MessageTemplate.QUIZ_QUESTION,
        )

    def create_monthly_quiz_invitation_message(
        self,
        patient_id: UUID,
        patient_name: str,
        link: str,
        expiry_hours: int,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz link invitation message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            link: Quiz link
            expiry_hours: Link expiry in hours
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates["invitation"].format(
            patient_name=patient_name, link=link, expiry_hours=expiry_hours
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "quiz_link": link,
            "expiry_hours": expiry_hours,
            "message_type": "monthly_quiz_invitation",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_LINK,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION,
        )

    def create_monthly_quiz_reminder_message(
        self,
        patient_id: UUID,
        patient_name: str,
        link: str,
        hours_remaining: int,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz reminder message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            link: Quiz link
            hours_remaining: Hours until expiry
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates["reminder"].format(
            patient_name=patient_name, link=link, hours_remaining=hours_remaining
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "quiz_link": link,
            "hours_remaining": hours_remaining,
            "message_type": "monthly_quiz_reminder",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_REMINDER,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER,
        )

    def create_monthly_quiz_expired_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz link expired message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates["expired"].format(
            patient_name=patient_name
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_expired",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_EXPIRED,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED,
        )

    def create_monthly_quiz_completed_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp",
    ) -> Message:
        """
        Create monthly quiz completion confirmation message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates["completed"].format(
            patient_name=patient_name
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_completed",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED.value,
            "delivery_method": delivery_method,
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_COMPLETED,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED,
        )

    def create_multi_channel_message(
        self,
        patient_id: UUID,
        content: str,
        channels: List[str],
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Message]:
        """
        Create message for multiple delivery channels.

        Args:
            patient_id: Patient UUID
            content: Message content
            channels: List of delivery channels (whatsapp, email, sms)
            message_type: Type of message
            metadata: Optional metadata

        Returns:
            List of created Message objects (one per channel)
        """
        messages = []

        for channel in channels:
            channel_metadata = metadata.copy() if metadata else {}
            channel_metadata["delivery_method"] = channel

            # Adapt content for channel if needed
            adapted_content = content
            if channel == "sms":
                # Truncate for SMS (160 chars)
                adapted_content = (
                    content[:157] + "..." if len(content) > 160 else content
                )
            elif channel == "email":
                # Could wrap in HTML template for email
                channel_metadata["email_format"] = "html"

            message = self.create_outbound_message(
                patient_id=patient_id,
                content=adapted_content,
                message_type=message_type,
                metadata=channel_metadata,
            )
            messages.append(message)

        return messages

    def _save_message(self, message: Message) -> Message:
        """
        Save message to database.

        Args:
            message: Message to save

        Returns:
            Saved Message object
        """
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message


# ============================================================================
# MessageScheduler - Time-based Message Scheduling
# ============================================================================


class MessageScheduler:
    """
    Service for scheduling and managing time-based message delivery.
    Handles patient timezone preferences and appropriate sending hours.

    Consolidated from: app/services/message_scheduler.py
    """

    def __init__(self, db: Session, config: Optional[MessageSchedulerConfig] = None):
        """
        Initialize MessageScheduler.

        Args:
            db: Database session
            config: Optional configuration
        """
        self.db = db
        self.config = config or MessageSchedulerConfig()

        if db:
            self.patient_repo = PatientRepository(db)
            self.message_repo = MessageRepository(db)
            self.message_service = MessageService(db)

        # Use configuration for scheduling windows
        self.scheduling_windows = self.config.SCHEDULING_WINDOWS

    def _get_patient_timezone(self, patient: Patient) -> str:
        """
        Get patient timezone from metadata or default to Brazil timezone.

        Args:
            patient: Patient object

        Returns:
            Timezone string
        """
        if patient.patient_metadata and "timezone" in patient.patient_metadata:
            return patient.patient_metadata["timezone"]
        return self.config.DEFAULT_TIMEZONE

    def _get_scheduling_window_times(
        self, window: SchedulingWindow
    ) -> Tuple[time, time]:
        """
        Get start and end times for a scheduling window.

        Args:
            window: Scheduling window enum

        Returns:
            Tuple of (start_time, end_time)
        """
        return self.scheduling_windows.get(
            window, self.scheduling_windows[SchedulingWindow.BUSINESS_HOURS]
        )

    def calculate_next_send_time(
        self,
        patient: Patient,
        window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS,
        min_delay_minutes: Optional[int] = None,
    ) -> datetime:
        """
        Calculate next appropriate send time for a patient.

        Args:
            patient: Patient object
            window: Desired scheduling window
            min_delay_minutes: Minimum delay in minutes

        Returns:
            Next send datetime (UTC)
        """
        try:
            # Get patient timezone
            patient_tz_str = self._get_patient_timezone(patient)
            patient_tz = pytz.timezone(patient_tz_str)

            # Get current time in patient timezone
            now_utc = datetime.utcnow()
            now_patient = now_utc.replace(tzinfo=pytz.utc).astimezone(patient_tz)

            # Get window times
            start_time, end_time = self._get_scheduling_window_times(window)

            # Calculate minimum send time
            min_delay = min_delay_minutes or self.config.MIN_SCHEDULING_BUFFER_MINUTES
            min_send_time = now_patient + timedelta(minutes=min_delay)

            # If within window and after minimum delay, send soon
            if start_time <= min_send_time.time() <= end_time:
                send_time_patient = min_send_time
            else:
                # Schedule for next window
                if min_send_time.time() < start_time:
                    # Same day, at window start
                    send_time_patient = min_send_time.replace(
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0,
                        microsecond=0,
                    )
                else:
                    # Next day, at window start
                    next_day = min_send_time + timedelta(days=1)
                    send_time_patient = next_day.replace(
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0,
                        microsecond=0,
                    )

            # Convert back to UTC
            send_time_utc = send_time_patient.astimezone(pytz.utc).replace(tzinfo=None)

            logger.info(
                f"Calculated send time for patient {patient.id}: "
                f"{send_time_utc} UTC ({send_time_patient} {patient_tz_str})"
            )

            return send_time_utc

        except Exception as e:
            logger.error(f"Error calculating send time: {e}", exc_info=True)
            # Fallback: send in 30 minutes
            fallback_time = datetime.utcnow() + timedelta(
                minutes=self.config.FALLBACK_DELAY_MINUTES
            )
            logger.warning(f"Using fallback send time: {fallback_time}")
            return fallback_time

    def schedule_message_for_patient(
        self,
        patient_id: UUID,
        content: str,
        window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        min_delay_minutes: Optional[int] = None,
    ) -> Message:
        """
        Schedule a message for a patient in appropriate time window.

        Args:
            patient_id: Patient UUID
            content: Message content
            window: Desired scheduling window
            message_type: Type of message
            metadata: Optional metadata
            min_delay_minutes: Minimum delay in minutes

        Returns:
            Scheduled Message object

        Raises:
            NotFoundError: If patient not found
        """
        # Get patient
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        # Calculate send time
        scheduled_for = self.calculate_next_send_time(
            patient, window, min_delay_minutes
        )

        # Create scheduled message
        return self.message_service.schedule_message(
            patient_id=patient_id,
            content=content,
            scheduled_for=scheduled_for,
            message_type=message_type,
            message_metadata=metadata,
        )

    def get_due_messages(self, limit: int = 100) -> List[Message]:
        """
        Get messages that are due to be sent.

        Args:
            limit: Maximum number of messages

        Returns:
            List of due Message objects
        """
        now = datetime.utcnow()
        return self.message_service.get_scheduled_messages(now, limit=limit)

    def reschedule_message(
        self, message_id: UUID, new_time: datetime
    ) -> Optional[Message]:
        """
        Reschedule an existing message.

        Args:
            message_id: Message UUID
            new_time: New scheduled time

        Returns:
            Updated Message object or None
        """
        message = self.message_service.get_message(message_id)
        if not message:
            return None

        if message.status not in [MessageStatus.SCHEDULED, MessageStatus.PENDING]:
            logger.warning(
                f"Cannot reschedule message {message_id} with status {message.status}"
            )
            return None

        message.scheduled_for = new_time
        message.status = MessageStatus.SCHEDULED

        self.db.commit()
        self.db.refresh(message)

        return message


# ============================================================================
# Factory Functions
# ============================================================================


def get_message_service(db: Session) -> MessageService:
    """Get MessageService instance."""
    return MessageService(db)


def get_message_factory(db: Session) -> MessageFactory:
    """Get MessageFactory instance."""
    return MessageFactory(db)


def get_message_scheduler(
    db: Session, config: Optional[MessageSchedulerConfig] = None
) -> MessageScheduler:
    """Get MessageScheduler instance."""
    return MessageScheduler(db, config)
