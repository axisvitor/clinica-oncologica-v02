"""
Patients API v2
Enhanced patient endpoints with cursor pagination, field selection, and eager loading.
"""

from typing import Optional, List, Tuple, Dict
from datetime import date, datetime
from uuid import UUID
import re
import logging
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.database import get_db
from app.models.patient import Patient, FlowState
from app.models.user import User, UserRole
from app.repositories.patient import PatientRepository
from app.services.flow_engine import FlowEngine
from app.services.patient import PatientService, PatientIntegrityService
from app.schemas.patient import PatientCreate, validate_cpf as validate_cpf_value
from app.schemas.v2.patient import (
    PatientV2Response,
    PatientV2List,
    PatientV2Create,
    PatientV2Update,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.dependencies import get_patient_service
from app.utils.rate_limiter import limiter
from app.utils.unified_cache import invalidate_patient_cache
from fastapi import Cookie, Header
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_current_user_simple(
    session_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """Simplified session validation without ServiceProvider."""
    final_session_id = session_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided"
        )
    
    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data"
        )
    
    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        # Query DB directly
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)
    
    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user_data


def _extract_user_context(current_user) -> Tuple[Optional[UserRole], Optional[str]]:
    """Return (role, user_id as str) from current_user (model or dict)."""
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


def _ensure_patient_access(current_user, patient_doctor_id):
    if _is_admin(current_user):
        return

    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)

    if user_uuid is None or patient_doctor_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this patient",
        )


