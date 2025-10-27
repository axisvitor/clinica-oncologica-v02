"""
Analytics API v2
Enhanced analytics endpoints with caching and aggregation.
"""

from typing import Optional, Tuple
import json
import hashlib
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from datetime import datetime, timedelta
from uuid import UUID

from app.database import get_db
from app.models.quiz import QuizSession
from app.models.patient import Patient
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.schemas.v2.analytics import (
    AnalyticsOverview,
    QuizStatusDistribution,
    CompletionTrend,
    PatientEngagement,
    TreatmentDistribution,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Cache TTL in seconds (15 minutes for analytics)
ANALYTICS_CACHE_TTL = 900
COLOR_PALETTE = [
    "#2563eb",  # blue
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#0ea5e9",  # sky
]


def _get_role_and_user(current_user) -> Tuple[UserRole, Optional[UUID]]:
    """Extract role and user UUID from current_user which can be model or dict."""
    if isinstance(current_user, dict):
        role_value = current_user.get("role", "doctor")
        user_id = current_user.get("id")
    else:
        role_value = getattr(current_user, "role", "doctor")
        user_id = getattr(current_user, "id", None)

    # Optimize role conversion
    if isinstance(role_value, UserRole):
        role = role_value
    elif isinstance(role_value, str):
        role_lower = role_value.lower()
        if role_lower == "admin":
            role = UserRole.ADMIN
        else:
            role = UserRole.DOCTOR
    else:
        role = UserRole.DOCTOR

    # Optimize UUID conversion
    if user_id:
        try:
            user_uuid = UUID(str(user_id))
        except (TypeError, ValueError):
            user_uuid = None
    else:
        user_uuid = None

    return role, user_uuid


def _get_cache_key(endpoint: str, **params) -> str:
    """Generate cache key from endpoint and parameters."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()
    return f"analytics:v2:{endpoint}:{param_hash}"


async def _get_cached_result(cache_key: str):
    """Get cached result from Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            logger.debug("Redis not available, skipping cache read")
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


async def _set_cached_result(cache_key: str, data: dict, ttl: int = ANALYTICS_CACHE_TTL):
    """Set cached result in Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            logger.debug("Redis not available, skipping cache write")
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


@router.get(
    "/overview",
    response_model=AnalyticsOverview,
    summary="Get analytics overview",
    description="Get high-level analytics overview with key metrics (ADMIN/DOCTOR only)"
)
async def get_analytics_overview(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
):
    """
    Get analytics overview with key metrics.
    
    Returns:
    - Total patients
    - Total quizzes
    - Completion rate
    - Active patients (last 30 days)
    """
    role, user_uuid = _get_role_and_user(current_user)

    # Check cache first (include role/user context)
    cache_key = _get_cache_key(
        "overview",
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await _get_cached_result(cache_key)
    if cached_result:
        return cached_result
    
    # Total patients (active = not cancelled/inactive)
    from app.models.patient import FlowState
    patient_filters = [Patient.flow_state != FlowState.CANCELLED]
    if role != UserRole.ADMIN and user_uuid:
        patient_filters.append(Patient.doctor_id == user_uuid)

    total_patients = db.query(func.count(Patient.id)).filter(*patient_filters).scalar()
    
    # Total quizzes
    quiz_query = db.query(func.count(QuizSession.id)).join(
        Patient, Patient.id == QuizSession.patient_id
    )
    if role != UserRole.ADMIN and user_uuid:
        quiz_query = quiz_query.filter(Patient.doctor_id == user_uuid)
    if start_date:
        quiz_query = quiz_query.filter(QuizSession.created_at >= start_date)
    if end_date:
        quiz_query = quiz_query.filter(QuizSession.created_at <= end_date)
    total_quizzes = quiz_query.scalar()
    
    # Completed quizzes
    completed_query = (
        db.query(func.count(QuizSession.id))
        .join(Patient, Patient.id == QuizSession.patient_id)
        .filter(QuizSession.status == "completed")
    )
    if role != UserRole.ADMIN and user_uuid:
        completed_query = completed_query.filter(Patient.doctor_id == user_uuid)
    if start_date:
        completed_query = completed_query.filter(QuizSession.created_at >= start_date)
    if end_date:
        completed_query = completed_query.filter(QuizSession.created_at <= end_date)
    completed_quizzes = completed_query.scalar()
    
    # Completion rate
    completion_rate = (completed_quizzes / total_quizzes * 100) if total_quizzes > 0 else 0
    
    # Active patients (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_query = (
        db.query(func.count(func.distinct(QuizSession.patient_id)))
        .join(Patient, Patient.id == QuizSession.patient_id)
        .filter(QuizSession.created_at >= thirty_days_ago)
    )
    if role != UserRole.ADMIN and user_uuid:
        active_query = active_query.filter(Patient.doctor_id == user_uuid)
    active_patients = active_query.scalar()
    
    result = {
        "total_patients": total_patients,
        "total_quizzes": total_quizzes,
        "completed_quizzes": completed_quizzes,
        "completion_rate": round(completion_rate, 2),
        "active_patients_30d": active_patients,
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }
    }
    
    # Cache the result
    await _set_cached_result(cache_key, result)
    
    return result


@router.get(
    "/quiz-status",
    response_model=QuizStatusDistribution,
    summary="Get quiz status distribution",
    description="Get distribution of quiz statuses with optional filtering (ADMIN/DOCTOR only)"
)
async def get_quiz_status_distribution(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month"),
    year: Optional[int] = Query(None, ge=2020, description="Filter by year"),
):
    """
    Get quiz status distribution.
    
    Returns count of quizzes by status (started, completed, cancelled).
    """
    role, user_uuid = _get_role_and_user(current_user)

    # Check cache first
    cache_key = _get_cache_key(
        "quiz-status",
        month=month,
        year=year,
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await _get_cached_result(cache_key)
    if cached_result:
        return cached_result
    
    query = db.query(
        QuizSession.status,
        func.count(QuizSession.id).label("count")
    ).join(Patient, Patient.id == QuizSession.patient_id)

    if role != UserRole.ADMIN and user_uuid:
        query = query.filter(Patient.doctor_id == user_uuid)

    if month:
        query = query.filter(func.extract('month', QuizSession.created_at) == month)
    if year:
        query = query.filter(func.extract('year', QuizSession.created_at) == year)

    results = query.group_by(QuizSession.status).all()
    
    distribution = {status: count for status, count in results}
    
    # Ensure all statuses are present
    for status in ["started", "completed", "cancelled"]:
        if status not in distribution:
            distribution[status] = 0
    
    result = {
        "distribution": distribution,
        "total": sum(distribution.values()),
        "filters": {
            "month": month,
            "year": year,
        }
    }
    
    # Cache the result
    await _set_cached_result(cache_key, result)
    
    return result


@router.get(
    "/completion-trend",
    response_model=CompletionTrend,
    summary="Get completion trend",
    description="Get quiz completion trend over the last N months (ADMIN/DOCTOR only)"
)
async def get_completion_trend(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    months: int = Query(6, ge=1, le=24, description="Number of months to include"),
):
    """
    Get quiz completion trend over the last N months.
    
    Returns monthly completion rates.
    """
    role, user_uuid = _get_role_and_user(current_user)

    # Check cache first
    cache_key = _get_cache_key(
        "completion-trend",
        months=months,
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await _get_cached_result(cache_key)
    if cached_result:
        return cached_result
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=months * 30)
    
    # Get monthly stats using date functions
    results_query = db.query(
        func.extract('year', QuizSession.created_at).label('year'),
        func.extract('month', QuizSession.created_at).label('month'),
        func.count(QuizSession.id).label("total"),
        func.sum(
            case(
                (QuizSession.status == "completed", 1),
                else_=0
            )
        ).label("completed")
    ).join(Patient, Patient.id == QuizSession.patient_id).filter(
        QuizSession.created_at >= start_date
    )

    if role != UserRole.ADMIN and user_uuid:
        results_query = results_query.filter(Patient.doctor_id == user_uuid)

    results = results_query.group_by(
        func.extract('year', QuizSession.created_at),
        func.extract('month', QuizSession.created_at)
    ).order_by(
        func.extract('year', QuizSession.created_at),
        func.extract('month', QuizSession.created_at)
    ).all()
    
    trend = []
    for year, month, total, completed in results:
        completion_rate = (completed / total * 100) if total > 0 else 0
        trend.append({
            "year": int(year),
            "month": int(month),
            "total": total,
            "completed": completed,
            "completion_rate": round(completion_rate, 2)
        })
    
    result = {
        "trend": trend,
        "period": {
            "months": months,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    }
    
    # Cache the result
    await _set_cached_result(cache_key, result)
    
    return result


@router.get(
    "/patient-engagement",
    response_model=PatientEngagement,
    summary="Get patient engagement metrics",
    description="Get patient engagement statistics and distribution (ADMIN/DOCTOR only)"
)
async def get_patient_engagement(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Get patient engagement metrics.
    
    Returns:
    - Patients with 0 quizzes
    - Patients with 1-5 quizzes
    - Patients with 6+ quizzes
    - Average quizzes per patient
    """
    role, user_uuid = _get_role_and_user(current_user)

    # Check cache first
    cache_key = _get_cache_key(
        "patient-engagement",
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await _get_cached_result(cache_key)
    if cached_result:
        return cached_result
    
    # Get quiz counts per patient
    patient_query = db.query(
        Patient.id,
        func.count(QuizSession.id).label("quiz_count")
    ).outerjoin(
        QuizSession, Patient.id == QuizSession.patient_id
    )

    if role != UserRole.ADMIN and user_uuid:
        patient_query = patient_query.filter(Patient.doctor_id == user_uuid)

    patient_quiz_counts = patient_query.group_by(
        Patient.id
    ).all()
    
    # Categorize patients
    no_quizzes = sum(1 for _, count in patient_quiz_counts if count == 0)
    low_engagement = sum(1 for _, count in patient_quiz_counts if 1 <= count <= 5)
    high_engagement = sum(1 for _, count in patient_quiz_counts if count >= 6)
    
    # Calculate average
    total_quizzes = sum(count for _, count in patient_quiz_counts)
    avg_quizzes = total_quizzes / len(patient_quiz_counts) if patient_quiz_counts else 0
    
    result = {
        "engagement_levels": {
            "no_quizzes": no_quizzes,
            "low_engagement": low_engagement,  # 1-5 quizzes
            "high_engagement": high_engagement,  # 6+ quizzes
        },
        "average_quizzes_per_patient": round(avg_quizzes, 2),
        "total_active_patients": len(patient_quiz_counts),
    }
    
    # Cache the result
    await _set_cached_result(cache_key, result)
    
    return result


@router.get(
    "/treatment-distribution",
    response_model=TreatmentDistribution,
    summary="Get treatment distribution",
    description="Get patient distribution by treatment type (ADMIN/DOCTOR only)"
)
async def get_treatment_distribution(
    period: str = Query("30d", regex="^(7d|30d|90d|all)$", description="Analytics period"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Return treatment distribution data with optional period filtering."""
    try:
        logger.info(f"Starting treatment-distribution endpoint, period={period}")
        
        role, user_uuid = _get_role_and_user(current_user)
        logger.info(f"User role: {role}, user_uuid: {user_uuid}")
    except Exception as e:
        logger.error(f"Error getting role and user: {e}")
        raise

    try:
        cache_key = _get_cache_key(
            "treatment-distribution",
            period=period,
            role=role.value,
            user=str(user_uuid) if user_uuid else None,
        )
        logger.info(f"Cache key generated: {cache_key}")
        
        cached_result = await _get_cached_result(cache_key)
        if cached_result:
            logger.info("Returning cached result")
            return cached_result
        logger.info("No cached result, proceeding with database query")

        now = datetime.utcnow()
        period_map = {"7d": 7, "30d": 30, "90d": 90}
        start_date = now - timedelta(days=period_map.get(period, 30)) if period != "all" else None
        logger.info(f"Query period: {period}, start_date: {start_date}")
    except Exception as e:
        logger.error(f"Error in cache setup: {e}")
        raise

    try:
        logger.info("Building distribution query...")
        distribution_query = db.query(
            Patient.treatment_type,
            func.count(Patient.id).label("count"),
        )
        
        if role != UserRole.ADMIN and user_uuid:
            distribution_query = distribution_query.filter(Patient.doctor_id == user_uuid)
            logger.info(f"Filtered by doctor_id: {user_uuid}")
        
        if start_date:
            distribution_query = distribution_query.filter(Patient.created_at >= start_date)
            logger.info(f"Filtered by start_date: {start_date}")

        logger.info("Executing distribution query...")
        distribution_results = (
            distribution_query
            .group_by(Patient.treatment_type)
            .order_by(func.count(Patient.id).desc())
            .all()
        )
        logger.info(f"Distribution query returned {len(distribution_results)} results")
    except Exception as e:
        logger.error(f"Error in distribution query: {e}")
        raise

    total_patients = sum(count for _, count in distribution_results)
    distribution = []
    for index, (treatment_type, count) in enumerate(distribution_results):
        label = treatment_type or "Não informado"
        percentage = (count / total_patients * 100) if total_patients else 0
        distribution.append(
            {
                "treatment_type": label,
                "count": count,
                "percentage": round(percentage, 2),
                "color": COLOR_PALETTE[index % len(COLOR_PALETTE)],
            }
        )

    trend_query = db.query(
        func.date_trunc('week', Patient.created_at).label('week_start'),
        func.count(Patient.id).label('count'),
    )
    if role != UserRole.ADMIN and user_uuid:
        trend_query = trend_query.filter(Patient.doctor_id == user_uuid)
    if start_date:
        trend_query = trend_query.filter(Patient.created_at >= start_date)

    trend_results = (
        trend_query
        .group_by(func.date_trunc('week', Patient.created_at))
        .order_by(func.date_trunc('week', Patient.created_at))
        .limit(12)
        .all()
    )

    trend_data = []
    for week_start, count in trend_results:
        if week_start is not None:
            if hasattr(week_start, "date"):
                week_value = week_start.date().isoformat()
            else:
                week_value = str(week_start)
            trend_data.append({"week": week_value, "count": count})

    result = {
        "period": period,
        "total_patients": total_patients,
        "distribution": distribution,
        "trend_data": trend_data,
        "last_updated": now.isoformat(),
    }

    try:
        logger.info("Caching result...")
        await _set_cached_result(cache_key, result)
        logger.info("Result cached successfully")
        
        logger.info(f"Returning result with {result['total_patients']} patients")
        return result
    except Exception as e:
        logger.error(f"Error in final steps: {e}")
        raise
