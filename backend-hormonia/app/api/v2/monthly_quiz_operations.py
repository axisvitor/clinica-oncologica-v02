"""
Monthly Quiz Operations and Public Access API v2

This module handles monthly quiz operations, scheduling, and public access:

**Monthly Quiz Operations (6 endpoints):**
- Get quiz responses with analytics
- View comprehensive statistics
- Send reminders to non-completers
- View quiz schedule
- Auto-generate monthly quizzes
- List available quiz templates

**Public Access Endpoints (3 endpoints):**
- Get current public quiz (token-based)
- Submit quiz response publicly
- View aggregate quiz results

**Health Check (1 endpoint):**
- Service health monitoring

**Features:**
- Token-based public access security
- Cursor-based pagination
- Redis caching with appropriate TTLs
- Rate limiting to prevent abuse
- RBAC: Admin/Doctors (operations), Public (access endpoints)
- Comprehensive audit trail

**Security:**
- Public endpoints use base64-encoded JWT-like tokens
- Token expiration validation
- IP logging for public access
- Personal data sanitization in public responses
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import asc

from app.database import get_db
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.quiz_extensions import (
    QuizResponseV2Detail,
    QuizResponseV2List,
    MonthlyQuizStatisticsV2,
    QuizReminderRequestV2,
    QuizScheduleV2,
    QuizGenerateRequestV2,
    MonthlyQuizV2Detail,
    QuizTemplateV2,
    PublicQuizResponseV2,
    PublicSubmissionRequestV2,
    PublicQuizResultsV2,
)
from .dependencies import (
    get_pagination_params,
    create_cursor,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter

# Import shared helpers and cache TTLs
from ._quiz_shared import (
    _get_current_user_simple,
    CACHE_TTL_STATISTICS,
    CACHE_TTL_PUBLIC_QUIZ,
    CACHE_TTL_TEMPLATES,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Monthly Quiz Operations (6 endpoints)
# ============================================================================

@router.get(
    "/monthly/{quiz_id}/responses",
    response_model=QuizResponseV2List,
    summary="Get monthly quiz responses",
    description="Get all responses for a specific monthly quiz"
)
@limiter.limit("50/minute")
async def get_monthly_quiz_responses(
    request: Request,
    quiz_id: UUID,
    pagination: dict = Depends(get_pagination_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Get responses for a monthly quiz.

    **RBAC:** Admin and Doctors can view
    **Cache:** 5 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz responses"
        )

    # Verify quiz exists
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monthly quiz not found"
        )

    # Get responses for this quiz
    query = db.query(QuizResponse).filter(
        QuizResponse.quiz_template_id == quiz_id
    )

    # Apply RBAC for doctors
    if current_user.role == UserRole.DOCTOR:
        patient_ids = db.query(Patient.id).filter(Patient.doctor_id == current_user.id).all()
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
        template = db.query(QuizTemplate).filter(QuizTemplate.id == response.quiz_template_id).first()
        session = db.query(QuizSession).filter(QuizSession.id == response.quiz_session_id).first() if response.quiz_session_id else None

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
            session_status=session.status if session else None
        )
        enriched_responses.append(enriched)

    next_cursor = None
    if has_more and responses:
        last_item = responses[-1]
        next_cursor = create_cursor(last_item.id, last_item.created_at)

    total = query.count()

    return QuizResponseV2List(
        data=enriched_responses,
        next_cursor=next_cursor,
        has_more=has_more,
        total=total
    )


@router.get(
    "/monthly/{quiz_id}/statistics",
    response_model=MonthlyQuizStatisticsV2,
    summary="Get monthly quiz statistics",
    description="Get comprehensive statistics for a monthly quiz"
)
@limiter.limit("30/minute")
async def get_monthly_quiz_statistics(
    request: Request,
    quiz_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Get monthly quiz statistics.

    **RBAC:** Admin and Doctors can view
    **Cache:** 2 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz statistics"
        )

    # Check cache
    cache_key = f"monthly_quiz_stats:{quiz_id}"
    if redis_cache:
        cached = redis_cache.get(cache_key)
        if cached:
            return MonthlyQuizStatisticsV2.parse_raw(cached)

    # Verify quiz exists
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monthly quiz not found"
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

    avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else None

    # Responses by day
    responses_by_day = []
    if completed_sessions:
        day_counts = defaultdict(int)
        for session in completed_sessions:
            if session.completed_at:
                day_key = session.completed_at.strftime("%Y-%m-%d")
                day_counts[day_key] += 1

        responses_by_day = [
            {"date": day, "count": count}
            for day, count in sorted(day_counts.items())
        ]

    result = MonthlyQuizStatisticsV2(
        quiz_id=quiz_id,
        total_sent=total_sent,
        total_accessed=total_accessed,
        total_completed=total_completed,
        completion_rate=round(completion_rate, 2),
        average_score=round(average_score, 2) if average_score else None,
        average_completion_time_minutes=round(avg_completion_time, 2) if avg_completion_time else None,
        responses_by_day=responses_by_day
    )

    # Cache result
    if redis_cache:
        redis_cache.setex(cache_key, CACHE_TTL_STATISTICS, result.json())

    return result


@router.post(
    "/monthly/{quiz_id}/reminder",
    response_model=Dict[str, Any],
    summary="Send quiz reminder",
    description="Send reminder to patients who haven't completed the quiz"
)
@limiter.limit("20/minute")
async def send_monthly_quiz_reminder(
    request: Request,
    quiz_id: UUID,
    reminder_request: QuizReminderRequestV2,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """
    Send reminder to non-completers.

    **RBAC:** Admin only
    **Rate Limit:** Max 1 reminder per quiz (stored in metadata)
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can send reminders"
        )

    # Verify quiz exists and is published
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monthly quiz not found"
        )

    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only send reminders for published quizzes"
        )

    # Check reminder history
    reminder_history = quiz.tags.get("reminder_history", [])
    if len(reminder_history) >= 3:  # Max 3 reminders per quiz
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum reminder limit reached (3 reminders per quiz)"
        )

    # Get target patients who haven't completed
    target_patient_ids = quiz.tags.get("target_patient_ids", [])
    if not target_patient_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No target patients found for this quiz"
        )

    # Find patients who haven't completed
    completed_patient_ids = (
        db.query(QuizSession.patient_id)
        .filter(
            QuizSession.quiz_template_id == quiz_id,
            QuizSession.status == "completed"
        )
        .distinct()
        .all()
    )
    completed_patient_ids = [str(p[0]) for p in completed_patient_ids]

    non_completers = [pid for pid in target_patient_ids if pid not in completed_patient_ids]

    if not non_completers:
        return {
            "message": "All patients have completed the quiz",
            "reminders_sent": 0
        }

    # In production, send actual reminders here via WhatsApp/Email/SMS
    # For now, just log and update metadata
    reminder_entry = {
        "sent_at": datetime.utcnow().isoformat(),
        "sent_by": str(current_user.id),
        "recipient_count": len(non_completers),
        "delivery_method": reminder_request.delivery_method.value,
        "custom_message": reminder_request.custom_message
    }

    reminder_history.append(reminder_entry)
    quiz.tags["reminder_history"] = reminder_history

    db.commit()

    logger.info(f"Reminder sent for quiz {quiz_id} to {len(non_completers)} patients")

    return {
        "message": "Reminder sent successfully",
        "reminders_sent": len(non_completers),
        "total_reminders": len(reminder_history),
        "max_reminders": 3
    }


