"""Delivery service for sending quiz links to patients."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.models.patient import Patient
from app.models.quiz import QuizSession, QuizTemplate
from app.domain.messaging.core import MessageFactory
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.schemas.monthly_quiz import DeliveryMethod
from sqlalchemy.orm import Session

import logging

logger = logging.getLogger(__name__)


class DeliveryService:
    """Handles delivery of quiz links to patients via various channels."""

    def __init__(self, db: Session):
        self.db = db

    async def send_quiz_link_notification(
        self,
        patient: Patient,
        template: QuizTemplate,
        session: QuizSession,
        link_url: str,
        delivery_method: DeliveryMethod,
        expiry_hours: int,
        custom_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send the monthly quiz link to the patient via WhatsApp with retries.

        Args:
            patient: Patient model
            template: Quiz template model
            session: Quiz session model
            link_url: Complete quiz link URL
            delivery_method: Delivery method (whatsapp, email, etc.)
            expiry_hours: Hours until link expires
            custom_message: Optional custom message

        Returns:
            Dictionary with delivery result:
                - sent: bool
                - message_id: str (if sent)
                - attempts: int

        Raises:
            Exception: If all retry attempts fail
        """
        max_retries = 3
        retry_delay = 2  # seconds
        last_error = None

        message_factory = MessageFactory(self.db)
        message = message_factory.create_monthly_quiz_link_message(
            patient_id=patient.id,
            patient_name=patient.name,
            link_url=link_url,
            quiz_session_id=str(session.id),
            expiry_hours=expiry_hours,
            delivery_method=delivery_method.value,
            custom_message=custom_message,
        )

        whatsapp_service = UnifiedWhatsAppService(
            db=self.db, messaging_mode=MessagingMode.HYBRID
        )

        for attempt in range(max_retries):
            try:
                sent = await whatsapp_service.send_message(message)

                if sent:
                    return {
                        "sent": True,
                        "message_id": str(message.id),
                        "attempts": attempt + 1,
                    }
                else:
                    # If send_message returns False without raising, treat as failure and retry
                    logger.warning(
                        f"WhatsApp send returned False (attempt {attempt + 1}/{max_retries})",
                        extra={"patient_id": str(patient.id)},
                    )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"Failed to send monthly quiz link (attempt {attempt + 1}/{max_retries}): {exc}",
                    extra={
                        "patient_id": str(patient.id),
                        "quiz_session_id": str(session.id),
                        "error": str(exc),
                    },
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff

        # If we get here, all retries failed
        error_msg = (
            str(last_error) if last_error else "Unknown error (send returned False)"
        )
        logger.error(
            "All retries failed for monthly quiz link delivery",
            extra={
                "patient_id": str(patient.id),
                "quiz_session_id": str(session.id),
                "delivery_method": delivery_method.value,
                "error": error_msg,
            },
        )
        raise Exception(f"Failed to send after {max_retries} attempts: {error_msg}")

    def record_delivery_attempt(
        self,
        session: QuizSession,
        delivery_method: DeliveryMethod,
        status: str,
        message_id: Optional[str] = None,
        error: Optional[str] = None,
        action: str = "send",
    ) -> None:
        """Record a delivery attempt in session metadata.

        Args:
            session: Quiz session model
            delivery_method: Method used for delivery
            status: Delivery status (sent, pending, failed)
            message_id: Message identifier if sent
            error: Error message if failed
            action: Action type (send, resend)
        """
        metadata = session.session_metadata or {}

        if "delivery_attempts" not in metadata:
            metadata["delivery_attempts"] = []

        attempt_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "delivery_method": delivery_method.value,
            "status": status,
            "message_id": message_id,
            "error": error,
        }

        metadata["delivery_attempts"].append(attempt_record)
        metadata["last_delivery_status"] = status
        metadata["last_delivery_method"] = delivery_method.value

        session.session_metadata = metadata
        # Note: Caller should commit
