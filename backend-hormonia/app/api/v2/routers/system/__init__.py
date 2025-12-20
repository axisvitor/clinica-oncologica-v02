"""
System Management Module - Modular Structure.

This module consolidates all system management endpoints:
- Config: Public configuration (NO auth required)
- Health: System health monitoring (admin only)
- Initialization: System initialization (admin only)
- Components: Component management (admin only)
- Metrics: System metrics (admin only)
- Validation: Configuration validation (admin only)

All sub-modules are combined into a single router with proper tags.
"""

from fastapi import APIRouter

# Import sub-routers
from .config import router as config_router
from .health import router as health_router
from .initialization import router as initialization_router
from .components import router as components_router
from .metrics import router as metrics_router
from .validation import router as validation_router

# Create combined router with system prefix (handled by parent router)
router = APIRouter(tags=["system"])

# Include config router without prefix (special case for public endpoint)
# This makes it accessible at /system/config
router.include_router(config_router, tags=["system-config"])

# Include all other sub-routers
router.include_router(health_router, tags=["system-health"])
router.include_router(initialization_router, tags=["system-initialization"])
router.include_router(components_router, tags=["system-components"])
router.include_router(metrics_router, tags=["system-metrics"])
router.include_router(validation_router, tags=["system-validation"])

# Export router and key functions
__all__ = [
    "router",
]
