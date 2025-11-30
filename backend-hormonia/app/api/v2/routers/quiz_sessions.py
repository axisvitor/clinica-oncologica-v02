from typing import Any, Optional, List, Tuple
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session,  joinedload
from sqlalchemy import and_, func

from app.database import get_db
from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient
from app.models.user import UserRole
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
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter

router = APIRouter()

def _extract_user_context(current_user) -> Tuple[Optional[UserRole], Optional[str]]:
    role = None
    user_id = None
    if isinstance(current_user, dict):
        role = current_user.get("role")
        user_id = current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole): role_enum = role
    elif isinstance(role, str):
        try: role_enum = UserRole(role.lower())
        except ValueError: role_enum = None
    else: role_enum = None

    if user_id is not None: user_id = str(user_id)
    return role_enum, user_id

def _is_admin(current_user) -> bool:
    role_enum, _ = _extract_user_context(current_user)
    return role_enum == UserRole.ADMIN

def _ensure_uuid(value: Optional[str]):
    if value is None: return None
    try: return UUID(str(value))
    except (TypeError, ValueError): return None

def _ensure_patient_owner(current_user, doctor_id):
    if _is_admin(current_user): return
    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)
    if user_uuid is None or doctor_id != user_uuid:
        raise HTTPException(status_code=403, detail="Not enough permissions")

@router.get("", response_model=QuizV2List, summary="List quizzes")
async def list_quizzes(
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    patient_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]
    query = db.query(QuizSession)

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if not current_user_uuid: raise HTTPException(status_code=403)
        query = query.join(Patient)

    if include and "patient" in include:
        query = query.options(joinedload(QuizSession.patient))

    filters = []
    if role_enum != UserRole.ADMIN:
        filters.append(Patient.doctor_id == current_user_uuid)

    if cursor_data and "id" in cursor_data:
        from datetime import datetime as dt
        cid = UUID(cursor_data["id"])
        cdate = dt.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        filters.append(
            (QuizSession.created_at < cdate) |
            ((QuizSession.created_at == cdate) & (QuizSession.id > cid))
        )

    if patient_id:
        try: filters.append(QuizSession.patient_id == UUID(patient_id))
        except (ValueError, TypeError): raise HTTPException(status_code=400, detail="Invalid patient_id UUID")

    if status_filter:
        filters.append(QuizSession.status == status_filter)

    if filters: query = query.filter(and_(*filters))

    total = None
    if not cursor_data:
        tq = db.query(func.count(QuizSession.id))
        if role_enum != UserRole.ADMIN: tq = tq.join(Patient)
        if filters: tq = tq.filter(and_(*filters))
        total = tq.scalar()

    query = query.order_by(QuizSession.created_at.desc(), QuizSession.id)
    quizzes = query.limit(limit + 1).all()

    has_more = len(quizzes) > limit
    if has_more: quizzes = quizzes[:limit]

    next_cursor = None
    if has_more and quizzes:
        import json, base64
        cd = {"id": str(quizzes[-1].id), "created_at": quizzes[-1].created_at.isoformat()}
        next_cursor = base64.b64encode(json.dumps(cd).encode()).decode()

    resp = []
    for q in quizzes:
        qd = {
            "id": str(q.id), "patient_id": str(q.patient_id), "quiz_template_id": str(q.quiz_template_id),
            "status": q.status, "created_at": q.created_at, "updated_at": q.updated_at,
            "started_at": q.started_at, "completed_at": q.completed_at,
            "score": float(q.score) if q.score else None,
            "max_score": float(q.max_score) if q.max_score else None,
            "passed": q.passed, "current_question": q.current_question,
            "total_questions": q.total_questions, "answered_questions": q.answered_questions,
            "time_spent_seconds": q.time_spent_seconds, "session_metadata": q.session_metadata
        }
        if include and "patient" in include and q.patient:
            qd["patient"] = {"id": str(q.patient.id), "name": q.patient.name, "email": q.patient.email}
        if fields: qd = apply_field_selection(qd, fields)
        resp.append(qd)

    return {"data": resp, "next_cursor": next_cursor, "has_more": has_more, "total": total}

