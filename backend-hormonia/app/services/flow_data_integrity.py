"""
DEPRECATED: This module has been moved to app.domain.flows.integrity

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.flows.integrity import FlowDataIntegrityChecker
"""
import warnings

warnings.warn(
    "flow_data_integrity has been moved to app.domain.flows.integrity. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.flows.integrity import (
    FlowDataIntegrityChecker,
    CorruptionType,
    CorruptionSeverity,
    CorruptionIssue,
    IntegrityCheckResult,
    CorrectionResult,
    get_flow_data_integrity_checker
)

__all__ = [
    "FlowDataIntegrityChecker",
    "CorruptionType",
    "CorruptionSeverity",
    "CorruptionIssue",
    "IntegrityCheckResult",
    "CorrectionResult",
    "get_flow_data_integrity_checker"
]
