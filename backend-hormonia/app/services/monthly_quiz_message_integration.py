"""
Monthly Quiz Message Integration Service

Integrates MonthlyQuizService with MessageFactory for seamless link delivery.
Updated to use UnifiedWhatsAppService for improved reliability and performance.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone


from app.domain.messaging.core import MessageFactory, MessageTemplate
from app.services.quiz.quiz_service import MonthlyQuizService
from app.domain.messaging.delivery import MessageSender  # For backward compatibility
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.schemas.monthly_quiz import MonthlyQuizLinkCreate, DeliveryMethod
from app.models.patient import Patient
from app.exceptions import NotFoundError


class MonthlyQuizMessageIntegration:
    """
    Integration service for monthly quiz link generation and delivery.
    Coordinates MonthlyQuizService with MessageFactory using UnifiedWhatsAppService.
    """

    def __init__(self, db: Any, use_unified_service: bool = True):
        self.db = db
        self.monthly_quiz_service = MonthlyQuizService(db)
        self.message_factory = MessageFactory(db)

        # Use unified service by default for better reliability
        if use_unified_service:
            self.message_sender = UnifiedWhatsAppService(
                db=db,
                messaging_mode=MessagingMode.HYBRID,  # Hybrid mode for quiz messages
            )
        else:
            # Fallback to legacy MessageSender for backward compatibility
            self.message_sender = MessageSender(db)

    async def send_quiz_link(
        self,
        patient_id: UUID,
        quiz_template_id: UUID,
        delivery_method: DeliveryMethod = DeliveryMethod.WHATSAPP,
        expiry_hours: int = 72,
        custom_message: Optional[str] = None,
        send_immediately: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate quiz link and send invitation message.

        Args:
            patient_id: Patient UUID
            quiz_template_id: Quiz template UUID
            delivery_method: Delivery channel
            expiry_hours: Link expiry in hours
            custom_message: Optional custom message
            send_immediately: Whether to send immediately or schedule

        Returns:
            Dictionary with link info and message status
        """
        # Get patient info
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise NotFoundError(f"Patient with ID {patient_id} not found")

        # Create quiz link
        link_data = MonthlyQuizLinkCreate(
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            delivery_method=delivery_method,
            expiry_hours=expiry_hours,
            custom_message=custom_message,
            send_immediately=False,  # Integration handles delivery manually
        )

        quiz_link = await self.monthly_quiz_service.create_quiz_link(link_data)

        # Create invitation message
        message = self.message_factory.create_monthly_quiz_link_message(
            patient_id=patient_id,
            patient_name=patient.name,
            link_url=quiz_link.link_url,
            quiz_session_id=str(quiz_link.id),
            expiry_hours=expiry_hours,
            delivery_method=delivery_method.value,
            custom_message=custom_message,
        )

        # Send message with quiz-specific context
        send_result = None
        max_retries = 3
        retry_delay = 2

        if send_immediately:
            # Add quiz-specific context for unified service
            quiz_context = {
                "message_type": "quiz_link",
                "quiz_session_id": str(quiz_link.id),
                "priority": "high",  # Quiz links are high priority
                "retry_policy": "quiz_link",
            }

            for attempt in range(max_retries):
                try:
                    if hasattr(self.message_sender, "send_flow_message"):
                        # Use flow message method if available (UnifiedWhatsAppService or MessageSender)
                        send_result = await self.message_sender.send_flow_message(
                            message, quiz_context
                        )
                    else:
                        # Fallback to regular send_message
                        send_result = await self.message_sender.send_message(message)

                    if send_result:
                        break

                    # If returned False, retry
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (attempt + 1))

                except Exception as e:
                    # FIX: Replace print() with proper logger for production visibility
                    import logging
                    _logger = logging.getLogger(__name__)

                    if attempt == max_retries - 1:
                        # Log error on final attempt but don't crash the whole flow,
                        # just return the result as is (likely None or False)
                        _logger.error(
                            f"Failed to send quiz link after {max_retries} attempts: {e}",
                            exc_info=True,
                            extra={
                                "patient_id": str(patient_id),
                                "quiz_session_id": str(quiz_link.id),
                                "delivery_method": delivery_method.value,
                            }
                        )
                    else:
                        _logger.warning(
                            f"Quiz link send attempt {attempt + 1}/{max_retries} failed: {e}, retrying..."
                        )
                        await asyncio.sleep(retry_delay * (attempt + 1))

        return {
            "quiz_session_id": str(quiz_link.id),
            "link_url": quiz_link.link_url,
            "token": quiz_link.token,
            "message_id": str(message.id),
            "message_sent": send_result,
            "expires_at": quiz_link.expires_at.isoformat(),
            "delivery_method": delivery_method.value,
        }

    def send_quiz_link_message(
        self,
        patient_id: UUID,
        link_url: str,
        custom_message: Optional[str] = None,
        delivery_method: str = DeliveryMethod.WHATSAPP.value,
    ) -> Dict[str, Any]:
        """Send a quiz link message using the configured messaging service."""
        try:
            try:
                delivery_enum = DeliveryMethod(delivery_method)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Unsupported delivery method: {delivery_method}",
                }

            if delivery_enum is not DeliveryMethod.WHATSAPP:
                return {
                    "success": False,
                    "error": f"Delivery method {delivery_enum.value} not supported",
                }

            patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                raise NotFoundError(f"Patient with ID {patient_id} not found")

            if custom_message:
                message_text = custom_message
            else:
                message_text = f"Seu link do quiz mensal: {link_url}"

            metadata = {
                "delivery_method": delivery_enum.value,
                "message_type": "monthly_quiz_link",
                "link_url": link_url,
            }

            message = self.message_factory.create_outbound_message(
                patient_id=patient_id,
                content=message_text,
                metadata=metadata,
                template_type=MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER,
            )

            success = asyncio.run(self.message_sender.send_message(message))
            return {"success": bool(success), "message_id": str(message.id)}

        except NotFoundError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def send_quiz_reminder(
        self, quiz_session_id: UUID, hours_before_expiry: int = 24
    ) -> Dict[str, Any]:
        """
        Send reminder message for pending quiz.

        Args:
            quiz_session_id: Quiz session UUID
            hours_before_expiry: Hours before expiry to send reminder

        Returns:
            Dictionary with reminder status
        """
        # Get quiz link status
        quiz_link = await self.monthly_quiz_service.get_quiz_link_status(
            quiz_session_id
        )

        # Check if reminder is needed
        if quiz_link.status.value != "active":
            return {
                "reminder_sent": False,
                "reason": f"Quiz link status is {quiz_link.status.value}",
            }

        # Calculate hours remaining
        hours_remaining = int(
            (quiz_link.expires_at - datetime.now(timezone.utc)).total_seconds() / 3600
        )

        if hours_remaining > hours_before_expiry:
            return {
                "reminder_sent": False,
                "reason": f"Quiz link has {hours_remaining} hours remaining",
            }

        # Get patient
        patient = (
            self.db.query(Patient).filter(Patient.id == quiz_link.patient_id).first()
        )
        if not patient:
            raise NotFoundError(f"Patient with ID {quiz_link.patient_id} not found")

        # Regenerate link to get valid token and URL
        try:
            link_data = await self.monthly_quiz_service.regenerate_link(quiz_session_id)
            link_url = link_data.link_url
            # Recalculate hours remaining with new expiry time
            hours_remaining = int(
                (link_data.expires_at - datetime.now(timezone.utc)).total_seconds() / 3600
            )
        except Exception as e:
            # If regeneration fails, return error
            return {
                "reminder_sent": False,
                "reason": f"Failed to regenerate link: {str(e)}",
            }

        # Create reminder message
        message = self.message_factory.create_monthly_quiz_reminder_message(
            patient_id=quiz_link.patient_id,
            patient_name=patient.name,
            link_url=link_url,
            quiz_session_id=str(quiz_session_id),
            hours_remaining=hours_remaining,
            delivery_method=quiz_link.delivery_method.value,
        )

        # Send message
        send_result = await self.message_sender.send_message(message)

        return {
            "reminder_sent": send_result,
            "message_id": str(message.id),
            "hours_remaining": hours_remaining,
        }

    async def send_expiration_notice(self, quiz_session_id: UUID) -> Dict[str, Any]:
        """
        Send expiration notice for expired quiz link.

        Args:
            quiz_session_id: Quiz session UUID

        Returns:
            Dictionary with notice status
        """
        # Get quiz link status
        quiz_link = await self.monthly_quiz_service.get_quiz_link_status(
            quiz_session_id
        )

        # Get patient
        patient = (
            self.db.query(Patient).filter(Patient.id == quiz_link.patient_id).first()
        )
        if not patient:
            raise NotFoundError(f"Patient with ID {quiz_link.patient_id} not found")

        # Create expiration message
        message = self.message_factory.create_monthly_quiz_expired_message(
            patient_id=quiz_link.patient_id,
            patient_name=patient.name,
            quiz_session_id=str(quiz_session_id),
            delivery_method=quiz_link.delivery_method.value,
        )

        # Send message
        send_result = await self.message_sender.send_message(message)

        return {"expiration_notice_sent": send_result, "message_id": str(message.id)}

    async def send_completion_confirmation(
        self, quiz_session_id: UUID
    ) -> Dict[str, Any]:
        """
        Send completion confirmation message.

        Args:
            quiz_session_id: Quiz session UUID

        Returns:
            Dictionary with confirmation status
        """
        # Get quiz link status
        quiz_link = await self.monthly_quiz_service.get_quiz_link_status(
            quiz_session_id
        )

        # Get patient
        patient = (
            self.db.query(Patient).filter(Patient.id == quiz_link.patient_id).first()
        )
        if not patient:
            raise NotFoundError(f"Patient with ID {quiz_link.patient_id} not found")

        # Create completion message
        message = self.message_factory.create_monthly_quiz_completed_message(
            patient_id=quiz_link.patient_id,
            patient_name=patient.name,
            quiz_session_id=str(quiz_session_id),
            delivery_method=quiz_link.delivery_method.value,
        )

        # Send message
        send_result = await self.message_sender.send_message(message)

        return {"confirmation_sent": send_result, "message_id": str(message.id)}

    async def send_bulk_quiz_links(
        self,
        patient_ids: list[UUID],
        quiz_template_id: UUID,
        delivery_method: DeliveryMethod = DeliveryMethod.WHATSAPP,
        expiry_hours: int = 72,
    ) -> Dict[str, Any]:
        """
        Send quiz links to multiple patients.

        Args:
            patient_ids: List of patient UUIDs
            quiz_template_id: Quiz template UUID
            delivery_method: Delivery channel
            expiry_hours: Link expiry in hours

        Returns:
            Dictionary with bulk send results
        """
        results = []
        failures = []

        for patient_id in patient_ids:
            try:
                result = await self.send_quiz_link(
                    patient_id=patient_id,
                    quiz_template_id=quiz_template_id,
                    delivery_method=delivery_method,
                    expiry_hours=expiry_hours,
                    send_immediately=True,
                )
                results.append(result)
            except Exception as e:
                failures.append({"patient_id": str(patient_id), "error": str(e)})

        return {
            "total_requested": len(patient_ids),
            "total_sent": len(results),
            "total_failed": len(failures),
            "results": results,
            "failures": failures,
        }
