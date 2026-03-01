"""Async service factory functions for flow-domain services.

These factories use Depends(get_async_db) to inject AsyncSession into services.
Each factory is a Depends()-compatible async function with flat injection only.

Pattern:
    async def get_async_X_service(
        db: AsyncSession = Depends(get_async_db),
    ) -> XService:
        return XService(db)

Sync factories remain in service_dependencies.py for Celery compatibility.
New flow-domain async factories are added here as services are migrated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db

if TYPE_CHECKING:
    from app.services.analytics import FlowAnalyticsService
    from app.services.flow_alerts import FlowAlertsService


async def get_async_flow_alerts_service(
    db: AsyncSession = Depends(get_async_db),
) -> FlowAlertsService:
    """Get FlowAlertsService with AsyncSession."""
    from app.services.flow_alerts import FlowAlertsService

    return FlowAlertsService(db)


async def get_async_flow_analytics_service(
    db: AsyncSession = Depends(get_async_db),
) -> FlowAnalyticsService:
    """Get FlowAnalyticsService with AsyncSession."""
    from app.services.analytics import FlowAnalyticsService

    return FlowAnalyticsService(db)
