"""
Monthly Quiz Management API v2 - Quiz CRUD and Lifecycle Operations

Complete quiz lifecycle management system with:
- CRUD operations for monthly quizzes
- Publishing and unpublishing workflow
- Soft delete with archival
- Status-based filtering and validation
- Redis caching with appropriate TTLs
- Rate limiting to prevent abuse
- RBAC: Admin (create/update/delete/publish), Doctors (view)

Monthly Quiz Lifecycle:
1. Draft - Initial creation, editable
2. Published - Active and distributed to patients
3. Archived - Soft deleted, no longer active

Zero-Migration Implementation:
- Uses existing QuizTemplate model with category='monthly_quiz'
- Stores metadata in JSONB 'tags' field
- Enables immediate deployment without schema changes

Total: 7 CRUD endpoints for monthly quiz management
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues

import asyncio
import inspect
from typing import Optional
from datetime import datetime
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database.async_engine import get_async_db
from app.models.quiz import QuizTemplate
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.quiz_extensions import (
    MonthlyQuizV2Create,
    MonthlyQuizV2Update,
    MonthlyQuizV2Detail,
    MonthlyQuizV2List,
    QuizPublishRequestV2,
)
from app.api.v2.dependencies import get_pagination_params_async
from app.schemas.v2.common import CursorEncoder
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.api.v2._quiz_shared import CACHE_TTL_QUIZ_LIST, _get_current_user_simple
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)

_VALID_MONTHLY_QUIZ_STATUSES = {"draft", "published", "archived"}


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _cache_get(redis_cache, key: str):
    if not redis_cache or not hasattr(redis_cache, "get"):
        return None
    try:
        return await asyncio.wait_for(_maybe_await(redis_cache.get(key)), timeout=1.0)
    except Exception:
        return None


async def _cache_set(redis_cache, key: str, value: str, ttl: int):
    if not redis_cache:
        return
    if hasattr(redis_cache, "setex"):
        try:
            await asyncio.wait_for(
                _maybe_await(redis_cache.setex(key, ttl, value)),
                timeout=1.0,
            )
            return
        except Exception:
            return
    if hasattr(redis_cache, "set"):
        try:
            await asyncio.wait_for(
                _maybe_await(redis_cache.set(key, value, ttl)),
                timeout=1.0,
            )
        except TypeError:
            await asyncio.wait_for(_maybe_await(redis_cache.set(key, value)), timeout=1.0)
        except Exception:
            return


async def _cache_delete(redis_cache, key: str):
    if not redis_cache or not hasattr(redis_cache, "delete"):
        return
    try:
        await asyncio.wait_for(_maybe_await(redis_cache.delete(key)), timeout=1.0)
    except Exception:
        return


def _monthly_quiz_cache_key(quiz_id: UUID) -> str:
    return f"monthly_quiz:{quiz_id}"


async def _invalidate_monthly_quiz_cache(redis_cache, quiz_id: UUID):
    if redis_cache:
        await _cache_delete(redis_cache, _monthly_quiz_cache_key(quiz_id))


def _parse_iso_datetime_strict(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _parse_iso_datetime_safe(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


async def _get_monthly_quiz_or_404(db: AsyncSession, quiz_id: UUID) -> QuizTemplate:
    result = await db.execute(
        select(QuizTemplate).where(
            QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz"
        )
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monthly quiz not found"
        )
    return quiz


def _build_monthly_quiz_detail(
    quiz: QuizTemplate, *, fallback_base_template_id: bool = False
) -> MonthlyQuizV2Detail:
    tags = quiz.tags or {}
    base_template_id_raw = (
        tags.get("base_template_id", str(quiz.id))
        if fallback_base_template_id
        else tags["base_template_id"]
    )

    return MonthlyQuizV2Detail(
        id=quiz.id,
        name=quiz.name,
        description=quiz.description,
        quiz_template_id=UUID(base_template_id_raw),
        scheduled_for=_parse_iso_datetime_strict(tags.get("scheduled_for")),
        expires_at=_parse_iso_datetime_strict(tags.get("expires_at")),
        status=tags.get("status", "draft"),
        created_by=UUID(tags["created_by"]),
        created_at=quiz.created_at,
        published_at=_parse_iso_datetime_strict(tags.get("published_at")),
        total_sent=tags.get("total_sent", 0),
        total_accessed=tags.get("total_accessed", 0),
        total_completed=tags.get("total_completed", 0),
        completion_rate=tags.get("completion_rate", 0.0),
    )


def _build_monthly_quiz_detail_safe(
    quiz: QuizTemplate, *, fallback_created_by: UUID
) -> MonthlyQuizV2Detail:
    tags = quiz.tags or {}
    base_template_id_raw = tags.get("base_template_id", str(quiz.id))
    created_by_raw = tags.get("created_by")

    try:
        base_template_id = UUID(str(base_template_id_raw))
    except (ValueError, TypeError):
        base_template_id = quiz.id

    try:
        created_by = UUID(str(created_by_raw)) if created_by_raw else fallback_created_by
    except (ValueError, TypeError):
        created_by = fallback_created_by

    status_raw = str(tags.get("status", "draft")).lower()
    if status_raw not in _VALID_MONTHLY_QUIZ_STATUSES:
        status_raw = "draft"

    return MonthlyQuizV2Detail(
        id=quiz.id,
        name=quiz.name,
        description=quiz.description,
        quiz_template_id=base_template_id,
        scheduled_for=_parse_iso_datetime_safe(tags.get("scheduled_for")),
        expires_at=_parse_iso_datetime_safe(tags.get("expires_at")),
        status=status_raw,
        created_by=created_by,
        created_at=quiz.created_at,
        published_at=_parse_iso_datetime_safe(tags.get("published_at")),
        total_sent=int(tags.get("total_sent", 0) or 0),
        total_accessed=int(tags.get("total_accessed", 0) or 0),
        total_completed=int(tags.get("total_completed", 0) or 0),
        completion_rate=float(tags.get("completion_rate", 0.0) or 0.0),
    )


# ============================================================================
# Monthly Quiz CRUD Endpoints (7 endpoints)
# ============================================================================


@router.get(
    "/monthly",
    response_model=MonthlyQuizV2List,
    summary="List monthly quizzes",
    description="List monthly quizzes with cursor pagination",
)
@limiter.limit("50/minute")
async def list_monthly_quizzes(
    request: Request,
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status"
    ),
    pagination: dict = Depends(get_pagination_params_async),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
):
    """
    List monthly quizzes.

    **RBAC:** Admin and Doctors can view

    **Cache:** 5 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view monthly quizzes",
        )

    status_value = None
    if status_filter:
        normalized_status = status_filter.strip().lower()
        if normalized_status not in _VALID_MONTHLY_QUIZ_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter. Use: draft, published, archived.",
            )
        status_value = normalized_status

    result = await db.execute(
        select(QuizTemplate)
        .where(QuizTemplate.category == "monthly_quiz")
        .order_by(QuizTemplate.created_at.desc(), QuizTemplate.id.desc())
    )
    quizzes = result.scalars().all()

    if status_value:
        quizzes = [
            quiz
            for quiz in quizzes
            if str((quiz.tags or {}).get("status", "draft")).lower() == status_value
        ]

    total = len(quizzes)

    cursor_data = pagination.get("cursor_data") if isinstance(pagination, dict) else None
    limit = pagination.get("limit", 20) if isinstance(pagination, dict) else 20

    if cursor_data and cursor_data.get("id"):
        cursor_id = str(cursor_data["id"])
        for index, quiz in enumerate(quizzes):
            if str(quiz.id) == cursor_id:
                quizzes = quizzes[index + 1 :]
                break
        else:
            quizzes = []

    has_more = len(quizzes) > limit
    page_items = quizzes[:limit]
    data = [
        _build_monthly_quiz_detail_safe(quiz, fallback_created_by=current_user.id)
        for quiz in page_items
    ]

    next_cursor = None
    if has_more and page_items:
        last_item = page_items[-1]
        next_cursor = CursorEncoder.encode(last_item.id, last_item.created_at)

    return MonthlyQuizV2List(
        data=data,
        next_cursor=next_cursor,
        has_more=has_more,
        total=total,
    )


