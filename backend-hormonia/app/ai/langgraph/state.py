"""LangGraph state definitions for flow message execution."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID


class FlowMessageState(TypedDict, total=False):
    """Shared LangGraph state for flow message execution."""

    patient_id: UUID
    day_number: int
    flow_kind: str
    flow_state_id: UUID
    flow_state_step_data: Dict[str, Any]
    day_config: Optional[Dict[str, Any]]
    messages: List[Dict[str, Any]]
    send_mode: str
    current_index: int
    result: Dict[str, Any]
    error: str
