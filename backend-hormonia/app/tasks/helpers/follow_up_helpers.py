"""Follow-up helpers extracted from app.tasks.follow_up."""

import logging
import os
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo

logger = logging.getLogger(__name__)

DEFAULT_FOLLOW_UP_DEDUP_WINDOW_SECONDS = 24 * 60 * 60
DEFAULT_FOLLOW_UP_DEDUP_LOCK_SECONDS = 5 * 60


def _parse_positive_int_env(var_name: str, default: int) -> int:
    try:
        value = int(os.getenv(var_name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(value, 0)


FOLLOW_UP_DEDUP_WINDOW_SECONDS = _parse_positive_int_env(
    "FOLLOW_UP_DEDUP_WINDOW_SECONDS", DEFAULT_FOLLOW_UP_DEDUP_WINDOW_SECONDS
)
FOLLOW_UP_DEDUP_LOCK_SECONDS = _parse_positive_int_env(
    "FOLLOW_UP_DEDUP_LOCK_SECONDS", DEFAULT_FOLLOW_UP_DEDUP_LOCK_SECONDS
)


def _get_last_follow_up_sent_at_db(
    db, patient_id: UUID, since: datetime
) -> Optional[datetime]:
    from app.repositories.patient import PatientRepository
    from app.repositories.message import MessageRepository

    patient_repo = PatientRepository(db)
    patient = patient_repo.get_by_id(patient_id)
    if patient:
        patient_data = patient.patient_data or {}
        last_sent_str = patient_data.get("last_message_sent_at")
        if last_sent_str:
            try:
                parsed = datetime.fromisoformat(last_sent_str)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=SAO_PAULO_TZ)
                if parsed >= since:
                    return parsed
            except ValueError:
                logger.warning(
                    "Invalid last_message_sent_at format on patient data",
                    extra={"patient_id": str(patient_id)},
                )

    message_repo = MessageRepository(db)
    return message_repo.get_recent_follow_up_message_time(patient_id, since)


def _is_follow_up_eligible(follow_up_service, patient_id: UUID) -> Tuple[bool, str]:
    from app.models.enums import FlowState

    patient = follow_up_service.patient_repo.get_by_id(patient_id)
    if not patient:
        return False, "patient_not_found"

    if getattr(patient, "deleted_at", None):
        return False, "patient_deleted"

    flow_state_value = (
        patient.flow_state.value
        if hasattr(patient.flow_state, "value")
        else str(patient.flow_state).lower()
        if patient.flow_state
        else None
    )
    if flow_state_value != FlowState.ACTIVE.value:
        return False, f"patient_flow_state_{flow_state_value or 'unknown'}"

    flow_state = follow_up_service.flow_state_repo.get_active_flow(patient_id)
    if not flow_state:
        return False, "no_active_flow"

    flow_status = (flow_state.status or "").lower()
    if flow_status in {"paused", "completed", "cancelled", "inactive"}:
        return False, f"flow_status_{flow_status}"

    return True, "eligible"


def _update_patient_last_message_sent_at(
    db, patient_id: UUID, sent_at: datetime
) -> bool:
    from app.repositories.patient import PatientRepository

    patient_repo = PatientRepository(db)
    patient = patient_repo.get_by_id(patient_id)
    if not patient:
        logger.warning(
            "Unable to update last_message_sent_at; patient not found",
            extra={"patient_id": str(patient_id)},
        )
        return False

    patient_data = dict(patient.patient_data or {})
    patient_data["last_message_sent_at"] = sent_at.isoformat()
    patient_repo.update(patient, {"patient_data": patient_data})
    return True
