"""
Data integrity checking and correction for flow operations.

This module has been refactored into a modular structure:
- types.py: Enums and dataclasses
- checkers/: Validation logic by domain
- corrections/: Fix logic by domain
- orchestrator.py: Main coordinator

The original data_integrity.py is kept for backward compatibility.
"""
from .orchestrator import FlowDataIntegrityChecker, get_flow_data_integrity_checker
from .types import (
    CorruptionIssue,
    CorruptionSeverity,
    CorruptionType,
    CorrectionResult,
    IntegrityCheckResult,
)

# Backward compatibility exports
__all__ = [
    # Main service
    "FlowDataIntegrityChecker",
    "get_flow_data_integrity_checker",
    # Types
    "CorruptionType",
    "CorruptionSeverity",
    "CorruptionIssue",
    "IntegrityCheckResult",
    "CorrectionResult",
]
