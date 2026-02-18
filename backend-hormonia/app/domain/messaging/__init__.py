"""Domain messaging exports with lazy loading.

Avoid eager imports that recursively pull scheduling/delivery/integrations during
task bootstrap, which can trigger circular imports in Celery workers.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .lazy_exports import resolve_lazy_export

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "MessageService": ("app.domain.messaging.core.message_service", "MessageService"),
    "MessageFactory": ("app.domain.messaging.core.message_factory", "MessageFactory"),
    "MessageScheduler": (
        "app.domain.messaging.scheduling.message_scheduler",
        "MessageScheduler",
    ),
    "IdempotentMessageSender": (
        "app.domain.messaging.delivery.idempotent_sender",
        "IdempotentMessageSender",
    ),
    "WhatsAppService": (
        "app.services.unified_whatsapp_service",
        "UnifiedWhatsAppService",
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
