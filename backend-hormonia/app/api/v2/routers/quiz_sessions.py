
# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, func
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.core.database.async_engine import get_async_db
from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient
from app.schemas.v2.quiz import (
    QuizV2Response,
    QuizV2List,
    QuizV2Create,
    QuizV2Update,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    apply_field_selection,
)
from app.utils.auth_helpers import (
    extract_user_context as _extract_user_context,
    is_admin,
    ensure_uuid as _ensure_uuid,
)
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from app.core.distributed_lock import acquire_lock, LockAcquisitionError, LockKeys
from app.utils.timezone import now_sao_paulo

router = APIRouter()


def _ensure_patient_owner(current_user, doctor_id):
    """Verify user has access to patient's data."""
    if is_admin(current_user):
        return
    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)
    if user_uuid is None or doctor_id != user_uuid:
        raise ForbiddenError("Not enough permissions")


async def _get_quiz_with_access(
    db: AsyncSession, current_user, quiz_id: str
) -> QuizSession:
    """Load quiz by ID and enforce patient ownership/admin access."""
    try:
        qid = UUID(quiz_id)
    except (ValueError, TypeError) as exc:
        raise ValidationError("Invalid quiz_id UUID", field="quiz_id") from exc

    quiz_result = await db.execute(select(QuizSession).where(QuizSession.id == qid))
    quiz = quiz_result.scalar_one_or_none()
    if not quiz:
        raise NotFoundError("Quiz", quiz_id)

    patient_result = await db.execute(select(Patient).where(Patient.id == quiz.patient_id))
    patient = patient_result.scalar_one_or_none()
    if patient is None:
        if not is_admin(current_user):
            raise ForbiddenError("Not enough permissions")
    else:
        _ensure_patient_owner(current_user, patient.doctor_id)
    return quiz


