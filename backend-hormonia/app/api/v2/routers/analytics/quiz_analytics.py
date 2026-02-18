"""
Quiz Analytics Module
Handles quiz-related analytics, status distribution and completion trends.
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues

from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case

from app.database import get_db
from app.models.quiz import QuizSession
from app.models.patient import Patient
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.schemas.v2.analytics import (
    QuizStatusDistribution,
    CompletionTrend,
)
from app.utils.logging import get_logger

from .base import (
    get_role_and_user,
    get_cache_key,
    get_cached_result,
    set_cached_result,
)
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/quiz-status",
    response_model=QuizStatusDistribution,
    summary="Get quiz status distribution",
    description="Get distribution of quiz statuses with optional filtering (ADMIN/DOCTOR only)",
)
async def get_quiz_status_distribution(
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month"),
    year: Optional[int] = Query(None, ge=2020, description="Filter by year"),
):
    """
    Get quiz status distribution.

    Returns count of quizzes by status (started, completed, cancelled).

    Args:
        month: Optional month filter (1-12)
        year: Optional year filter

    Returns:
        Dict with distribution by status and totals
    """
    role, user_uuid = get_role_and_user(current_user)

    # Check cache first
    cache_key = get_cache_key(
        "quiz-status",
        month=month,
        year=year,
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await get_cached_result(cache_key)
    if cached_result:
        return cached_result

    query = db.query(
        QuizSession.status, func.count(QuizSession.id).label("count")
    ).join(Patient, Patient.id == QuizSession.patient_id)

    if role != UserRole.ADMIN and user_uuid:
        query = query.filter(Patient.doctor_id == user_uuid)

    if month:
        query = query.filter(func.extract("month", QuizSession.created_at) == month)
    if year:
        query = query.filter(func.extract("year", QuizSession.created_at) == year)

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
        },
    }

    # Cache the result
    await set_cached_result(cache_key, result)

    return result


@router.get(
    "/completion-trend",
    response_model=CompletionTrend,
    summary="Get completion trend",
    description="Get quiz completion trend over the last N months (ADMIN/DOCTOR only)",
)
async def get_completion_trend(
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    months: int = Query(6, ge=1, le=24, description="Number of months to include"),
):
    """
    Get quiz completion trend over the last N months.

    Returns monthly completion rates.

    Args:
        months: Number of months to analyze (1-24)

    Returns:
        Dict with monthly trend data and period information
    """
    role, user_uuid = get_role_and_user(current_user)

    # Check cache first
    cache_key = get_cache_key(
        "completion-trend",
        months=months,
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await get_cached_result(cache_key)
    if cached_result:
        return cached_result

    # Calculate date range
    end_date = now_sao_paulo()
    start_date = end_date - timedelta(days=months * 30)

    # Get monthly stats using date functions
    results_query = (
        db.query(
            func.extract("year", QuizSession.created_at).label("year"),
            func.extract("month", QuizSession.created_at).label("month"),
            func.count(QuizSession.id).label("total"),
            func.sum(case((QuizSession.status == "completed", 1), else_=0)).label(
                "completed"
            ),
        )
        .join(Patient, Patient.id == QuizSession.patient_id)
        .filter(QuizSession.created_at >= start_date)
    )

    if role != UserRole.ADMIN and user_uuid:
        results_query = results_query.filter(Patient.doctor_id == user_uuid)

    results = (
        results_query.group_by(
            func.extract("year", QuizSession.created_at),
            func.extract("month", QuizSession.created_at),
        )
        .order_by(
            func.extract("year", QuizSession.created_at),
            func.extract("month", QuizSession.created_at),
        )
        .all()
    )

    trend = []
    for year, month, total, completed in results:
        completion_rate = (completed / total * 100) if total > 0 else 0
        trend.append(
            {
                "year": int(year),
                "month": int(month),
                "total": total,
                "completed": completed,
                "completion_rate": round(completion_rate, 2),
            }
        )

    result = {
        "trend": trend,
        "period": {
            "months": months,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    }

    # Cache the result
    await set_cached_result(cache_key, result)

    return result
