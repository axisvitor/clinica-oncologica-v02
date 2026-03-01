"""
Patients API v2 - CSV Import/Export

This module handles CSV-based patient data operations:
- Export patients to CSV with filters
- Import patients from CSV with validation
- Bulk data operations

Migrated from: app/api/v2/routers/patients_import.py
Lines: 45-434
"""

# Standard library imports
import csv
import io
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4

# Third-party imports
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.database import get_async_db
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
)
from app.models.patient import FlowState, Patient
from app.models.user import UserRole
from app.schemas.validators.cpf import is_valid_cpf
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode
from app.utils.rate_limiter import limiter

from .base import (
    ImportError,
    ImportResponse,
    ensure_uuid,
    extract_user_context,
    normalize_cpf,
    parse_flow_state_filter,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)
router = APIRouter()

IMPORT_HISTORY_TTL_SECONDS = 60 * 60 * 24 * 30
IMPORT_HISTORY_MAX_ITEMS = 200


def _normalize_header(header: str) -> str:
    return re.sub(r"\s+", "_", header.strip().lower())


def _normalize_row(row: dict) -> dict:
    normalized = {}
    for key, value in row.items():
        if key is None:
            continue
        normalized_key = _normalize_header(str(key))
        normalized_value = value.strip() if isinstance(value, str) else value
        normalized[normalized_key] = normalized_value
    return normalized


async def _load_import_history(redis_cache, key: str) -> list:
    try:
        raw = await redis_cache.get(key)
        if not raw:
            return []
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception:
        return []


async def _store_import_history(redis_cache, key: str, history: list) -> None:
    try:
        await redis_cache.set(
            key,
            json.dumps(history, default=str),
            ex=IMPORT_HISTORY_TTL_SECONDS,
        )
    except Exception:
        logger.debug("Failed to persist import history", exc_info=True)


async def _append_import_history(redis_cache, key: str, entry: dict) -> None:
    history = await _load_import_history(redis_cache, key)
    history.insert(0, entry)
    del history[IMPORT_HISTORY_MAX_ITEMS:]
    await _store_import_history(redis_cache, key, history)


@router.post(
    "/import/validate",
    summary="Validate patient import file",
    description="Validate CSV format and data before importing patients",
)
@require_permission(Permission.PATIENT_CREATE)
@limiter.limit("20/hour")
async def validate_import_file(
    request: Request,
    file: UploadFile = File(..., description="CSV file with patient data"),
    current_user=Depends(get_current_user_from_session),
):
    filename = file.filename or ""
    filename_lower = filename.lower()

    if filename_lower.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="XLSX validation is not supported",
        )
    if not filename_lower.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted",
        )

    try:
        contents = await file.read()
        file_size = len(contents)
        csv_content = contents.decode("utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read CSV file: {str(e)}",
        )

    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        return {
            "valid": False,
            "totalRows": 0,
            "validRows": 0,
            "errorRows": 0,
            "warningRows": 0,
            "errors": [
                {
                    "row": 0,
                    "column": "headers",
                    "message": "CSV file is empty or has no headers",
                    "severity": "error",
                }
            ],
            "warnings": [],
            "preview": [],
            "format": "csv",
            "fileSize": file_size,
        }

    required_headers = {"name", "phone"}
    normalized_headers = {
        _normalize_header(header) for header in reader.fieldnames if header
    }
    missing_headers = required_headers - normalized_headers
    if missing_headers:
        return {
            "valid": False,
            "totalRows": 0,
            "validRows": 0,
            "errorRows": 0,
            "warningRows": 0,
            "errors": [
                {
                    "row": 0,
                    "column": "headers",
                    "message": f"Missing required headers: {', '.join(sorted(missing_headers))}",
                    "severity": "error",
                }
            ],
            "warnings": [],
            "preview": [],
            "format": "csv",
            "fileSize": file_size,
        }

    errors = []
    warnings = []
    preview = []
    total_rows = 0
    valid_rows = 0
    error_rows = 0
    warning_rows = 0

    for row in reader:
        total_rows += 1
        row_index = total_rows + 1
        normalized_row = _normalize_row(row)

        if len(preview) < 10:
            preview.append(
                {
                    "row": row_index,
                    "name": normalized_row.get("name"),
                    "email": normalized_row.get("email"),
                    "phone": normalized_row.get("phone"),
                    "cpf": normalized_row.get("cpf"),
                }
            )

        row_errors = []

        name = (normalized_row.get("name") or "").strip()
        phone = (normalized_row.get("phone") or "").strip()
        email = (normalized_row.get("email") or "").strip()
        cpf_raw = (normalized_row.get("cpf") or "").strip()

        if not name:
            row_errors.append(
                {
                    "row": row_index,
                    "column": "name",
                    "message": "Name is required",
                    "severity": "error",
                }
            )

        if not phone:
            row_errors.append(
                {
                    "row": row_index,
                    "column": "phone",
                    "message": "Phone is required",
                    "severity": "error",
                }
            )
        else:
            try:
                normalize_phone(
                    phone, mode=PhoneValidationMode.BR_TO_E164, allow_none=False
                )
            except ValueError:
                row_errors.append(
                    {
                        "row": row_index,
                        "column": "phone",
                        "message": "Invalid phone format",
                        "severity": "error",
                    }
                )

        if email:
            try:
                validate_email(email)
            except EmailNotValidError:
                row_errors.append(
                    {
                        "row": row_index,
                        "column": "email",
                        "message": "Invalid email format",
                        "severity": "error",
                    }
                )

        if cpf_raw:
            normalized_cpf = await normalize_cpf(cpf_raw)
            if not normalized_cpf or len(normalized_cpf) != 11:
                row_errors.append(
                    {
                        "row": row_index,
                        "column": "cpf",
                        "message": "CPF must have 11 digits",
                        "severity": "error",
                    }
                )
            elif not is_valid_cpf(normalized_cpf, allow_none=False):
                row_errors.append(
                    {
                        "row": row_index,
                        "column": "cpf",
                        "message": "Invalid CPF checksum",
                        "severity": "error",
                    }
                )

        if row_errors:
            errors.extend(row_errors)
            error_rows += 1
        else:
            valid_rows += 1

    return {
        "valid": error_rows == 0,
        "totalRows": total_rows,
        "validRows": valid_rows,
        "errorRows": error_rows,
        "warningRows": warning_rows,
        "errors": errors,
        "warnings": warnings,
        "preview": preview,
        "format": "csv",
        "fileSize": file_size,
    }


