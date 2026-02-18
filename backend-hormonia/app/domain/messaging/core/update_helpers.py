"""Shared update helpers for messaging service implementations."""

from __future__ import annotations

from typing import Optional, Any
from uuid import UUID


def update_message_by_id(
    repository: Any,
    *,
    message_id: UUID,
    message_data: Any,
) -> Optional[Any]:
    """Fetch, patch and persist a message entity by id."""
    message = repository.get_by_id(message_id)
    if not message:
        return None

    update_data = message_data.dict(exclude_unset=True)
    return repository.update(message, update_data)
