from typing import List, Optional, Any, Dict, Generator
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass
from base64 import b64encode
import json
import hashlib

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.repositories.message import MessageRepository
from app.schemas.message import MessageCreate, MessageUpdate
from app.utils.db_retry import with_db_retry


class MessageService:
    """Service layer for message management"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = MessageRepository(db)
    
    @with_db_retry(max_retries=3)
    def create_message(self, message_data: MessageCreate) -> Message:
        """Create a new message"""
        message_dict = message_data.dict()
        return self.repository.create(message_dict)
    
    @with_db_retry(max_retries=3)
    def get_message(self, message_id: UUID) -> Optional[Message]:
        """Get message by ID"""
        return self.repository.get_by_id(message_id)
    
    @with_db_retry(max_retries=3)
    def get_message_by_whatsapp_id(self, whatsapp_id: str) -> Optional[Message]:
        """Get message by WhatsApp ID"""
        return self.repository.get_by_whatsapp_id(whatsapp_id)
    
    @with_db_retry(max_retries=3)
    def update_message(self, message_id: UUID, message_data: MessageUpdate) -> Optional[Message]:
        """Update message information"""
        message = self.repository.get_by_id(message_id)
        if not message:
            return None
        
        update_data = message_data.dict(exclude_unset=True)
        return self.repository.update(message, update_data)
    
    @with_db_retry(max_retries=3)
    def get_patient_messages(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> List[Message]:
        """Get all messages for a patient"""
        return self.repository.get_by_patient(patient_id, skip, limit)
    
    @with_db_retry(max_retries=3)
    def get_conversation_history(self, patient_id: UUID, skip: int = 0, limit: int = 50) -> List[Message]:
        """Get conversation history for a patient"""
        return self.repository.get_conversation_history(patient_id, skip, limit)
    
    @with_db_retry(max_retries=3)
    def get_pending_messages(
        self, skip: int = 0, limit: int = 100, patient_id: Optional[UUID] = None
    ) -> List[Message]:
        """Get pending messages for sending"""
        return self.repository.get_pending_messages(skip, limit, patient_id)
    
    @with_db_retry(max_retries=3)
    def get_scheduled_messages(self, before_time: datetime, skip: int = 0, limit: int = 100) -> List[Message]:
        """Get messages scheduled before a specific time"""
        return self.repository.get_scheduled_messages(before_time, skip, limit)
    
    @with_db_retry(max_retries=3)
    def schedule_message(
        self,
        patient_id: UUID,
        content: str,
        scheduled_for: datetime,
        message_type: MessageType = MessageType.TEXT,
        message_metadata: Optional[dict[str, Any]] = None,
        idempotency_key: Optional[str] = None
    ) -> Message:
        """Schedule a message for later delivery"""
        # Generate deterministic idempotency key if not provided (minute precision)
        if idempotency_key is None:
            ts = scheduled_for.replace(second=0, microsecond=0).isoformat() if scheduled_for else datetime.utcnow().replace(second=0, microsecond=0).isoformat()
            base = f"{patient_id}:{message_type.value}:{content}:{ts}"
            idempotency_key = hashlib.sha256(base.encode('utf-8')).hexdigest()[:32]

        message_data = {
            "patient_id": patient_id,
            "direction": MessageDirection.OUTBOUND,
            "type": message_type,
            "content": content,
            "scheduled_for": scheduled_for,
            "message_metadata": message_metadata or {},
            "status": MessageStatus.PENDING,
            "idempotency_key": idempotency_key,
        }
        return self.repository.create(message_data)

    @with_db_retry(max_retries=3)
    def get_messages_with_filters(
        self,
        skip: int = 0,
        limit: int = 100,
        patient_id: Optional[UUID] = None,
        status: Optional[MessageStatus] = None,
        message_type: Optional[MessageType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        eager_load: bool = False,
    ) -> List[Message]:
        """
        Get messages with comprehensive filtering.

        PERFORMANCE FIX #2: Uses repository method with database-level filtering
        to prevent N+1 queries and unnecessary data loading.
        """
        return self.repository.get_messages_with_filters(
            skip=skip,
            limit=limit,
            patient_id=patient_id,
            status=status,
            message_type=message_type,
            start_date=start_date,
            end_date=end_date,
            eager_load=eager_load,
        )

    @with_db_retry(max_retries=3)
    def count_messages_with_filters(
        self,
        patient_id: Optional[UUID] = None,
        status: Optional[MessageStatus] = None,
        message_type: Optional[MessageType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Count messages with filters efficiently.

        PERFORMANCE FIX #2: Uses COUNT at database level without loading data.
        """
        return self.repository.count_messages_with_filters(
            patient_id=patient_id,
            status=status,
            message_type=message_type,
            start_date=start_date,
            end_date=end_date,
        )

    @with_db_retry(max_retries=3)
    def mark_as_sent(self, message_id: UUID, whatsapp_id: str) -> Optional[Message]:
        """Mark message as sent"""
        message = self.repository.get_by_id(message_id)
        if not message:
            return None
        
        update_data = {
            "status": MessageStatus.SENT,
            "whatsapp_id": whatsapp_id,
            "sent_at": datetime.utcnow()
        }
        return self.repository.update(message, update_data)
    
    @with_db_retry(max_retries=3)
    def mark_as_delivered(self, whatsapp_id: str) -> Optional[Message]:
        """Mark message as delivered using WhatsApp ID"""
        message = self.repository.get_by_whatsapp_id(whatsapp_id)
        if not message:
            return None
        
        update_data = {
            "status": MessageStatus.DELIVERED,
            "delivered_at": datetime.utcnow()
        }
        return self.repository.update(message, update_data)
    
    @with_db_retry(max_retries=3)
    def mark_as_read(self, whatsapp_id: str) -> Optional[Message]:
        """Mark message as read using WhatsApp ID"""
        message = self.repository.get_by_whatsapp_id(whatsapp_id)
        if not message:
            return None
        
        update_data = {
            "status": MessageStatus.READ,
            "read_at": datetime.utcnow()
        }
        return self.repository.update(message, update_data)
    
    @with_db_retry(max_retries=3)
    def mark_as_failed(self, message_id: UUID, error_info: Optional[dict[str, Any]] = None) -> Optional[Message]:
        """Mark message as failed"""
        message = self.repository.get_by_id(message_id)
        if not message:
            return None
        
        message_metadata = message.message_metadata or {}
        if error_info:
            message_metadata["error"] = error_info
            message_metadata["failed_at"] = datetime.utcnow().isoformat()
        
        update_data = {
            "status": MessageStatus.FAILED,
            "message_metadata": message_metadata
        }
        return self.repository.update(message, update_data)
    
    def mark_as_failed_by_whatsapp_id(self, whatsapp_id: str, error_info: Optional[dict[str, Any]] = None) -> Optional[Message]:
        """Mark message as failed using WhatsApp ID"""
        message = self.repository.get_by_whatsapp_id(whatsapp_id)
        if not message:
            return None
        
        return self.mark_as_failed(message.id, error_info)
    
    @with_db_retry(max_retries=3)
    def update_message_status(self, whatsapp_id: str, status: MessageStatus, timestamp: Optional[datetime] = None) -> Optional[Message]:
        """Update message status with timestamp tracking"""
        message = self.repository.get_by_whatsapp_id(whatsapp_id)
        if not message:
            return None
        
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        update_data = {"status": status}
        
        # Set appropriate timestamp field based on status
        if status == MessageStatus.SENT:
            update_data["sent_at"] = timestamp
        elif status == MessageStatus.DELIVERED:
            update_data["delivered_at"] = timestamp
        elif status == MessageStatus.READ:
            update_data["read_at"] = timestamp
        
        return self.repository.update(message, update_data)
    
    def get_failed_messages(self, skip: int = 0, limit: int = 100) -> List[Message]:
        """Get failed messages for retry processing"""
        return self.repository.get_failed_messages(skip, limit)

    def get_messages_by_status(self, status: MessageStatus, skip: int = 0, limit: int = 100) -> List[Message]:
        """Get messages by status"""
        return self.repository.get_by_status(status, skip, limit)

    def count_conversation_history(self, patient_id: UUID) -> int:
        """Count messages in a patient's conversation"""
        return self.repository.count_conversation_history(patient_id)

    def count_pending_messages(self, patient_id: Optional[UUID] = None) -> int:
        """Count total pending messages"""
        return self.repository.count_pending_messages(patient_id)

    def count_failed_messages(self, patient_id: Optional[UUID] = None) -> int:
        """Count total failed messages"""
        return self.repository.count_failed_messages(patient_id)

    def count_by_status(
        self, status: MessageStatus, patient_id: Optional[UUID] = None
    ) -> int:
        """Count messages by status"""
        return self.repository.count_by_status(status, patient_id)
    
    def get_message_statistics(self, patient_id: Optional[UUID] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> dict[str, int]:
        """Get message statistics"""
        return self.repository.get_message_statistics(patient_id, start_date, end_date)
    
    @with_db_retry(max_retries=3)
    def process_inbound_message(
        self,
        patient_id: UUID,
        content: str,
        whatsapp_id: str,
        message_type: MessageType = MessageType.TEXT,
        message_metadata: Optional[dict[str, Any]] = None
    ) -> Message:
        """Process an inbound message from WhatsApp"""
        message_data = {
            "patient_id": patient_id,
            "direction": MessageDirection.INBOUND,
            "type": message_type,
            "content": content,
            "whatsapp_id": whatsapp_id,
            "message_metadata": message_metadata or {},
            "status": MessageStatus.READ  # Inbound messages are considered read
        }
        return self.repository.create(message_data)
