"""
Health Checks Implementation (FIX #11)

Implements proactive health monitoring with:
- Database connectivity checks
- External services availability
- Resource utilization monitoring
- Detailed health reports
"""

from .checker import HealthChecker, HealthStatus, HealthResult
from .checks import (
    DatabaseHealthCheck,
    DiskSpaceHealthCheck,
    MemoryHealthCheck,
    CPUHealthCheck,
)

try:  # Optional dependency: Flask is only required when using the blueprint
    from .endpoints import create_health_blueprint  # type: ignore

    HAS_HEALTH_BLUEPRINT = True
except ModuleNotFoundError:
    create_health_blueprint = None  # type: ignore
    HAS_HEALTH_BLUEPRINT = False

__all__ = [
    "HealthChecker",
    "HealthStatus",
    "HealthResult",
    "DatabaseHealthCheck",
    "DiskSpaceHealthCheck",
    "MemoryHealthCheck",
    "CPUHealthCheck",
]

if HAS_HEALTH_BLUEPRINT:
    __all__.append("create_health_blueprint")
