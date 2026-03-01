"""
CRUD operations for monthly quiz responses.

Endpoints:
- GET /monthly/{quiz_id}/responses - Get responses for a monthly quiz
- GET /monthly/{quiz_id}/statistics - Get comprehensive statistics
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues

import inspect
import secrets
import string
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.domain.quizzes.session import TokenManager
from app.domain.quizzes.delivery import LinkBuilder

from ._shared import (
    UUID,
    defaultdict,
    get_async_db,
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
from .response_utils import build_quiz_response_detail

router = APIRouter()

_SHORT_CODE_ALPHABET = string.ascii_lowercase + string.digits
_SHORT_CODE_LENGTH = 8
_SHORT_CODE_MAX_ATTEMPTS = 5


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _cache_get(redis_cache, key: str):
    if not redis_cache:
        return None
    getter = getattr(redis_cache, "get", None)
    if not callable(getter):
        return None
    try:
        return await _maybe_await(getter(key))
    except Exception:
        return None


async def _cache_set(redis_cache, key: str, value: str, ttl: int) -> None:
    if not redis_cache:
        return
    setex = getattr(redis_cache, "setex", None)
    if callable(setex):
        try:
            await _maybe_await(setex(key, ttl, value))
        except Exception:
            pass
        return

    setter = getattr(redis_cache, "set", None)
    if not callable(setter):
        return

    try:
        await _maybe_await(setter(key, value, ex=ttl))
    except TypeError:
        try:
            await _maybe_await(setter(key, value, ttl))
        except Exception:
            pass
    except Exception:
        pass


async def _generate_unique_short_code(db: AsyncSession) -> str:
    for _ in range(_SHORT_CODE_MAX_ATTEMPTS):
        code = "".join(secrets.choice(_SHORT_CODE_ALPHABET) for _ in range(_SHORT_CODE_LENGTH))
        exists_result = await db.execute(
            select(QuizSession.id).where(QuizSession.session_metadata["short_code"].astext == code)
        )
        if exists_result.first() is None:
            return code
    raise RuntimeError("Failed to generate a unique short code")


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
    db: AsyncSession = Depends(get_async_db),
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
    quiz_result = await db.execute(
        select(QuizTemplate).where(
            QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz"
        )
    )
    quiz = quiz_result.scalar_one_or_none()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monthly quiz not found"
        )

    # Get responses for this quiz
    query = select(QuizResponse).where(QuizResponse.quiz_template_id == quiz_id)

    # Apply RBAC for doctors
    if current_user.role == UserRole.DOCTOR:
        patient_ids_result = await db.execute(
            select(Patient.id).where(Patient.doctor_id == current_user.id)
        )
        patient_ids = patient_ids_result.scalars().all()
        query = query.where(QuizResponse.patient_id.in_(patient_ids))

    # Apply pagination
    cursor_data = pagination.get("cursor_data")
    limit = pagination.get("limit", 20)

    if cursor_data:
        query = query.where(QuizResponse.id > cursor_data.get("id"))

    query = query.order_by(asc(QuizResponse.id))
    responses = (await db.execute(query.limit(limit + 1))).scalars().all()

    has_more = len(responses) > limit
    if has_more:
        responses = responses[:limit]

    # Enrich responses
    template_ids = {response.quiz_template_id for response in responses}
    session_ids = {
        response.quiz_session_id for response in responses if response.quiz_session_id
    }

    templates_by_id = {}
    if template_ids:
        templates_result = await db.execute(
            select(QuizTemplate).where(QuizTemplate.id.in_(template_ids))
        )
        templates_by_id = {template.id: template for template in templates_result.scalars().all()}

    sessions_by_id = {}
    if session_ids:
        sessions_result = await db.execute(
            select(QuizSession).where(QuizSession.id.in_(session_ids))
        )
        sessions_by_id = {session.id: session for session in sessions_result.scalars().all()}

    enriched_responses = []
    for response in responses:
        template = templates_by_id.get(response.quiz_template_id)
        session = sessions_by_id.get(response.quiz_session_id)
        enriched_responses.append(
            QuizResponseV2Detail(
                **build_quiz_response_detail(
                    response,
                    template=template,
                    session=session,
                )
            )
        )

    next_cursor = None
    if has_more and responses:
        last_item = responses[-1]
        next_cursor = create_cursor(last_item.id, last_item.created_at)

    total_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_query)).scalar_one()

    return QuizResponseV2List(
        data=enriched_responses, next_cursor=next_cursor, has_more=has_more, total=total
    )


# --- New Endpoints matching Frontend monthly-quiz.ts ---

from pydantic import BaseModel
from app.utils.timezone import now_sao_paulo

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
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """Create a quiz link (session + token)."""
    # Verify template
    template_result = await db.execute(
        select(QuizTemplate).where(QuizTemplate.id == link_data.quiz_template_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Quiz template not found")

    # Check/Create Session
    session_result = await db.execute(
        select(QuizSession).where(
            QuizSession.quiz_template_id == link_data.quiz_template_id,
            QuizSession.patient_id == link_data.patient_id,
            QuizSession.status.in_(["started", "active"]),
        )
    )
    session = session_result.scalar_one_or_none()

    if not session:
        session = QuizSession(
            patient_id=link_data.patient_id,
            quiz_template_id=link_data.quiz_template_id,
            status="started",
            started_at=now_sao_paulo(),
            session_metadata={
                "delivery_method": link_data.delivery_method,
                "custom_message": link_data.custom_message
            }
        )
        session.set_expiration_date(hours=link_data.expiry_hours)
        db.add(session)
        await db.commit()
        await db.refresh(session)
    
    # Ensure short code exists (for short link)
    metadata = session.session_metadata or {}
    if session.expiration_date and not metadata.get("expires_at"):
        metadata["expires_at"] = session.expiration_date.isoformat()
    metadata.setdefault("link_status", "active")
    if not metadata.get("short_code"):
        metadata["short_code"] = await _generate_unique_short_code(db)

    # Generate JWT token for access (patient/session scoped)
    token_manager = TokenManager()
    expires_at = session.expiration_date or (
        now_sao_paulo() + timedelta(hours=48)
    )
    token = token_manager.generate_token(
        patient_id=session.patient_id,
        quiz_template_id=session.quiz_template_id,
        expires_at=expires_at,
        session_id=session.id,
        token_type="quiz_access",
    )

    # Keep metadata synchronized with token/expiry used by resolver and monitoring.
    metadata["token_hash"] = token_manager.hash_token(token)
    metadata["expires_at"] = expires_at.isoformat()
    metadata["link_status"] = "active"
    session.expiration_date = expires_at
    session.session_metadata = metadata
    await db.commit()
    await db.refresh(session)

    # Construct Link using configured base URL (prefer short)
    link_builder = LinkBuilder()
    link = link_builder.build_preferred_link(token, metadata.get("short_code"))

    return QuizLinkResponse(
        id=session.id, # Session ID as Link ID for now
        quiz_session_id=session.id,
        patient_id=session.patient_id,
        quiz_template_id=session.quiz_template_id,
        link=link,
        token=token,
        status=session.status,
        expires_at=session.expiration_date or (now_sao_paulo() + timedelta(hours=48)),
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
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple)
):
    sessions = (
        await db.execute(
            select(QuizSession)
            .where(QuizSession.patient_id == patient_id)
            .order_by(desc(QuizSession.started_at))
            .limit(5)
        )
    ).scalars().all()

    template_ids = {session.quiz_template_id for session in sessions}
    templates_by_id = {}
    if template_ids:
        templates_result = await db.execute(
            select(QuizTemplate).where(QuizTemplate.id.in_(template_ids))
        )
        templates_by_id = {template.id: template for template in templates_result.scalars().all()}

    result = []
    for s in sessions:
        template = templates_by_id.get(s.quiz_template_id)
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
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple)
):
    return await get_patient_quiz_status(patient_id, db, current_user)

@router.get(
    "/links/active/",
    summary="Get active quiz links",
    response_model=List[Dict[str, Any]]
)
async def get_active_links(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """Get all active (non-expired, non-completed) quiz links/sessions."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        now = now_sao_paulo()
        
        # Get active sessions (started, not expired)
        sessions = (
            await db.execute(
                select(QuizSession)
                .where(QuizSession.status.in_(["started", "active"]))
                .order_by(desc(QuizSession.started_at))
                .limit(50)
            )
        ).scalars().all()

        template_ids = {session.quiz_template_id for session in sessions}
        patient_ids = {session.patient_id for session in sessions}

        templates_by_id = {}
        if template_ids:
            templates_result = await db.execute(
                select(QuizTemplate).where(QuizTemplate.id.in_(template_ids))
            )
            templates_by_id = {
                template.id: template for template in templates_result.scalars().all()
            }

        patients_by_id = {}
        if patient_ids:
            patients_result = await db.execute(
                select(Patient).where(Patient.id.in_(patient_ids))
            )
            patients_by_id = {
                patient.id: patient for patient in patients_result.scalars().all()
            }
        
        result = []
        for s in sessions:
            # Check expiration
            if s.expiration_date and s.expiration_date < now:
                continue
                
            template = templates_by_id.get(s.quiz_template_id)
            patient = patients_by_id.get(s.patient_id)
            
            result.append({
                "id": str(s.id),
                "quiz_session_id": str(s.id),
                "patient_id": str(s.patient_id),
                "patient_name": patient.name if patient and patient.name else "Unknown",
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
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """Get dashboard statistics for monthly quizzes."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Aggregate stats
        total_active = (
            await db.execute(
                select(func.count(QuizSession.id)).where(QuizSession.status == "started")
            )
        ).scalar_one()
        total_completed = (
            await db.execute(
                select(func.count(QuizSession.id)).where(QuizSession.status == "completed")
            )
        ).scalar_one()
        total_expired = (
            await db.execute(
                select(func.count(QuizSession.id)).where(QuizSession.status == "expired")
            )
        ).scalar_one()
        total_sent = total_active + total_completed + total_expired  # Approximate

        # Avg score - with safe conversion
        completed_sessions = (
            await db.execute(
                select(QuizSession).where(QuizSession.status == "completed")
            )
        ).scalars().all()
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
    db: AsyncSession = Depends(get_async_db),
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
        cached = await _cache_get(redis_cache, cache_key)
        if cached:
            return MonthlyQuizStatisticsV2.parse_raw(cached)

    # Verify quiz exists
    quiz_result = await db.execute(
        select(QuizTemplate).where(
            QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz"
        )
    )
    quiz = quiz_result.scalar_one_or_none()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monthly quiz not found"
        )

    # Get sessions for this quiz
    total_accessed = (
        await db.execute(
            select(func.count(QuizSession.id)).where(QuizSession.quiz_template_id == quiz_id)
        )
    ).scalar_one()
    completed_sessions = (
        await db.execute(
            select(QuizSession).where(
                QuizSession.quiz_template_id == quiz_id,
                QuizSession.status == "completed",
            )
        )
    ).scalars().all()
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
        await _cache_set(redis_cache, cache_key, result.json(), CACHE_TTL_STATISTICS)

    return result
