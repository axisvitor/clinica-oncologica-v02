"""
Message Service - CRUD Operations (QW-022).

This module handles core message CRUD operations and basic message management.
Consolidated from: app/services/message.py
"""

from typing import List, Optional, Any, Dict
from uuid import UUID
from datetime import datetime, timezone
import logging
import hashlib

from sqlalchemy.orm import Session

from app.models.message import (
    Message,
    MessageDirection,
    MessageType,
    MessageStatus,
    DeliveryStatus,
)
from app.repositories.message import MessageRepository
from app.schemas.message import MessageCreate, MessageUpdate
from app.utils.db_retry import with_db_retry


logger = logging.getLogger(__name__)


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

    def _generate_idempotency_key(
        self,
        patient_id: UUID,
        content: str,
        scheduled_for: datetime,
        message_type: MessageType,
    ) -> str:
        """
        Build deterministic idempotency key for message insertion.

        Combines patient, type, scheduled time and content hash to prevent
        duplicação de envios quando o mesmo payload é gerado mais de uma vez.
        """
        ts = scheduled_for.replace(microsecond=0).isoformat()
        base = f"{patient_id}:{message_type.value}:{ts}:{content or ''}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

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
        scheduled_time = message_dict.get("scheduled_for") or datetime.now(
            timezone.utc
        ).replace(microsecond=0)
        message_type = message_dict.get("type", MessageType.TEXT)
        message_dict["scheduled_for"] = scheduled_time
        message_dict["idempotency_key"] = self._generate_idempotency_key(
            patient_id=message_dict["patient_id"],
            content=message_dict.get("content"),
            scheduled_for=scheduled_time,
            message_type=message_type,
        )
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
    def process_inbound_message(
        self,
        patient_id: UUID,
        content: str,
        whatsapp_id: str,
        message_type: MessageType = MessageType.TEXT,
        message_metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Process an inbound message from WhatsApp.

        Creates a message marked as read to represent patient inbound traffic.
        """
        idempotency_base = f"inbound:{patient_id}:{whatsapp_id or ''}:{content or ''}"
        idempotency_key = hashlib.sha256(idempotency_base.encode("utf-8")).hexdigest()
        message_data = {
            "patient_id": patient_id,
            "direction": MessageDirection.INBOUND,
            "type": message_type,
            "content": content,
            "whatsapp_id": whatsapp_id,
            "message_metadata": message_metadata or {},
            "idempotency_key": idempotency_key,
            "status": MessageStatus.READ,
        }
        return self.repository.create(message_data)

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
        auto_commit: bool = True,
    ) -> Message:
        """
        Schedule a message for later delivery.

        Args:
            patient_id: Patient UUID
            content: Message content
            scheduled_for: Scheduled delivery time
            message_type: Type of message
            message_metadata: Optional metadata
            auto_commit: If True (default), commits immediately.
                         Set to False when using within a saga/Unit of Work pattern.

        Returns:
            Scheduled Message object
        """
        scheduled_time = (scheduled_for or datetime.now(timezone.utc)).replace(
            microsecond=0
        )
        idempotency_key = self._generate_idempotency_key(
            patient_id=patient_id,
            content=content,
            scheduled_for=scheduled_time,
            message_type=message_type,
        )
        message_data = {
            "patient_id": patient_id,
            "direction": MessageDirection.OUTBOUND,
            "type": message_type,
            "content": content,
            "scheduled_for": scheduled_time,
            "message_metadata": message_metadata or {},
            "status": MessageStatus.PENDING,
            "idempotency_key": idempotency_key,
        }
        return self.repository.create(message_data, auto_commit=auto_commit)

    @with_db_retry(max_retries=3)
    def mark_as_sent(
        self, message_id: UUID, whatsapp_id: Optional[str] = None
    ) -> Optional[Message]:
        """
        Mark message as sent (síncrono).
        """
        message = self.repository.get_by_id(message_id)
        if not message:
            return None

        update_data = {"status": MessageStatus.SENT, "sent_at": datetime.now(timezone.utc)}
        if whatsapp_id:
            update_data["whatsapp_id"] = whatsapp_id

        return self.repository.update(message, update_data)

    @with_db_retry(max_retries=3)
    def mark_as_failed(self, message_id: UUID, error_message: str) -> Optional[Message]:
        """
        Mark message as failed (síncrono).
        """
        message = self.repository.get_by_id(message_id)
        if not message:
            return None

        update_data = {
            "status": MessageStatus.FAILED,
            "delivery_status": DeliveryStatus.FAILED,
            "message_metadata": {
                **(message.message_metadata or {}),
                "error": error_message,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        return self.repository.update(message, update_data)

    async def mark_as_sent_async(
        self, message_id: UUID, whatsapp_id: Optional[str] = None
    ) -> Optional[Message]:
        """
        Versão async: executa em thread para não bloquear o loop.
        """
        import asyncio

        return await asyncio.to_thread(self.mark_as_sent, message_id, whatsapp_id)

    async def mark_as_failed_async(
        self, message_id: UUID, error_message: str
    ) -> Optional[Message]:
        """
        Versão async: executa em thread para não bloquear o loop.
        """
        import asyncio

        return await asyncio.to_thread(self.mark_as_failed, message_id, error_message)

    @with_db_retry(max_retries=3)
    def get_messages_with_filters(
        self,
        status: Optional[MessageStatus] = None,
        patient_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> List[Message]:
        """
        Get messages matching filters.

        Args:
            status: Optional status filter
            patient_id: Optional patient filter
            limit: Maximum number of results

        Returns:
            List of Message objects matching filters
        """
        query = self.db.query(Message)
        if status:
            query = query.filter(Message.status == status)
        if patient_id:
            query = query.filter(Message.patient_id == patient_id)
        return query.limit(limit).all()

    @with_db_retry(max_retries=3)
    def get_message_statistics(
        self,
        patient_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get message count statistics by status.

        Args:
            patient_id: Optional patient filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary mapping status values to counts
        """
        from sqlalchemy import func

        query = self.db.query(Message.status, func.count(Message.id))
        if patient_id:
            query = query.filter(Message.patient_id == patient_id)
        if start_date:
            query = query.filter(Message.created_at >= start_date)
        if end_date:
            query = query.filter(Message.created_at <= end_date)

        results = query.group_by(Message.status).all()
        return {str(status.value): count for status, count in results}
