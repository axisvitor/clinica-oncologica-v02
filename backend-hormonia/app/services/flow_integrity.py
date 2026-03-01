"""Shim - canonical code lives in flow_integrity_pkg/. See Phase 19."""

from app.services.flow_integrity_pkg import (
    FlowIntegrityService,
    get_flow_integrity_service,
)

__all__ = [
    "FlowIntegrityService",
    "get_flow_integrity_service",
]