@router.get(
    "/import/template",
    summary="Download patient import template",
    description="Download CSV template for patient import",
)
@require_permission(Permission.PATIENT_CREATE)
@limiter.limit("60/minute")
async def download_import_template(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    format: str = Query("csv", description="Template format (csv or xlsx)"),
):
    format_value = (format or "csv").lower()
    if format_value == "xlsx":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="XLSX template is not supported",
        )
    if format_value != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV templates are supported",
        )

    output = io.StringIO()
    writer = csv.writer(output)
    headers = [
        "name",
        "email",
        "phone",
        "cpf",
        "birth_date",
        "treatment_type",
        "treatment_start_date",
        "diagnosis",
        "treatment_phase",
        "doctor_notes",
    ]
    writer.writerow(headers)
    writer.writerow(
        [
            "Joao Silva",
            "joao@example.com",
            "11999999999",
            "12345678900",
            "1980-05-15",
            "Reposicao Hormonal",
            "2025-01-10",
            "Breast",
            "initial",
            "Paciente em acompanhamento",
        ]
    )
    csv_content = output.getvalue()
    output.close()

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Type": "text/csv"},
    )


@router.get(
    "/import/history",
    summary="List patient import history",
    description="Retrieve paginated import history",
)
@require_permission(Permission.PATIENT_CREATE)
@limiter.limit("60/minute")
async def get_import_history(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    user_id: Optional[str] = Query(None, alias="user_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    start_date: Optional[str] = Query(None, alias="start_date"),
    end_date: Optional[str] = Query(None, alias="end_date"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    role_enum, current_user_id = await extract_user_context(current_user)
    current_user_uuid = await ensure_uuid(current_user_id)

    if role_enum != UserRole.ADMIN and current_user_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to determine user permissions",
        )

    if role_enum == UserRole.ADMIN:
        history_key = (
            f"patient_import_history:user:{user_id}"
            if user_id
            else "patient_import_history:all"
        )
    else:
        history_key = f"patient_import_history:user:{current_user_uuid}"

    history = await _load_import_history(redis_cache, history_key)

    if status_filter:
        status_value = status_filter.lower()
        history = [item for item in history if item.get("status") == status_value]

    def _parse_dt(value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    start_dt = _parse_dt(start_date) if start_date else None
    end_dt = _parse_dt(end_date) if end_date else None

    if start_dt or end_dt:
        filtered = []
        for item in history:
            item_dt = _parse_dt(item.get("startedAt") or "")
            if not item_dt:
                continue
            if start_dt and item_dt < start_dt:
                continue
            if end_dt and item_dt > end_dt:
                continue
            filtered.append(item)
        history = filtered

    total = len(history)
    start_index = (page - 1) * size
    end_index = start_index + size
    items = history[start_index:end_index]
    pages = (total + size - 1) // size if total else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.get(
    "/export",
    summary="Export patients to CSV",
    description="Export patients to CSV with optional filters (ADMIN/DOCTOR only)",
)
@require_permission(Permission.PATIENT_READ)
@limiter.limit("10/hour")
async def export_patients(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by patient status/flow state"
    ),
    doctor_id: Optional[str] = Query(
        None, description="Filter by doctor ID (ADMIN only)"
    ),
    start_date_from: Optional[date] = Query(
        None,
        description="Filter patients with treatment_start_date on or after this date",
    ),
    start_date_to: Optional[date] = Query(
        None,
        description="Filter patients with treatment_start_date on or before this date",
    ),
):
    """
    Export patients to CSV file with optional filters.

    Features:
    - Filter by status, doctor_id, date range
    - Streaming response for large datasets
    - Rate limited to 10 requests per hour
    - Includes all patient fields
    - Redis caching for 5 minutes
    """
    role_enum, user_id = await extract_user_context(current_user)
    current_user_uuid = await ensure_uuid(user_id)

    stmt = select(Patient).filter(Patient.deleted_at.is_(None))

    # RBAC: Non-admin users can only export their own patients
    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        stmt = stmt.filter(Patient.doctor_id == current_user_uuid)

    # Apply doctor_id filter (admin only)
    if doctor_id:
        if role_enum != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can filter by doctor_id",
            )
        try:
            doctor_uuid = UUID(doctor_id)
            stmt = stmt.filter(Patient.doctor_id == doctor_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid doctor ID format",
            )

    # Apply status filter
    if status_filter:
        target_state = await parse_flow_state_filter(status_filter)
        stmt = stmt.filter(Patient.flow_state == target_state)

    # Apply date range filters
    if start_date_from:
        stmt = stmt.filter(Patient.treatment_start_date >= start_date_from)

    if start_date_to:
        stmt = stmt.filter(Patient.treatment_start_date <= start_date_to)

    # Order by created_at for consistent export
    stmt = stmt.order_by(Patient.created_at.desc())

    # Check if export is cached
    cache_key = f"patient_export:{user_id}:{status_filter}:{doctor_id}:{start_date_from}:{start_date_to}"
    await redis_cache.get(cache_key)

    # Fetch all patients
    patients_result = await db.execute(stmt)
    patients = patients_result.scalars().all()

    if not patients:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No patients found matching the criteria",
        )

    # Create CSV in memory using streaming
    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV headers
    headers = [
        "ID",
        "Name",
        "Email",
        "Phone",
        "Birth Date",
        "CPF",
        "Doctor ID",
        "Treatment Type",
        "Treatment Start Date",
        "Diagnosis",
        "Treatment Phase",
        "Flow State",
        "Current Day",
        "Doctor Notes",
        "Created At",
        "Updated At",
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
            patient.treatment_start_date.isoformat()
            if patient.treatment_start_date
            else "",
            patient.diagnosis or "",
            patient.treatment_phase or "",
            patient.flow_state.value
            if isinstance(patient.flow_state, FlowState)
            else patient.flow_state,
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
        yield csv_content.encode("utf-8")

    filename = f"patients_export_{now_sao_paulo().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@router.post(
    "/import",
    response_model=ImportResponse,
    summary="Import patients from CSV",
    description="Import patients from CSV file with validation (ADMIN/DOCTOR only)",
)
@require_permission(Permission.PATIENT_CREATE)
@limiter.limit("5/hour")
async def import_patients(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with patient data"),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    """
    Import patients from CSV file with validation.

    Features:
    - Accept multipart/form-data with CSV file
    - Validate CSV structure and data
    - Return detailed success/failure report
    - Rate limited to 5 requests per hour
    - Background task support for large imports

    CSV Format:
    - Required headers: name, phone
    - Optional headers: email, birth_date, cpf, treatment_type,
      treatment_start_date, diagnosis, treatment_phase, doctor_notes
    - Date format: YYYY-MM-DD
    - Phone format: E.164 format (+5511987654321)
    - CPF format: 11 digits (formatting optional)
    """
    role_enum, user_id = await extract_user_context(current_user)
    current_user_uuid = await ensure_uuid(user_id)

    if current_user_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to determine user permissions",
        )

    started_at = now_sao_paulo()
    filename = file.filename or ""
    filename_lower = filename.lower()
    file_format = "csv"

    # Validate file type
    if filename_lower.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="XLSX import is not supported",
        )
    if not filename_lower.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted",
        )

    # Read CSV content
    try:
        contents = await file.read()
        csv_content = contents.decode("utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read CSV file: {str(e)}",
        )

    # Parse CSV
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)

    # Validate CSV headers
    required_headers = {"name", "phone"}

    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or has no headers",
        )

    normalized_headers = {
        _normalize_header(header) for header in reader.fieldnames if header
    }
    missing_headers = required_headers - normalized_headers
    if missing_headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required headers: {', '.join(missing_headers)}",
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
            normalized_row = _normalize_row(row)
            name = normalized_row.get("name", "").strip()
            phone = normalized_row.get("phone", "").strip()

            if not name:
                errors.append(ImportError(row=row_number, message="Name is required"))
                failed_count += 1
                continue

            if not phone:
                errors.append(ImportError(row=row_number, message="Phone is required"))
                failed_count += 1
                continue

            # Normalize phone to E.164
            try:
                e164_phone = normalize_phone(
                    phone, mode=PhoneValidationMode.BR_TO_E164, allow_none=False
                )
            except ValueError:
                errors.append(
                    ImportError(row=row_number, message="Invalid phone format")
                )
                failed_count += 1
                continue

            # Check for duplicate phone (LGPD: use hash lookup)
            from app.services.encryption import get_lgpd_encryption_service

            phone_service = get_lgpd_encryption_service()
            phone_hash = phone_service.hash_phone(e164_phone)
            existing_phone_result = await db.execute(
                select(Patient.id)
                .filter(Patient.phone_hash == phone_hash, Patient.deleted_at.is_(None))
                .limit(1)
            )
            existing_phone = existing_phone_result.scalar_one_or_none()
            if existing_phone:
                errors.append(
                    ImportError(
                        row=row_number,
                        message=f"Patient with phone {phone} already exists",
                    )
                )
                failed_count += 1
                continue

            # Parse optional fields
            email = normalized_row.get("email", "").strip() or None
            cpf_value = normalized_row.get("cpf", "").strip()
            cpf = await normalize_cpf(cpf_value) if cpf_value else None
            treatment_type = normalized_row.get("treatment_type", "").strip() or None
            diagnosis = normalized_row.get("diagnosis", "").strip() or None
            treatment_phase = normalized_row.get("treatment_phase", "").strip() or None
            doctor_notes = normalized_row.get("doctor_notes", "").strip() or None

            # Validate email format (parity with API)
            if email:
                try:
                    validated_email = validate_email(email)
                    email = validated_email.normalized
                except EmailNotValidError:
                    errors.append(
                        ImportError(row=row_number, message="Invalid email format")
                    )
                    failed_count += 1
                    continue

            # Parse dates
            birth_date = None
            birth_date_raw = normalized_row.get("birth_date", "").strip()
            if birth_date_raw:
                try:
                    birth_date = datetime.strptime(
                        birth_date_raw, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    errors.append(
                        ImportError(
                            row=row_number,
                            message="Invalid birth date format (use YYYY-MM-DD)",
                        )
                    )
                    failed_count += 1
                    continue

            treatment_start_date = None
            treatment_start_raw = normalized_row.get(
                "treatment_start_date", ""
            ).strip()
            if treatment_start_raw:
                try:
                    treatment_start_date = datetime.strptime(
                        treatment_start_raw, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    errors.append(
                        ImportError(
                            row=row_number,
                            message="Invalid treatment start date format (use YYYY-MM-DD)",
                        )
                    )
                    failed_count += 1
                    continue

            # Birth date range validation (parity with API)
            if birth_date:
                today = date.today()
                min_date = today - timedelta(days=int(18 * 365.25))
                max_date = today - timedelta(days=int(120 * 365.25))
                if birth_date > today:
                    errors.append(
                        ImportError(
                            row=row_number, message="Birth date cannot be in future"
                        )
                    )
                    failed_count += 1
                    continue
                if birth_date > min_date:
                    errors.append(
                        ImportError(
                            row=row_number, message="Patient must be 18+"
                        )
                    )
                    failed_count += 1
                    continue
                if birth_date < max_date:
                    errors.append(
                        ImportError(
                            row=row_number, message="Birth date is not realistic"
                        )
                    )
                    failed_count += 1
                    continue

            # Validate CPF if provided
            if cpf and len(cpf) != 11:
                errors.append(
                    ImportError(
                        row=row_number,
                        message=f"CPF must have exactly 11 digits, got {len(cpf)}",
                    )
                )
                failed_count += 1
                continue
            if cpf and not is_valid_cpf(cpf, allow_none=False):
                errors.append(
                    ImportError(row=row_number, message="Invalid CPF checksum")
                )
                failed_count += 1
                continue

            # Check for duplicate CPF (LGPD: use hash lookup)
            if cpf:
                from app.services.encryption import get_cpf_encryption_service

                cpf_service = get_cpf_encryption_service()
                cpf_hash = cpf_service.hash_cpf(cpf)
                existing_cpf_result = await db.execute(
                    select(Patient.id)
                    .filter(Patient.cpf_hash == cpf_hash, Patient.deleted_at.is_(None))
                    .limit(1)
                )
                existing_cpf = existing_cpf_result.scalar_one_or_none()
                if existing_cpf:
                    errors.append(
                        ImportError(
                            row=row_number, message="Patient with CPF already exists"
                        )
                    )
                    failed_count += 1
                    continue

            # Check for duplicate email (LGPD: use hash lookup)
            if email:
                from app.services.encryption import get_lgpd_encryption_service

                lgpd_service = get_lgpd_encryption_service()
                email_hash = lgpd_service.hash_email(email.lower())
                existing_email_result = await db.execute(
                    select(Patient.id)
                    .filter(
                        Patient.email_hash == email_hash, Patient.deleted_at.is_(None)
                    )
                    .limit(1)
                )
                existing_email = existing_email_result.scalar_one_or_none()
                if existing_email:
                    errors.append(
                        ImportError(
                            row=row_number,
                            message=f"Patient with email {email} already exists",
                        )
                    )
                    failed_count += 1
                    continue

            # Create patient (LGPD: use encrypted fields)
            savepoint = await db.begin_nested()
            try:
                new_patient = Patient(
                    name=name,
                    birth_date=birth_date,
                    treatment_type=treatment_type,
                    treatment_start_date=treatment_start_date,
                    diagnosis=diagnosis,
                    treatment_phase=treatment_phase,
                    doctor_notes=doctor_notes,
                    doctor_id=current_user_uuid,
                    flow_state=FlowState.ONBOARDING,
                    current_day=0,
                )

                # LGPD: Set encrypted fields using proper methods
                if e164_phone:
                    new_patient.set_phone(e164_phone)
                if email:
                    new_patient.set_email(email)
                if cpf:
                    new_patient.set_cpf(cpf)

                db.add(new_patient)
                await db.flush()  # Flush to get the ID but don't commit yet
                await savepoint.commit()

                success_count += 1
            except Exception:
                if savepoint.is_active:
                    await savepoint.rollback()
                raise

        except Exception as e:
            logger.error(f"Failed to import row {row_number}: {e}")
            errors.append(
                ImportError(row=row_number, message=f"Unexpected error: {str(e)}")
            )
            failed_count += 1
            continue

    # Commit all successful imports
    completed_at = now_sao_paulo()
    status_value = "completed"
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        completed_at = now_sao_paulo()
        status_value = "failed"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit imports: {str(e)}",
        )

    user_name = ""
    if isinstance(current_user, dict):
        user_name = current_user.get("full_name") or current_user.get("email") or ""
    else:
        user_name = getattr(current_user, "full_name", "") or getattr(
            current_user, "email", ""
        )

    history_entry = {
        "id": str(uuid4()),
        "userId": str(current_user_uuid),
        "userName": user_name,
        "filename": filename or "patients.csv",
        "format": file_format,
        "status": status_value,
        "totalRows": success_count + failed_count,
        "successfulRows": success_count,
        "failedRows": failed_count,
        "skippedRows": 0,
        "startedAt": started_at.isoformat(),
        "completedAt": completed_at.isoformat(),
        "duration": int((completed_at - started_at).total_seconds()),
    }

    if redis_cache:
        await _append_import_history(
            redis_cache,
            f"patient_import_history:user:{current_user_uuid}",
            history_entry,
        )
        await _append_import_history(
            redis_cache,
            "patient_import_history:all",
            history_entry,
        )

    # Return import results
    return ImportResponse(
        success=success_count,
        failed=failed_count,
        errors=errors[:100],  # Limit to first 100 errors
    )
