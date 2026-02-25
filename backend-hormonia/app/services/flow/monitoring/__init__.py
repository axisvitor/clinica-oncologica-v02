"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

This package has been decommissioned. It was a pure re-export shim of
``app.services.flow.analytics`` which has also been tombstoned.

Production flow monitoring uses ``app.services.flow_monitoring`` instead.

Do not import from this package.
"""

raise ImportError(
    "app.services.flow.monitoring has been tombstoned in Phase 16 (Dead Code Removal). "
    "This package had zero production callers. "
    "Use app.services.flow_monitoring for production monitoring."
)