@router.get("/{quiz_id}", response_model=QuizV2Response)
async def get_quiz(
    quiz_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    try: qid = UUID(quiz_id)
    except (ValueError, TypeError): raise HTTPException(status_code=400, detail="Invalid quiz_id UUID")

    query = db.query(QuizSession)
    if include and "patient" in include:
        query = query.options(joinedload(QuizSession.patient))

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)
    
    if role_enum != UserRole.ADMIN:
        if not current_user_uuid: raise HTTPException(status_code=403)
        query = query.join(Patient).filter(Patient.doctor_id == current_user_uuid)

    quiz = query.filter(QuizSession.id == qid).first()
    if not quiz: raise HTTPException(status_code=404)

    if role_enum != UserRole.ADMIN:
        # Extra check if not joined (though join handles filter)
        patient = quiz.patient if hasattr(quiz, "patient") and quiz.patient else db.query(Patient).get(quiz.patient_id)
        if patient: _ensure_patient_owner(current_user, patient.doctor_id)

    qd = {
        "id": str(quiz.id), "patient_id": str(quiz.patient_id), "quiz_template_id": str(quiz.quiz_template_id),
        "status": quiz.status, "created_at": quiz.created_at, "updated_at": quiz.updated_at,
        "started_at": quiz.started_at, "completed_at": quiz.completed_at,
        "score": float(quiz.score) if quiz.score else None,
        "max_score": float(quiz.max_score) if quiz.max_score else None,
        "passed": quiz.passed
    }
    if include and "patient" in include and hasattr(quiz, "patient") and quiz.patient:
        qd["patient"] = {"id": str(quiz.patient.id), "name": quiz.patient.name, "email": quiz.patient.email}
    if fields: qd = apply_field_selection(qd, fields)
    return qd

@router.post("", response_model=QuizV2Response, status_code=201)
@limiter.limit("30/hour")
async def create_quiz(
    request: Request,
    quiz_data: QuizV2Create,
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    from datetime import datetime
    try:
        pid = UUID(quiz_data.patient_id)
        tid = UUID(quiz_data.quiz_template_id)
    except (ValueError, TypeError): raise HTTPException(status_code=400, detail="Invalid UUID format")

    patient = db.query(Patient).get(pid)
    if not patient: raise HTTPException(status_code=404, detail="Patient not found")
    _ensure_patient_owner(current_user, patient.doctor_id)

    template = db.query(QuizTemplate).get(tid)
    if not template: raise HTTPException(status_code=404, detail="Template not found")
    if not template.is_active: raise HTTPException(status_code=400, detail="Template inactive")

    existing = db.query(QuizSession).filter(
        QuizSession.patient_id == pid,
        QuizSession.quiz_template_id == tid,
        QuizSession.status == "started"
    ).first()
    if existing: raise HTTPException(status_code=409, detail="Active session exists")

    new_quiz = QuizSession(
        patient_id=pid, quiz_template_id=tid,
        status=quiz_data.status or "started", started_at=datetime.utcnow()
    )
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    return {
        "id": str(new_quiz.id), "patient_id": str(new_quiz.patient_id),
        "quiz_template_id": str(new_quiz.quiz_template_id), "status": new_quiz.status,
        "created_at": new_quiz.created_at, "updated_at": new_quiz.updated_at,
        "started_at": new_quiz.started_at, "completed_at": new_quiz.completed_at,
        "score": float(new_quiz.score) if new_quiz.score else None,
        "max_score": float(new_quiz.max_score) if new_quiz.max_score else None,
        "passed": new_quiz.passed
    }

@router.patch("/{quiz_id}", response_model=QuizV2Response)
async def update_quiz(
    quiz_id: str,
    quiz_data: QuizV2Update,
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    try: qid = UUID(quiz_id)
    except (ValueError, TypeError): raise HTTPException(status_code=400, detail="Invalid quiz_id UUID")

    quiz = db.query(QuizSession).get(qid)
    if not quiz: raise HTTPException(status_code=404)

    patient = db.query(Patient).get(quiz.patient_id)
    if patient: _ensure_patient_owner(current_user, patient.doctor_id)

    update_data = quiz_data.dict(exclude_unset=True)
    for k, v in update_data.items(): setattr(quiz, k, v)
    db.commit()
    db.refresh(quiz)

    return {
        "id": str(quiz.id), "patient_id": str(quiz.patient_id),
        "quiz_template_id": str(quiz.quiz_template_id), "status": quiz.status,
        "created_at": quiz.created_at, "updated_at": quiz.updated_at,
        "started_at": quiz.started_at, "completed_at": quiz.completed_at,
        "score": float(quiz.score) if quiz.score else None,
        "max_score": float(quiz.max_score) if quiz.max_score else None,
        "passed": quiz.passed
    }

@router.delete("/{quiz_id}", status_code=204)
async def delete_quiz(
    quiz_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    try: qid = UUID(quiz_id)
    except (ValueError, TypeError): raise HTTPException(status_code=400, detail="Invalid quiz_id UUID")

    quiz = db.query(QuizSession).get(qid)
    if not quiz: raise HTTPException(status_code=404)

    patient = db.query(Patient).get(quiz.patient_id)
    if patient: _ensure_patient_owner(current_user, patient.doctor_id)

    db.delete(quiz)
    db.commit()
    return None
