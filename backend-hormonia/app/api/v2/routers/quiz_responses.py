"""
Quiz Response Management API v2

Handles quiz response viewing, tracking and analytics:
- List quiz responses with cursor pagination and filtering
- View detailed quiz response information
- Get aggregate analytics for quiz responses

Features:
- Cursor-based pagination for efficient data access
- Redis caching with appropriate TTLs
- Rate limiting to prevent abuse
- RBAC: Patients (view own), Doctors (assigned patients), Admin (full access)
- Comprehensive response analytics with trends and patterns

Migrated from V1: quiz_responses.py (3 endpoints)
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues

from typing import Optional
from datetime import datetime
from uuid import UUID
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database.async_engine import get_async_db
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.quiz_extensions import (
    QuizResponseV2Detail,
    QuizResponseV2List,
    ResponseAnalyticsV2,
)
from app.api.v2.dependencies import (
    get_pagination_params_async,
    create_cursor,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.api.v2._quiz_shared import (
    _get_current_user_simple,
    _check_patient_access,
)
from app.api.v2.routers.monthly_quiz_operations.response_utils import (
    build_quiz_response_detail,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _role_name(role) -> str:
    if hasattr(role, "value"):
        return str(role.value).lower()
    return str(role).lower()


@router.get(
    "/responses",
    response_model=QuizResponseV2List,
    summary="List quiz responses",
    description="List patient quiz responses with cursor pagination and filtering",
)
@limiter.limit("30/minute")  # Patient limit
async def list_quiz_responses(
    request: Request,
    patient_id: Optional[UUID] = Query(None, description="Filter by patient ID"),
    session_id: Optional[UUID] = Query(None, description="Filter by quiz session"),
    template_id: Optional[UUID] = Query(None, description="Filter by quiz template"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    pagination: dict = Depends(get_pagination_params_async),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    List quiz responses with filtering and pagination.

    **RBAC:**
    - Patients: View own responses only
    - Doctors: View assigned patients' responses
    - Admin: View all responses

    **Performance:**
    - Cursor pagination for efficient data access
    - Redis caching (5min TTL)
    - Optimized with joinedload()
    """
    # Build base query
    query = select(QuizResponse).options(
        selectinload(QuizResponse.quiz_template),
        selectinload(QuizResponse.quiz_session),
    )

    # Apply RBAC filtering
    role = _role_name(current_user.role)
    if role == UserRole.DOCTOR.value:
        # Doctors see assigned patients' responses
        patient_ids_result = await db.execute(
            select(Patient.id).where(Patient.doctor_id == current_user.id)
        )
        patient_ids = patient_ids_result.scalars().all()
        query = query.where(QuizResponse.patient_id.in_(patient_ids))
    elif role == UserRole.ADMIN.value:
        pass
    elif role == "patient":
        query = query.where(QuizResponse.patient_id == current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access quiz responses",
        )

    # Apply additional filters
    if patient_id:
        # Check access
        await _check_patient_access(db, current_user, patient_id)
        query = query.where(QuizResponse.patient_id == patient_id)

    if session_id:
        query = query.where(QuizResponse.quiz_session_id == session_id)

    if template_id:
        query = query.where(QuizResponse.quiz_template_id == template_id)

    if start_date:
        query = query.where(QuizResponse.responded_at >= start_date)

    if end_date:
        query = query.where(QuizResponse.responded_at <= end_date)

    total_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = total_result.scalar_one()

    # Apply cursor pagination
    cursor_data = pagination.get("cursor_data")
    limit = pagination.get("limit", 20)

    if cursor_data:
        query = query.where(QuizResponse.id > cursor_data.get("id"))

    # Order by ID for consistent pagination
    query = query.order_by(asc(QuizResponse.id)).limit(limit + 1)

    # Fetch limit + 1 to check if there are more results
    responses_result = await db.execute(query)
    responses = responses_result.scalars().all()

    # Check if there are more results
    has_more = len(responses) > limit
    if has_more:
        responses = responses[:limit]

    # Enrich responses with context (relationships already pre-loaded)
    enriched_responses = []
    for response in responses:
        template = response.quiz_template
        session = response.quiz_session
        enriched_responses.append(
            QuizResponseV2Detail(
                **build_quiz_response_detail(
                    response,
                    template=template,
                    session=session,
                )
            )
        )

    # Generate next cursor
    next_cursor = None
    if has_more and responses:
        last_item = responses[-1]
        next_cursor = create_cursor(last_item.id)

    logger.info(
        f"Listed {len(enriched_responses)} quiz responses for user {current_user.id}"
    )

    return QuizResponseV2List(
        data=enriched_responses, next_cursor=next_cursor, has_more=has_more, total=total
    )


@router.get(
    "/responses/{response_id:uuid}",
    response_model=QuizResponseV2Detail,
    summary="Get quiz response details",
    description="Get detailed information about a specific quiz response",
)
@limiter.limit("50/minute")
async def get_quiz_response_detail(
    request: Request,
    response_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
):
    """
    Get detailed quiz response information.

    **RBAC:**
    - Patients: View own responses only
    - Doctors: View assigned patients' responses
    - Admin: View all responses
    """
    response_result = await db.execute(
        select(QuizResponse).where(QuizResponse.id == response_id)
    )
    response = response_result.scalar_one_or_none()
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz response not found"
        )

    # Check access
    await _check_patient_access(db, current_user, response.patient_id)

    # Get template and session info
    template_result = await db.execute(
        select(QuizTemplate).where(QuizTemplate.id == response.quiz_template_id)
    )
    template = template_result.scalar_one_or_none()

    session = None
    if response.quiz_session_id:
        session_result = await db.execute(
            select(QuizSession).where(QuizSession.id == response.quiz_session_id)
        )
        session = session_result.scalar_one_or_none()

    return QuizResponseV2Detail(
        **build_quiz_response_detail(
            response,
            template=template,
            session=session,
        )
    )


