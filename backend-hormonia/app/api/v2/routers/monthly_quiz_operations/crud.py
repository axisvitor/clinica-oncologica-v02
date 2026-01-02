"""
CRUD operations for monthly quiz responses.

Endpoints:
- GET /monthly/{quiz_id}/responses - Get responses for a monthly quiz
- GET /monthly/{quiz_id}/statistics - Get comprehensive statistics
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request

from ._shared import (
    UUID,
    defaultdict,
    get_db,
    limiter,
    get_pagination_params,
    create_cursor,
    QuizResponse,
    QuizSession,
    QuizTemplate,
    User,
    UserRole,
    Patient,
    QuizResponseV2Detail,
    QuizResponseV2List,
    MonthlyQuizStatisticsV2,
    _get_current_user_simple,
    get_redis_cache,
    CACHE_TTL_STATISTICS,
    asc,
    desc,
)

router = APIRouter()


@router.get(
    "/monthly/{quiz_id}/responses",
    response_model=QuizResponseV2List,
    summary="Get monthly quiz responses",
    description="Get all responses for a specific monthly quiz",
)
@limiter.limit("50/minute")
async def get_monthly_quiz_responses(
    request: Request,
    quiz_id: UUID,
    pagination: dict = Depends(get_pagination_params),
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Get responses for a monthly quiz.

    **RBAC:** Admin and Doctors can view
    **Cache:** 5 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz responses",
        )

    # Verify quiz exists
    quiz = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz")
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monthly quiz not found"
        )

    # Get responses for this quiz
    query = db.query(QuizResponse).filter(QuizResponse.quiz_template_id == quiz_id)

    # Apply RBAC for doctors
    if current_user.role == UserRole.DOCTOR:
        patient_ids = (
            db.query(Patient.id).filter(Patient.doctor_id == current_user.id).all()
        )
        patient_ids = [p[0] for p in patient_ids]
        query = query.filter(QuizResponse.patient_id.in_(patient_ids))

    # Apply pagination
    cursor_data = pagination.get("cursor_data")
    limit = pagination.get("limit", 20)

    if cursor_data:
        query = query.filter(QuizResponse.id > cursor_data.get("id"))

    query = query.order_by(asc(QuizResponse.id))
    responses = query.limit(limit + 1).all()

    has_more = len(responses) > limit
    if has_more:
        responses = responses[:limit]

    # Enrich responses
    enriched_responses = []
    for response in responses:
        template = (
            db.query(QuizTemplate)
            .filter(QuizTemplate.id == response.quiz_template_id)
            .first()
        )
        session = (
            db.query(QuizSession)
            .filter(QuizSession.id == response.quiz_session_id)
            .first()
            if response.quiz_session_id
            else None
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

    next_cursor = None
    if has_more and responses:
        last_item = responses[-1]
        next_cursor = create_cursor(last_item.id, last_item.created_at)

    total = query.count()

    return QuizResponseV2List(
        data=enriched_responses, next_cursor=next_cursor, has_more=has_more, total=total
    )


# --- New Endpoints matching Frontend monthly-quiz.ts ---

from pydantic import BaseModel

class QuizLinkCreate(BaseModel):
    patient_id: UUID
    quiz_template_id: UUID
    delivery_method: str = "whatsapp"
    expiry_hours: int = 48
    custom_message: Optional[str] = None

class QuizLinkResponse(BaseModel):
    id: UUID
    quiz_session_id: UUID
    patient_id: UUID
    quiz_template_id: UUID
    link: str
    token: str
    status: str
    expires_at: datetime
    created_at: datetime
    delivery_method: str

class QuizStatsDashboard(BaseModel):
    total_sent: int
    total_completed: int
    total_expired: int
    total_active: int
    average_score: float
    completion_rate: float
    expiration_rate: float

@router.post(
    "/links/",
    response_model=QuizLinkResponse,
    summary="Create quiz link",
    description="Create a monthly quiz link for a patient"
)
async def create_quiz_link(
    link_data: QuizLinkCreate,
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """Create a quiz link (session + token)."""
    # Verify template
    template = db.query(QuizTemplate).filter(QuizTemplate.id == link_data.quiz_template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Quiz template not found")

    # Check/Create Session
    session = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == link_data.quiz_template_id,
        QuizSession.patient_id == link_data.patient_id,
        QuizSession.status.in_(["started", "active"])
    ).first()

    if not session:
        session = QuizSession(
            patient_id=link_data.patient_id,
            quiz_template_id=link_data.quiz_template_id,
            status="started",
            started_at=datetime.now(timezone.utc),
            session_metadata={
                "delivery_method": link_data.delivery_method,
                "custom_message": link_data.custom_message
            }
        )
        session.set_expiration_date(hours=link_data.expiry_hours)
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # Generate Token (Base64 JSON as per public.py)
    import json
    import base64
    
    token_data = {
        "quiz_id": str(link_data.quiz_template_id),
        "exp": int(session.expiration_date.timestamp()) if session.expiration_date else None,
        "type": "quiz_access"
    }
    token = base64.b64encode(json.dumps(token_data).encode()).decode()
    
    # Construct Link (Mock frontend URL)
    # In production, use env var for frontend URL
    link = f"http://localhost:3000/quiz-mensal/{token}" 

    return QuizLinkResponse(
        id=session.id, # Session ID as Link ID for now
        quiz_session_id=session.id,
        patient_id=session.patient_id,
        quiz_template_id=session.quiz_template_id,
        link=link,
        token=token,
        status=session.status,
        expires_at=session.expiration_date or (datetime.now(timezone.utc) + timedelta(hours=48)),
        created_at=session.started_at,
        delivery_method=session.session_metadata.get("delivery_method", "whatsapp")
    )

@router.get(
    "/patients/{patient_id}/status",
    summary="Get patient quiz status",
    response_model=List[Dict[str, Any]]
)
async def get_patient_quiz_status(
    patient_id: UUID,
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    sessions = db.query(QuizSession).filter(
        QuizSession.patient_id == patient_id
    ).order_by(desc(QuizSession.started_at)).limit(5).all()

    result = []
    for s in sessions:
        template = db.query(QuizTemplate).filter(QuizTemplate.id == s.quiz_template_id).first()
        result.append({
            "id": str(s.id),
            "quiz_session_id": str(s.id),
            "quiz_template_id": str(s.quiz_template_id),
            "template_name": template.name if template else "Unknown",
            "status": s.status,
            "score": float(s.score) if s.score is not None else None,
            "expires_at": s.expiration_date,
            "created_at": s.started_at,
            "completed_at": s.completed_at
        })
    return result

@router.get(
    "/patients/{patient_id}/history",
    summary="Get patient quiz history",
    response_model=List[Dict[str, Any]]
)
async def get_patient_quiz_history(
    patient_id: UUID,
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    return await get_patient_quiz_status(patient_id, db, current_user)

@router.get(
    "/links/active/",
    summary="Get active quiz links",
    response_model=List[Dict[str, Any]]
)
async def get_active_links(
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """Get all active (non-expired, non-completed) quiz links/sessions."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        now = datetime.now(timezone.utc)
        
        # Get active sessions (started, not expired)
        sessions = db.query(QuizSession).filter(
            QuizSession.status.in_(["started", "active"]),
        ).order_by(desc(QuizSession.started_at)).limit(50).all()
        
        result = []
        for s in sessions:
            # Check expiration
            if s.expiration_date and s.expiration_date < now:
                continue
                
            template = db.query(QuizTemplate).filter(QuizTemplate.id == s.quiz_template_id).first()
            patient = db.query(Patient).filter(Patient.id == s.patient_id).first()
            
            result.append({
                "id": str(s.id),
                "quiz_session_id": str(s.id),
                "patient_id": str(s.patient_id),
                "patient_name": patient.full_name if patient else "Unknown",
                "quiz_template_id": str(s.quiz_template_id),
                "template_name": template.name if template else "Unknown",
                "status": s.status,
                "expires_at": s.expiration_date.isoformat() if s.expiration_date else None,
                "created_at": s.started_at.isoformat() if s.started_at else None,
            })
        return result
    except Exception as e:
        logger.error(f"Error getting active links: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active links: {str(e)}"
        )

