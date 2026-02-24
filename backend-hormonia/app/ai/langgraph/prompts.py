"""
TOMBSTONED -- Phase 12 (Flow Orchestration Replacement)

This module has been decommissioned.  All prompt builders and node helpers
have moved to ``app.ai.agents.helpers``.  Flow orchestration has moved to
``app.services.flow._flow_functions``.

Do not import from this module.  Update your import to:
  - Prompts/node helpers: ``from app.ai.agents.helpers import <name>``
  - Flow functions: ``from app.services.flow._flow_functions import <name>``
"""
raise ImportError(
    "app.ai.langgraph has been tombstoned in Phase 12 (Flow Orchestration Replacement). "
    "Import from app.ai.agents.helpers for prompt builders and node helpers, "
    "or from app.services.flow._flow_functions for flow orchestration functions."
)
