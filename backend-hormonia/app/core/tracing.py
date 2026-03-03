"""
TOMBSTONED -- Phase 40 (OTel Removal & ADK Foundation)

OpenTelemetry tracing instrumentation was removed from this repository.
Use Sentry integrations configured in `app.core.setup.sentry` instead.
"""

raise ImportError(
    "app.core.tracing has been tombstoned in Phase 40. "
    "Use app.core.setup.sentry for tracing and correlation."
)
