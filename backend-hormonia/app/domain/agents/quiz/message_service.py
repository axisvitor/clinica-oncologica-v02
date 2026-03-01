"""
Quiz Message Service - Shared message persistence and delivery for quiz domain.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.messaging.delivery.idempotent_sender import IdempotentMessageSender
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.utils.timezone import now_sao_paulo


class QuizMessageService:
    """
    Shared message service to avoid duplicated persistence + delivery logic.
    """

    def __init__(
        self,
        db_session: Session,
        message_sender: IdempotentMessageSender,
        logger: Optional[logging.Logger] = None,
    ):
        self.db_session = db_session
        self.message_sender = message_sender
        self._logger = logger or logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def create_and_send_text(
        self,
        *,
        patient_id: UUID,
        content: str,
        message_metadata: Dict[str, Any],
        status: MessageStatus = MessageStatus.PENDING,
    ) -> Tuple[Message, bool]:
        """
        Persist and send an outbound text message.

        Returns:
            Tuple of persisted Message and normalized delivery success bool.
        """
        message = Message(
            patient_id=patient_id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content=content,
            message_metadata=message_metadata,
            status=status,
            scheduled_for=now_sao_paulo(),
        )

        try:
            self.db_session.add(message)
            self.db_session.commit()
            self.db_session.refresh(message)
        except Exception:
            self.db_session.rollback()
            raise

        delivery_result = await self.message_sender.send_message(message)
        delivery_success = True if delivery_result is None else bool(delivery_result)
        return message, delivery_success
