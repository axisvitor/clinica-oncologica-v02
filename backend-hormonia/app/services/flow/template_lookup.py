"""
Shared helpers for flow template lookup operations.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def find_step_in_template(
    template: Dict[str, Any], step_id: str
) -> Optional[Dict[str, Any]]:
    """Return a step dict by `step_id` from a flow template payload."""
    steps = template.get("steps", [])
    for step in steps:
        if step.get("step_id") == step_id:
            return step
    return None