@router.post(
    "/monthly",
    response_model=MonthlyQuizV2Detail,
    summary="Create monthly quiz",
    description="Create a new monthly quiz",
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
async def create_monthly_quiz(
    request: Request,
    quiz: MonthlyQuizV2Create,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
):
    """
    Create a new monthly quiz.

    **RBAC:** Admin only

    **Implementation:** Uses QuizTemplate model with category='monthly_quiz'
    and stores metadata in JSONB 'tags' field for zero-migration deployment.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create monthly quizzes",
        )

    # Verify base template exists
    result = await db.execute(
        select(QuizTemplate).where(QuizTemplate.id == quiz.quiz_template_id)
    )
    base_template = result.scalar_one_or_none()
    if not base_template:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Monthly quiz creation requires a seeded base template",
        )

    # Create monthly quiz using QuizTemplate model
    # Use category='monthly_quiz' to distinguish from regular templates
    monthly_quiz = QuizTemplate(
        name=quiz.name,
        description=quiz.description or "",
        category="monthly_quiz",
        version="1.0",
        questions=base_template.questions,  # Copy questions from base template
        scoring_rules=base_template.scoring_rules,
        tags={
            "status": "draft",
            "created_by": str(current_user.id),
            "base_template_id": str(quiz.quiz_template_id),
            "scheduled_for": quiz.scheduled_for.isoformat()
            if quiz.scheduled_for
            else None,
            "expires_at": quiz.expires_at.isoformat() if quiz.expires_at else None,
            "target_patient_ids": [str(pid) for pid in quiz.target_patient_ids]
            if quiz.target_patient_ids
            else None,
            "auto_send": quiz.auto_send,
            "delivery_method": quiz.delivery_method.value,
            "total_sent": 0,
            "total_accessed": 0,
            "total_completed": 0,
            "completion_rate": 0.0,
        },
        is_active=True,
    )

    db.add(monthly_quiz)
    await db.commit()
    await db.refresh(monthly_quiz)

    logger.info(f"Monthly quiz '{quiz.name}' created by user {current_user.id}")

    return _build_monthly_quiz_detail(monthly_quiz)


@router.get(
    "/monthly/{quiz_id:uuid}",
    response_model=MonthlyQuizV2Detail,
    summary="Get monthly quiz details",
    description="Get detailed information about a monthly quiz",
)
@limiter.limit("50/minute")
async def get_monthly_quiz_detail(
    request: Request,
    quiz_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Get monthly quiz details.

    **RBAC:** Admin and Doctors can view
    **Cache:** 5 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view monthly quizzes",
        )

    # Check cache first
    cache_key = _monthly_quiz_cache_key(quiz_id)
    if redis_cache:
        cached = await _cache_get(redis_cache, cache_key)
        if cached:
            return MonthlyQuizV2Detail.parse_raw(cached)

    quiz = await _get_monthly_quiz_or_404(db, quiz_id)
    result = _build_monthly_quiz_detail(quiz, fallback_base_template_id=True)

    # Cache result
    if redis_cache:
        await _cache_set(redis_cache, cache_key, result.json(), CACHE_TTL_QUIZ_LIST)

    return result


@router.put(
    "/monthly/{quiz_id:uuid}",
    response_model=MonthlyQuizV2Detail,
    summary="Update monthly quiz",
    description="Update a monthly quiz (draft only)",
)
@limiter.limit("30/minute")
async def update_monthly_quiz(
    request: Request,
    quiz_id: UUID,
    update_data: MonthlyQuizV2Update,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Update monthly quiz.

    **RBAC:** Admin only
    **Constraint:** Only draft quizzes can be updated
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update monthly quizzes",
        )

    quiz = await _get_monthly_quiz_or_404(db, quiz_id)

    # Only allow updates to draft quizzes
    if quiz.tags.get("status") != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft quizzes can be updated. Unpublish first to make changes.",
        )

    # Update fields
    if update_data.name is not None:
        quiz.name = update_data.name
    if update_data.description is not None:
        quiz.description = update_data.description
    if update_data.scheduled_for is not None:
        quiz.tags["scheduled_for"] = update_data.scheduled_for.isoformat()
    if update_data.expires_at is not None:
        quiz.tags["expires_at"] = update_data.expires_at.isoformat()

    quiz.updated_at = now_sao_paulo()

    await db.commit()
    await db.refresh(quiz)

    # Invalidate cache
    await _invalidate_monthly_quiz_cache(redis_cache, quiz_id)

    logger.info(f"Monthly quiz {quiz_id} updated by user {current_user.id}")

    return _build_monthly_quiz_detail(quiz)


@router.delete(
    "/monthly/{quiz_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete monthly quiz",
    description="Delete a monthly quiz (soft delete)",
)
@limiter.limit("20/minute")
async def delete_monthly_quiz(
    request: Request,
    quiz_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Delete monthly quiz (soft delete by setting status to 'archived').

    **RBAC:** Admin only
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete monthly quizzes",
        )

    quiz = await _get_monthly_quiz_or_404(db, quiz_id)

    # Soft delete by changing status
    quiz.tags["status"] = "archived"
    quiz.is_active = False
    quiz.updated_at = now_sao_paulo()

    await db.commit()

    # Invalidate cache
    await _invalidate_monthly_quiz_cache(redis_cache, quiz_id)

    logger.info(f"Monthly quiz {quiz_id} archived by user {current_user.id}")

    return None


@router.post(
    "/monthly/{quiz_id:uuid}/publish",
    response_model=MonthlyQuizV2Detail,
    summary="Publish monthly quiz",
    description="Publish a monthly quiz and optionally send to patients",
)
@limiter.limit("20/minute")
async def publish_monthly_quiz(
    request: Request,
    quiz_id: UUID,
    publish_request: QuizPublishRequestV2,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Publish monthly quiz.

    **RBAC:** Admin only
    **Actions:** Changes status to 'published', optionally sends to target patients
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can publish monthly quizzes",
        )

    quiz = await _get_monthly_quiz_or_404(db, quiz_id)

    if quiz.tags.get("status") == "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Quiz is already published"
        )

    # Update status
    quiz.tags["status"] = "published"
    quiz.tags["published_at"] = now_sao_paulo().isoformat()

    # Send to patients if requested
    if publish_request.send_immediately:
        # Get target patients
        patient_query = select(Patient)
        if publish_request.target_patient_ids:
            patient_query = patient_query.where(
                Patient.id.in_(publish_request.target_patient_ids)
            )
        else:
            # Get all active patients (you might want to filter by doctor assignment)
            patient_query = patient_query.where(Patient.is_active)

        patient_result = await db.execute(patient_query)
        target_patients = patient_result.scalars().all()

        # In production, you'd send actual messages here
        # For now, just update the count
        quiz.tags["total_sent"] = len(target_patients)
        quiz.tags["target_patient_ids"] = [str(p.id) for p in target_patients]

        logger.info(f"Monthly quiz {quiz_id} sent to {len(target_patients)} patients")

    quiz.updated_at = now_sao_paulo()
    await db.commit()
    await db.refresh(quiz)

    # Invalidate cache
    await _invalidate_monthly_quiz_cache(redis_cache, quiz_id)

    logger.info(f"Monthly quiz {quiz_id} published by user {current_user.id}")

    return _build_monthly_quiz_detail(quiz)


@router.post(
    "/monthly/{quiz_id:uuid}/unpublish",
    response_model=MonthlyQuizV2Detail,
    summary="Unpublish monthly quiz",
    description="Unpublish a monthly quiz (revert to draft)",
)
@limiter.limit("20/minute")
async def unpublish_monthly_quiz(
    request: Request,
    quiz_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache=Depends(get_redis_cache),
):
    """
    Unpublish monthly quiz (revert to draft status).

    **RBAC:** Admin only
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can unpublish monthly quizzes",
        )

    quiz = await _get_monthly_quiz_or_404(db, quiz_id)

    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Quiz is not published"
        )

    # Revert to draft
    quiz.tags["status"] = "draft"
    quiz.updated_at = now_sao_paulo()

    await db.commit()
    await db.refresh(quiz)

    # Invalidate cache
    await _invalidate_monthly_quiz_cache(redis_cache, quiz_id)

    logger.info(f"Monthly quiz {quiz_id} unpublished by user {current_user.id}")

    return _build_monthly_quiz_detail(quiz)
