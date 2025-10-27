"""
Quiz API v2
Enhanced quiz endpoints with cursor pagination and eager loading.
"""

from typing import Optional, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.database import get_db
from app.models.quiz import QuizSession
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.v2.quiz import (
    QuizV2Response,
    QuizV2List,
    QuizV2Create,
    QuizV2Update,
)
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
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

    if isinstance(role, UserRole):
        role_enum = role
    elif isinstance(role, str):
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            role_enum = None
    else:
        role_enum = None

    if user_id is not None:
        user_id = str(user_id)

    return role_enum, user_id


def _is_admin(current_user) -> bool:
    role_enum, _ = _extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def _ensure_uuid(value: Optional[str]):
    from uuid import UUID

    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _ensure_patient_owner(current_user, doctor_id):
    if _is_admin(current_user):
        return

    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)

    if user_uuid is None or doctor_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this resource",
        )


@router.get(
    "",
    response_model=QuizV2List,
    summary="List quizzes with pagination",
    description="Get paginated list of quizzes with optional filtering"
)
async def list_quizzes(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    patient_id: Optional[str] = Query(None, description="Filter by patient UUID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month"),
    year: Optional[int] = Query(None, ge=2020, description="Filter by year"),
):
    """
    List quizzes with cursor-based pagination.
    
    Features:
    - Cursor-based pagination
    - Field selection (?fields=id,status,month)
    - Eager loading (?include=patient)
    - Filter by patient, status, month, year
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]
    
    # Build base query
    query = db.query(QuizSession)

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.join(Patient)
    
    # Apply eager loading
    if include and "patient" in include:
        query = query.options(joinedload(QuizSession.patient))
    
    # Apply filters
    filters = []

    if role_enum != UserRole.ADMIN:
        filters.append(Patient.doctor_id == current_user_uuid)
    
    if cursor_data and "id" in cursor_data:
        from uuid import UUID
        from datetime import datetime as dt
        cursor_uuid = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at_str = cursor_data.get("created_at", "1970-01-01T00:00:00")
        # Parse ISO string to datetime before comparison
        cursor_created_at = dt.fromisoformat(cursor_created_at_str.replace("Z", "+00:00"))
        filters.append(
            (QuizSession.created_at < cursor_created_at) |
            ((QuizSession.created_at == cursor_created_at) & (QuizSession.id > cursor_uuid))
        )
    
    if patient_id:
        from uuid import UUID
        try:
            patient_uuid = UUID(patient_id)
            filters.append(QuizSession.patient_id == patient_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient UUID format"
            )
    
    if status:
        filters.append(QuizSession.status == status)
    
    # Note: QuizSession doesn't have month/year fields, filtering by date range instead
    # if month:
    #     filters.append(QuizSession.month == month)
    # if year:
    #     filters.append(QuizSession.year == year)
    
    if filters:
        query = query.filter(and_(*filters))

    total = None
    if not cursor_data:
        total_query = db.query(func.count(QuizSession.id))
        if role_enum != UserRole.ADMIN:
            total_query = total_query.join(Patient)
        if filters:
            total_query = total_query.filter(and_(*filters))
        total = total_query.scalar()
    
    # Order and limit (use created_at + id for stable cursor pagination)
    query = query.order_by(QuizSession.created_at.desc(), QuizSession.id)
    quizzes = query.limit(limit + 1).all()
    
    # Check if there are more results
    has_more = len(quizzes) > limit
    if has_more:
        quizzes = quizzes[:limit]
    
    # Create next cursor
    next_cursor = None
    if has_more and quizzes:
        import json
        import base64
        cursor_data = {
            "id": str(quizzes[-1].id),
            "created_at": quizzes[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()
    
    # Convert to response models
    quiz_responses = []
    for quiz in quizzes:
        quiz_dict = {
            "id": str(quiz.id),
            "patient_id": str(quiz.patient_id),
            "quiz_template_id": str(quiz.quiz_template_id),
            "status": quiz.status,
            "created_at": quiz.created_at,
            "updated_at": quiz.updated_at,
            "started_at": quiz.started_at,
            "completed_at": quiz.completed_at,
            "score": float(quiz.score) if quiz.score else None,
            "max_score": float(quiz.max_score) if quiz.max_score else None,
            "passed": quiz.passed,
        }
        
        # Add eager-loaded patient
        if include and "patient" in include and quiz.patient:
            quiz_dict["patient"] = {
                "id": str(quiz.patient.id),
                "name": quiz.patient.name,
                "email": quiz.patient.email,
            }
        
        # Apply field selection
        if fields:
            quiz_dict = apply_field_selection(quiz_dict, fields)
        
        quiz_responses.append(quiz_dict)
    
    return {
        "data": quiz_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.get(
    "/{quiz_id}",
    response_model=QuizV2Response,
    summary="Get quiz by ID",
    description="Get a single quiz with optional eager loading"
)
async def get_quiz(
    quiz_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """Get a single quiz by UUID."""
    from uuid import UUID
    
    try:
        quiz_uuid = UUID(quiz_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid quiz UUID format"
        )
    
    query = db.query(QuizSession)
    
    # Apply eager loading
    if include and "patient" in include:
        query = query.options(joinedload(QuizSession.patient))

    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.join(Patient)
        query = query.filter(Patient.doctor_id == current_user_uuid)
    
    quiz = query.filter(QuizSession.id == quiz_uuid).first()
    
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with id {quiz_id} not found"
        )
    
    if role_enum != UserRole.ADMIN:
        patient = quiz.patient if hasattr(quiz, "patient") and quiz.patient else db.query(Patient).filter(Patient.id == quiz.patient_id).first()
        if patient:
            _ensure_patient_owner(current_user, patient.doctor_id)

    # Build response
    quiz_dict = {
        "id": str(quiz.id),
        "patient_id": str(quiz.patient_id),
        "quiz_template_id": str(quiz.quiz_template_id),
        "status": quiz.status,
        "created_at": quiz.created_at,
        "updated_at": quiz.updated_at,
        "started_at": quiz.started_at,
        "completed_at": quiz.completed_at,
        "score": float(quiz.score) if quiz.score else None,
        "max_score": float(quiz.max_score) if quiz.max_score else None,
        "passed": quiz.passed,
    }
    
    # Add eager-loaded patient
    if include and "patient" in include and quiz.patient:
        quiz_dict["patient"] = {
            "id": str(quiz.patient.id),
            "name": quiz.patient.name,
            "email": quiz.patient.email,
        }
    
    # Apply field selection
    if fields:
        quiz_dict = apply_field_selection(quiz_dict, fields)
    
    return quiz_dict


@router.post(
    "",
    response_model=QuizV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new quiz",
    description="Create a new quiz for a patient (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def create_quiz(
    request: Request,
    quiz_data: QuizV2Create,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Create a new quiz session."""
    from uuid import UUID
    from datetime import datetime
    
    # Convert and validate patient_id
    try:
        patient_uuid = UUID(quiz_data.patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient UUID format"
        )
    
    # Convert and validate quiz_template_id
    try:
        template_uuid = UUID(quiz_data.quiz_template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid quiz template UUID format"
        )
    
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {quiz_data.patient_id} not found"
        )

    _ensure_patient_owner(current_user, patient.doctor_id)
    
    # Check for existing active session
    existing_session = db.query(QuizSession).filter(
        and_(
            QuizSession.patient_id == patient_uuid,
            QuizSession.quiz_template_id == template_uuid,
            QuizSession.status == "started"
        )
    ).first()
    
    if existing_session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active quiz session already exists for patient {quiz_data.patient_id}"
        )
    
    # Create quiz session
    new_quiz = QuizSession(
        patient_id=patient_uuid,
        quiz_template_id=template_uuid,
        status=quiz_data.status or "started",
        started_at=datetime.utcnow()
    )
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)
    
    # Return formatted response
    return {
        "id": str(new_quiz.id),
        "patient_id": str(new_quiz.patient_id),
        "quiz_template_id": str(new_quiz.quiz_template_id),
        "status": new_quiz.status,
        "created_at": new_quiz.created_at,
        "updated_at": new_quiz.updated_at,
        "started_at": new_quiz.started_at,
        "completed_at": new_quiz.completed_at,
        "score": float(new_quiz.score) if new_quiz.score else None,
        "max_score": float(new_quiz.max_score) if new_quiz.max_score else None,
        "passed": new_quiz.passed,
    }


