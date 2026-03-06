"""Admin flow observability endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.user import User
from app.schemas.v2.admin_extensions import (
    FlowHealthSummaryResponse,
    FlowStallCheckResponse,
)
from app.services.audit import AuditService
from app.services.flow.health import FlowHealthService
from app.utils.rate_limiter import limiter
from app.utils.request_context import RequestContext, get_request_context

from .dependencies import get_admin_user, log_admin_extension_action

router = APIRouter()


@router.get("/", response_model=FlowHealthSummaryResponse, summary="Get flow health summary")
@limiter.limit("100/minute")
async def get_flow_health_summary(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User | dict[str, Any] = Depends(get_admin_user),
):
    del request, admin_user
    service = FlowHealthService(db)
    summary = await service.get_health_summary()
    return FlowHealthSummaryResponse(**summary)


@router.post(
    "/check-stalls",
    response_model=FlowStallCheckResponse,
    summary="Check stalled flows and fire alerts",
)
@limiter.limit("10/minute")
async def check_stalled_flows(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User | dict[str, Any] = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    del request
    service = FlowHealthService(db)
    stalled_flows = await service.check_and_fire_stall_alerts()

    await log_admin_extension_action(
        AuditService(db),
        "flow_health_check_stalls",
        admin_user,
        context,
        additional_data={
            "stalled_count": len(stalled_flows),
            "alerts_fired": bool(stalled_flows),
        },
    )

    return FlowStallCheckResponse(
        stalled_count=len(stalled_flows),
        alerts_fired=bool(stalled_flows),
        stalled_flows=stalled_flows,
    )
