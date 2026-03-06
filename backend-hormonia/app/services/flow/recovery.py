"""Detection and recovery utilities for stuck patient flows."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from asgiref.sync import async_to_sync
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config.settings.tasks import (
    STUCK_FLOW_DETECT_HOURS,
    STUCK_FLOW_MAX_RECOVERY_ATTEMPTS,
    STUCK_FLOW_RECOVERY_IDEMPOTENCY_TTL,
)
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.services.flow.flags import is_awaiting_response
from app.services.flow.management.service import FlowManagementService
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

MAX_STUCK_FLOW_BATCH = 100
RECOVERY_IDEMPOTENCY_PREFIX = "recovery:"
MANUAL_INTERVENTION_REASON = "stuck_flow_recovery_exhausted"
SQL_TRUTHY_VALUES = ("true", "True", "1", "yes")


def _is_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _idempotency_key(flow_state_id: Any) -> str:
    return f"{RECOVERY_IDEMPOTENCY_PREFIX}{flow_state_id}"


def _get_prompt_message_id(step_data: dict[str, Any]) -> str | None:
    pending_context = step_data.get("pending_response_context")
    if isinstance(pending_context, dict):
        prompt_message_id = pending_context.get("prompt_message_id")
        if prompt_message_id:
            return str(prompt_message_id)

    last_message_sent = step_data.get("last_message_sent")
    if isinstance(last_message_sent, dict):
        message_id = last_message_sent.get("message_id")
        if message_id:
            return str(message_id)

    return None


def _build_flow_context(flow_state: PatientFlowState, step_data: dict[str, Any]) -> dict[str, Any]:
    current_day = step_data.get("current_flow_day") or flow_state.current_step
    current_index = step_data.get("current_day_message_index", 0)
    flow_kind = step_data.get("flow_kind")

    flow_type = flow_kind
    if not flow_type:
        raw_flow_type = getattr(flow_state, "flow_type", None)
        flow_type = getattr(raw_flow_type, "value", raw_flow_type) or "unknown"

    flow_context = {
        "flow_day": current_day,
        "flow_type": flow_type,
        "flow_kind": flow_kind or flow_type,
        "message_index": current_index,
        "current_message_index": current_index,
        "template_id": f"{flow_type}_day_{current_day}",
        "personalized": True,
        "awaiting_response": step_data.get("awaiting_response", False),
    }

    prompt_message_id = _get_prompt_message_id(step_data)
    if prompt_message_id:
        flow_context["prompt_message_id"] = prompt_message_id

    return flow_context


def _mark_manual_intervention(flow_state: PatientFlowState, step_data: dict[str, Any]) -> None:
    step_data["manual_intervention_required"] = True
    step_data["manual_intervention_reason"] = MANUAL_INTERVENTION_REASON
    step_data["manual_intervention_flagged_at"] = now_sao_paulo().isoformat()
    flow_state.step_data = step_data


def find_stuck_flows(
    db: Session,
    threshold_hours: int = STUCK_FLOW_DETECT_HOURS,
) -> list[PatientFlowState]:
    """Return active flows that have been awaiting a response beyond the threshold."""
    cutoff = now_sao_paulo() - timedelta(hours=threshold_hours)

    query = (
        db.query(PatientFlowState)
        .join(Patient, Patient.id == PatientFlowState.patient_id)
        .filter(
            PatientFlowState.completed_at.is_(None),
            Patient.deleted_at.is_(None),
            PatientFlowState.step_data["awaiting_response"].astext.in_(SQL_TRUTHY_VALUES),
            or_(
                PatientFlowState.last_interaction_at.is_(None),
                PatientFlowState.last_interaction_at < cutoff,
            ),
        )
        .order_by(PatientFlowState.last_interaction_at.asc().nullsfirst())
        .limit(MAX_STUCK_FLOW_BATCH)
    )
    return query.all()


def determine_recovery_action(step_data: dict[str, Any]) -> str:
    """Choose the recovery path based on persisted flow progress markers."""
    day_complete = _is_truthy(step_data.get("day_complete"))
    day_advance_verified = _is_truthy(step_data.get("day_advance_verified"))
    if day_complete and not day_advance_verified:
        return "advance_day"
    return "resend_prompt"


def attempt_recovery(
    db: Session,
    flow_state: PatientFlowState,
    redis_client,
) -> dict[str, Any]:
    """Attempt bounded, idempotent recovery for a single stuck flow."""
    current_step_data = dict(flow_state.step_data or {})
    flow_state_id = str(flow_state.id)

    attempts = int(current_step_data.get("recovery_attempts") or 0)
    if attempts >= STUCK_FLOW_MAX_RECOVERY_ATTEMPTS:
        _mark_manual_intervention(flow_state, current_step_data)
        db.add(flow_state)
        db.commit()
        return {
            "status": "max_attempts_exceeded",
            "flow_state_id": flow_state_id,
        }

    idempotency_key = _idempotency_key(flow_state.id)
    if redis_client.get(idempotency_key):
        return {
            "status": "already_recovering",
            "flow_state_id": flow_state_id,
        }

    acquired = redis_client.set(
        idempotency_key,
        now_sao_paulo().isoformat(),
        ex=STUCK_FLOW_RECOVERY_IDEMPOTENCY_TTL,
        nx=True,
    )
    if acquired in (False, None):
        return {
            "status": "already_recovering",
            "flow_state_id": flow_state_id,
        }

    latest_flow = (
        db.query(PatientFlowState)
        .filter(
            PatientFlowState.id == flow_state.id,
            PatientFlowState.version == getattr(flow_state, "version", None),
        )
        .first()
    )
    if latest_flow is None:
        latest_flow = db.query(PatientFlowState).filter(PatientFlowState.id == flow_state.id).first()

    if latest_flow is None or not is_awaiting_response(latest_flow.step_data):
        return {
            "status": "no_longer_stuck",
            "flow_state_id": flow_state_id,
        }

    updated_step_data = dict(latest_flow.step_data or {})
    updated_step_data["recovery_attempts"] = int(updated_step_data.get("recovery_attempts") or 0) + 1
    updated_step_data["last_recovery_at"] = now_sao_paulo().isoformat()
    latest_flow.step_data = updated_step_data
    latest_flow.version = int(getattr(latest_flow, "version", 0) or 0) + 1
    db.add(latest_flow)
    db.commit()

    action = determine_recovery_action(updated_step_data)

    if action == "advance_day":
        flow_repo = FlowStateRepository(db)
        flow_manager = FlowManagementService(flow_repo=flow_repo, db=db)
        current_day = updated_step_data.get("current_flow_day") or latest_flow.current_step
        force_day = int(current_day or latest_flow.current_step or 0) + 1
        async_to_sync(flow_manager.advance_patient_flow)(
            latest_flow.patient_id,
            force_day=force_day,
        )
    else:
        prompt_message_id = _get_prompt_message_id(updated_step_data)
        if not prompt_message_id:
            raise ValueError(
                f"Unable to recover flow {flow_state_id}: missing prompt message id"
            )

        from app.tasks.flows.send_retry import retry_failed_flow_send

        retry_failed_flow_send.delay(
            prompt_message_id,
            flow_context=_build_flow_context(latest_flow, updated_step_data),
        )

    logger.info(
        "Recovered stuck flow",
        extra={
            "flow_state_id": flow_state_id,
            "patient_id": str(latest_flow.patient_id),
            "action": action,
            "attempt": updated_step_data["recovery_attempts"],
        },
    )

    return {
        "status": "recovered",
        "action": action,
        "flow_state_id": flow_state_id,
    }


__all__ = [
    "find_stuck_flows",
    "determine_recovery_action",
    "attempt_recovery",
]
