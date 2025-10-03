"""User Sync Log Model

Audit trail for Firebase-PostgreSQL synchronization operations.
"""
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.models.base import BaseModel


class UserSyncLog(BaseModel):
    """
    Audit log for user synchronization operations.

    Tracks all sync operations between Firebase and PostgreSQL
    for debugging and compliance purposes.
    """
    __tablename__ = "user_sync_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(String(255), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)

    # Operation details
    operation = Column(String(50), nullable=False)  # create, update, link, sync
    sync_direction = Column(String(20), nullable=False)  # firebase_to_pg, pg_to_firebase

    # Changes and status
    changes = Column(JSONB, default={}, nullable=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    def __repr__(self):
        return f"<UserSyncLog(firebase_uid='{self.firebase_uid}', operation='{self.operation}', success={self.success})>"