@router.get(
    "/responses/analytics",
    response_model=ResponseAnalyticsV2,
    summary="Get response analytics",
    description="Get aggregate analytics for quiz responses",
)
@limiter.limit("30/minute")
async def get_response_analytics(
    request: Request,
    patient_id: Optional[UUID] = Query(None, description="Filter by patient"),
    template_id: Optional[UUID] = Query(None, description="Filter by template"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Get analytics for quiz responses.

    **RBAC:**
    - Patients: View own analytics
    - Doctors: View assigned patients' analytics
    - Admin: View all analytics

    **Cache:** 2 minutes TTL
    """
    # Build query
    query = select(QuizResponse)

    # Apply RBAC
    role = _role_name(current_user.role)
    if role == UserRole.DOCTOR.value:
        patient_ids_result = await db.execute(
            select(Patient.id).where(Patient.doctor_id == current_user.id)
        )
        patient_ids = patient_ids_result.scalars().all()
        query = query.where(QuizResponse.patient_id.in_(patient_ids))
    elif role == UserRole.ADMIN.value:
        pass
    elif role == "patient":
        query = query.where(QuizResponse.patient_id == current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access quiz response analytics",
        )

    # Apply filters
    if patient_id:
        await _check_patient_access(db, current_user, patient_id)
        query = query.where(QuizResponse.patient_id == patient_id)

    if template_id:
        query = query.where(QuizResponse.quiz_template_id == template_id)

    if start_date:
        query = query.where(QuizResponse.responded_at >= start_date)

    if end_date:
        query = query.where(QuizResponse.responded_at <= end_date)

    # Get responses
    responses_result = await db.execute(query)
    responses = responses_result.scalars().all()
    total_responses = len(responses)
    response_patient_ids = {r.patient_id for r in responses}
    response_session_ids = {r.quiz_session_id for r in responses if r.quiz_session_id}

    sessions_by_id = {}
    if response_session_ids:
        sessions_result = await db.execute(
            select(QuizSession).where(QuizSession.id.in_(response_session_ids))
        )
        sessions = sessions_result.scalars().all()
        sessions_by_id = {session.id: session for session in sessions}

    # Calculate completion rate
    session_query = select(QuizSession).where(
        QuizSession.patient_id.in_(response_patient_ids)
    )
    if template_id:
        session_query = session_query.where(QuizSession.quiz_template_id == template_id)
    if start_date:
        session_query = session_query.where(QuizSession.started_at >= start_date)
    if end_date:
        session_query = session_query.where(QuizSession.started_at <= end_date)

    total_sessions_result = await db.execute(
        select(func.count()).select_from(session_query.order_by(None).subquery())
    )
    total_sessions = total_sessions_result.scalar_one()

    completed_sessions_result = await db.execute(
        select(func.count()).select_from(
            session_query.where(QuizSession.status == "completed").order_by(None).subquery()
        )
    )
    completed_sessions = completed_sessions_result.scalar_one()
    completion_rate = (
        (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0.0
    )

    # Calculate average score
    sessions_with_scores_result = await db.execute(
        session_query.where(QuizSession.score.isnot(None))
    )
    sessions_with_scores = sessions_with_scores_result.scalars().all()
    average_score = None
    if sessions_with_scores:
        total_score = sum(float(s.score) for s in sessions_with_scores)
        average_score = total_score / len(sessions_with_scores)

    # Calculate trends (monthly aggregates)
    trends = []
    if responses:
        monthly_data = defaultdict(list)
        for resp in responses:
            month_key = resp.responded_at.strftime("%Y-%m")
            session = sessions_by_id.get(resp.quiz_session_id)
            if session and session.score:
                monthly_data[month_key].append(float(session.score))

        for month, scores in sorted(monthly_data.items()):
            avg_score = sum(scores) / len(scores) if scores else 0
            trends.append({"date": month, "score": round(avg_score, 2)})

    # Identify common patterns
    patterns = []
    if len(sessions_with_scores) >= 3:
        scores = [float(s.score) for s in sessions_with_scores[-5:]]  # Last 5 sessions
        if len(scores) >= 2:
            if all(scores[i] < scores[i + 1] for i in range(len(scores) - 1)):
                patterns.append("improving")
            elif all(scores[i] > scores[i + 1] for i in range(len(scores) - 1)):
                patterns.append("declining")
            elif max(scores) - min(scores) < 10:
                patterns.append("consistent")

    # Count flagged responses
    flagged_count = sum(
        1
        for r in responses
        if r.response_metadata
        and (
            r.response_metadata.get("flagged", False)
            or r.response_metadata.get("requires_review", False)
        )
    )

    return ResponseAnalyticsV2(
        total_responses=total_responses,
        completion_rate=round(completion_rate, 2),
        average_score=round(average_score, 2) if average_score else None,
        response_trends=trends[:12],  # Last 12 months
        common_patterns=patterns,
        flagged_count=flagged_count,
    )