def _normalize_cpf(cpf: Optional[str]) -> Optional[str]:
    """
    Normalize CPF by removing non-digit characters.
    
    Args:
        cpf: CPF string with optional formatting (dots, dashes)
    
    Returns:
        CPF with only digits (max 11 chars) or None
    """
    if not cpf:
        return None
    # Remove all non-digit characters
    normalized = re.sub(r'[^0-9]', '', cpf)
    # Limit to 11 digits (CPF max length)
    return normalized[:11] if normalized else None


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone by removing non-digit characters.
    
    Args:
        phone: Phone string with optional formatting
    
    Returns:
        Phone with only digits or None
    """
    if not phone:
        return None
    # Remove all non-digit characters (spaces, parentheses, dashes)
    normalized = re.sub(r'[^0-9+]', '', phone)
    return normalized if normalized else None


def _serialize_patient(patient) -> Optional[dict]:
    """Serialize Patient SQLAlchemy model to API-friendly dict."""
    if patient is None:
        return None

    flow_state = getattr(patient, "flow_state", None)
    if isinstance(flow_state, FlowState):
        flow_state_value = flow_state.value
    else:
        flow_state_value = flow_state

    created_at = getattr(patient, "created_at", None)
    updated_at = getattr(patient, "updated_at", None)

    return {
        "id": str(getattr(patient, "id")),
        "name": getattr(patient, "name"),
        "email": getattr(patient, "email"),
        "phone": getattr(patient, "phone"),
        "birth_date": getattr(patient, "birth_date"),
        "cpf": getattr(patient, "cpf"),
        "doctor_id": str(getattr(patient, "doctor_id")) if getattr(patient, "doctor_id", None) else None,
        "treatment_type": getattr(patient, "treatment_type", None),
        "treatment_start_date": getattr(patient, "treatment_start_date", None),
        "doctor_notes": getattr(patient, "doctor_notes", None),
        "diagnosis": getattr(patient, "diagnosis", None),
        "treatment_phase": getattr(patient, "treatment_phase", None),
        "current_day": getattr(patient, "current_day", None),
        "flow_state": flow_state_value,
        "created_at": created_at,
        "updated_at": updated_at,
    }


class PatientStatsResponse(BaseModel):
    total_patients: int
    active_patients: int
    inactive_patients: int
    new_this_month: int
    by_status: Dict[str, int]


class CPFValidationRequest(BaseModel):
    cpf: str


class EmailCheckResponse(BaseModel):
    email: EmailStr
    exists: bool


class ImportError(BaseModel):
    row: int
    message: str


class ImportResponse(BaseModel):
    success: int
    failed: int
    errors: List[ImportError]


@router.get(
    "",
    response_model=PatientV2List,
    summary="List patients with pagination",
    description="Get paginated list of patients with optional field selection and eager loading"
)
async def list_patients(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    search: Optional[str] = Query(None, description="Search by name or email"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by patient status/flow state"),
    treatment_type: Optional[str] = Query(None, description="Filter by treatment type"),
    start_date_from: Optional[date] = Query(None, description="Filter patients with treatment_start_date on or after this date"),
    start_date_to: Optional[date] = Query(None, description="Filter patients with treatment_start_date on or before this date"),
):
    """
    List patients with cursor-based pagination.
    
    Features:
    - Cursor-based pagination (efficient for large datasets)
    - Field selection (?fields=id,name,email)
    - Eager loading (?include=doctor,quizzes)
    - Search by name or email
    - Filter by active status
    
    Example:
        GET /api/v2/patients?limit=20&fields=id,name,email&include=doctor
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]
    
    # Build base query
    query = db.query(Patient)
    
    # Apply eager loading
    if include:
        if "doctor" in include:
            query = query.options(joinedload(Patient.doctor))
        if "quiz_sessions" in include or "quizzes" in include:
            query = query.options(joinedload(Patient.quiz_sessions))
    
    # Apply filters
    filters = []
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # Filter out soft-deleted patients by default
    filters.append(Patient.deleted_at.is_(None))

    # RBAC: Non-admin users can only see their own patients
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        filters.append(Patient.doctor_id == current_user_uuid)

    if cursor_data and "id" in cursor_data:
        # Handle UUID comparison
        from uuid import UUID
        from datetime import datetime as dt
        cursor_id = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at = dt.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        
        # For descending order, we want records with created_at < cursor OR (created_at == cursor AND id > cursor_id)
        # This ensures proper pagination with tie-breaking
        filters.append(
            (Patient.created_at < cursor_created_at) |
            ((Patient.created_at == cursor_created_at) & (Patient.id > cursor_id))
        )
    
    if search:
        search_filter = f"%{search}%"
        filters.append(
            (Patient.name.ilike(search_filter)) | (Patient.email.ilike(search_filter))
        )
    
    if status_filter:
        status_value = status_filter.strip().lower()
        status_aliases = {
            "inactive": FlowState.CANCELLED,
            "canceled": FlowState.CANCELLED,
            "cancelled": FlowState.CANCELLED,
        }
        target_state = status_aliases.get(status_value)
        if target_state is None:
            try:
                target_state = FlowState(status_value)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status filter. Use active, paused, completed, cancelled or inactive."
                )
        filters.append(Patient.flow_state == target_state)
    
    if treatment_type:
        filters.append(Patient.treatment_type.ilike(f"%{treatment_type.strip()}%"))
    
    if start_date_from:
        filters.append(Patient.treatment_start_date >= start_date_from)
    
    if start_date_to:
        filters.append(Patient.treatment_start_date <= start_date_to)
    
    if filters:
        query = query.filter(and_(*filters))

    total = None
    if not cursor_data:
        total_query = db.query(func.count(Patient.id))
        if filters:
            total_query = total_query.filter(and_(*filters))
        total = total_query.scalar()
    
    # Order and limit
    query = query.order_by(Patient.created_at.desc(), Patient.id)
    patients = query.limit(limit + 1).all()
    
    # Check if there are more results
    has_more = len(patients) > limit
    if has_more:
        patients = patients[:limit]
    
    # Create next cursor
    next_cursor = None
    if has_more and patients:
        import json
        import base64
        cursor_data = {
            "id": str(patients[-1].id),
            "created_at": patients[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()
    
    # Convert to response models
    patient_responses = []
    for patient in patients:
        patient_dict = _serialize_patient(patient)
        
        # Add eager-loaded relationships
        if include:
            if "doctor" in include and patient.doctor:
                patient_dict["doctor"] = {
                    "id": str(patient.doctor.id),
                    "name": patient.doctor.name,
                    "email": patient.doctor.email,
                }
            if ("quiz_sessions" in include or "quizzes" in include) and hasattr(patient, "quiz_sessions"):
                patient_dict["quiz_sessions"] = [
                    {
                        "id": str(q.id),
                        "status": q.status,
                        "started_at": q.started_at,
                        "completed_at": q.completed_at,
                        "score": float(q.score) if q.score else None,
                        "passed": q.passed,
                    }
                    for q in patient.quiz_sessions
                ]
        
        # Apply field selection
        if fields:
            patient_dict = apply_field_selection(patient_dict, fields)
        
        patient_responses.append(patient_dict)
    
    return {
        "data": patient_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.get(
    "/search",
    response_model=List[PatientV2Response],
    summary="Search patients",
    description="Search patients by name or email (doctor/admin only)",
)
@limiter.limit("120/minute")
async def search_patients(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    query = db.query(Patient).filter(Patient.deleted_at.is_(None))

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.filter(Patient.doctor_id == current_user_uuid)

    search_filter = f"%{q}%"
    patients = (
        query.filter(
            (Patient.name.ilike(search_filter)) | (Patient.email.ilike(search_filter))
        )
        .order_by(Patient.created_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_patient(patient) for patient in patients]


@router.get(
    "/export",
    summary="Export patients to CSV",
    description="Export patients to CSV with optional filters (ADMIN/DOCTOR only)",
)
@limiter.limit("10/hour")
async def export_patients(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by patient status/flow state"),
    doctor_id: Optional[str] = Query(None, description="Filter by doctor ID (ADMIN only)"),
    start_date_from: Optional[date] = Query(None, description="Filter patients with treatment_start_date on or after this date"),
    start_date_to: Optional[date] = Query(None, description="Filter patients with treatment_start_date on or before this date"),
):
    """
    Export patients to CSV file with optional filters.

    Features:
    - Filter by status, doctor_id, date range
    - Streaming response for large datasets
    - Rate limited to 10 requests per hour
    - Includes all patient fields

    Example:
        GET /api/v2/patients/export?status=active&start_date_from=2024-01-01
    """
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # Build query with filters
    query = db.query(Patient).filter(Patient.deleted_at.is_(None))

    # RBAC: Non-admin users can only export their own patients
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.filter(Patient.doctor_id == current_user_uuid)

    # Apply doctor_id filter (admin only)
    if doctor_id:
        if role_enum != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can filter by doctor_id",
            )
        try:
            doctor_uuid = UUID(doctor_id)
            query = query.filter(Patient.doctor_id == doctor_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid doctor ID format"
            )

    # Apply status filter
    if status_filter:
        status_value = status_filter.strip().lower()
        status_aliases = {
            "inactive": FlowState.CANCELLED,
            "canceled": FlowState.CANCELLED,
            "cancelled": FlowState.CANCELLED,
        }
        target_state = status_aliases.get(status_value)
        if target_state is None:
            try:
                target_state = FlowState(status_value)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status filter. Use active, paused, completed, cancelled or inactive."
                )
        query = query.filter(Patient.flow_state == target_state)

    # Apply date range filters
    if start_date_from:
        query = query.filter(Patient.treatment_start_date >= start_date_from)

    if start_date_to:
        query = query.filter(Patient.treatment_start_date <= start_date_to)

    # Order by created_at for consistent export
    query = query.order_by(Patient.created_at.desc())

    # Check if export is cached (optional optimization)
    cache_key = f"patient_export:{user_id}:{status_filter}:{doctor_id}:{start_date_from}:{start_date_to}"
    cached_data = await redis_cache.get(cache_key)

    # Fetch all patients (streaming for large datasets)
    patients = query.all()

    if not patients:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No patients found matching the criteria"
        )

    # Create CSV in memory using streaming
    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV headers
    headers = [
        "ID", "Name", "Email", "Phone", "Birth Date", "CPF",
        "Doctor ID", "Treatment Type", "Treatment Start Date",
        "Diagnosis", "Treatment Phase", "Flow State", "Current Day",
        "Doctor Notes", "Created At", "Updated At"
    ]
    writer.writerow(headers)

    # Write patient rows
    for patient in patients:
        row = [
            str(patient.id),
            patient.name,
            patient.email or "",
            patient.phone or "",
            patient.birth_date.isoformat() if patient.birth_date else "",
            patient.cpf or "",
            str(patient.doctor_id) if patient.doctor_id else "",
            patient.treatment_type or "",
            patient.treatment_start_date.isoformat() if patient.treatment_start_date else "",
            patient.diagnosis or "",
            patient.treatment_phase or "",
            patient.flow_state.value if isinstance(patient.flow_state, FlowState) else patient.flow_state,
            patient.current_day or 0,
            patient.doctor_notes or "",
            patient.created_at.isoformat() if patient.created_at else "",
            patient.updated_at.isoformat() if patient.updated_at else "",
        ]
        writer.writerow(row)

    # Get CSV content
    csv_content = output.getvalue()
    output.close()

    # Cache the export for 5 minutes
    await redis_cache.set(cache_key, csv_content, ttl=300)

    # Return streaming response
    def iter_csv():
        yield csv_content.encode('utf-8')

    filename = f"patients_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        }
    )


@router.post(
    "/import",
    response_model=ImportResponse,
    summary="Import patients from CSV",
    description="Import patients from CSV file with validation (ADMIN/DOCTOR only)",
)
@limiter.limit("5/hour")
async def import_patients(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with patient data"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Import patients from CSV file with validation.

    Features:
    - Accept multipart/form-data with CSV file
    - Validate CSV structure and data
    - Return detailed success/failure report
    - Rate limited to 5 requests per hour
    - Background task for large imports (>100 rows)

    CSV Format:
    - Required headers: Name, Phone, Email (optional), Birth Date (optional),
      CPF (optional), Treatment Type (optional), Treatment Start Date (optional),
      Diagnosis (optional), Treatment Phase (optional), Doctor Notes (optional)

    Example:
        POST /api/v2/patients/import
        Content-Type: multipart/form-data
        file: patients.csv
    """
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if current_user_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to determine user permissions",
        )

    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted"
        )

    # Read CSV content
    try:
        contents = await file.read()
        csv_content = contents.decode('utf-8')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read CSV file: {str(e)}"
        )

    # Parse CSV
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)

    # Validate CSV headers
    required_headers = {'Name', 'Phone'}
    optional_headers = {
        'Email', 'Birth Date', 'CPF', 'Treatment Type',
        'Treatment Start Date', 'Diagnosis', 'Treatment Phase', 'Doctor Notes'
    }
    valid_headers = required_headers | optional_headers

    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or has no headers"
        )

    csv_headers = set(reader.fieldnames)
    missing_headers = required_headers - csv_headers
    if missing_headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required headers: {', '.join(missing_headers)}"
        )

    # Track results
    success_count = 0
    failed_count = 0
    errors: List[ImportError] = []
    row_number = 1  # Start at 1 (header is row 0)

    # Process rows
    for row in reader:
        row_number += 1

        try:
            # Validate required fields
            name = row.get('Name', '').strip()
            phone = row.get('Phone', '').strip()

            if not name:
                errors.append(ImportError(row=row_number, message="Name is required"))
                failed_count += 1
                continue

            if not phone:
                errors.append(ImportError(row=row_number, message="Phone is required"))
                failed_count += 1
                continue

            # Normalize phone
            normalized_phone = _normalize_phone(phone)
            if not normalized_phone:
                errors.append(ImportError(row=row_number, message="Invalid phone format"))
                failed_count += 1
                continue

            # Ensure E.164 format
            e164_phone = normalized_phone if normalized_phone.startswith('+') else f"+{normalized_phone}"

            # Check for duplicate phone
            existing_phone = db.query(Patient).filter(
                Patient.phone == e164_phone,
                Patient.deleted_at.is_(None)
            ).first()
            if existing_phone:
                errors.append(ImportError(row=row_number, message=f"Patient with phone {phone} already exists"))
                failed_count += 1
                continue

            # Parse optional fields
            email = row.get('Email', '').strip() or None
            cpf = _normalize_cpf(row.get('CPF', '').strip()) if row.get('CPF') else None
            treatment_type = row.get('Treatment Type', '').strip() or None
            diagnosis = row.get('Diagnosis', '').strip() or None
            treatment_phase = row.get('Treatment Phase', '').strip() or None
            doctor_notes = row.get('Doctor Notes', '').strip() or None

            # Parse dates
            birth_date = None
            if row.get('Birth Date'):
                try:
                    birth_date = datetime.strptime(row.get('Birth Date').strip(), '%Y-%m-%d').date()
                except ValueError:
                    errors.append(ImportError(row=row_number, message="Invalid birth date format (use YYYY-MM-DD)"))
                    failed_count += 1
                    continue

            treatment_start_date = None
            if row.get('Treatment Start Date'):
                try:
                    treatment_start_date = datetime.strptime(row.get('Treatment Start Date').strip(), '%Y-%m-%d').date()
                except ValueError:
                    errors.append(ImportError(row=row_number, message="Invalid treatment start date format (use YYYY-MM-DD)"))
                    failed_count += 1
                    continue

            # Validate CPF if provided
            if cpf and len(cpf) != 11:
                errors.append(ImportError(row=row_number, message=f"CPF must have exactly 11 digits, got {len(cpf)}"))
                failed_count += 1
                continue

            # Check for duplicate CPF
            if cpf:
                existing_cpf = db.query(Patient).filter(
                    Patient.cpf == cpf,
                    Patient.deleted_at.is_(None)
                ).first()
                if existing_cpf:
                    errors.append(ImportError(row=row_number, message=f"Patient with CPF already exists"))
                    failed_count += 1
                    continue

            # Check for duplicate email
            if email:
                existing_email = db.query(Patient).filter(
                    Patient.email == email,
                    Patient.deleted_at.is_(None)
                ).first()
                if existing_email:
                    errors.append(ImportError(row=row_number, message=f"Patient with email {email} already exists"))
                    failed_count += 1
                    continue

            # Create patient
            new_patient = Patient(
                name=name,
                phone=e164_phone,
                email=email,
                birth_date=birth_date,
                cpf=cpf,
                treatment_type=treatment_type,
                treatment_start_date=treatment_start_date,
                diagnosis=diagnosis,
                treatment_phase=treatment_phase,
                doctor_notes=doctor_notes,
                doctor_id=current_user_uuid,
                flow_state=FlowState.ONBOARDING,
                current_day=0,
            )

            db.add(new_patient)
            db.flush()  # Flush to get the ID but don't commit yet

            success_count += 1

        except Exception as e:
            logger.error(f"Failed to import row {row_number}: {e}")
            errors.append(ImportError(row=row_number, message=f"Unexpected error: {str(e)}"))
            failed_count += 1
            db.rollback()
            continue

    # Commit all successful imports
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit imports: {str(e)}"
        )

    # Return import results
    return ImportResponse(
        success=success_count,
        failed=failed_count,
        errors=errors[:100]  # Limit to first 100 errors
    )


@router.get(
    "/{patient_id}",
    response_model=PatientV2Response,
    summary="Get patient by ID",
    description="Get a single patient with optional field selection and eager loading"
)
async def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get a single patient by ID.
    
    Features:
    - Field selection (?fields=id,name,email)
    - Eager loading (?include=doctor,quiz_sessions)
    
    Example:
        GET /api/v2/patients/123e4567-e89b-12d3-a456-426614174000?fields=id,name,email&include=doctor
    """
    from uuid import UUID
    
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    query = db.query(Patient)
    
    # Apply eager loading
    if include:
        if "doctor" in include:
            query = query.options(joinedload(Patient.doctor))
        if "quiz_sessions" in include or "quizzes" in include:
            query = query.options(joinedload(Patient.quiz_sessions))
    
    patient = query.filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    _ensure_patient_access(current_user, patient.doctor_id)
    
    # Build response
    patient_dict = _serialize_patient(patient)
    
    # Add eager-loaded relationships
    if include:
        if "doctor" in include and patient.doctor:
            patient_dict["doctor"] = {
                "id": str(patient.doctor.id),
                "name": patient.doctor.name,
                "email": patient.doctor.email,
            }
        if ("quiz_sessions" in include or "quizzes" in include) and hasattr(patient, "quiz_sessions"):
            patient_dict["quiz_sessions"] = [
                {
                    "id": str(q.id),
                    "status": q.status,
                    "started_at": q.started_at,
                    "completed_at": q.completed_at,
                    "score": float(q.score) if q.score else None,
                    "passed": q.passed,
                }
                for q in patient.quiz_sessions
            ]
    
    # Apply field selection
    if fields:
        patient_dict = apply_field_selection(patient_dict, fields)
    
    return patient_dict


@router.post(
    "",
    response_model=PatientV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new patient",
    description="Create a new patient record (ADMIN/DOCTOR only)"
)
@limiter.limit("20/hour")
async def create_patient(
    request: Request,
    patient_data: PatientV2Create,
    db: Session = Depends(get_db),
    current_user = Depends(_get_current_user_simple),
):
    """
    Create a new patient.
    
    Validates:
    - Doctor exists
    - Email is unique (if provided)
    - CPF is unique (if provided)
    - Phone is unique
    """
    from uuid import UUID
    
    # Convert doctor_id to UUID
    try:
        doctor_uuid = UUID(patient_data.doctor_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID format"
        )
    
    # Check if doctor exists
    doctor = db.query(User).filter(User.id == doctor_uuid).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {patient_data.doctor_id} not found"
        )
    
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None or current_user_uuid != doctor_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors can only create patients for themselves"
            )

    # Normalize CPF and Phone before validation
    normalized_cpf = _normalize_cpf(patient_data.cpf)
    normalized_phone = _normalize_phone(patient_data.phone)
    
    # Validate CPF length after normalization
    if normalized_cpf and len(normalized_cpf) != 11:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CPF must have exactly 11 digits, got {len(normalized_cpf)}"
        )
    
    # Check email uniqueness (if provided)
    if patient_data.email:
        existing_email = db.query(Patient).filter(
            Patient.email == patient_data.email,
            Patient.deleted_at.is_(None)
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with email {patient_data.email} already exists"
            )
    
    # Check CPF uniqueness (if provided)
    if normalized_cpf:
        existing_cpf = db.query(Patient).filter(
            Patient.cpf == normalized_cpf,
            Patient.deleted_at.is_(None)
        ).first()
        if existing_cpf:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with CPF already exists"
            )
    
    # Check phone uniqueness (required field)
    if normalized_phone:
        existing_phone = db.query(Patient).filter(
            Patient.phone == normalized_phone,
            Patient.deleted_at.is_(None)
        ).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient with phone already exists"
            )
    
    # Use service layer (Saga + welcome WhatsApp + auto flow) for creation
    # Ensure phone matches PatientCreate validator (E.164 starting with '+')
    e164_phone = normalized_phone if (normalized_phone and normalized_phone.startswith('+')) else (f"+{normalized_phone}" if normalized_phone else None)
    if not e164_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required"
        )

    # Instantiate services directly (thread-safe per-request pattern)
    patient_repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, patient_repo)
    flow_engine = FlowEngine(db)
    
    # Create SagaOrchestrator using the same DB session to maintain consistency
    saga_orchestrator = None
    try:
        from app.coordination.saga_orchestrator import SagaOrchestrator
        from app.core.redis_client import get_redis_client
        from app.integrations.evolution import EvolutionClient
        
        saga_orchestrator = SagaOrchestrator(
            db=db,
            redis=get_redis_client(),
            evolution_client=EvolutionClient()
        )
    except Exception as e:
        logger.warning(f"Failed to initialize SagaOrchestrator: {e}. Patient will be created without Saga.")
    
    service = PatientService(
        db=db,
        patient_repository=patient_repo,
        integrity_service=integrity_service,
        flow_engine=flow_engine,
        saga_orchestrator=saga_orchestrator
    )

    created = await service.create_patient(
        patient_data=PatientCreate(
            phone=e164_phone,
            name=patient_data.name,
            email=patient_data.email,
            birth_date=patient_data.birth_date,
            cpf=normalized_cpf,
            treatment_type=patient_data.treatment_type,
            treatment_start_date=patient_data.treatment_start_date,
            doctor_notes=patient_data.doctor_notes,
            diagnosis=patient_data.diagnosis,
            treatment_phase=patient_data.treatment_phase,
        ),
        doctor_id=doctor_uuid,
        current_user=current_user,
    )

    # Return formatted response from created entity
    return _serialize_patient(created)


