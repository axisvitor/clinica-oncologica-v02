"""
Compatibility layer for patient-related utilities.

The full patient CRUD endpoints were migrated to ``patients_crud.py``, but
other modules (appointments, medications) still import ``_get_current_user_simple``
from ``app.api.v2.patients``. This module re-exports the router and keeps the
helper available to avoid breaking those dependencies.
"""

from typing import Optional, Dict, Any, List
from datetime import date, datetime
import inspect
import logging

from fastapi import (
    Cookie,
    Body,
    Header,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.api.v2.dependencies import (
    get_eager_load_params,
    get_field_selection,
    get_pagination_params,
)
from app.api.v2.routers.patients.crud import (
    create_patient as create_patient_v2,
    list_patients as list_patients_v2,
)
from app.api.v2.routers.patients import router as patients_router
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.models.user import User, UserRole
from app.repositories.patient import PatientRepository
from app.schemas.v2.patient import PatientV2Create
from app.services.patient import PatientCRUDService

logger = logging.getLogger(__name__)

# Re-export router so legacy imports keep working
router = patients_router
get_current_user = get_current_user_from_session
PatientService = PatientCRUDService


def _extract_user_id(current_user: Any) -> Optional[str]:
    if isinstance(current_user, dict):
        return current_user.get("id")
    user_id = getattr(current_user, "id", None)
    return str(user_id) if user_id is not None else None


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _resolve_current_user(
    request: Request,
    session_cookie_id: Optional[str],
    x_session_id: Optional[str],
    authorization: Optional[str],
    redis_cache,
):
    resolver = get_current_user
    if resolver is get_current_user_from_session:
        return await resolver(
            request=request,
            session_cookie_id=session_cookie_id,
            x_session_id=x_session_id,
            authorization=authorization,
            redis_cache=redis_cache,
        )
    try:
        result = resolver()
    except TypeError:
        result = resolver(request)
    return await _maybe_await(result)


async def list_patients_compat(
    request: Request,
    db: Session = Depends(get_db),
    session_cookie_id: Optional[str] = Cookie(None, alias="session_id"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    authorization: Optional[str] = Header(None),
    redis_cache=Depends(get_redis_cache),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    limit: Optional[int] = Query(None, ge=1, description="Items per page (max 1000)"),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    search: Optional[str] = Query(None, description="Search by name or email"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by patient status/flow state"
    ),
    treatment_type: Optional[str] = Query(None, description="Filter by treatment type"),
    start_date_from: Optional[date] = Query(
        None,
        description="Filter patients with treatment_start_date on or after this date",
    ),
    start_date_to: Optional[date] = Query(
        None,
        description="Filter patients with treatment_start_date on or before this date",
    ),
    treatment_phase: Optional[str] = Query(
        None, description="Filter by treatment phase"
    ),
    has_active_flow: Optional[bool] = Query(
        None, description="Filter by active flow state"
    ),
    created_after: Optional[datetime] = Query(
        None, description="Filter patients created after this datetime"
    ),
    created_before: Optional[datetime] = Query(
        None, description="Filter patients created before this datetime"
    ),
    sort_by: Optional[str] = Query("created_at", description="Sort by field"),
    sort_order: Optional[str] = Query(
        "desc", pattern="^(asc|desc)$", description="Sort order"
    ),
):
    current_user = await _resolve_current_user(
        request=request,
        session_cookie_id=session_cookie_id,
        x_session_id=x_session_id,
        authorization=authorization,
        redis_cache=redis_cache,
    )
    service = PatientService(db=db, repository=PatientRepository(db))
    if not isinstance(service, PatientCRUDService) and hasattr(service, "list_patients"):
        result = service.list_patients(
            doctor_id=_extract_user_id(current_user),
            page=page,
            size=size,
            search=search,
        )
        return await _maybe_await(result)

    pagination = get_pagination_params(cursor=cursor, limit=limit or size)
    return await list_patients_v2(
        request=request,
        db=db,
        current_user=current_user,
        pagination=pagination,
        fields=fields,
        include=include,
        search=search,
        status_filter=status_filter,
        treatment_type=treatment_type,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        treatment_phase=treatment_phase,
        has_active_flow=has_active_flow,
        created_after=created_after,
        created_before=created_before,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def create_patient_compat(
    request: Request,
    patient_data: dict = Body(...),
    db: Session = Depends(get_db),
    session_cookie_id: Optional[str] = Cookie(None, alias="session_id"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    authorization: Optional[str] = Header(None),
    redis_cache=Depends(get_redis_cache),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    current_user = await _resolve_current_user(
        request=request,
        session_cookie_id=session_cookie_id,
        x_session_id=x_session_id,
        authorization=authorization,
        redis_cache=redis_cache,
    )
    service = PatientService(db=db, repository=PatientRepository(db))
    if not isinstance(service, PatientCRUDService) and hasattr(service, "create_patient"):
        result = service.create_patient(
            patient_data,
            current_user=current_user,
            idempotency_key=x_idempotency_key,
        )
        return await _maybe_await(result)

    payload = dict(patient_data)
    if "doctor_id" not in payload:
        doctor_id = _extract_user_id(current_user)
        if doctor_id:
            payload["doctor_id"] = doctor_id
    patient_model = PatientV2Create(**payload)

    return await create_patient_v2(
        request=request,
        patient_data=patient_model,
        db=db,
        current_user=current_user,
        x_idempotency_key=x_idempotency_key,
    )


async def _get_current_user_simple(
    session_cookie_id: Optional[str] = Cookie(None, alias="session_id"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
) -> Dict[str, Any]:
    """
    Minimal session validation helper used by other endpoints.

    Returns a dict with user information or raises HTTP 401/403 accordingly.
    """
    final_session_id = session_cookie_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided",
        )

    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
        )

    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
            if isinstance(user.role, UserRole)
            else str(user.role),
            "is_active": user.is_active,
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user_data


__all__ = [
    "router",
    "_get_current_user_simple",
    "get_current_user",
    "PatientService",
    "list_patients_compat",
    "create_patient_compat",
]
