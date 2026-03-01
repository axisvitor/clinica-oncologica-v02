from typing import Any, Optional

from app.repositories.flow import FlowStateRepository
from app.services.enhanced_flow_engine import EnhancedFlowEngine

from .advancement import (
    FLOW_ADVANCE_BLOCKED_CODE,
    FLOW_ADVANCE_BLOCKED_MESSAGE,
    FLOW_ADVANCE_BLOCKED_REASON,
    FlowManagementAdvancementMixin,
)
from .pause_resume import FlowManagementPauseResumeMixin
from .state_management import FlowManagementStateMixin


class FlowManagementService(
    FlowManagementPauseResumeMixin,
    FlowManagementAdvancementMixin,
    FlowManagementStateMixin,
):
    """Composed flow management service preserving legacy contract."""

    def __init__(
        self,
        flow_repo: FlowStateRepository,
        db,
        flow_engine: Optional[Any] = None,
    ):
        self.flow_repo = flow_repo
        self.db = db
        engine_class = EnhancedFlowEngine
        try:
            from app.services import flow_management as legacy_flow_management

            engine_class = legacy_flow_management.EnhancedFlowEngine
        except Exception:
            pass
        self.enhanced_flow_engine = (
            flow_engine if flow_engine is not None else engine_class(db)
        )


__all__ = [
    "FLOW_ADVANCE_BLOCKED_CODE",
    "FLOW_ADVANCE_BLOCKED_MESSAGE",
    "FLOW_ADVANCE_BLOCKED_REASON",
    "FlowManagementService",
]
