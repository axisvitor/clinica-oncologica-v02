"""
Admin Extensions API v2 - Dead Letter Queue & Audit Management
Comprehensive admin endpoints for system monitoring, troubleshooting, and compliance.

Features:
- Dead Letter Queue (DLQ) management for failed operations
- Comprehensive audit log management for compliance (HIPAA, LGPD)
- Cursor-based pagination on all list endpoints
- Redis caching with SHORT TTLs (critical operations)
- Rate limiting (30-60 req/min)
- Eager loading with joinedload() to prevent N+1
- Field selection (?fields=id,name,email)
- RBAC - Admin-only endpoints (highly sensitive)
- Comprehensive audit trail for all operations

CRITICAL: This module handles sensitive system data and compliance requirements.
All operations must be thoroughly validated and logged.
"""

from fastapi import APIRouter

from .dlq import router as dlq_router
from .audit import router as audit_router
from .flow_ops import router as flow_ops_router
from .flow_health import router as flow_health_router

# Create main router
router = APIRouter()

# Include sub-routers
router.include_router(dlq_router, prefix="/dlq", tags=["Admin Extensions - DLQ"])

router.include_router(
    audit_router, prefix="/audit-logs", tags=["Admin Extensions - Audit Logs"]
)
router.include_router(
    flow_ops_router, prefix="/flow-ops", tags=["Admin Extensions - Flow Ops"]
)
router.include_router(
    flow_health_router, prefix="/flow-health", tags=["admin-flow-health"]
)

__all__ = ["router"]
