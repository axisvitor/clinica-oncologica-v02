"""
CRUD operations for monthly quiz responses.

Endpoints:
- GET /monthly/{quiz_id}/responses - Get responses for a monthly quiz
- GET /monthly/{quiz_id}/statistics - Get comprehensive statistics
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues

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