@router.get(
    "/stats/dashboard/",
    summary="Get dashboard quiz stats",
    response_model=QuizStatsDashboard
)
async def get_dashboard_stats(
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """Get dashboard statistics for monthly quizzes."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Aggregate stats
        total_active = db.query(QuizSession).filter(QuizSession.status == "started").count()
        total_completed = db.query(QuizSession).filter(QuizSession.status == "completed").count()
        total_expired = db.query(QuizSession).filter(QuizSession.status == "expired").count()
        total_sent = total_active + total_completed + total_expired  # Approximate

        # Avg score - with safe conversion
        completed_sessions = db.query(QuizSession).filter(QuizSession.status == "completed").all()
        scores = []
        for s in completed_sessions:
            if s.score is not None:
                try:
                    scores.append(float(s.score))
                except (TypeError, ValueError):
                    pass
        avg_score = sum(scores) / len(scores) if scores else 0.0

        completion_rate = (total_completed / total_sent * 100) if total_sent > 0 else 0.0
        expiration_rate = (total_expired / total_sent * 100) if total_sent > 0 else 0.0

        return QuizStatsDashboard(
            total_sent=total_sent,
            total_completed=total_completed,
            total_expired=total_expired,
            total_active=total_active,
            average_score=round(avg_score, 2),
            completion_rate=round(completion_rate, 2),
            expiration_rate=round(expiration_rate, 2)
        )
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard stats: {str(e)}"
        )

@router.get(
    "/monthly/{quiz_id}/statistics",
    response_model=MonthlyQuizStatisticsV2,
    summary="Get monthly quiz statistics",
    description="Get comprehensive statistics for a monthly quiz",
)
@limiter.limit("30/minute")
async def get_monthly_quiz_statistics(
    request: Request,
    quiz_id: UUID,
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Get monthly quiz statistics.

    **RBAC:** Admin and Doctors can view
    **Cache:** 2 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz statistics",
        )

    # Check cache
    cache_key = f"monthly_quiz_stats:{quiz_id}"
    if redis_cache:
        cached = redis_cache.get(cache_key)
        if cached:
            return MonthlyQuizStatisticsV2.parse_raw(cached)

    # Verify quiz exists
    quiz = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz")
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monthly quiz not found"
        )

    # Get sessions for this quiz
    sessions_query = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id
    )

    total_accessed = sessions_query.count()
    completed_sessions = sessions_query.filter(QuizSession.status == "completed").all()
    total_completed = len(completed_sessions)

    # Calculate statistics
    total_sent = quiz.tags.get("total_sent", 0)
    completion_rate = (total_completed / total_sent * 100) if total_sent > 0 else 0.0

    # Average score
    scores = [float(s.score) for s in completed_sessions if s.score is not None]
    average_score = sum(scores) / len(scores) if scores else None

    # Average completion time
    completion_times = []
    for session in completed_sessions:
        if session.completed_at and session.started_at:
            time_diff = (session.completed_at - session.started_at).total_seconds() / 60
            completion_times.append(time_diff)

    avg_completion_time = (
        sum(completion_times) / len(completion_times) if completion_times else None
    )

    # Responses by day
    responses_by_day = []
    if completed_sessions:
        day_counts = defaultdict(int)
        for session in completed_sessions:
            if session.completed_at:
                day_key = session.completed_at.strftime("%Y-%m-%d")
                day_counts[day_key] += 1

        responses_by_day = [
            {"date": day, "count": count} for day, count in sorted(day_counts.items())
        ]

    result = MonthlyQuizStatisticsV2(
        quiz_id=quiz_id,
        total_sent=total_sent,
        total_accessed=total_accessed,
        total_completed=total_completed,
        completion_rate=round(completion_rate, 2),
        average_score=round(average_score, 2) if average_score else None,
        average_completion_time_minutes=round(avg_completion_time, 2)
        if avg_completion_time
        else None,
        responses_by_day=responses_by_day,
    )

    # Cache result
    if redis_cache:
        redis_cache.setex(cache_key, CACHE_TTL_STATISTICS, result.json())

    return result
