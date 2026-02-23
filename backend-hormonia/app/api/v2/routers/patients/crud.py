"""
Patients API v2 - CRUD Operations

This module handles core patient CRUD operations:
- List patients with advanced filtering and pagination
- Get patient by ID
- Create new patient with saga orchestration
- Update patient data
- Delete patient (soft delete)

Migrated from: app/api/v2/routers/patients.py
Lines: 50-372
"""

# Standard library imports
# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
import logging
import re
import time
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

# Third-party imports
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session
from sqlalchemy import select as sa_select

# Local application imports
from app.api.v2.dependencies import (
    apply_field_selection,
    get_eager_load_params,
    get_field_selection,
    get_pagination_params,
)
from app.core.authorization import (
    require_doctor_or_admin,
    require_permission,
)
from app.core.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PatientNotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.exceptions import ValidationError as DomainValidationError
from app.core.permissions import Permission
from app.config.constants import TreatmentPhase
from app.core import redis_client as redis_client_module
from app.database import get_db, get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import UserRole
from app.metrics.patient_metrics import (
    patient_create_duration,
    patient_create_idempotency_hits,
    patient_create_idempotency_misses,
)
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate as DomainPatientUpdate
from app.schemas.v2.patient import (
    PatientMetadataV2,
    PatientV2Create,
    PatientV2List,
    PatientV2Response,
    PatientV2Update,
)
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode
from app.services.patient import PatientIntegrityService
from app.services.patient.crud_service import PatientCRUDService
from app.utils.rate_limiter import limiter

# Import shared utilities from base module
from .base import (
    ensure_patient_access,
    ensure_uuid,
    extract_user_context,
    serialize_patient,
    serialize_patient_with_includes,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_sync_redis_client():
    """
    Resolve Redis client at call-time for test monkeypatch compatibility.
    """
    return redis_client_module.get_redis_client()


def _split_list(value: Optional[object], field: str) -> Optional[list[str]]:
    """Split string/list values into a normalized list of strings."""
    if value is None:
        return None

    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items

    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"Invalid {field} format")

    raw = value.strip()
    if not raw:
        return None

    items: list[str] = []
    for chunk in re.split(r"[,;\n]+", raw):
        part = chunk.strip()
        if not part:
            continue

        if "/" in part and not re.search(r"\d", part):
            for sub_part in re.split(r"/+", part):
                sub_item = sub_part.strip()
                if sub_item:
                    items.append(sub_item)
        else:
            items.append(part)

    if not items:
        logger.warning(
            "Split list produced no items",
            extra={"field": field, "original_value": value, "parsed_value": items},
        )
        return None

    return items


def _normalize_clinical_list(
    value: Optional[object],
    *,
    field: str,
    max_items: int = 100,
    max_item_length: int = 500,
) -> Optional[list[str]]:
    normalized = _split_list(value, field=field)
    if normalized is None:
        return None

    if len(normalized) > max_items:
        raise HTTPException(
            status_code=400,
            detail=f"{field} cannot have more than {max_items} items",
        )

    for item in normalized:
        if len(item) > max_item_length:
            raise HTTPException(
                status_code=400,
                detail=f"{field} item exceeds maximum length of {max_item_length} characters",
            )

    return normalized


def _validate_blood_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    blood_type = value.strip()
    valid = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
    if blood_type not in valid:
        raise HTTPException(status_code=400, detail="Invalid blood_type value")

    return blood_type


def _validate_emergency_phone_format(phone: str) -> str:
    phone_value = phone.strip()
    if not re.fullmatch(r"\+55\d{10,11}", phone_value):
        raise HTTPException(
            status_code=400, detail="Invalid emergency_contact_phone format"
        )
    return phone_value