@router.patch(
    "/{patient_id}",
    response_model=PatientV2Response,
    summary="Update patient",
    description="Update patient information (partial update) (ADMIN/DOCTOR only)"
)
@limiter.limit("30/hour")
async def update_patient(
    request: Request,
    patient_id: str,
    patient_data: PatientV2Update,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Update a patient (partial update).
    
    Only provided fields will be updated.
    """
    from uuid import UUID
    
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )

    _ensure_patient_access(current_user, patient.doctor_id)
    
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    # Update only provided fields
    update_data = patient_data.dict(exclude_unset=True)
    
    # Normalize CPF and Phone if provided
    if "cpf" in update_data and update_data["cpf"]:
        normalized_cpf = _normalize_cpf(update_data["cpf"])
        if normalized_cpf and len(normalized_cpf) != 11:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CPF must have exactly 11 digits, got {len(normalized_cpf)}"
            )
        update_data["cpf"] = normalized_cpf
        
        # Check CPF uniqueness (exclude current patient)
        if normalized_cpf:
            existing_cpf = db.query(Patient).filter(
                Patient.cpf == normalized_cpf,
                Patient.id != patient.id,
                Patient.deleted_at.is_(None)
            ).first()
            if existing_cpf:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Patient with CPF already exists"
                )
    
    if "phone" in update_data and update_data["phone"]:
        normalized_phone = _normalize_phone(update_data["phone"])
        update_data["phone"] = normalized_phone
        
        # Check phone uniqueness (exclude current patient)
        if normalized_phone:
            existing_phone = db.query(Patient).filter(
                Patient.phone == normalized_phone,
                Patient.id != patient.id,
                Patient.deleted_at.is_(None)
            ).first()
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Patient with phone already exists"
                )
    
    # Convert doctor_id to UUID if provided
    if "doctor_id" in update_data:
        if update_data["doctor_id"]:
            try:
                new_doctor_uuid = UUID(update_data["doctor_id"])
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid doctor ID format"
                )
            if role_enum != UserRole.ADMIN:
                if current_user_uuid is None or current_user_uuid != new_doctor_uuid:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Doctors cannot reassign patients to other doctors"
                    )
            update_data["doctor_id"] = new_doctor_uuid
        else:
            # Prevent doctors from clearing doctor assignment
            if role_enum != UserRole.ADMIN:
                update_data.pop("doctor_id")
    
    for field, value in update_data.items():
        setattr(patient, field, value)
    
    db.commit()
    db.refresh(patient)
    
    # Return formatted response
    return _serialize_patient(patient)


@router.post(
    "/{patient_id}/activate",
    response_model=PatientV2Response,
    summary="Activate patient flow",
    description="Set patient flow_state to active (doctor/admin only)",
)
@limiter.limit("30/hour")
async def activate_patient(
    patient_id: str,
    current_user = Depends(get_current_user_from_session),
    patient_service: PatientService = Depends(get_patient_service),
):
    patient_uuid = _ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        )

    patient = patient_service.repository.get_by_id(patient_uuid)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    updated_patient = await patient_service.activate_patient(patient_uuid)
    if not updated_patient:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate patient",
        )

    invalidate_patient_cache(str(patient_uuid))
    return _serialize_patient(updated_patient)


@router.post(
    "/{patient_id}/deactivate",
    response_model=PatientV2Response,
    summary="Deactivate patient flow",
    description="Pause/mark patient as inactive (doctor/admin only)",
)
@limiter.limit("30/hour")
async def deactivate_patient(
    patient_id: str,
    current_user = Depends(get_current_user_from_session),
    patient_service: PatientService = Depends(get_patient_service),
):
    patient_uuid = _ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        )

    patient = patient_service.repository.get_by_id(patient_uuid)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    updated_patient = await patient_service.deactivate_patient(patient_uuid)
    if not updated_patient:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate patient",
        )

    invalidate_patient_cache(str(patient_uuid))
    return _serialize_patient(updated_patient)


@router.post(
    "/{patient_id}/archive",
    response_model=PatientV2Response,
    summary="Archive patient",
    description="Archive a patient (similar to deactivate but with archived status) (ADMIN/DOCTOR only)",
)
@limiter.limit("30/hour")
async def archive_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Archive a patient.

    Similar to deactivate but sets the patient flow_state to CANCELLED and
    adds an archived flag to metadata for future filtering and reporting.

    Archived patients:
    - Are marked as CANCELLED in flow_state
    - Have metadata.archived = true
    - Can be distinguished from regular cancelled patients
    - Can still be viewed and restored if needed
    """
    patient_uuid = _ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        )

    # Get patient
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    _ensure_patient_access(current_user, patient.doctor_id)

    # Update patient flow state to CANCELLED
    patient.flow_state = FlowState.CANCELLED

    # Add archived flag to metadata
    if patient.patient_data is None:
        patient.patient_data = {}

    patient.patient_data["archived"] = True
    patient.patient_data["archived_at"] = datetime.utcnow().isoformat()

    # Get user info for metadata
    role_enum, user_id = _extract_user_context(current_user)
    if user_id:
        patient.patient_data["archived_by"] = str(user_id)

    # Mark the patient_data as modified to trigger SQLAlchemy update
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(patient, "patient_data")

    # Commit changes
    try:
        db.commit()
        db.refresh(patient)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to archive patient {patient_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive patient: {str(e)}"
        )

    # Invalidate cache
    invalidate_patient_cache(str(patient_uuid))

    # Return updated patient
    return _serialize_patient(patient)


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete patient (soft delete)",
    description="Soft delete a patient record - marks as deleted without removing from database"
)
@limiter.limit("10/hour")
async def delete_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Soft delete a patient.
    
    This marks the patient as deleted (sets deleted_at timestamp) without
    removing the record from the database. This preserves data for audit
    purposes and allows restoration if needed.
    """
    from uuid import UUID
    from datetime import datetime
    
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    # Only get active patients (not already deleted)
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active patient with id {patient_id} not found"
        )
    
    # Soft delete: set deleted_at timestamp
    patient.deleted_at = datetime.utcnow()
    db.commit()
    
    return None


@router.post(
    "/{patient_id}/restore",
    response_model=PatientV2Response,
    summary="Restore deleted patient",
    description="Restore a soft-deleted patient record"
)
@limiter.limit("10/hour")
async def restore_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Restore a soft-deleted patient.
    
    This removes the deleted_at timestamp, making the patient active again.
    """
    from uuid import UUID
    
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    # Only get deleted patients
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.isnot(None)
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deleted patient with id {patient_id} not found"
        )
    
    # Restore: remove deleted_at timestamp
    patient.deleted_at = None
    db.commit()
    db.refresh(patient)
    
    return PatientV2Response.from_orm(patient)


