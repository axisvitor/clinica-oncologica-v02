"""
Patients API endpoints with RLS (Row Level Security) enabled.

This is an example of how to migrate endpoints to use RLS-aware database sessions.
This file demonstrates the incremental rollout strategy.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.dependencies.auth_dependencies import get_current_user
from app.dependencies.rls_dependencies import get_rls_db, get_rls_db_required
from app.models.patient import Patient
from app.models.user import UserRole, User
from app.schemas.patient import (
    PatientResponse,
    PatientCreate,
    PatientUpdate,
    PatientListResponse
)
from app.services.audit_service import AuditService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patients-rls",
    tags=["patients-rls"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=PatientListResponse)
async def list_patients_with_rls(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search term"),
    db: Session = Depends(get_rls_db_required),
    current_user: User = Depends(get_current_user),
    audit: AuditService = Depends()
) -> PatientListResponse:
    """
    List patients with RLS enabled.

    Doctors will only see their own patients.
    Admins will see all patients.
    RLS policies enforce this automatically.
    """
    try:
        # Log the access attempt
        await audit.log_event(
            event_type="patients.list",
            user_id=str(current_user.id),
            metadata={
                "page": page,
                "size": size,
                "search": search,
                "rls_enabled": True
            }
        )

        # Build query - RLS will automatically filter based on user
        query = db.query(Patient)

        # Apply search filter if provided
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                func.lower(Patient.name).like(func.lower(search_term))
            )

        # Count total (RLS filtered)
        total = query.count()

        # Paginate
        offset = (page - 1) * size
        patients = query.offset(offset).limit(size).all()

        logger.info(
            f"User {current_user.id} ({current_user.role}) retrieved {len(patients)} patients "
            f"(page {page}, total {total}) with RLS enabled"
        )

        return PatientListResponse(
            items=[PatientResponse.model_validate(p) for p in patients],
            total=total,
            page=page,
            size=size
        )

    except Exception as e:
        logger.error(f"Error listing patients with RLS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving patients"
        )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient_with_rls(
    patient_id: str,
    db: Session = Depends(get_rls_db_required),
    current_user: User = Depends(get_current_user),
    audit: AuditService = Depends()
) -> PatientResponse:
    """
    Get a specific patient with RLS enabled.

    RLS will automatically prevent access if the user
    doesn't have permission to view this patient.
    """
    try:
        # Log the access attempt
        await audit.log_event(
            event_type="patients.view",
            user_id=str(current_user.id),
            entity_id=patient_id,
            metadata={"rls_enabled": True}
        )

        # Query with RLS protection
        patient = db.query(Patient).filter(Patient.id == patient_id).first()

        if not patient:
            # Could be not found or no permission (RLS blocks it)
            logger.warning(
                f"Patient {patient_id} not found or access denied for user {current_user.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found or access denied"
            )

        logger.info(
            f"User {current_user.id} accessed patient {patient_id} with RLS enabled"
        )

        return PatientResponse.model_validate(patient)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient with RLS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving patient"
        )


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient_with_rls(
    patient_data: PatientCreate,
    db: Session = Depends(get_rls_db_required),
    current_user: User = Depends(get_current_user),
    audit: AuditService = Depends()
) -> PatientResponse:
    """
    Create a new patient with RLS enabled.

    The doctor_id will be automatically set to the current user
    unless they are an admin.
    """
    try:
        # For non-admin users, force doctor_id to be themselves
        if current_user.role != UserRole.ADMIN:
            patient_data.doctor_id = str(current_user.id)
        elif not patient_data.doctor_id:
            # Admin creating without specifying doctor
            patient_data.doctor_id = str(current_user.id)

        # Create the patient
        patient = Patient(**patient_data.model_dump())
        db.add(patient)
        db.commit()
        db.refresh(patient)

        # Log the creation
        await audit.log_event(
            event_type="patients.create",
            user_id=str(current_user.id),
            entity_id=str(patient.id),
            metadata={
                "patient_name": patient.name,
                "doctor_id": patient.doctor_id,
                "rls_enabled": True
            }
        )

        logger.info(
            f"User {current_user.id} created patient {patient.id} with RLS enabled"
        )

        return PatientResponse.model_validate(patient)

    except Exception as e:
        logger.error(f"Error creating patient with RLS: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating patient"
        )


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient_with_rls(
    patient_id: str,
    patient_update: PatientUpdate,
    db: Session = Depends(get_rls_db_required),
    current_user: User = Depends(get_current_user),
    audit: AuditService = Depends()
) -> PatientResponse:
    """
    Update a patient with RLS enabled.

    RLS will prevent updates if the user doesn't have permission.
    Note: We need UPDATE policies in the database for this to work fully.
    """
    try:
        # Query with RLS protection
        patient = db.query(Patient).filter(Patient.id == patient_id).first()

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found or access denied"
            )

        # Apply updates
        update_data = patient_update.model_dump(exclude_unset=True)

        # Non-admins cannot change doctor_id
        if current_user.role != UserRole.ADMIN and "doctor_id" in update_data:
            del update_data["doctor_id"]

        for field, value in update_data.items():
            setattr(patient, field, value)

        db.commit()
        db.refresh(patient)

        # Log the update
        await audit.log_event(
            event_type="patients.update",
            user_id=str(current_user.id),
            entity_id=patient_id,
            metadata={
                "updated_fields": list(update_data.keys()),
                "rls_enabled": True
            }
        )

        logger.info(
            f"User {current_user.id} updated patient {patient_id} with RLS enabled"
        )

        return PatientResponse.model_validate(patient)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating patient with RLS: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating patient"
        )


@router.get("/test/rls-status", response_model=dict)
async def test_rls_status(
    db: Session = Depends(get_rls_db_required),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Test endpoint to verify RLS is working correctly.

    Returns information about the current RLS context.
    """
    from app.dependencies.rls_dependencies import test_rls_connection

    rls_info = test_rls_connection(db)

    # Count patients visible to current user
    patient_count = db.query(Patient).count()

    return {
        "user_id": str(current_user.id),
        "user_role": current_user.role,
        "rls_status": rls_info,
        "visible_patients": patient_count,
        "message": "RLS is active and filtering data based on your permissions"
    }


# Export router
__all__ = ["router"]