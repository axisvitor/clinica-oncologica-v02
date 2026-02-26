"""Split flow integrity package with compatibility re-exports."""

from .service import FlowIntegrityService, get_flow_integrity_service

__all__ = [
    "FlowIntegrityService",
    "get_flow_integrity_service",
]
