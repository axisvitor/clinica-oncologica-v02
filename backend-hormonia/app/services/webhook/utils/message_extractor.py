"""
TOMBSTONED -- Phase 37 (Evolution Cleanup)

Evolution message extraction logic has been decommissioned.
WuzAPI uses app.integrations.wuzapi.extractor for inbound message parsing.

Do not import from this module.
"""
raise ImportError(
    "app.services.webhook.utils.message_extractor has been tombstoned in Phase 37 (Evolution Cleanup). "
    "Use app.integrations.wuzapi.extractor for WuzAPI message extraction."
)