@router.get(
    "/{patient_id}/timeline",
    summary="Get patient timeline",
    description="Return a lightweight patient timeline for activity feeds",
)
@limiter.limit("60/minute")
async def get_patient_timeline(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    patient_uuid = _ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        )

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_uuid, Patient.deleted_at.is_(None))
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    _ensure_patient_access(current_user, patient.doctor_id)

    created_event = {
        "date": patient.created_at,
        "event": "patient_created",
        "details": f"Paciente {patient.name} foi cadastrado",
        "metadata": {
            "doctor_id": str(patient.doctor_id) if patient.doctor_id else None,
            "treatment_type": patient.treatment_type,
        },
    }

    return {
        "patient_id": patient_id,
        "events": [created_event],
    }


@router.get(
    "/stats",
    response_model=PatientStatsResponse,
    summary="Get patient statistics summary",
)
@limiter.limit("30/minute")
async def get_patient_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    base_query = db.query(Patient).filter(Patient.deleted_at.is_(None))
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        base_query = base_query.filter(Patient.doctor_id == current_user_uuid)

    total_patients = base_query.count()
    active_patients = base_query.filter(Patient.flow_state == FlowState.ACTIVE).count()
    inactive_patients = base_query.filter(Patient.flow_state == FlowState.CANCELLED).count()

    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = base_query.filter(Patient.created_at >= start_of_month).count()

    by_status: Dict[str, int] = {}
    for state in FlowState:
        by_status[state.value] = base_query.filter(Patient.flow_state == state).count()

    return PatientStatsResponse(
        total_patients=total_patients,
        active_patients=active_patients,
        inactive_patients=inactive_patients,
        new_this_month=new_this_month,
        by_status=by_status,
    )


