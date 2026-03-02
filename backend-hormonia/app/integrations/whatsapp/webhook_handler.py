"""
TOMBSTONED -- Phase 37 (Evolution Cleanup)

Evolution webhook handler (/api/v2/webhooks/whatsapp/evolution/*) has been decommissioned.
WuzAPI inbound events are routed through /api/v2/webhooks/wuzapi.

Do not import from this module.
"""
raise ImportError(
    "app.integrations.whatsapp.webhook_handler has been tombstoned in Phase 37 (Evolution Cleanup). "
    "Use /api/v2/webhooks/wuzapi for inbound WhatsApp events."
)