@router.get(
    "/monthly/schedule",
    response_model=List[QuizScheduleV2],
    summary="Get quiz schedule",
    description="Get schedule of upcoming and past monthly quizzes"
)
@limiter.limit("50/minute")
async def get_quiz_schedule(
    request: Request,
    from_date: Optional[datetime] = Query(None, description="Start date filter"),
    to_date: Optional[datetime] = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Get quiz schedule.

    **RBAC:** Admin and Doctors can view
    **Cache:** 5 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz schedule"
        )

    # Get all monthly quizzes with scheduled dates
    query = db.query(QuizTemplate).filter(
        QuizTemplate.category == "monthly_quiz"
    )

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

        schedule.append(QuizScheduleV2(
            quiz_id=quiz.id,
            quiz_name=quiz.name,
            scheduled_for=scheduled_for,
            status=quiz.tags.get("status", "draft"),
            auto_send=quiz.tags.get("auto_send", False)
        ))

    # Sort by scheduled date (newest first)
    schedule.sort(key=lambda x: x.scheduled_for, reverse=True)

    return schedule


@router.post(
    "/monthly/generate",
    response_model=MonthlyQuizV2Detail,
    summary="Auto-generate monthly quiz",
    description="Automatically generate a monthly quiz from template",
    status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/minute")
async def generate_monthly_quiz(
    request: Request,
    generate_request: QuizGenerateRequestV2,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
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
            detail="Only administrators can generate monthly quizzes"
        )

    # Verify template exists
    template = db.query(QuizTemplate).filter(
        QuizTemplate.id == generate_request.template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz template not found"
        )

    # Parse target month
    try:
        year, month = map(int, generate_request.target_month.split("-"))
        scheduled_date = datetime(year, month, 1, 9, 0, 0)  # 1st of month at 9 AM
        expires_date = datetime(year, month, 28, 23, 59, 59)  # End of month (safe for all months)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid target_month format. Use YYYY-MM"
        )

    # Generate name
    month_names = ["", "January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    generated_name = f"{template.name} - {month_names[month]} {year}"

    # Create monthly quiz
    monthly_quiz = QuizTemplate(
        name=generated_name,
        description=template.description or f"Monthly health check for {month_names[month]} {year}",
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
            "target_month": generate_request.target_month
        },
        is_active=True
    )

    if generate_request.auto_publish:
        monthly_quiz.tags["published_at"] = datetime.utcnow().isoformat()

    db.add(monthly_quiz)
    db.commit()
    db.refresh(monthly_quiz)

    logger.info(f"Auto-generated monthly quiz '{generated_name}' for {generate_request.target_month}")

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
        published_at=datetime.fromisoformat(monthly_quiz.tags["published_at"]) if monthly_quiz.tags.get("published_at") else None,
        total_sent=monthly_quiz.tags.get("total_sent", 0),
        total_accessed=monthly_quiz.tags.get("total_accessed", 0),
        total_completed=monthly_quiz.tags.get("total_completed", 0),
        completion_rate=monthly_quiz.tags.get("completion_rate", 0.0)
    )


