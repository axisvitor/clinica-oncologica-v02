"""Async service factory functions for patient-domain services.

These factories use Depends(get_async_db) to inject AsyncSession into services.
Each factory is a Depends()-compatible async function with flat injection only.

Pattern:
    async def get_async_X_service(
        db: AsyncSession = Depends(get_async_db),
    ) -> XService:
        return XService(db)

Sync factories remain in service_dependencies.py for Celery compatibility.
New patient-domain async factories are added here as services are migrated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db

if TYPE_CHECKING:
    from app.services.data_integrity_monitoring import DataIntegrityMonitoringService


async def get_async_data_integrity_service(
    db: AsyncSession = Depends(get_async_db),
) -> DataIntegrityMonitoringService:
    """Get DataIntegrityMonitoringService with AsyncSession."""
    from app.services.data_integrity_monitoring import DataIntegrityMonitoringService

    return DataIntegrityMonitoringService(db)
