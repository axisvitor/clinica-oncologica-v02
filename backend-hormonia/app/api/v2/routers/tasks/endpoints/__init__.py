"""Tasks API Endpoints Package."""

from .crud import router as crud_router
from .operations import router as operations_router
from .monitoring import router as monitoring_router
from .bulk import router as bulk_router

__all__ = [
    "crud_router",
    "operations_router",
    "monitoring_router",
    "bulk_router",
]