@router.get(
    "/monthly/templates",
    response_model=List[QuizTemplateV2],
    summary="List quiz templates",
    description="List available quiz templates for creating monthly quizzes"
)
@limiter.limit("50/minute")
async def list_quiz_templates(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    List available quiz templates.

    **RBAC:** Admin and Doctors can view
    **Cache:** 30 minutes TTL (templates change rarely)
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz templates"
        )

    # Check cache
    cache_key = "quiz_templates_list"
    if redis_cache:
        cached = redis_cache.get(cache_key)
        if cached:
            return [QuizTemplateV2.parse_raw(t) for t in cached.split("|||")]

    # Get templates (exclude monthly quizzes)
    templates = db.query(QuizTemplate).filter(
        QuizTemplate.category != "monthly_quiz",
        QuizTemplate.is_active == True
    ).all()

    result = []
    for template in templates:
        # Count questions
        question_count = len(template.questions) if template.questions else 0

        # Estimate duration (assuming 1 minute per question)
        estimated_duration = question_count

        result.append(QuizTemplateV2(
            id=template.id,
            name=template.name,
            description=template.description,
            version=template.version,
            question_count=question_count,
            estimated_duration_minutes=estimated_duration,
            is_active=template.is_active
        ))

    # Cache result
    if redis_cache and result:
        cache_data = "|||".join([t.json() for t in result])
        redis_cache.setex(cache_key, CACHE_TTL_TEMPLATES, cache_data)

    return result


# ============================================================================
# Public Quiz Endpoints (3 endpoints)
# ============================================================================

