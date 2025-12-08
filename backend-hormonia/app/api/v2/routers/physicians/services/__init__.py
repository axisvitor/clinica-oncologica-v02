"""
Physicians services module.
"""

from .statistics_service import PhysicianStatisticsService
from .availability_service import PhysicianAvailabilityService

__all__ = [
    "PhysicianStatisticsService",
    "PhysicianAvailabilityService",
]
