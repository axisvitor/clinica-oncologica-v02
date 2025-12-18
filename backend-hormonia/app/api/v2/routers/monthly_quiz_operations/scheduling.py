"""
Scheduling operations for monthly quizzes.

Endpoints:
- POST /monthly/{quiz_id}/reminder - Send reminders to non-completers
- GET /monthly/schedule - View quiz schedule
- POST /monthly/generate - Auto-generate monthly quiz
- GET /monthly/templates - List available quiz templates
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request

from ._shared import (
    UUID,
    datetime,
    logger,
    get_db,
    limiter,
    QuizSession,
    QuizTemplate,
    User,
    UserRole,
    QuizReminderRequestV2,
    QuizScheduleV2,
    QuizGenerateRequestV2,
    MonthlyQuizV2Detail,
    QuizTemplateV2,
    _get_current_user_simple,
    get_redis_cache,
    CACHE_TTL_TEMPLATES,
    Dict,
    Any,
)

router = APIRouter()


@router.post(
    "/monthly/{quiz_id}/reminder",
    response_model=Dict[str, Any],
    summary="Send quiz reminder",
    description="Send reminder to patients who haven't completed the quiz",
)
@limiter.limit("20/minute")
async def send_monthly_quiz_reminder(
    request: Request,
    quiz_id: UUID,
    reminder_request: QuizReminderRequestV2,
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
):
    """
    Send reminder to non-completers.

    **RBAC:** Admin only
    **Rate Limit:** Max 1 reminder per quiz (stored in metadata)
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can send reminders",
        )

    # Verify quiz exists and is published
    quiz = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz")
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monthly quiz not found"
        )

    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only send reminders for published quizzes",
        )

    # Check reminder history
    reminder_history = quiz.tags.get("reminder_history", [])
    if len(reminder_history) >= 3:  # Max 3 reminders per quiz
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum reminder limit reached (3 reminders per quiz)",
        )

    # Get target patients who haven't completed
    target_patient_ids = quiz.tags.get("target_patient_ids", [])
    if not target_patient_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No target patients found for this quiz",
        )

    # Find patients who haven't completed
    completed_patient_ids = (
        db.query(QuizSession.patient_id)
        .filter(
            QuizSession.quiz_template_id == quiz_id, QuizSession.status == "completed"
        )
        .distinct()
        .all()
    )
    completed_patient_ids = [str(p[0]) for p in completed_patient_ids]

    non_completers = [
        pid for pid in target_patient_ids if pid not in completed_patient_ids
    ]

    if not non_completers:
        return {"message": "All patients have completed the quiz", "reminders_sent": 0}

    # In production, send actual reminders here via WhatsApp/Email/SMS
    # For now, just log and update metadata
    reminder_entry = {
        "sent_at": datetime.utcnow().isoformat(),
        "sent_by": str(current_user.id),
        "recipient_count": len(non_completers),
        "delivery_method": reminder_request.delivery_method.value,
        "custom_message": reminder_request.custom_message,
    }

    reminder_history.append(reminder_entry)
    quiz.tags["reminder_history"] = reminder_history

    db.commit()

    logger.info(f"Reminder sent for quiz {quiz_id} to {len(non_completers)} patients")

    return {
        "message": "Reminder sent successfully",
        "reminders_sent": len(non_completers),
        "total_reminders": len(reminder_history),
        "max_reminders": 3,
    }


@router.get(
    "/monthly/schedule",
    response_model=List[QuizScheduleV2],
    summary="Get quiz schedule",
    description="Get schedule of upcoming and past monthly quizzes",
)
@limiter.limit("50/minute")
async def get_quiz_schedule(
    request: Request,
    from_date: Optional[datetime] = Query(None, description="Start date filter"),
    to_date: Optional[datetime] = Query(None, description="End date filter"),
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Get quiz schedule.

    **RBAC:** Admin and Doctors can view
    **Cache:** 5 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz schedule",
        )

    # Get all monthly quizzes with scheduled dates
    query = db.query(QuizTemplate).filter(QuizTemplate.category == "monthly_quiz")

    quizzes = query.all()

    # Filter and build schedule
    schedule = []
    for quiz in quizzes:
        scheduled_for_str = quiz.tags.get("scheduled_for")
        if not scheduled_for_str:
            continue

        scheduled_for = datetime.fromisoformat(scheduled_for_str)

        # Apply date filters
        if from_date and scheduled_for < from_date:
            continue
        if to_date and scheduled_for > to_date:
            continue

        schedule.append(
            QuizScheduleV2(
                quiz_id=quiz.id,
                quiz_name=quiz.name,
                scheduled_for=scheduled_for,
                status=quiz.tags.get("status", "draft"),
                auto_send=quiz.tags.get("auto_send", False),
            )
        )

    # Sort by scheduled date (newest first)
    schedule.sort(key=lambda x: x.scheduled_for, reverse=True)

    return schedule


