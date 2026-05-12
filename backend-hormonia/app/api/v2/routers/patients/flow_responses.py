"""
Patients API v2 - Flow Responses

Query endpoint for structured patient responses stored in patient_flow_responses.
Returns responses with full flow context (day, message index, timestamps).

Endpoint:
  GET /{patient_id}/flow-responses?start_date=...&end_date=...
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
import logging
from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.patients_shared_helpers import load_patient_with_access
from app.core.authorization import require_doctor_or_admin
from app.database import get_async_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.patient_flow_response import PatientFlowResponse
from app.utils.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


class FlowResponseItem(BaseModel):
    """Schema for a single patient flow response."""

    id: UUID
    flow_state_id: Optional[UUID] = None
    day_number: Optional[int] = None
    message_index: Optional[int] = None
    response_text: str
    responded_at: datetime
    prompt_message_id: Optional[str] = None
    response_message_id: Optional[str] = None

    class Config:
        from_attributes = True


@router.get(
    "/{patient_id}/flow-responses",
    response_model=List[FlowResponseItem],
    summary="List patient flow responses",
    description="Query structured patient responses by date range. "
    "Returns responses ordered by responded_at ascending.",
)
@require_doctor_or_admin()
@limiter.limit("120/minute")
async def list_flow_responses(
    request: Request,
    patient_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    start_date: Optional[date] = Query(
        None, description="Filter responses on or after this date"
    ),
    end_date: Optional[date] = Query(
        None, description="Filter responses on or before this date"
    ),
):
    """
    List structured flow responses for a patient.

    Args:
        request: FastAPI request object.
        patient_id: Patient UUID.
        db: Async database session.
        current_user: Authenticated user from session.
        start_date: Optional start date filter (inclusive).
        end_date: Optional end date filter (inclusive, end of day).

    Returns:
        List[FlowResponseItem] ordered by responded_at ASC.

    Raises:
        HTTPException: 404 if patient does not exist.
        HTTPException: 403 if user lacks doctor_or_admin role or patient ownership.
    """
    await load_patient_with_access(db, patient_id, current_user)

    # Build query
    stmt = (
        select(PatientFlowResponse)
        .filter(PatientFlowResponse.patient_id == patient_id)
    )

    if start_date is not None:
        start_dt = datetime.combine(start_date, time.min)
        stmt = stmt.filter(PatientFlowResponse.responded_at >= start_dt)

    if end_date is not None:
        end_dt = datetime.combine(end_date, time.max)
        stmt = stmt.filter(PatientFlowResponse.responded_at <= end_dt)

    stmt = stmt.order_by(PatientFlowResponse.responded_at.asc())

    result = await db.execute(stmt)
    responses = result.scalars().all()

    return [FlowResponseItem.model_validate(r) for r in responses]
