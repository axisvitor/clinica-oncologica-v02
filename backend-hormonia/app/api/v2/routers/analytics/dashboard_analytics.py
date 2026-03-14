"""
Dashboard Analytics Module
Handles overview, treatment distribution and consolidated dashboard metrics.
"""

from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.quiz import QuizSession
from app.models.patient import Patient, FlowState
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.schemas.v2.analytics import (
    AnalyticsOverview,
    TreatmentDistribution,
)
from app.utils.logging import get_logger

from .base import (
    get_role_and_user,
    get_cache_key,
    get_cached_result,
    set_cached_result,
    COLOR_PALETTE,
)
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/overview",
    response_model=AnalyticsOverview,
    summary="Get analytics overview",
    description="Get high-level analytics overview with key metrics (ADMIN/DOCTOR only)",
)
async def get_analytics_overview(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    start_date: Optional[datetime] = Query(
        None, description="Start date for filtering"
    ),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
):
    """
    Get analytics overview with key metrics.

    Returns:
    - Total patients
    - Total quizzes
    - Completion rate
    - Active patients (last 30 days)

    Args:
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering

    Returns:
        Dict with overview metrics and period information
    """
    role, user_uuid = get_role_and_user(current_user)

    # Check cache first (include role/user context)
    cache_key = get_cache_key(
        "overview",
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await get_cached_result(cache_key)
    if cached_result:
        return cached_result

    # Total patients (active = not cancelled/inactive)
    patient_stmt = select(func.count(Patient.id)).where(
        cast(Patient.flow_state, String) != FlowState.CANCELLED.value
    )
    if role != UserRole.ADMIN and user_uuid:
        patient_stmt = patient_stmt.where(Patient.doctor_id == user_uuid)
    total_patients = (await db.execute(patient_stmt)).scalar() or 0

    # Total quizzes
    quiz_stmt = (
        select(func.count(QuizSession.id))
        .join(Patient, Patient.id == QuizSession.patient_id)
    )
    if role != UserRole.ADMIN and user_uuid:
        quiz_stmt = quiz_stmt.where(Patient.doctor_id == user_uuid)
    if start_date:
        quiz_stmt = quiz_stmt.where(QuizSession.created_at >= start_date)
    if end_date:
        quiz_stmt = quiz_stmt.where(QuizSession.created_at <= end_date)
    total_quizzes = (await db.execute(quiz_stmt)).scalar() or 0

    # Completed quizzes
    completed_stmt = (
        select(func.count(QuizSession.id))
        .join(Patient, Patient.id == QuizSession.patient_id)
        .where(QuizSession.status == "completed")
    )
    if role != UserRole.ADMIN and user_uuid:
        completed_stmt = completed_stmt.where(Patient.doctor_id == user_uuid)
    if start_date:
        completed_stmt = completed_stmt.where(QuizSession.created_at >= start_date)
    if end_date:
        completed_stmt = completed_stmt.where(QuizSession.created_at <= end_date)
    completed_quizzes = (await db.execute(completed_stmt)).scalar() or 0

    # Completion rate
    completion_rate = (
        (completed_quizzes / total_quizzes * 100) if total_quizzes > 0 else 0
    )

    # Active patients (last 30 days)
    thirty_days_ago = now_sao_paulo() - timedelta(days=30)
    active_stmt = (
        select(func.count(func.distinct(QuizSession.patient_id)))
        .join(Patient, Patient.id == QuizSession.patient_id)
        .where(QuizSession.created_at >= thirty_days_ago)
    )
    if role != UserRole.ADMIN and user_uuid:
        active_stmt = active_stmt.where(Patient.doctor_id == user_uuid)
    active_patients = (await db.execute(active_stmt)).scalar() or 0

    result = {
        "total_patients": total_patients,
        "total_quizzes": total_quizzes,
        "completed_quizzes": completed_quizzes,
        "completion_rate": round(completion_rate, 2),
        "active_patients_30d": active_patients,
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    }

    # Cache the result
    await set_cached_result(cache_key, result)

    return result


@router.get(
    "/treatment-distribution",
    response_model=TreatmentDistribution,
    summary="Get treatment distribution",
    description="Get patient distribution by treatment type (ADMIN/DOCTOR only)",
)
async def get_treatment_distribution(
    period: str = Query(
        "30d", pattern="^(7d|30d|90d|all)$", description="Analytics period"
    ),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Return treatment distribution data with optional period filtering.

    Args:
        period: Time period for analysis (7d, 30d, 90d, all)

    Returns:
        Dict with distribution by treatment type and weekly trend data
    """
    try:
        logger.info(f"Starting treatment-distribution endpoint, period={period}")

        role, user_uuid = get_role_and_user(current_user)
        logger.info(f"User role: {role}, user_uuid: {user_uuid}")
    except Exception as e:
        logger.error(f"Error getting role and user: {e}")
        raise

    try:
        cache_key = get_cache_key(
            "treatment-distribution",
            period=period,
            role=role.value,
            user=str(user_uuid) if user_uuid else None,
        )
        logger.info(f"Cache key generated: {cache_key}")

        cached_result = await get_cached_result(cache_key)
        if cached_result:
            logger.info("Returning cached result")
            return cached_result
        logger.info("No cached result, proceeding with database query")

        now = now_sao_paulo()
        period_map = {"7d": 7, "30d": 30, "90d": 90}
        start_date = (
            now - timedelta(days=period_map.get(period, 30))
            if period != "all"
            else None
        )
        logger.info(f"Query period: {period}, start_date: {start_date}")
    except Exception as e:
        logger.error(f"Error in cache setup: {e}")
        raise

    try:
        logger.info("Building distribution query...")
        distribution_stmt = select(
            Patient.treatment_type,
            func.count(Patient.id).label("count"),
        )

        if role != UserRole.ADMIN and user_uuid:
            distribution_stmt = distribution_stmt.where(
                Patient.doctor_id == user_uuid
            )
            logger.info(f"Filtered by doctor_id: {user_uuid}")

        if start_date:
            distribution_stmt = distribution_stmt.where(
                Patient.created_at >= start_date
            )
            logger.info(f"Filtered by start_date: {start_date}")

        distribution_stmt = (
            distribution_stmt.group_by(Patient.treatment_type)
            .order_by(func.count(Patient.id).desc())
        )

        logger.info("Executing distribution query...")
        distribution_results = (await db.execute(distribution_stmt)).all()
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

    try:
        logger.info("Building trend query...")
        # Use a subquery or alias to avoid GROUP BY issues
        week_start_expr = func.date_trunc("week", Patient.created_at)

        trend_stmt = select(
            week_start_expr.label("week_start"),
            func.count(Patient.id).label("count"),
        )

        if role != UserRole.ADMIN and user_uuid:
            trend_stmt = trend_stmt.where(Patient.doctor_id == user_uuid)
            logger.info(f"Trend filtered by doctor_id: {user_uuid}")

        if start_date:
            trend_stmt = trend_stmt.where(Patient.created_at >= start_date)
            logger.info(f"Trend filtered by start_date: {start_date}")

        trend_stmt = (
            trend_stmt.group_by(week_start_expr)
            .order_by(week_start_expr)
            .limit(12)
        )

        logger.info("Executing trend query...")
        trend_results = (await db.execute(trend_stmt)).all()
        logger.info(f"Trend query returned {len(trend_results)} results")
    except Exception as e:
        logger.error(f"Error in trend query: {e}")
        raise

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
        await set_cached_result(cache_key, result)
        logger.info("Result cached successfully")
    except Exception as cache_error:
        logger.warning(f"Failed to cache analytics result: {cache_error}")

    logger.info(f"Returning result with {result['total_patients']} patients")
    return result


@router.get(
    "/patient-status",
    summary="Get patient status distribution",
    description="Get count of patients by flow state (active, paused, completed, etc.)",
)
async def get_patient_status_distribution(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Get patient status distribution.

    Returns count of patients grouped by their flow state:
    - active: Currently receiving treatment
    - paused: Treatment temporarily suspended
    - completed: Treatment finished
    - onboarding: Initial setup
    - cancelled: Archived/cancelled
    """
    role, user_uuid = get_role_and_user(current_user)

    # Check cache first
    cache_key = get_cache_key(
        "patient-status",
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await get_cached_result(cache_key)
    if cached_result:
        return cached_result

    # Query patient counts by flow_state
    stmt = select(
        Patient.flow_state,
        func.count(Patient.id).label("count")
    )

    # Filter by doctor if not admin
    if role != UserRole.ADMIN and user_uuid:
        stmt = stmt.where(Patient.doctor_id == user_uuid)

    stmt = stmt.group_by(Patient.flow_state)
    results = (await db.execute(stmt)).all()

    # Build distribution dict
    status_counts = {
        "active": 0,
        "paused": 0,
        "completed": 0,
        "onboarding": 0,
        "cancelled": 0,
    }

    for flow_state, count in results:
        if flow_state:
            state_value = flow_state.value if hasattr(flow_state, 'value') else str(flow_state)
            if state_value in status_counts:
                status_counts[state_value] = count

    total = sum(status_counts.values())

    result = {
        "distribution": status_counts,
        "total": total,
        "active_percentage": round((status_counts["active"] / total * 100) if total > 0 else 0, 1),
    }

    # Cache the result
    await set_cached_result(cache_key, result)

    return result
