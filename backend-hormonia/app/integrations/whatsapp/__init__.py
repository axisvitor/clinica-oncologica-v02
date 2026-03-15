"""WhatsApp integration package exports."""

from __future__ import annotations

from importlib import import_module

_EXPORTS: dict[str, tuple[str, str]] = {
    # Models
    "WhatsAppMessage": ("app.integrations.whatsapp.models.message", "WhatsAppMessage"),
    "WhatsAppContact": ("app.integrations.whatsapp.models.message", "WhatsAppContact"),
    "WhatsAppInstance": ("app.integrations.whatsapp.models.message", "WhatsAppInstance"),
    "MessageRequest": ("app.integrations.whatsapp.models.message", "MessageRequest"),
    "MessageResponse": ("app.integrations.whatsapp.models.message", "MessageResponse"),
    "MessageStatus": ("app.integrations.whatsapp.models.message", "MessageStatus"),
    "MessageType": ("app.integrations.whatsapp.models.message", "MessageType"),
    "ContactResponse": ("app.integrations.whatsapp.models.message", "ContactResponse"),
    "InstanceStatus": ("app.integrations.whatsapp.models.message", "InstanceStatus"),
    "WebhookPayload": ("app.integrations.whatsapp.models.message", "WebhookPayload"),
    "MessageStatusUpdate": (
        "app.integrations.whatsapp.models.message",
        "MessageStatusUpdate",
    ),
    # Services
    "WhatsAppMessageService": (
        "app.integrations.whatsapp.services.message_service",
        "WhatsAppMessageService",
    ),
    "MessageQueue": (
        "app.integrations.whatsapp.services.message_service",
        "MessageQueue",
    ),
    # Routers
    "whatsapp_router": ("app.integrations.whatsapp.api.routes", "router"),
}

__all__ = list(_EXPORTS)
__version__ = "1.0.0"
__author__ = "Hormonia System"


def __getattr__(name: str):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
