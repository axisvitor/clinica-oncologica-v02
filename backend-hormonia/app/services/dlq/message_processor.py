"""
Message processing handlers for DLQ Service.

This module contains all message reprocessing logic for different
message types (WhatsApp, Email, Quiz, Notifications).
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from app.models.failed_message import FailedMessage, FailureReason

logger = logging.getLogger(__name__)


class DLQMessageProcessor:
    """
    Handles reprocessing of different message types.

    Supports:
    - WhatsApp messages
    - Email notifications
    - Quiz messages
    - Generic notifications
    """

    def __init__(self):
        """Initialize message processor."""
        self._executor = ThreadPoolExecutor(max_workers=4)

    def reprocess_message(
        self,
        failed_message: FailedMessage
    ) -> bool:
        """
        Main entry point for message reprocessing.

        Routes to appropriate handler based on failure reason and type.

        Args:
            failed_message: Message to reprocess

        Returns:
            True if processing succeeded
        """
        try:
            payload = failed_message.payload or {}
            message_type = payload.get("type", "unknown")
            failure_reason = failed_message.failure_reason

            logger.info(
                f"Reprocessing message {failed_message.message_id} "
                f"(type: {message_type}, reason: {failure_reason.value})"
            )

            # Route to specific handler
            if failure_reason == FailureReason.WHATSAPP_ERROR or message_type == "whatsapp":
                return self._reprocess_whatsapp(failed_message, payload)

            elif failure_reason == FailureReason.EMAIL_ERROR or message_type == "email":
                return self._reprocess_email(failed_message, payload)

            elif failure_reason == FailureReason.QUIZ_ERROR or message_type == "quiz":
                return self._reprocess_quiz(failed_message, payload)

            elif failure_reason == FailureReason.NOTIFICATION_ERROR or message_type == "notification":
                return self._reprocess_notification(failed_message, payload)

            else:
                # Try to infer from payload
                return self._infer_and_process(failed_message, payload)

        except Exception as e:
            logger.error(
                f"Error reprocessing message {failed_message.message_id}: {e}",
                exc_info=True
            )
            failed_message.metadata["last_reprocess_error"] = str(e)
            failed_message.metadata["last_reprocess_at"] = datetime.utcnow().isoformat()
            return False

    def _infer_and_process(
        self,
        failed_message: FailedMessage,
        payload: Dict[str, Any]
    ) -> bool:
        """Infer message type from payload and process."""
        if "phone_number" in payload or "whatsapp" in payload:
            return self._reprocess_whatsapp(failed_message, payload)
        elif "email" in payload or "recipients" in payload:
            return self._reprocess_email(failed_message, payload)
        else:
            logger.warning(
                f"Unknown message type for {failed_message.message_id}"
            )
            return False

    def _reprocess_whatsapp(
        self,
        failed_message: FailedMessage,
        payload: Dict[str, Any]
    ) -> bool:
        """Reprocess WhatsApp message via WhatsApp Unified Service."""
        try:
            from app.services.unified_whatsapp_service import (
                get_whatsapp_service,
                MessageType,
                MessagePriority
            )

            whatsapp_service = get_whatsapp_service()

            phone_number = payload.get("phone_number") or payload.get("phone")
            content = payload.get("content", {})
            message_type_str = payload.get("message_type", "text")

            if not phone_number:
                logger.error(f"Missing phone_number in payload: {failed_message.message_id}")
                return False

            # Map string to MessageType enum
            message_type_map = {
                "text": MessageType.TEXT,
                "template": MessageType.TEMPLATE,
                "media": MessageType.MEDIA,
                "interactive": MessageType.INTERACTIVE,
            }
            message_type = message_type_map.get(message_type_str, MessageType.TEXT)

            # Priority based on retry count
            priority = (
                MessagePriority.HIGH
                if failed_message.retry_count > 2
                else MessagePriority.NORMAL
            )

            # Send message asynchronously
            async def send_async():
                return await whatsapp_service.send_message(
                    phone_number=phone_number,
                    message_type=message_type,
                    content=content,
                    priority=priority,
                    metadata={
                        "dlq_retry": True,
                        "retry_count": failed_message.retry_count,
                        "original_message_id": str(failed_message.message_id),
                    }
                )

            result = self._run_async(send_async)

            if result and result.get("status") in ["sent", "queued", "success"]:
                logger.info(f"WhatsApp message {failed_message.message_id} reprocessed")
                return True

            logger.warning(f"WhatsApp reprocess failed: {result}")
            return False

        except ImportError as e:
            logger.error(f"WhatsApp service not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error reprocessing WhatsApp message: {e}", exc_info=True)
            return False

    def _reprocess_email(
        self,
        failed_message: FailedMessage,
        payload: Dict[str, Any]
    ) -> bool:
        """Reprocess email message via NotificationService."""
        try:
            from app.services.notification_service import (
                get_notification_service,
                NotificationChannel,
                NotificationPriority
            )

            notification_service = get_notification_service()

            recipients = payload.get("recipients", [])
            if not recipients:
                email = payload.get("email")
                if email:
                    recipients = [email]
                else:
                    logger.error(f"Missing recipients in payload: {failed_message.message_id}")
                    return False

            subject = payload.get("subject", "Mensagem Reprocessada")
            message = payload.get("message") or payload.get("content", "")
            priority = (
                NotificationPriority.HIGH
                if failed_message.retry_count > 2
                else NotificationPriority.NORMAL
            )

            async def send_async():
                return await notification_service.send_notification(
                    channels=[NotificationChannel.EMAIL],
                    subject=subject,
                    message=message,
                    recipients=recipients,
                    priority=priority,
                    template_data=payload.get("template_data")
                )

            result = self._run_async(send_async)

            # Check if any channel succeeded
            if result:
                for channel, res in result.items():
                    if res.success:
                        logger.info(f"Email {failed_message.message_id} reprocessed")
                        return True

            logger.warning(f"Email reprocess failed for {failed_message.message_id}")
            return False

        except ImportError as e:
            logger.error(f"Notification service not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error reprocessing email: {e}", exc_info=True)
            return False

    def _reprocess_quiz(
        self,
        failed_message: FailedMessage,
        payload: Dict[str, Any]
    ) -> bool:
        """Reprocess quiz-related message."""
        try:
            quiz_session_id = payload.get("quiz_session_id")
            action = payload.get("action", "send_reminder")

            if not quiz_session_id:
                logger.error(f"Missing quiz_session_id: {failed_message.message_id}")
                return False

            if action == "send_reminder":
                phone_number = payload.get("phone_number")
                if phone_number:
                    return self._reprocess_whatsapp(failed_message, {
                        "phone_number": phone_number,
                        "message_type": "template",
                        "content": {
                            "template_name": "quiz_reminder",
                            "parameters": payload.get("template_params", {})
                        }
                    })

            elif action == "send_results":
                email = payload.get("email")
                if email:
                    return self._reprocess_email(failed_message, {
                        "recipients": [email],
                        "subject": payload.get("subject", "Resultados do Quiz"),
                        "message": payload.get("message", ""),
                        "template_data": payload.get("template_data")
                    })

            logger.warning(f"Quiz action '{action}' not supported")
            return False

        except Exception as e:
            logger.error(f"Error reprocessing quiz message: {e}", exc_info=True)
            return False

    def _reprocess_notification(
        self,
        failed_message: FailedMessage,
        payload: Dict[str, Any]
    ) -> bool:
        """Reprocess generic notification."""
        try:
            from app.services.notification_service import (
                get_notification_service,
                NotificationChannel,
                NotificationPriority
            )

            notification_service = get_notification_service()

            # Determine channels
            channels_str = payload.get("channels", ["email"])
            channel_map = {
                "email": NotificationChannel.EMAIL,
                "whatsapp": NotificationChannel.WHATSAPP,
            }
            channels = [
                channel_map[ch.lower()]
                for ch in channels_str
                if ch.lower() in channel_map
            ]

            if not channels:
                channels = [NotificationChannel.EMAIL]

            recipients = payload.get("recipients", [])
            if not recipients:
                logger.error(f"Missing recipients: {failed_message.message_id}")
                return False

            subject = payload.get("subject", "Notificação")
            message = payload.get("message", "")

            async def send_async():
                return await notification_service.send_notification(
                    channels=channels,
                    subject=subject,
                    message=message,
                    recipients=recipients,
                    priority=NotificationPriority.HIGH,
                    template_data=payload.get("template_data")
                )

            result = self._run_async(send_async)

            if result:
                for channel, res in result.items():
                    if res.success:
                        logger.info(f"Notification {failed_message.message_id} reprocessed")
                        return True

            logger.warning(f"Notification reprocess failed: {failed_message.message_id}")
            return False

        except ImportError as e:
            logger.error(f"Notification service not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error reprocessing notification: {e}", exc_info=True)
            return False

    def _run_async(self, coro):
        """
        Run async coroutine in sync context.

        Handles both running and non-running event loops.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In async context, submit to executor
                future = self._executor.submit(asyncio.run, coro)
                return future.result(timeout=30)
            else:
                return asyncio.run(coro)
        except Exception as e:
            logger.error(f"Error running async operation: {e}")
            return None


__all__ = ["DLQMessageProcessor"]
