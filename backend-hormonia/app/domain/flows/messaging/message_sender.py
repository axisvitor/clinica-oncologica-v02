"""
Message Sending Module - Message Delivery and Scheduling

Handles message scheduling and delivery through WhatsApp service.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.domain.messaging.scheduling import MessageScheduler
from app.resilience.circuit_breaker.breaker import CircuitBreaker
from app.utils.date_helpers import get_next_scheduled_time


logger = logging.getLogger(__name__)


class MessageSender:
    """
    Manages message delivery and scheduling.

    Responsibilities:
    - Schedule message delivery
    - Calculate optimal send times
    - Create message records with metadata
    - Handle circuit breaker for WhatsApp service
    """

    def __init__(
        self,
        db: Session,
        message_scheduler: MessageScheduler,
        whatsapp_circuit_breaker: CircuitBreaker,
    ):
        """
        Initialize MessageSender.

        Args:
            db: Database session
            message_scheduler: Message scheduling service
            whatsapp_circuit_breaker: Circuit breaker for WhatsApp service
        """
        self.db = db
        self.message_scheduler = message_scheduler
        self.whatsapp_circuit_breaker = whatsapp_circuit_breaker

        logger.info("MessageSender initialized")

    async def schedule_flow_message(
        self,
        patient_id: UUID,
        patient: Patient,
        flow_state_id: UUID,
        flow_type: str,
        current_day: int,
        operation: str,
        message_template_intent: str,
        message_template_day: int,
        personalized_content: str,
    ) -> Dict[str, Any]:
        """
        Schedule message delivery with WhatsApp service using circuit breaker.

        Args:
            patient_id: Patient UUID
            patient: Patient object
            flow_state_id: Flow state UUID
            flow_type: Flow type identifier
            current_day: Current treatment day
            operation: Operation type
            message_template_intent: Template intent
            message_template_day: Template day
            personalized_content: Personalized message content

        Returns:
            Scheduling result dictionary
        """
        try:
            # Create message record
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=personalized_content,
                status=MessageStatus.PENDING,
                message_metadata={
                    "flow_context": {
                        "flow_state_id": str(flow_state_id),
                        "flow_type": flow_type,
                        "current_day": current_day,
                        "template_intent": message_template_intent,
                        "operation": operation,
                    },
                    "template_data": {
                        "intent": message_template_intent,
                        "day": message_template_day,
                        "ai_generated": True,
                    },
                },
            )

            self.db.add(message)
            self.db.flush()  # Get ID without committing

            # Calculate send time
            send_time = self.calculate_optimal_send_time(patient, current_day)

            # Schedule message with circuit breaker protection
            async def schedule_call():
                return await self.message_scheduler.schedule_message(
                    message_id=message.id, send_time=send_time, priority="normal"
                )

            scheduled = await self.whatsapp_circuit_breaker.call(schedule_call)

            if scheduled:
                self.db.commit()
                self.db.refresh(message)

                logger.info(
                    f"Message scheduled for patient {patient_id} at {send_time}"
                )

                return {
                    "success": True,
                    "message_id": message.id,
                    "scheduled_for": send_time.isoformat(),
                    "send_time": send_time,
                }
            else:
                self.db.rollback()
                return {"success": False, "error": "Message scheduling failed"}

        except Exception as e:
            logger.error(f"Error scheduling flow message: {e}", exc_info=True)
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def calculate_optimal_send_time(
        self, patient: Patient, current_day: int
    ) -> datetime:
        """
        Calculate optimal send time for patient message.

        Args:
            patient: Patient object
            current_day: Current treatment day

        Returns:
            Optimal send time as datetime
        """
        try:
            # Get patient preferences
            preferred_hour = getattr(patient, "preferred_message_hour", 10)
            timezone = getattr(patient, "timezone", "America/Sao_Paulo")

            # Calculate send time for today or next business day
            now = datetime.now(timezone.utc)
            send_time = now.replace(
                hour=preferred_hour, minute=0, second=0, microsecond=0
            )

            # If time has passed, schedule for next business day
            if send_time <= now:
                send_time = get_next_scheduled_time("daily", send_time, timezone)

            # Add randomization to avoid system overload
            random_minutes = random.randint(-15, 15)
            send_time += timedelta(minutes=random_minutes)

            return send_time

        except Exception as e:
            logger.warning(f"Error calculating send time: {e}, using default")
            return datetime.now(timezone.utc) + timedelta(hours=1)