@router.get("/sessions", response_model=QuizV2List, summary="List quizzes")
async def list_quizzes(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    patient_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    
    try:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]
        query = select(QuizSession)

        role_enum, user_id = _extract_user_context(current_user)
        current_user_uuid = _ensure_uuid(user_id)

        if role_enum != UserRole.ADMIN:
            if not current_user_uuid:
                raise ForbiddenError("Insufficient permissions")
            query = query.join(Patient)

        if include and "patient" in include:
            query = query.options(joinedload(QuizSession.patient))

        filters = []
        if role_enum != UserRole.ADMIN:
            filters.append(Patient.doctor_id == current_user_uuid)

        if cursor_data and "id" in cursor_data:
            from datetime import datetime as dt

            try:
                raw_cursor_id = cursor_data["id"]
                raw_created_at = cursor_data["created_at"]

                cid = (
                    raw_cursor_id
                    if isinstance(raw_cursor_id, UUID)
                    else UUID(str(raw_cursor_id))
                )
                cdate = (
                    raw_created_at
                    if isinstance(raw_created_at, dt)
                    else dt.fromisoformat(str(raw_created_at))
                )
            except (KeyError, TypeError, ValueError):
                raise ValidationError("Invalid cursor format", field="cursor")

            filters.append(
                (QuizSession.created_at < cdate)
                | ((QuizSession.created_at == cdate) & (QuizSession.id > cid))
            )

        if patient_id:
            try:
                filters.append(QuizSession.patient_id == UUID(patient_id))
            except (ValueError, TypeError):
                raise ValidationError("Invalid patient_id UUID", field="patient_id")

        if status_filter:
            filters.append(QuizSession.status == status_filter)

        if filters:
            query = query.where(and_(*filters))

        total = None
        if not cursor_data:
            tq = select(func.count(QuizSession.id)).select_from(QuizSession)
            if role_enum != UserRole.ADMIN:
                tq = tq.join(Patient)
            if filters:
                tq = tq.where(and_(*filters))
            total = (await db.execute(tq)).scalar_one()

        query = query.order_by(QuizSession.created_at.desc(), QuizSession.id).limit(limit + 1)
        quizzes = (await db.execute(query)).scalars().all()

        has_more = len(quizzes) > limit
        if has_more:
            quizzes = quizzes[:limit]

        next_cursor = None
        if has_more and quizzes:
            import json
            import base64

            cd = {
                "id": str(quizzes[-1].id),
                "created_at": quizzes[-1].created_at.isoformat(),
            }
            next_cursor = base64.b64encode(json.dumps(cd).encode()).decode()

        resp = []
        for q in quizzes:
            qd = {
                "id": str(q.id),
                "patient_id": str(q.patient_id),
                "quiz_template_id": str(q.quiz_template_id),
                "status": q.status,
                "created_at": q.created_at.isoformat() if q.created_at else None,
                "updated_at": q.updated_at.isoformat() if q.updated_at else None,
                "started_at": q.started_at.isoformat() if q.started_at else None,
                "completed_at": q.completed_at.isoformat() if q.completed_at else None,
                "score": float(q.score) if q.score else None,
                "max_score": float(q.max_score) if q.max_score else None,
                "passed": q.passed,
                "current_question": q.current_question,
                "total_questions": q.total_questions,
                "answered_questions": q.answered_questions,
                "time_spent_seconds": q.time_spent_seconds,
                "session_metadata": q.session_metadata,
            }
            if include and "patient" in include and q.patient:
                qd["patient"] = {
                    "id": str(q.patient.id),
                    "name": q.patient.name,
                    "email": q.patient.email,
                }
            if fields:
                qd = apply_field_selection(qd, fields)
            resp.append(qd)

        result = {
            "data": resp,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": total,
        }
        
        # Validate the response matches expected schema
        from app.schemas.v2.quiz import QuizV2List
        validated = QuizV2List(**result)
        return result
        
    except Exception as e:
        print(f"\\n\\n=== ERROR in list_quizzes ===\\n{type(e).__name__}: {e}\\n{traceback.format_exc()}\\n===\\n")
        logger.error(f"ERROR in list_quizzes: {type(e).__name__}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


@router.get("/{quiz_id}", response_model=QuizV2Response)
async def get_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    try:
        qid = UUID(quiz_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid quiz_id UUID", field="quiz_id")

    query = select(QuizSession)
    if include and "patient" in include:
        query = query.options(joinedload(QuizSession.patient))

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid:
            raise ForbiddenError("Insufficient permissions")
        query = query.join(Patient).where(Patient.doctor_id == current_user_uuid)

    quiz_result = await db.execute(query.where(QuizSession.id == qid))
    quiz = quiz_result.scalar_one_or_none()
    if not quiz:
        raise NotFoundError("Quiz", quiz_id)

    if role_enum != UserRole.ADMIN:
        # Extra check if not joined (though join handles filter)
        patient = (
            quiz.patient
            if hasattr(quiz, "patient") and quiz.patient
            else (
                await db.execute(select(Patient).where(Patient.id == quiz.patient_id))
            ).scalar_one_or_none()
        )
        if patient:
            _ensure_patient_owner(current_user, patient.doctor_id)

    qd = {
        "id": str(quiz.id),
        "patient_id": str(quiz.patient_id),
        "quiz_template_id": str(quiz.quiz_template_id),
        "status": quiz.status,
        "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
        "updated_at": quiz.updated_at.isoformat() if quiz.updated_at else None,
        "started_at": quiz.started_at.isoformat() if quiz.started_at else None,
        "completed_at": quiz.completed_at.isoformat() if quiz.completed_at else None,
        "score": float(quiz.score) if quiz.score else None,
        "max_score": float(quiz.max_score) if quiz.max_score else None,
        "passed": quiz.passed,
    }
    if include and "patient" in include and hasattr(quiz, "patient") and quiz.patient:
        qd["patient"] = {
            "id": str(quiz.patient.id),
            "name": quiz.patient.name,
            "email": quiz.patient.email,
        }
    if fields:
        qd = apply_field_selection(qd, fields)
    return qd


@router.post("", response_model=QuizV2Response, status_code=201)
@limiter.limit("30/hour")
async def create_quiz(
    request: Request,
    quiz_data: QuizV2Create,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Create a new quiz session for a patient.

    Uses distributed lock to prevent race condition where concurrent requests
    could both pass the "existing session" check and create duplicate sessions.
    """
    try:
        pid = UUID(quiz_data.patient_id)
        tid = UUID(quiz_data.quiz_template_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid UUID format", field="patient_id or quiz_template_id")

    patient_result = await db.execute(select(Patient).where(Patient.id == pid))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise NotFoundError("Patient", str(pid))
    _ensure_patient_owner(current_user, patient.doctor_id)

    template_result = await db.execute(select(QuizTemplate).where(QuizTemplate.id == tid))
    template = template_result.scalar_one_or_none()
    if not template:
        raise NotFoundError("Template", str(tid))
    if not template.is_active:
        raise ValidationError("Template inactive", field="quiz_template_id")

    # Acquire distributed lock per patient+template to prevent duplicate sessions
    lock_key = LockKeys.quiz_session(str(pid))
    try:
        async with acquire_lock(lock_key, timeout=5.0, ttl=30):
            # Re-check for existing session within lock (double-check pattern)
            existing_result = await db.execute(
                select(QuizSession).where(
                    QuizSession.patient_id == pid,
                    QuizSession.quiz_template_id == tid,
                    QuizSession.status == "started",
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing:
                raise ConflictError("Active session exists", {"patient_id": str(pid), "quiz_template_id": str(tid)})

            new_quiz = QuizSession(
                patient_id=pid,
                quiz_template_id=tid,
                status=quiz_data.status or "started",
                started_at=now_sao_paulo(),
            )
            db.add(new_quiz)
            await db.commit()
            await db.refresh(new_quiz)

    except LockAcquisitionError:
        raise ServiceUnavailableError("Service busy, please retry")

    return {
        "id": str(new_quiz.id),
        "patient_id": str(new_quiz.patient_id),
        "quiz_template_id": str(new_quiz.quiz_template_id),
        "status": new_quiz.status,
        "created_at": new_quiz.created_at.isoformat() if new_quiz.created_at else None,
        "updated_at": new_quiz.updated_at.isoformat() if new_quiz.updated_at else None,
        "started_at": new_quiz.started_at.isoformat() if new_quiz.started_at else None,
        "completed_at": new_quiz.completed_at.isoformat() if new_quiz.completed_at else None,
        "score": float(new_quiz.score) if new_quiz.score else None,
        "max_score": float(new_quiz.max_score) if new_quiz.max_score else None,
        "passed": new_quiz.passed,
    }


@router.patch("/{quiz_id}", response_model=QuizV2Response)
async def update_quiz(
    quiz_id: str,
    quiz_data: QuizV2Update,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    quiz = await _get_quiz_with_access(db, current_user, quiz_id)

    update_data = quiz_data.dict(exclude_unset=True)
    for k, v in update_data.items():
        setattr(quiz, k, v)
    await db.commit()
    await db.refresh(quiz)

    return {
        "id": str(quiz.id),
        "patient_id": str(quiz.patient_id),
        "quiz_template_id": str(quiz.quiz_template_id),
        "status": quiz.status,
        "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
        "updated_at": quiz.updated_at.isoformat() if quiz.updated_at else None,
        "started_at": quiz.started_at.isoformat() if quiz.started_at else None,
        "completed_at": quiz.completed_at.isoformat() if quiz.completed_at else None,
        "score": float(quiz.score) if quiz.score else None,
        "max_score": float(quiz.max_score) if quiz.max_score else None,
        "passed": quiz.passed,
    }


@router.delete("/{quiz_id}", status_code=204)
async def delete_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
):
    quiz = await _get_quiz_with_access(db, current_user, quiz_id)

    await db.delete(quiz)
    await db.commit()
    return None
