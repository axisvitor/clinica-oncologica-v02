"""
Messages API v2 - Bulk Operations
Handles bulk operations: bulk send messages.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import MessageType
from app.models.patient import Patient
from app.models.user import UserRole
from app.domain.messaging.core import MessageService
from app.schemas.v2.messages import (
    BulkMessageV2Request,
    BulkMessageV2Response,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from .helpers import _extract_user_context

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/bulk/send",
    response_model=BulkMessageV2Response,
    summary="Send bulk messages",
    description="Send messages to multiple patients at once",
)
@limiter.limit("10/minute")
async def bulk_send_messages(
    request: Request,
    bulk_request: BulkMessageV2Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """Send bulk messages to multiple patients."""
    role_enum, user_id = _extract_user_context(current_user)

    # Verify all patients exist and user has access
    patient_uuids = []
    failed_patients = []

    for patient_id in bulk_request.patient_ids:
        try:
            patient_uuid = UUID(patient_id)
            patient = db.query(Patient).filter(Patient.id == patient_uuid).first()

            if not patient:
                failed_patients.append(patient_id)
                continue

            # RBAC check
            if role_enum != UserRole.ADMIN and str(patient.doctor_id) != user_id:
                failed_patients.append(patient_id)
                continue

            patient_uuids.append(patient_uuid)
        except ValueError:
            failed_patients.append(patient_id)

    # Create messages for valid patients
    message_service = MessageService(db)
    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    scheduled_count = 0
    for patient_uuid in patient_uuids:
        try:
            metadata = bulk_request.message_metadata or {}
            metadata["batch_id"] = batch_id

            message_service.schedule_message(
                patient_id=patient_uuid,
                content=bulk_request.content,
                scheduled_for=bulk_request.scheduled_for or datetime.now(timezone.utc),
                message_type=MessageType.TEXT,
                message_metadata=metadata,
            )
            scheduled_count += 1
        except Exception as e:
            logger.error(f"Failed to schedule message for patient {patient_uuid}: {e}")
            failed_patients.append(str(patient_uuid))

    return {
        "success": scheduled_count > 0,
        "batch_id": batch_id,
        "total_messages": len(bulk_request.patient_ids),
        "scheduled_count": scheduled_count,
        "failed_count": len(failed_patients),
        "failed_patients": failed_patients,
        "estimated_completion": (
            bulk_request.scheduled_for or datetime.now(timezone.utc) + timedelta(minutes=5)
        ).isoformat()
        if scheduled_count > 0
        else None,
    }
