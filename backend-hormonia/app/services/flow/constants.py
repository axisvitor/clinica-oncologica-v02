"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

This module has been decommissioned. All flow template and validation
constants have moved to ``app.agents.patient.flow_coordinator.constants``.

Do not import from this module. Update your import to:
  - Constants: ``from app.agents.patient.flow_coordinator.constants import <name>``
"""
raise ImportError(
    "app.services.flow.constants has been tombstoned in Phase 16 (Dead Code Removal). "
    "Import from app.agents.patient.flow_coordinator.constants instead."
)