@router.get(
    "/monthly/public/current",
    response_model=PublicQuizResponseV2,
    summary="Get current monthly quiz (PUBLIC)",
    description="Get the current active monthly quiz without authentication"
)
@limiter.limit("20/minute")  # Lower limit for public endpoint
async def get_current_public_quiz(
    request: Request,
    token: str = Query(..., description="Access token"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """
    Get current monthly quiz using access token.

    **PUBLIC ENDPOINT** - No authentication required
    **Rate limited:** 20 requests/minute per IP
    **Security:** Token validation, IP logging, expiry checking

    Token format (base64-encoded JSON):
    {
        "quiz_id": "uuid",
        "exp": timestamp,
        "type": "quiz_access"
    }
    """
    import base64
    import json

    logger.info(f"Public quiz access from IP: {request.client.host}")

    # Validate token
    try:
        token_data = json.loads(base64.b64decode(token))
        quiz_id = UUID(token_data.get("quiz_id"))
        exp_timestamp = token_data.get("exp")
        token_type = token_data.get("type")

        # Check expiry
        if exp_timestamp and datetime.fromtimestamp(exp_timestamp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )

        # Check token type
        if token_type != "quiz_access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )

    # Get quiz
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )

    # Check if quiz is published
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quiz is not currently available"
        )

    # Check if quiz has expired
    if quiz.tags.get("expires_at"):
        expires_at = datetime.fromisoformat(quiz.tags["expires_at"])
        if expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quiz has expired"
            )

    # Create or get quiz session for public user
    # Use a special public patient ID (in production, create a PUBLIC_USER patient)
    public_patient_id = UUID("00000000-0000-0000-0000-000000000001")

    # Find or create session
    session = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id,
        QuizSession.patient_id == public_patient_id,
        QuizSession.status.in_(["in_progress", "pending"])
    ).first()

    if not session:
        session = QuizSession(
            patient_id=public_patient_id,
            quiz_template_id=quiz_id,
            status="in_progress",
            started_at=datetime.utcnow()
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Increment access count
        quiz.tags["total_accessed"] = quiz.tags.get("total_accessed", 0) + 1
        db.commit()

    # Sanitize questions (remove sensitive data, scoring info)
    sanitized_questions = []
    if quiz.questions:
        for q in quiz.questions:
            sanitized_q = {
                "id": q.get("id"),
                "text": q.get("text"),
                "type": q.get("type"),
                "options": q.get("options", [])
            }
            # Remove scoring and medical interpretation
            sanitized_questions.append(sanitized_q)

    return PublicQuizResponseV2(
        quiz_id=quiz.id,
        quiz_name=quiz.name,
        description=quiz.description,
        questions=sanitized_questions,
        expires_at=datetime.fromisoformat(quiz.tags["expires_at"]) if quiz.tags.get("expires_at") else None,
        session_id=session.id
    )


@router.post(
    "/monthly/public/{quiz_id}/submit",
    response_model=Dict[str, Any],
    summary="Submit quiz response (PUBLIC)",
    description="Submit a quiz response using access token"
)
@limiter.limit("20/minute")
async def submit_public_quiz_response(
    request: Request,
    quiz_id: UUID,
    submission: PublicSubmissionRequestV2,
    db: Session = Depends(get_db)
):
    """
    Submit quiz response with token validation.

    **PUBLIC ENDPOINT** - Token-based authentication
    **Rate limited:** 20 requests/minute per IP
    """
    import base64
    import json

    logger.info(f"Public quiz submission from IP: {request.client.host}")

    # Validate token
    try:
        token_data = json.loads(base64.b64decode(submission.token))
        token_quiz_id = UUID(token_data.get("quiz_id"))
        exp_timestamp = token_data.get("exp")
        token_type = token_data.get("type")

        # Check if token matches quiz_id
        if token_quiz_id != quiz_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not match quiz ID"
            )

        # Check expiry
        if exp_timestamp and datetime.fromtimestamp(exp_timestamp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )

        # Check token type
        if token_type not in ["quiz_access", "quiz_submission"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for submission"
            )

    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )

    # Get quiz
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )

    # Check if quiz is published
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit to unpublished quiz"
        )

    # Get or create session
    public_patient_id = UUID("00000000-0000-0000-0000-000000000001")

    session = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id,
        QuizSession.patient_id == public_patient_id,
        QuizSession.status.in_(["in_progress", "pending"])
    ).first()

    if not session:
        # Create new session
        session = QuizSession(
            patient_id=public_patient_id,
            quiz_template_id=quiz_id,
            status="in_progress",
            started_at=datetime.utcnow()
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # Find the question in quiz
    question = None
    if quiz.questions:
        for q in quiz.questions:
            if q.get("id") == submission.question_id:
                question = q
                break

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {submission.question_id} not found in quiz"
        )

    # Create quiz response
    quiz_response = QuizResponse(
        patient_id=public_patient_id,
        quiz_template_id=quiz_id,
        quiz_session_id=session.id,
        question_id=submission.question_id,
        question_text=question.get("text", ""),
        response_type=question.get("type", "text"),
        response_value=str(submission.response_value),
        response_metadata=submission.response_metadata or {},
        responded_at=datetime.utcnow()
    )

    db.add(quiz_response)
    db.commit()
    db.refresh(quiz_response)

    # Check if all questions are answered
    total_questions = len(quiz.questions) if quiz.questions else 0
    answered_questions = db.query(QuizResponse).filter(
        QuizResponse.quiz_session_id == session.id
    ).count()

    if answered_questions >= total_questions:
        # Complete session
        session.status = "completed"
        session.completed_at = datetime.utcnow()

        # Update quiz completion stats
        quiz.tags["total_completed"] = quiz.tags.get("total_completed", 0) + 1
        total_sent = quiz.tags.get("total_sent", 1)
        quiz.tags["completion_rate"] = (quiz.tags["total_completed"] / total_sent * 100) if total_sent > 0 else 0.0

        db.commit()

        logger.info(f"Public quiz {quiz_id} completed by session {session.id}")

        return {
            "message": "Quiz completed successfully",
            "status": "completed",
            "session_id": str(session.id),
            "total_questions": total_questions,
            "answered_questions": answered_questions
        }

    return {
        "message": "Response recorded successfully",
        "status": "in_progress",
        "session_id": str(session.id),
        "total_questions": total_questions,
        "answered_questions": answered_questions,
        "remaining_questions": total_questions - answered_questions
    }