def _resolve_emergency_contact_fields(
    *,
    emergency_contact: Optional[str],
    emergency_contact_name: Optional[str],
    emergency_contact_phone: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    explicit_name = emergency_contact_name.strip() if isinstance(emergency_contact_name, str) else None
    explicit_phone = emergency_contact_phone.strip() if isinstance(emergency_contact_phone, str) else None

    if explicit_name or explicit_phone:
        if not explicit_name or not explicit_phone:
            raise HTTPException(
                status_code=400,
                detail="emergency_contact_name and emergency_contact_phone must be provided together",
            )
        return explicit_name, _validate_emergency_phone_format(explicit_phone)

    if emergency_contact:
        parsed_name, parsed_phone = _parse_emergency_contact(emergency_contact)
        if parsed_name and parsed_phone:
            return parsed_name, _validate_emergency_phone_format(parsed_phone)
        raise HTTPException(status_code=400, detail="Invalid emergency_contact format")

    return None, None


def _normalize_phone_safe(phone_raw: str) -> Optional[str]:
    try:
        return normalize_phone(
            phone_raw, mode=PhoneValidationMode.BR_TO_E164, allow_none=True
        )
    except ValueError:
        return None


def _parse_emergency_contact(
    value: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Parse emergency contact into (name, phone) tuple."""
    if value is None:
        return None, None

    raw = value.strip()
    if not raw:
        return None, None

    parts = re.split(r"\s+[-–—]\s+|\s*[:|]\s*", raw, maxsplit=1)
    if len(parts) == 2:
        name = parts[0].strip() or None
        phone_raw = parts[1].strip()
        phone = _normalize_phone_safe(phone_raw)
        if phone is None:
            logger.warning(
                "Emergency contact parsing failed",
                extra={
                    "field": "emergency_contact",
                    "original_value": value,
                    "parsed_value": {"name": name, "phone": phone},
                },
            )
        return name, phone

    if not any(char.isalpha() for char in raw):
        phone = _normalize_phone_safe(raw)
        if phone:
            return None, phone

    logger.warning(
        "Emergency contact parsing failed",
        extra={
            "field": "emergency_contact",
            "original_value": value,
            "parsed_value": {"name": raw or None, "phone": None},
        },
    )
    return raw or None, None


def _parse_datetime_query(value: Optional[str], field_name: str) -> Optional[datetime]:
    """Parse ISO datetime query params and normalize validation errors to HTTP 400."""
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        return datetime.fromisoformat(normalized)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} date format",
        ) from e


@router.get(
    "/",
    response_model=PatientV2List,
    status_code=status.HTTP_200_OK,
    summary="List patients with pagination",
    description="Get paginated list of patients with optional field selection and eager loading",
)
@require_permission(Permission.PATIENT_READ)
@limiter.limit("120/minute")
async def list_patients(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
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
    created_after: Optional[str] = Query(
        None, description="Filter patients created after this datetime (ISO format)"
    ),
    created_before: Optional[str] = Query(
        None, description="Filter patients created before this datetime (ISO format)"
    ),
    include_quarantined: bool = Query(
        False,
        description="Include quarantined patients in the list (default: false)",
    ),
    sort_by: Optional[str] = Query("created_at", description="Sort by field"),
    sort_order: Optional[str] = Query("desc", description="Sort order"),
):
    """
    List patients with advanced filtering and pagination.

    Args:
        request: FastAPI request object.
        db: Database session.
        current_user: Authenticated user from session.
        pagination: Pagination parameters (cursor, limit).
        fields: Optional list of fields to include in response.
        include: Optional list of relations to eager load.
        search: Search query for name or email.
        status_filter: Filter by patient flow state.
        treatment_type: Filter by treatment type.
        start_date_from: Filter by treatment start date (from).
        start_date_to: Filter by treatment start date (to).
        treatment_phase: Filter by treatment phase.
        has_active_flow: Filter by active flow state.
        created_after: Filter by creation date (after).
        created_before: Filter by creation date (before).
        include_quarantined: Include quarantined patients in results.
        sort_by: Field to sort by.
        sort_order: Sort order (asc/desc).

    Returns:
        PatientV2List with paginated patient data.

    Raises:
        ForbiddenError: 403 if unable to determine user context (non-admin).
        ServiceUnavailableError: 500 if internal server error occurs.
    """
    try:
        repo = PatientRepository(db)
        role_enum, user_id = await extract_user_context(current_user)
        current_user_uuid = await ensure_uuid(user_id)

        if status_filter is not None:
            status_value = status_filter.strip()
            if not status_value or status_value.lower() in {"all", "todos"}:
                status_filter = None
            else:
                status_filter = status_value

        treatment_phase_value = None
        if treatment_phase is not None:
            treatment_phase_value = treatment_phase.strip().lower()
            if treatment_phase_value:
                if treatment_phase_value not in TreatmentPhase.ALL_PHASES:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid treatment_phase value",
                    )
            else:
                treatment_phase_value = None

        created_after_dt = _parse_datetime_query(created_after, "created_after")
        created_before_dt = _parse_datetime_query(created_before, "created_before")

        allowed_sort_fields = {
            "name",
            "created_at",
            "updated_at",
            "treatment_start_date",
            "treatment_phase",
            "flow_state",
            "current_day",
            "email",
        }
        sort_by_value = (sort_by or "created_at").strip()
        if sort_by_value not in allowed_sort_fields:
            raise HTTPException(status_code=400, detail="Invalid sort_by value")

        sort_order_value = (sort_order or "desc").strip().lower()
        if sort_order_value not in {"asc", "desc"}:
            raise HTTPException(status_code=400, detail="Invalid sort_order value")

        page_value: Optional[int] = None
        page_size_param = request.query_params.get("page_size")
        page_param = request.query_params.get("page")
        limit_value = pagination["limit"]

        if page_size_param is not None:
            try:
                page_size_value = int(page_size_param)
                if page_size_value < 1 or page_size_value > 100:
                    raise ValueError
            except ValueError as e:
                raise HTTPException(status_code=400, detail="Invalid page_size value") from e
            limit_value = page_size_value

        if page_param is not None:
            try:
                page_value = int(page_param)
                if page_value < 1:
                    raise ValueError
            except ValueError as e:
                raise HTTPException(status_code=400, detail="Invalid page value") from e

        if page_value is None and page_size_param is not None:
            page_value = 1

        # Build filters
        filters = {
            "search": search,
            "status": status_filter,
            "treatment_type": treatment_type,
            "treatment_phase": treatment_phase_value,
            "start_date_from": start_date_from,
            "start_date_to": start_date_to,
            "has_active_flow": has_active_flow,
            "created_after": created_after_dt,
            "created_before": created_before_dt,
            "include_quarantined": include_quarantined,
        }

        # RBAC: Non-admin users can only see their own patients
        if role_enum != UserRole.ADMIN:
            if not current_user_uuid:
                logger.warning("Unable to determine user context for non-admin user")
                raise ForbiddenError("Unable to determine user context")
            filters["doctor_id"] = current_user_uuid

        repo_sort_by = "created_at" if sort_by_value == "email" else sort_by_value

        # Execute query via repository
        patients, has_more, next_cursor, total = repo.list_v2(
            filters=filters,
            cursor_data=pagination["cursor_data"],
            limit=limit_value,
            sort_by=repo_sort_by,
            sort_order=sort_order_value,
            eager_load=include,
        )

        # Serialize response
        patient_responses = []
        for patient in patients:
            patient_dict = await serialize_patient_with_includes(patient, include)

            if fields:
                patient_dict = apply_field_selection(patient_dict, fields)
            patient_responses.append(patient_dict)

        if sort_by_value == "email":
            patient_responses.sort(
                key=lambda item: (item.get("email") or "").lower(),
                reverse=sort_order_value == "desc",
            )

        response_payload = {
            "data": patient_responses,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": total,
        }
        if page_value is not None:
            response_payload["page"] = page_value
            response_payload["page_size"] = limit_value
        return response_payload

    except (HTTPException, ForbiddenError, ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing patients: {e}", exc_info=True)
        raise ServiceUnavailableError("Internal server error")


@router.get(
    "/{patient_id}",
    response_model=PatientV2Response,
    status_code=status.HTTP_200_OK,
    summary="Get patient by ID",
    description="Retrieve a single patient by their unique ID with optional field selection and eager loading",
)
@require_permission(Permission.PATIENT_READ)
@limiter.limit("120/minute")
async def get_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    Get a single patient by ID.

    Args:
        request: FastAPI request object.
        patient_id: Patient UUID as string.
        db: Database session.
        current_user: Authenticated user from session.
        fields: Optional list of fields to include in response.
        include: Optional list of relations to eager load.

    Returns:
        PatientV2Response with patient data.

    Raises:
        ValidationError: 422 if patient ID format is invalid.
        ForbiddenError: 403 if user lacks permissions to access patient.
        PatientNotFoundError: 404 if patient not found.
        ServiceUnavailableError: 500 if internal server error occurs.
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError as e:
        logger.warning(f"Invalid patient ID format: {patient_id}", extra={"error": str(e)})
        raise ValidationError("Invalid patient ID format", field="patient_id")

    try:
        repo = PatientRepository(db)
        patient = repo.get_by_id(patient_uuid, eager_load=True)

        if not patient:
            logger.warning(f"Patient not found: {patient_id}")
            raise PatientNotFoundError(patient_id)

        await ensure_patient_access(current_user, patient.doctor_id)

        # Serialize
        patient_dict = await serialize_patient_with_includes(patient, include)

        if fields:
            patient_dict = apply_field_selection(patient_dict, fields)

        return patient_dict

    except (HTTPException, ForbiddenError, ValidationError, NotFoundError, PatientNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving patient {patient_id}: {e}", exc_info=True)
        raise ServiceUnavailableError("Internal server error")


@router.post(
    "/",
    response_model=PatientV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new patient",
    description="Create a new patient with saga orchestration, WhatsApp registration, and idempotency support",
)
@require_doctor_or_admin()
@limiter.limit("60/hour")  # Production limit
async def create_patient(
    request: Request,
    response: Response,
    patient_data: PatientV2Create,
    db: AsyncSession = Depends(get_async_db),  # AsyncSession for saga compensation/steps
    current_user=Depends(get_current_user_from_session),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Create a new patient with full saga orchestration.

    Clinical Fields Format:
    - allergies: Comma, semicolon, or newline-delimited string
      Examples: "Penicilina, Dipirona" or "Penicilina; Dipirona"
    - medications: Same format as allergies
      Examples: "Levotiroxina 100mcg, Metformina 500mg"
    - emergency_contact: "Name - Phone" or "Name: Phone" format
      Examples: "Maria Silva - (11) 99999-9999" or "Maria Silva: 11999999999"
      Note: Phone will be normalized to E.164 format

    Args:
        request: FastAPI request object.
        patient_data: Patient creation data.
        db: Database session.
        current_user: Authenticated user from session.
        x_idempotency_key: Optional idempotency key for duplicate request prevention.

    Returns:
        PatientV2Response with created patient data.

    Raises:
        ValidationError: 422 if doctor ID format is invalid.
        BusinessRuleError: 400 if creation fails.
    """
    start_time = time.monotonic()

    # QW-004: Database-level idempotency key support for duplicate request prevention
    if x_idempotency_key:
        from app.models.patient import Patient as PatientModel

        # Async idempotency DB check (inlined for AsyncSession compat)
        _idem_result = await db.execute(
            sa_select(PatientModel).filter(
                PatientModel.idempotency_key == x_idempotency_key,
                PatientModel.deleted_at.is_(None),
            )
        )
        existing = _idem_result.scalars().first()
        if existing:
            await ensure_patient_access(current_user, existing.doctor_id)
            duration_seconds = time.monotonic() - start_time
            patient_create_idempotency_hits.labels(source="db").inc()
            patient_create_duration.labels(idempotent="true").observe(
                duration_seconds
            )
            logger.info(
                "Idempotency hit (DB)",
                extra={
                    "idempotency_key": x_idempotency_key,
                    "patient_id": str(existing.id),
                    "source": "db",
                    "duration_ms": int(duration_seconds * 1000),
                },
            )
            response.status_code = status.HTTP_200_OK
            return await serialize_patient(existing)

        # QW-006: Redis cache for fast idempotency checks (secondary layer).
        redis = _get_sync_redis_client()
        if redis:
            try:
                cache_key = f"idempotency:patient:create:{x_idempotency_key}"
                cached_result = redis.get(cache_key)
                if cached_result:
                    import json

                    cached_payload = json.loads(cached_result)
                    cached_doctor_id = cached_payload.get("doctor_id")

                    # Enforce RBAC on idempotency replay as well.
                    owner_doctor_id = None
                    if cached_doctor_id:
                        try:
                            owner_doctor_id = UUID(str(cached_doctor_id))
                        except (TypeError, ValueError):
                            owner_doctor_id = None

                    if owner_doctor_id is None:
                        cached_patient_id = cached_payload.get("id")
                        if cached_patient_id:
                            try:
                                cached_patient_uuid = UUID(str(cached_patient_id))
                                # Async patient lookup for owner_doctor_id resolution
                                _p_result = await db.execute(
                                    sa_select(PatientModel).filter(
                                        PatientModel.id == cached_patient_uuid,
                                        PatientModel.deleted_at.is_(None),
                                    )
                                )
                                cached_patient = _p_result.scalars().first()
                                if cached_patient:
                                    owner_doctor_id = cached_patient.doctor_id
                            except (TypeError, ValueError):
                                owner_doctor_id = None

                    if owner_doctor_id is not None:
                        await ensure_patient_access(current_user, owner_doctor_id)

                    duration_seconds = time.monotonic() - start_time
                    patient_create_idempotency_hits.labels(source="redis").inc()
                    patient_create_duration.labels(idempotent="true").observe(
                        duration_seconds
                    )
                    logger.info(
                        "Idempotency hit (Redis)",
                        extra={
                            "idempotency_key": x_idempotency_key,
                            "patient_id": cached_payload.get("id"),
                            "source": "redis",
                            "duration_ms": int(duration_seconds * 1000),
                        },
                    )
                    response.status_code = status.HTTP_200_OK
                    return cached_payload
            except Exception as redis_err:
                logger.debug(
                    f"Idempotency cache check failed (non-critical): {redis_err}"
                )

    try:
        # Handle both UUID and string types
        if isinstance(patient_data.doctor_id, UUID):
            doctor_uuid = patient_data.doctor_id
        else:
            doctor_uuid = UUID(str(patient_data.doctor_id))
    except (ValueError, AttributeError):
        raise ValidationError("Invalid doctor ID format", field="doctor_id")

    role_enum, user_id = await extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        if doctor_uuid.int == 0:
            raise ForbiddenError("Doctors cannot create patients for another doctor")
        current_user_uuid = await ensure_uuid(user_id)
        if not current_user_uuid:
            raise ForbiddenError("Unable to determine user context")
        # Doctors can only create patients under their own ownership.
        doctor_uuid = current_user_uuid

    # Initialize coordinator via factory
    from app.services.patient.onboarding_factory import get_onboarding_coordinator
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.integrations.evolution import EvolutionClient

    saga_orchestrator = SagaOrchestrator(
        db=db, redis_client=_get_sync_redis_client(), evolution_client=EvolutionClient()
    )

    coordinator = get_onboarding_coordinator(db, saga_orchestrator)

    try:
        # FIX: Normalize phone to E.164 format for saga/v1 compatibility
        # V2 HYBRID mode preserves original format, but saga expects E.164

        original_phone = patient_data.phone
        normalized_phone = normalize_phone(
            original_phone,
            mode=PhoneValidationMode.BR_TO_E164,  # Force E.164 conversion
            allow_none=False,
        )
        logger.info(
            "Phone normalized for patient creation",
            extra={
                "phone_original": original_phone,
                "phone_normalized": normalized_phone,
                "validation_mode": "BR_TO_E164",
                "context": "api_v2",
            },
        )
        
        # Clinical field compatibility (accept both legacy and modern payloads)
        allergies_list = _normalize_clinical_list(
            patient_data.allergies, field="allergies"
        )
        raw_medications = (
            patient_data.current_medications
            if patient_data.current_medications is not None
            else patient_data.medications
        )
        meds_list = _normalize_clinical_list(
            raw_medications, field="current_medications"
        )
        comorbidities_list = _normalize_clinical_list(
            patient_data.comorbidities, field="comorbidities"
        )
        blood_type_value = _validate_blood_type(patient_data.blood_type)
        emergency_name, emergency_phone = _resolve_emergency_contact_fields(
            emergency_contact=patient_data.emergency_contact,
            emergency_contact_name=patient_data.emergency_contact_name,
            emergency_contact_phone=patient_data.emergency_contact_phone,
        )

        # Build metadata with Pydantic validation
        metadata = {}
        extras = {}
        if patient_data.patient_data:
            try:
                validated_metadata = PatientMetadataV2(**patient_data.patient_data)
                metadata = validated_metadata.model_dump(exclude_none=True)
            except PydanticValidationError as e:
                for error in e.errors():
                    if not error.get("loc"):
                        continue
                    field_path = ".".join(str(loc) for loc in error["loc"])
                    field_root = error["loc"][0]
                    field_value = patient_data.patient_data.get(field_root)

                    if error["type"] == "extra_forbidden":
                        extras[field_root] = field_value
                        logger.warning(
                            "Metadata key moved to custom_fields due to unknown key",
                            extra={
                                "field": f"patient_data.{field_path}",
                                "original_value": field_value,
                                "parsed_value": "custom_fields",
                            },
                        )
                    else:
                        extras[field_root] = field_value
                        logger.warning(
                            "Metadata key moved to custom_fields due to type mismatch",
                            extra={
                                "field": f"patient_data.{field_path}",
                                "original_value": field_value,
                                "parsed_value": "custom_fields",
                                "error": error["msg"],
                            },
                        )

                valid_fields = {
                    k: v
                    for k, v in patient_data.patient_data.items()
                    if k not in extras
                }
                if valid_fields:
                    validated_metadata = PatientMetadataV2(**valid_fields)
                    metadata = validated_metadata.model_dump(exclude_none=True)
        if extras:
            # Ensure custom_fields is a dict before update
            existing_cf = metadata.get("custom_fields")
            if existing_cf is None or not isinstance(existing_cf, dict):
                metadata["custom_fields"] = {}
            metadata["custom_fields"].update(extras)
        
        # Create using specialized Onboarding Coordinator
        created = await coordinator.create_patient(
            patient_data=PatientCreate(
                phone=normalized_phone,  # Use normalized E.164 phone
                name=patient_data.name,
                email=patient_data.email,
                birth_date=patient_data.birth_date,
                cpf=patient_data.cpf,
                treatment_type=patient_data.treatment_type,
                treatment_start_date=patient_data.treatment_start_date,
                doctor_notes=patient_data.doctor_notes,
                diagnosis=patient_data.diagnosis,
                treatment_phase=patient_data.treatment_phase,
                timezone=patient_data.timezone,
                # Clinical fields as proper types (not in metadata)
                allergies=allergies_list,
                current_medications=meds_list,
                comorbidities=comorbidities_list,
                blood_type=blood_type_value,
                emergency_contact_name=emergency_name,
                emergency_contact_phone=emergency_phone,
                metadata=metadata if metadata else None,
            ),
            doctor_id=doctor_uuid,
            current_user=current_user,
            idempotency_key=x_idempotency_key,  # QW-004: Pass idempotency key to coordinator
        )
        result = await serialize_patient(created)

        # QW-006: Store result with idempotency key in Redis (TTL: 24 hours) as secondary cache
        if x_idempotency_key:
            redis = _get_sync_redis_client()
            if redis:
                try:
                    import json

                    cache_key = f"idempotency:patient:create:{x_idempotency_key}"
                    redis.setex(cache_key, 86400, json.dumps(result, default=str))
                except Exception as redis_err:
                    logger.debug(
                        f"Idempotency cache store failed (non-critical): {redis_err}"
                    )

        duration_seconds = time.monotonic() - start_time
        patient_create_idempotency_misses.inc()
        patient_create_duration.labels(idempotent="false").observe(duration_seconds)
        logger.info(
            "New patient created",
            extra={
                "idempotency_key": x_idempotency_key,
                "patient_id": result.get("id") if isinstance(result, dict) else None,
                "source": "create",
                "duration_ms": int(duration_seconds * 1000),
            },
        )
        return result

    except DomainValidationError as exc:
        message = exc.message if hasattr(exc, "message") else str(exc)
        details = getattr(exc, "details", None)
        code = getattr(exc, "code", None) or (details or {}).get("code")
        if code in {"duplicate_email", "duplicate_phone", "duplicate_cpf"} or (
            isinstance(message, str) and "already exists" in message.lower()
        ):
            raise ConflictError(message, details=details)
        raise ValidationError(message, details=details)
    except (ForbiddenError, ValidationError, NotFoundError, BusinessRuleError):
        raise
    except Exception as e:
        if hasattr(e, "status_code"):
            raise e
        logger.error(f"Error creating patient: {e}", exc_info=True)
        raise BusinessRuleError("Failed to create patient")


@router.put(
    "/{patient_id}", response_model=PatientV2Response, summary="Update patient"
)
@router.patch(
    "/{patient_id}", response_model=PatientV2Response, summary="Update patient"
)
@require_permission(Permission.PATIENT_UPDATE)
@limiter.limit("30/hour")
async def update_patient(
    request: Request,
    patient_id: str,
    patient_data: PatientV2Update,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Update patient data.

    Features:
    - Partial updates (only provided fields are updated)
    - Data integrity validation
    - RBAC: Doctors cannot reassign patients to other doctors
    - Uses CRUD service layer for business logic

    Raises:
        ValidationError: 422 if patient ID format is invalid or data validation fails.
        PatientNotFoundError: 404 if patient not found.
        ForbiddenError: 403 if doctor tries to reassign patient.
        ServiceUnavailableError: 500 if update fails.
    """
    try:
        # Handle both UUID and string types
        if isinstance(patient_id, UUID):
            patient_uuid = patient_id
        else:
            patient_uuid = UUID(str(patient_id))
    except (ValueError, AttributeError):
        raise ValidationError("Invalid patient ID", field="patient_id")

    # Initialize services
    repo = PatientRepository(db)
    crud_service = PatientCRUDService(db, repo)
    integrity_service = PatientIntegrityService(db, repo)

    # Check existence and permissions
    patient = repo.get_by_id(patient_uuid, eager_load=False)
    if not patient:
        raise PatientNotFoundError(str(patient_uuid))

    await ensure_patient_access(current_user, patient.doctor_id)

    # Validate/update compatibility payload
    update_dict = patient_data.dict(exclude_unset=True)
    if "medications" in update_dict and "current_medications" not in update_dict:
        update_dict["current_medications"] = update_dict.pop("medications")
    else:
        update_dict.pop("medications", None)

    for clinical_field in ("allergies", "current_medications", "comorbidities"):
        if clinical_field in update_dict:
            update_dict[clinical_field] = _normalize_clinical_list(
                update_dict[clinical_field], field=clinical_field
            )

    if "blood_type" in update_dict:
        update_dict["blood_type"] = _validate_blood_type(update_dict.get("blood_type"))

    if (
        "emergency_contact" in update_dict
        or "emergency_contact_name" in update_dict
        or "emergency_contact_phone" in update_dict
    ):
        emergency_name, emergency_phone = _resolve_emergency_contact_fields(
            emergency_contact=update_dict.get("emergency_contact"),
            emergency_contact_name=update_dict.get("emergency_contact_name"),
            emergency_contact_phone=update_dict.get("emergency_contact_phone"),
        )
        update_dict["emergency_contact_name"] = emergency_name
        update_dict["emergency_contact_phone"] = emergency_phone
        update_dict.pop("emergency_contact", None)

    patient_data = PatientV2Update(**update_dict)

    if update_dict:
        try:
            validated = integrity_service.validate_patient_data(
                patient_data=patient_data,
                doctor_id=patient.doctor_id,
                patient_id=patient_uuid,
                is_update=True,
            )
            # Use validated data
            for k, v in validated.items():
                if k != "validation_errors" and v is not None:
                    if hasattr(patient_data, k):
                        setattr(patient_data, k, v)
        except Exception as e:
            logger.error(f"Error validating patient data: {e}", exc_info=True)
            raise ValidationError("Invalid patient data")

    # Handle doctor reassignment check
    if patient_data.doctor_id:
        role_enum, user_id = await extract_user_context(current_user)
        if role_enum != UserRole.ADMIN:
            if str(patient_data.doctor_id) != str(patient.doctor_id):
                raise ForbiddenError("Doctors cannot reassign patients")

    # Delegate to CRUD service
    domain_update = DomainPatientUpdate(**patient_data.dict(exclude_unset=True))
    updated_patient = crud_service.update_patient(patient_uuid, domain_update)

    if not updated_patient:
        raise ServiceUnavailableError("Failed to update patient")

    return await serialize_patient(updated_patient)


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete patient",
)
@require_permission(Permission.PATIENT_DELETE)
@limiter.limit("10/hour")  # Strict rate limit for deletions
async def delete_patient(
    request: Request,  # Required for rate limiter
    patient_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Soft delete a patient.

    The patient is marked as deleted but not removed from the database.
    This preserves data for audit purposes.

    Raises:
        ValidationError: 422 if patient ID format is invalid.
        PatientNotFoundError: 404 if patient not found.
        ServiceUnavailableError: 500 if deletion fails.
    """
    try:
        # Handle both UUID and string types
        if isinstance(patient_id, UUID):
            pid = patient_id
        else:
            pid = UUID(str(patient_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid patient_id UUID", field="patient_id")

    role_enum, user_id_str = await extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        raise ForbiddenError("Admin privileges required to delete patients")

    # Resolve authenticated user identity for LGPD audit record
    performer_uuid: Optional[UUID] = None
    if user_id_str:
        try:
            performer_uuid = UUID(str(user_id_str))
        except (TypeError, ValueError):
            performer_uuid = None

    performer_email: Optional[str] = (
        current_user.get("email")
        if isinstance(current_user, dict)
        else getattr(current_user, "email", None)
    )

    # Initialize CRUD service
    repo = PatientRepository(db)
    service = PatientCRUDService(db, repo)

    # Check existence
    patient = repo.get_by_id(pid, eager_load=False)
    if not patient:
        raise PatientNotFoundError(str(pid))

    success = service.delete_patient(
        pid,
        performed_by_user_id=performer_uuid,
        performed_by_email=performer_email,
    )
    if not success:
        raise ServiceUnavailableError("Failed to delete patient")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