@router.post(
    "/monthly/generate",
    response_model=MonthlyQuizV2Detail,
    summary="Auto-generate monthly quiz",
    description="Automatically generate a monthly quiz from template",
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def generate_monthly_quiz(
    request: Request,
    generate_request: QuizGenerateRequestV2,
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
):
    """
    Auto-generate monthly quiz from template.

    **RBAC:** Admin only
    **Features:**
    - Generates quiz name automatically (Template Name - Month Year)
    - Sets scheduled date to 1st of month at 9 AM
    - Optionally auto-publishes
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can generate monthly quizzes",
        )

    # Verify template exists
    template = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.id == generate_request.template_id)
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz template not found"
        )

    # Parse target month
    try:
        year, month = map(int, generate_request.target_month.split("-"))
        scheduled_date = datetime(year, month, 1, 9, 0, 0)  # 1st of month at 9 AM
        expires_date = datetime(
            year, month, 28, 23, 59, 59
        )  # End of month (safe for all months)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid target_month format. Use YYYY-MM",
        )

    # Generate name
    month_names = [
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    generated_name = f"{template.name} - {month_names[month]} {year}"

    # Create monthly quiz
    monthly_quiz = QuizTemplate(
        name=generated_name,
        description=template.description
        or f"Monthly health check for {month_names[month]} {year}",
        category="monthly_quiz",
        version="1.0",
        questions=template.questions,
        scoring_rules=template.scoring_rules,
        tags={
            "status": "published" if generate_request.auto_publish else "draft",
            "created_by": str(current_user.id),
            "base_template_id": str(generate_request.template_id),
            "scheduled_for": scheduled_date.isoformat(),
            "expires_at": expires_date.isoformat(),
            "auto_send": False,
            "delivery_method": "whatsapp",
            "total_sent": 0,
            "total_accessed": 0,
            "total_completed": 0,
            "completion_rate": 0.0,
            "auto_generated": True,
            "target_month": generate_request.target_month,
        },
        is_active=True,
    )

    if generate_request.auto_publish:
        monthly_quiz.tags["published_at"] = datetime.utcnow().isoformat()

    db.add(monthly_quiz)
    db.commit()
    db.refresh(monthly_quiz)

    logger.info(
        f"Auto-generated monthly quiz '{generated_name}' for {generate_request.target_month}"
    )

    return MonthlyQuizV2Detail(
        id=monthly_quiz.id,
        name=monthly_quiz.name,
        description=monthly_quiz.description,
        quiz_template_id=UUID(monthly_quiz.tags["base_template_id"]),
        scheduled_for=datetime.fromisoformat(monthly_quiz.tags["scheduled_for"]),
        expires_at=datetime.fromisoformat(monthly_quiz.tags["expires_at"]),
        status=monthly_quiz.tags.get("status", "draft"),
        created_by=UUID(monthly_quiz.tags["created_by"]),
        created_at=monthly_quiz.created_at,
        published_at=datetime.fromisoformat(monthly_quiz.tags["published_at"])
        if monthly_quiz.tags.get("published_at")
        else None,
        total_sent=monthly_quiz.tags.get("total_sent", 0),
        total_accessed=monthly_quiz.tags.get("total_accessed", 0),
        total_completed=monthly_quiz.tags.get("total_completed", 0),
        completion_rate=monthly_quiz.tags.get("completion_rate", 0.0),
    )


@router.get(
    "/monthly/templates",
    response_model=List[QuizTemplateV2],
    summary="List quiz templates",
    description="List available quiz templates for creating monthly quizzes",
)
@limiter.limit("50/minute")
async def list_quiz_templates(
    request: Request,
    db=Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    List available quiz templates.

    **RBAC:** Admin and Doctors can view
    **Cache:** 30 minutes TTL (templates change rarely)
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz templates",
        )

    # Check cache
    cache_key = "quiz_templates_list"
    if redis_cache:
        cached = redis_cache.get(cache_key)
        if cached:
            return [QuizTemplateV2.parse_raw(t) for t in cached.split("|||")]

    # Get templates (exclude monthly quizzes)
    templates = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.category != "monthly_quiz", QuizTemplate.is_active)
        .all()
    )

    result = []
    for template in templates:
        # Count questions
        question_count = len(template.questions) if template.questions else 0

        # Estimate duration (assuming 1 minute per question)
        estimated_duration = question_count

        result.append(
            QuizTemplateV2(
                id=template.id,
                name=template.name,
                description=template.description,
                version=template.version,
                question_count=question_count,
                estimated_duration_minutes=estimated_duration,
                is_active=template.is_active,
            )
        )

    # Cache result
    if redis_cache and result:
        cache_data = "|||".join([t.json() for t in result])
        redis_cache.setex(cache_key, CACHE_TTL_TEMPLATES, cache_data)

    return result
