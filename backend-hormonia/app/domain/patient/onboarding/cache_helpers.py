"""Cache helpers for patient onboarding services."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.infrastructure.cache import get_unified_cache_manager as get_cache_manager


def invalidate_patient_list_cache(logger: Any, doctor_id: UUID) -> None:
    """Invalidate patient list cache entries scoped to a doctor."""
    cache_manager = get_cache_manager()
    cache_manager.invalidate_pattern(
        f"patient_list:*:{doctor_id}*", namespace="cache"
    )
    logger.debug(
        "Invalidated patient list cache",
        extra={"doctor_id": str(doctor_id)},
    )
