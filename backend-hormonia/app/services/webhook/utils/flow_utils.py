"""
Flow utilities for webhook processing.
Helper functions for flow-related operations.
"""
import logging
from typing import Any

from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion

logger = logging.getLogger(__name__)


def get_flow_type_from_state(db: Any, flow_state: PatientFlowState) -> str:
    """
    Get flow type from flow state using template version.

    Args:
        db: Database session
        flow_state: Patient flow state

    Returns:
        Flow type string
    """
    try:
        template_version = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == flow_state.template_version_id
        ).first()

        if not template_version:
            return "unknown"

        flow_kind = db.query(FlowKind).filter(
            FlowKind.id == template_version.kind_id
        ).first()

        return flow_kind.flow_type if flow_kind else "unknown"

    except Exception as e:
        logger.error(f"Error getting flow type: {e}")
        return "unknown"