@router.patch(
    "/{quiz_id}",
    response_model=QuizV2Response,
    summary="Update quiz",
    description="Update quiz information (partial update) (ADMIN/DOCTOR only)"
)
@limiter.limit("50/hour")
async def update_quiz(
    request: Request,
    quiz_id: str,
    quiz_data: QuizV2Update,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Update a quiz session (partial update)."""
    from uuid import UUID
    
    try:
        quiz_uuid = UUID(quiz_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid quiz UUID format"
        )
    
    quiz = db.query(QuizSession).filter(QuizSession.id == quiz_uuid).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with id {quiz_id} not found"
        )

    patient = db.query(Patient).filter(Patient.id == quiz.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated patient not found"
        )

    _ensure_patient_owner(current_user, patient.doctor_id)
    
    # Update only provided fields
    update_data = quiz_data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(quiz, field, value)
    
    db.commit()
    db.refresh(quiz)
    
    # Return formatted response
    return {
        "id": str(quiz.id),
        "patient_id": str(quiz.patient_id),
        "quiz_template_id": str(quiz.quiz_template_id),
        "status": quiz.status,
        "created_at": quiz.created_at,
        "updated_at": quiz.updated_at,
        "started_at": quiz.started_at,
        "completed_at": quiz.completed_at,
        "score": float(quiz.score) if quiz.score else None,
        "max_score": float(quiz.max_score) if quiz.max_score else None,
        "passed": quiz.passed,
    }


@router.delete(
    "/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete quiz",
    description="Delete a quiz (ADMIN/DOCTOR only)"
)
@limiter.limit("10/hour")
async def delete_quiz(
    request: Request,
    quiz_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Delete a quiz session."""
    from uuid import UUID
    
    try:
        quiz_uuid = UUID(quiz_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid quiz UUID format"
        )
    
    quiz = db.query(QuizSession).filter(QuizSession.id == quiz_uuid).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with id {quiz_id} not found"
        )

    patient = db.query(Patient).filter(Patient.id == quiz.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated patient not found"
        )

    _ensure_patient_owner(current_user, patient.doctor_id)

    db.delete(quiz)
    db.commit()
    
    return None
