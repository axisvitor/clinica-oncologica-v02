"""Explicit Firebase sync history surface.

This module preserves the legacy Firebase sync residue behind an append-only,
historical table. It is intentionally not a live domain model.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db.base import Base


class FirebaseSyncHistory(Base):
    """Append-only Firebase sync history preserved for forensic replay."""

    __tablename__ = "firebase_sync_history"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    firebase_uid = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Preserved Firebase identifier from the historical sync event",
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Canonical user linked to the preserved Firebase sync event",
    )
    operation = Column(
        String(50),
        nullable=False,
        comment="Historical sync operation: create, update, link, or sync",
    )
    sync_direction = Column(
        String(20),
        nullable=False,
        comment="Historical direction marker: firebase_to_pg or pg_to_firebase",
    )
    changes = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Captured payload for the preserved historical sync event",
    )
    success = Column(
        Boolean,
        nullable=False,
        comment="Whether the historical sync event completed successfully",
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Failure residue captured for historical replay/debugging",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Timestamp when the Firebase sync history row was appended",
    )

    def __repr__(self) -> str:
        return (
            "<FirebaseSyncHistory("
            f"operation='{self.operation}', "
            f"success={self.success}, "
            f"has_firebase_uid={bool(self.firebase_uid)}"
            ")>"
        )
