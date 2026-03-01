"""Shared idempotency key helpers."""

from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID


def build_message_idempotency_key(
    *,
    patient_id: UUID,
    content: str,
    scheduled_for: datetime,
    message_type_value: str,
) -> str:
    """Build deterministic idempotency key for message scheduling payloads."""
    ts = scheduled_for.replace(microsecond=0).isoformat()
    base = f"{patient_id}:{message_type_value}:{ts}:{content or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
