"""
TOMBSTONED -- Phase 37 (Evolution Cleanup)

This module has been decommissioned. WuzAPI is the sole WhatsApp provider.
All outbound messaging: use app.integrations.wuzapi.
All inbound events: routed through /api/v2/webhooks/wuzapi.

Do not import from this module.
"""
raise ImportError(
    "app.integrations.whatsapp.services.mock_evolution has been tombstoned in Phase 37 (Evolution Cleanup). "
    "Use app.integrations.wuzapi for WhatsApp messaging."
)