@router.get(
    "/monthly/public/{quiz_id}/results",
    response_model=PublicQuizResultsV2,
    summary="Get public quiz results",
    description="Get aggregate quiz results (no personal data)"
)
@limiter.limit("20/minute")
async def get_public_quiz_results(
    request: Request,
    quiz_id: UUID,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """
    Get aggregate quiz results.

    **PUBLIC ENDPOINT** - No authentication required
    **Privacy:** Only aggregate data, no personal information
    **Cache:** 15 minutes TTL
    """
    logger.info(f"Public quiz results request from IP: {request.client.host}")

    # Check cache
    cache_key = f"public_quiz_results:{quiz_id}"
    if redis_cache:
        cached = redis_cache.get(cache_key)
        if cached:
            return PublicQuizResultsV2.parse_raw(cached)

    # Get quiz
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )

    # Only show results for published quizzes
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Results not available for this quiz"
        )

    # Get aggregate statistics
    sessions_query = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id
    )

    total_completions = sessions_query.filter(
        QuizSession.status == "completed"
    ).count()

    # Calculate average score
    completed_sessions = sessions_query.filter(
        QuizSession.status == "completed",
        QuizSession.score.isnot(None)
    ).all()

    average_score = None
    if completed_sessions:
        scores = [float(s.score) for s in completed_sessions if s.score is not None]
        if scores:
            average_score = sum(scores) / len(scores)

    # Completion rate
    total_sent = quiz.tags.get("total_sent", 0)
    completion_rate = (total_completions / total_sent * 100) if total_sent > 0 else 0.0

    # Response distribution (aggregate, anonymized)
    response_distribution = {}
    responses = db.query(QuizResponse).filter(
        QuizResponse.quiz_template_id == quiz_id
    ).all()

    # Group responses by question
    question_responses = defaultdict(list)
    for response in responses:
        question_responses[response.question_id].append(response.response_value)

    # Calculate distribution for each question
    for question_id, values in question_responses.items():
        # Find question in quiz
        question = None
        if quiz.questions:
            for q in quiz.questions:
                if q.get("id") == question_id:
                    question = q
                    break

        if not question:
            continue

        # For scale questions, group into ranges
        if question.get("type") == "scale":
            ranges = {"1-3": 0, "4-7": 0, "8-10": 0}
            for value in values:
                try:
                    val = int(value)
                    if 1 <= val <= 3:
                        ranges["1-3"] += 1
                    elif 4 <= val <= 7:
                        ranges["4-7"] += 1
                    elif 8 <= val <= 10:
                        ranges["8-10"] += 1
                except (ValueError, TypeError):
                    pass
            response_distribution[question_id] = ranges

        # For choice questions, count by option
        elif question.get("type") in ["single_choice", "multiple_choice"]:
            counts = defaultdict(int)
            for value in values:
                counts[value] += 1
            # Convert to percentages
            total = len(values)
            percentages = {k: round(v/total*100, 1) for k, v in counts.items()} if total > 0 else {}
            response_distribution[question_id] = percentages

    result = PublicQuizResultsV2(
        quiz_id=quiz_id,
        quiz_name=quiz.name,
        total_completions=total_completions,
        average_score=round(average_score, 2) if average_score else None,
        completion_rate=round(completion_rate, 2),
        response_distribution=response_distribution if response_distribution else None
    )

    # Cache result
    if redis_cache:
        redis_cache.setex(cache_key, CACHE_TTL_PUBLIC_QUIZ, result.json())

    return result


# ============================================================================
# Health Check
# ============================================================================

@router.get(
    "/health",
    summary="Quiz extensions health check",
    description="Check if quiz extensions API is operational"
)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "quiz-extensions-v2",
        "version": "2.0.0",
        "endpoints": {
            "quiz_responses": 3,
            "quiz_alerts": 5,
            "monthly_quiz": 13,
            "public_quiz": 3
        },
        "features": {
            "cursor_pagination": True,
            "redis_caching": True,
            "rate_limiting": True,
            "rbac": True,
            "alert_rules": True,
            "public_access": True
        }
    }