@router.post(
    "/validate-cpf",
    summary="Validate CPF",
)
@limiter.limit("60/minute")
async def validate_cpf_endpoint(payload: CPFValidationRequest):
    if not payload.cpf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF is required",
        )

    if not validate_cpf_value(payload.cpf):
        return {"valid": False, "message": "CPF inválido"}

    normalized = _normalize_cpf(payload.cpf)
    if normalized and len(normalized) != 11:
        return {"valid": False, "message": "CPF deve conter 11 dígitos"}

    return {"valid": True}


@router.get(
    "/check-email",
    response_model=EmailCheckResponse,
    summary="Check if patient email exists",
)
@limiter.limit("60/minute")
async def check_email_exists(
    email: EmailStr = Query(..., description="Email to validate"),
    db: Session = Depends(get_db),
):
    exists = (
        db.query(Patient)
        .filter(
            Patient.deleted_at.is_(None),
            func.lower(Patient.email) == email.lower(),
        )
        .first()
        is not None
    )
    return EmailCheckResponse(email=email, exists=exists)


@router.get(
    "/deleted",
    response_model=PatientV2List,
    summary="List deleted patients",
    description="Get list of soft-deleted patients (ADMIN only)"
)
@limiter.limit("30/minute")
async def list_deleted_patients(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    field_selection = Depends(get_field_selection),
):
    """
    List soft-deleted patients.
    
    Only administrators can view deleted patients.
    """
    role_enum, user_id = _extract_user_context(current_user)
    
    # Only admins can view deleted patients
    if role_enum != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view deleted patients"
        )
    
    # Query deleted patients
    query = db.query(Patient).filter(Patient.deleted_at.isnot(None))
    
    # Apply pagination
    total = query.count()
    patients = query.offset(pagination.skip).limit(pagination.limit).all()
    
    # Apply field selection
    patient_data = [apply_field_selection(patient, field_selection) for patient in patients]
    
    return PatientV2List(
        data=patient_data,
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        has_more=pagination.skip + len(patients) < total
    )
