"""
Patients CSV Import/Export API v2
Handles CSV-based patient data import and export operations.
"""

from typing import Any, Optional, List
from datetime import date, datetime
from uuid import UUID
import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.database import get_db
from app.models.patient import Patient, FlowState
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.utils.rate_limiter import limiter
from app.api.v2.patients_utils import (
    _extract_user_context,
    _ensure_uuid,
    _normalize_cpf,
    _normalize_phone,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class ImportError(BaseModel):
    row: int
    message: str


class ImportResponse(BaseModel):
    success: int
    failed: int
    errors: List[ImportError]


@router.get(
    "/export",
    summary="Export patients to CSV",
    description="Export patients to CSV with optional filters (ADMIN/DOCTOR only)",
)
@limiter.limit("10/hour")
async def export_patients(
    request: Request,
    db = Depends(get_db),
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
    db = Depends(get_db),
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

            # Check for duplicate phone (LGPD: use hash lookup)
            from app.services.encryption import get_lgpd_encryption_service
            phone_service = get_lgpd_encryption_service()
            phone_hash = phone_service.hash_phone(e164_phone)
            existing_phone = db.query(Patient).filter(
                Patient.phone_hash == phone_hash,
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

            # Check for duplicate CPF (LGPD: use hash lookup)
            if cpf:
                from app.services.encryption import get_cpf_encryption_service
                cpf_service = get_cpf_encryption_service()
                cpf_hash = cpf_service.hash_cpf(cpf)
                existing_cpf = db.query(Patient).filter(
                    Patient.cpf_hash == cpf_hash,
                    Patient.deleted_at.is_(None)
                ).first()
                if existing_cpf:
                    errors.append(ImportError(row=row_number, message=f"Patient with CPF already exists"))
                    failed_count += 1
                    continue

            # Check for duplicate email (LGPD: use hash lookup)
            if email:
                from app.services.encryption import get_lgpd_encryption_service
                lgpd_service = get_lgpd_encryption_service()
                email_hash = lgpd_service.hash_email(email.lower())
                existing_email = db.query(Patient).filter(
                    Patient.email_hash == email_hash,
                    Patient.deleted_at.is_(None)
                ).first()
                if existing_email:
                    errors.append(ImportError(row=row_number, message=f"Patient with email {email} already exists"))
                    failed_count += 1
                    continue

            # Create patient (LGPD: use encrypted fields)
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
