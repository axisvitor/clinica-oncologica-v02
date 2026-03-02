"""
TOMBSTONED -- Phase 37 (Evolution Cleanup)

Evolution webhook endpoints (/webhooks/whatsapp/*) have been decommissioned.
WuzAPI inbound events are routed through /api/v2/webhooks/wuzapi.

Do not import from this module.
"""
raise ImportError(
    "app.integrations.whatsapp.api.webhooks has been tombstoned in Phase 37 (Evolution Cleanup). "
    "Use /api/v2/webhooks/wuzapi for inbound WhatsApp events."
)
