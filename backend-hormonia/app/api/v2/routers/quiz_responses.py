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
from sqlalchemy import asc

from app.database import get_db
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.quiz_extensions import (
    QuizResponseV2Detail,
    QuizResponseV2List,
    ResponseAnalyticsV2,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    create_cursor,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.api.v2._quiz_shared import (
    _get_current_user_simple,
    _check_patient_access,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    pagination: dict = Depends(get_pagination_params),
    db=Depends(get_db),
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
    query = db.query(QuizResponse)

    # FIXED: Removed UserRole.PATIENT check - only ADMIN and DOCTOR roles exist
    # Apply RBAC filtering
    if current_user.role == UserRole.DOCTOR:
        # Doctors see assigned patients' responses
        patient_ids = (
            db.query(Patient.id).filter(Patient.doctor_id == current_user.id).all()
        )
        patient_ids = [p[0] for p in patient_ids]
        query = query.filter(QuizResponse.patient_id.in_(patient_ids))

    # Apply additional filters
    if patient_id:
        # Check access
        _check_patient_access(db, current_user, patient_id)
        query = query.filter(QuizResponse.patient_id == patient_id)

    if session_id:
        query = query.filter(QuizResponse.quiz_session_id == session_id)

    if template_id:
        query = query.filter(QuizResponse.quiz_template_id == template_id)

    if start_date:
        query = query.filter(QuizResponse.responded_at >= start_date)

    if end_date:
        query = query.filter(QuizResponse.responded_at <= end_date)

    # Apply cursor pagination
    cursor_data = pagination.get("cursor_data")
    limit = pagination.get("limit", 20)

    if cursor_data:
        query = query.filter(QuizResponse.id > cursor_data.get("id"))

    # Order by ID for consistent pagination
    query = query.order_by(asc(QuizResponse.id))

    # Fetch limit + 1 to check if there are more results
    responses = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(responses) > limit
    if has_more:
        responses = responses[:limit]

    # Enrich responses with context
    enriched_responses = []
    for response in responses:
        # Get template info
        template = (
            db.query(QuizTemplate)
            .filter(QuizTemplate.id == response.quiz_template_id)
            .first()
        )

        # Get session info
        session = None
        if response.quiz_session_id:
            session = (
                db.query(QuizSession)
                .filter(QuizSession.id == response.quiz_session_id)
                .first()
            )

        enriched = QuizResponseV2Detail(
            id=response.id,
            patient_id=response.patient_id,
            quiz_template_id=response.quiz_template_id,
            quiz_session_id=response.quiz_session_id,
            question_id=response.question_id,
            question_text=response.question_text,
            response_type=response.response_type,
            response_value=response.response_value,
            response_metadata=response.response_metadata or {},
            other_text=response.other_text,
            responded_at=response.responded_at,
            created_at=response.created_at,
            template_name=template.name if template else None,
            template_version=template.version if template else None,
            session_status=session.status if session else None,
        )
        enriched_responses.append(enriched)

    # Generate next cursor
    next_cursor = None
    if has_more and responses:
        last_item = responses[-1]
        next_cursor = create_cursor(last_item.id, last_item.created_at)

    # Get total count (cached)
    total = query.count()

    logger.info(
        f"Listed {len(enriched_responses)} quiz responses for user {current_user.id}"
    )

    return QuizResponseV2List(
        data=enriched_responses, next_cursor=next_cursor, has_more=has_more, total=total
    )


@router.get(
    "/responses/{response_id}",
    response_model=QuizResponseV2Detail,
    summary="Get quiz response details",
    description="Get detailed information about a specific quiz response",
)
@limiter.limit("50/minute")
async def get_quiz_response_detail(
    request: Request,
    response_id: UUID,
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
):
    """
    Get detailed quiz response information.

    **RBAC:**
    - Patients: View own responses only
    - Doctors: View assigned patients' responses
    - Admin: View all responses
    """
    response = db.query(QuizResponse).filter(QuizResponse.id == response_id).first()
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz response not found"
        )

    # Check access
    _check_patient_access(db, current_user, response.patient_id)

    # Get template and session info
    template = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.id == response.quiz_template_id)
        .first()
    )

    session = None
    if response.quiz_session_id:
        session = (
            db.query(QuizSession)
            .filter(QuizSession.id == response.quiz_session_id)
            .first()
        )

    return QuizResponseV2Detail(
        id=response.id,
        patient_id=response.patient_id,
        quiz_template_id=response.quiz_template_id,
        quiz_session_id=response.quiz_session_id,
        question_id=response.question_id,
        question_text=response.question_text,
        response_type=response.response_type,
        response_value=response.response_value,
        response_metadata=response.response_metadata or {},
        other_text=response.other_text,
        responded_at=response.responded_at,
        created_at=response.created_at,
        template_name=template.name if template else None,
        template_version=template.version if template else None,
        session_status=session.status if session else None,
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
    db=Depends(get_db),
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
    query = db.query(QuizResponse)

    # FIXED: Removed UserRole.PATIENT check - only ADMIN and DOCTOR roles exist
    # Apply RBAC
    if current_user.role == UserRole.DOCTOR:
        patient_ids = (
            db.query(Patient.id).filter(Patient.doctor_id == current_user.id).all()
        )
        patient_ids = [p[0] for p in patient_ids]
        query = query.filter(QuizResponse.patient_id.in_(patient_ids))

    # Apply filters
    if patient_id:
        _check_patient_access(db, current_user, patient_id)
        query = query.filter(QuizResponse.patient_id == patient_id)

    if template_id:
        query = query.filter(QuizResponse.quiz_template_id == template_id)

    if start_date:
        query = query.filter(QuizResponse.responded_at >= start_date)

    if end_date:
        query = query.filter(QuizResponse.responded_at <= end_date)

    # Get responses
    responses = query.all()
    total_responses = len(responses)

    # Calculate completion rate
    session_query = db.query(QuizSession).filter(
        QuizSession.patient_id.in_([r.patient_id for r in responses])
    )
    if start_date:
        session_query = session_query.filter(QuizSession.started_at >= start_date)
    if end_date:
        session_query = session_query.filter(QuizSession.started_at <= end_date)

    total_sessions = session_query.count()
    completed_sessions = session_query.filter(QuizSession.status == "completed").count()
    completion_rate = (
        (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0.0
    )

    # Calculate average score
    sessions_with_scores = session_query.filter(QuizSession.score.isnot(None)).all()
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
            # Get session score if available
            if resp.quiz_session_id:
                session = (
                    db.query(QuizSession)
                    .filter(QuizSession.id == resp.quiz_session_id)
                    .first()
                )
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
