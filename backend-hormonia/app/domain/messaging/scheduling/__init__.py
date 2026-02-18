"""Canonical scheduling exports with lazy loading.

Import from this module for scheduler features to avoid depending on legacy
`core.message_service.scheduler` compatibility code.
"""

from __future__ import annotations

from typing import Dict, Tuple

from app.domain.messaging.lazy_exports import resolve_lazy_export

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "MessageScheduler": (
        "app.domain.messaging.scheduling.message_scheduler",
        "MessageScheduler",
    ),
    "MessageSchedulerConfig": (
        "app.domain.messaging.scheduling.message_scheduler",
        "MessageSchedulerConfig",
    ),
    "SchedulingWindow": (
        "app.domain.messaging.scheduling.message_scheduler",
        "SchedulingWindow",
    ),
    "get_message_scheduler": (
        "app.domain.messaging.scheduling.message_scheduler",
        "get_message_scheduler",
    ),
}

__all__ = sorted(_EXPORTS.keys())


def __getattr__(name: str):
    return resolve_lazy_export(
        name=name,
        exports=_EXPORTS,
        module_name=__name__,
        target_globals=globals(),
    )
