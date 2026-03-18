"""Flow helpers extracted from app.tasks.flow_automation, batch_tasks, send_retry, followup_retry."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config.settings.tasks import (
    FLOW_MAX_RETRIES,
    MESSAGE_RETRY_DELAY,
    RETRY_BACKOFF_FACTOR,
)
from app.database import get_scoped_session
from app.models.flow import PatientFlowOverride, PatientFlowState
from app.models.message import (
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.services.flow.types import FlowType, normalize_flow_type
from app.services.follow_up_system.enums import FollowUpType
from app.services.follow_up_system.models import FollowUpAction
from app.services.template_loader_pkg import MessageTemplate
from app.agents.patient.flow_coordinator.constants import (
    MONTHLY_CYCLE_DAYS,
    MONTHLY_CYCLE_START_DAY,
)
from app.utils.timezone import SAO_PAULO_TZ_NAME, SAO_PAULO_TZ, now_sao_paulo

logger = logging.getLogger(__name__)

# ── send_retry constants ──────────────────────────────────────────────────────
SEND_RETRY_MAX_RETRIES = FLOW_MAX_RETRIES
SEND_RETRY_BASE_DELAY = MESSAGE_RETRY_DELAY
SEND_RETRY_BACKOFF_FACTOR = RETRY_BACKOFF_FACTOR
SEND_RETRY_MAX_JITTER = 10

_TERMINAL_MESSAGE_STATUSES = {
    MessageStatus.SENT,
    MessageStatus.DELIVERED,
    MessageStatus.READ,
}

# ── followup_retry constants ─────────────────────────────────────────────────
FOLLOWUP_RETRY_MAX = 3
FOLLOWUP_RETRY_BASE_DELAY = 30
FOLLOWUP_RETRY_BACKOFF = 2
FOLLOWUP_RETRY_MAX_JITTER = 10

_RECURRING_MONTHLY_FLOW_TYPES = {"quiz_mensal"}


# ── flow_automation helpers ──────────────────────────────────────────────────

def _get_reminder_message(patient_name: str) -> str:
    """Generate reminder message content."""
    return (
        f"Olá {patient_name}! 👋\n\n"
        f"Você tem um questionário pendente que é importante "
        f"para acompanharmos seu tratamento.\n\n"
        f"Por favor, reserve alguns minutos para completá-lo. "
        f"Sua participação é fundamental! 💪\n\n"
        f"Equipe Hormonia"
    )


def _determine_template_for_patient(patient) -> Optional[str]:
    """Determine the appropriate flow template based on patient data."""
    if hasattr(patient, "treatment_type") and patient.treatment_type:
        treatment_lower = patient.treatment_type.lower()

        if "hormone" in treatment_lower or "hormonal" in treatment_lower:
            return "hormonia_fluxo_hormonal"
        elif "quimio" in treatment_lower or "chemo" in treatment_lower:
            return "hormonia_fluxo_quimio"
        elif "radio" in treatment_lower or "radiation" in treatment_lower:
            return "hormonia_fluxo_radio"

    return "hormonia_fluxo_padrao"


def _is_auto_resume_due(auto_resume_at: Optional[str]) -> bool:
    if not auto_resume_at:
        return False

    try:
        normalized = auto_resume_at.replace("Z", "+00:00")
        due_at = datetime.fromisoformat(normalized)
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=now_sao_paulo().tzinfo)
        return due_at <= now_sao_paulo()
    except ValueError:
        logger.warning("Skipping auto-resume due to invalid auto_resume_at", extra={"auto_resume_at": auto_resume_at})
        return False


# ── batch_tasks helpers ──────────────────────────────────────────────────────

def get_db():
    """Backward-compatible DB session factory alias."""
    return get_scoped_session()


def _is_awaiting_response(flow_state: PatientFlowState) -> bool:
    """Return whether the flow is currently waiting for patient response."""
    step_data = flow_state.step_data
    if not isinstance(step_data, Mapping):
        return False
    value = step_data.get("awaiting_response")
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (bool, int, float)):
        return bool(value)
    if value is None:
        return False
    return bool(value)


def _is_flow_paused(flow_state: PatientFlowState) -> bool:
    """Return whether the flow is paused by status or step_data flag."""
    if getattr(flow_state, "status", None) == "paused":
        return True
    step_data = flow_state.step_data
    if not isinstance(step_data, Mapping):
        return False
    value = step_data.get("paused")
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (bool, int, float)):
        return bool(value)
    if value is None:
        return False
    return bool(value)


def _normalize_template_day(flow_type: FlowType, day: int) -> int:
    """Normalize absolute treatment day to template day when needed."""
    flow_type_str = flow_type.value if hasattr(flow_type, "value") else str(flow_type)
    try:
        normalized_day = int(day)
    except (TypeError, ValueError):
        normalized_day = 1
    normalized_day = max(1, normalized_day)

    if flow_type_str in _RECURRING_MONTHLY_FLOW_TYPES:
        if normalized_day >= MONTHLY_CYCLE_START_DAY:
            return (
                (normalized_day - MONTHLY_CYCLE_START_DAY) % MONTHLY_CYCLE_DAYS
            ) + 1
        return ((normalized_day - 1) % MONTHLY_CYCLE_DAYS) + 1

    return normalized_day


def _check_patient_override_for_day(
    flow_state_id: UUID, day: int, db: Session
) -> Optional[dict]:
    """Check for per-patient override, using Redis cache with DB fallback.

    Returns override dict {content, message_type, expects_response, skip}
    for the given day, or None if no override exists.
    Cache key: flow_override:{flow_state_id}:days — matches S01 invalidation.
    """
    cache_key = f"flow_override:{flow_state_id}:days"
    day_key = str(day)
    overrides_dict: Optional[dict] = None

    # Try Redis cache first
    try:
        from app.core.redis_manager import get_sync_redis_client

        redis_client = get_sync_redis_client()
        cached = redis_client.get(cache_key)
        if cached is not None:
            logger.debug(
                "Override cache hit for flow_state %s day %s",
                flow_state_id, day,
            )
            overrides_dict = json.loads(cached)
        else:
            logger.debug(
                "Override cache miss for flow_state %s day %s, querying DB",
                flow_state_id, day,
            )
    except Exception:
        logger.warning("Redis override cache error in batch path (falling back to DB)")

    # DB fallback when cache missed
    if overrides_dict is None:
        try:
            rows = (
                db.query(PatientFlowOverride)
                .filter(PatientFlowOverride.patient_flow_state_id == flow_state_id)
                .all()
            )
            overrides_dict = {}
            for row in rows:
                overrides_dict[str(row.day_number)] = {
                    "content": row.content,
                    "message_type": row.message_type,
                    "expects_response": row.expects_response,
                    "skip": row.skip,
                }
            # Cache the result (including empty dict as miss sentinel)
            try:
                from app.core.redis_manager import get_sync_redis_client

                redis_client = get_sync_redis_client()
                redis_client.set(cache_key, json.dumps(overrides_dict), ex=3600)
            except Exception:
                logger.warning("Redis cache write error in batch path (non-fatal)")
        except Exception:
            logger.warning(
                "Failed to query patient overrides in batch path (falling back to global)"
            )
            return None

    return overrides_dict.get(day_key) if overrides_dict else None


async def _process_single_patient_flow_by_id(patient_id) -> dict[str, Any]:
    """Process flow for a single patient with FULLY ISOLATED session."""
    from app.services.enhanced_flow_engine import get_enhanced_flow_engine

    async def _run_for_db(db: Session) -> dict[str, Any]:
        flow_engine = get_enhanced_flow_engine(db)
        flow_repo = FlowStateRepository(db)

        flow_state = flow_repo.get_active_flow(patient_id)
        if not flow_state:
            return {
                "status": "skipped",
                "patient_id": str(patient_id),
                "reason": "No active flow found",
            }

        if _is_flow_paused(flow_state):
            return {
                "status": "skipped",
                "patient_id": str(patient_id),
                "reason": "Flow is paused",
            }

        if _is_awaiting_response(flow_state):
            return {
                "status": "skipped",
                "patient_id": str(patient_id),
                "reason": "Awaiting patient response",
            }

        return await _process_single_patient_flow(flow_engine, flow_state, db)

    try:
        db_resource = get_db()
        if hasattr(db_resource, "__enter__"):
            with db_resource as db:
                return await _run_for_db(db)

        db = next(db_resource)
        try:
            return await _run_for_db(db)
        finally:
            close = getattr(db, "close", None)
            if callable(close):
                close()

    except asyncio.TimeoutError:
        logger.error(f"Flow processing timeout for patient {patient_id}")
        return {
            "status": "timeout",
            "patient_id": str(patient_id),
            "error": "Processing timeout",
        }
    except Exception as e:
        logger.error(
            f"Flow processing error for patient {patient_id}: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "patient_id": str(patient_id),
            "error": str(e),
        }


async def _process_single_patient_flow(
    flow_engine, flow_state: PatientFlowState, db: Optional[Session] = None
) -> dict[str, Any]:
    """Process flow for a single patient."""
    if db is None:
        with get_scoped_session() as scoped_db:
            return await _process_single_patient_flow(flow_engine, flow_state, scoped_db)

    try:
        patient_id = flow_state.patient_id

        current_day = await flow_engine.calculate_patient_day(patient_id)

        patient = flow_state.patient
        if patient is None:
            patient = db.get(Patient, patient_id)
        if patient and patient.current_day != current_day:
            patient.current_day = current_day
            patient.updated_at = now_sao_paulo()

        if _is_awaiting_response(flow_state):
            return {
                "status": "skipped",
                "reason": "Awaiting patient response",
                "patient_id": str(patient_id),
                "current_day": current_day,
            }
        if _is_flow_paused(flow_state):
            return {
                "status": "skipped",
                "reason": "Flow is paused",
                "patient_id": str(patient_id),
                "current_day": current_day,
            }

        import pytz

        tz = pytz.timezone(SAO_PAULO_TZ_NAME)

        last_message_date = None
        if flow_state.step_data and "last_message_sent" in flow_state.step_data:
            last_message_date = datetime.fromisoformat(
                flow_state.step_data["last_message_sent"]
            )
            if last_message_date.tzinfo is None:
                last_message_date = tz.localize(last_message_date)
            last_message_date = last_message_date.astimezone(tz)

        today_local = datetime.now(tz).date()

        flow_type_enum = normalize_flow_type(flow_state.flow_type)

        if last_message_date and last_message_date.date() == today_local:
            _update_scheduling(flow_state, flow_type_enum, tz, db)
            db.commit()
            return {
                "status": "skipped",
                "reason": "Message already sent today",
                "patient_id": str(patient_id),
                "current_day": current_day,
            }

        # ── Patient override check (before template lookup / AI) ──────────
        template_day = _normalize_template_day(flow_type_enum, current_day)
        override = _check_patient_override_for_day(flow_state.id, template_day, db)

        if override and override.get("skip"):
            logger.info(
                "Day %s skipped by patient override for patient %s",
                template_day, patient_id,
                extra={"flow_state_id": str(flow_state.id), "current_day": current_day},
            )
            _update_scheduling(flow_state, flow_type_enum, tz, db)
            db.commit()
            return {
                "status": "skipped",
                "patient_id": str(patient_id),
                "current_day": current_day,
                "reason": "Day skipped by patient override",
            }

        if override:
            logger.info(
                "Using patient override content for day %s patient %s",
                template_day, patient_id,
                extra={"flow_state_id": str(flow_state.id)},
            )
            personalized_content = override["content"]
            step_data = flow_state.step_data or {}
            message_metadata = {
                "generated_at": now_sao_paulo().isoformat(),
                "template_intent": "patient_override",
                "flow_context": {
                    "flow_day": current_day,
                    "flow_type": flow_type_enum.value,
                    "flow_kind": step_data.get("flow_kind", flow_type_enum.value),
                    "template_id": f"override_{flow_type_enum.value}_day_{template_day}",
                    "personalized": False,
                    "override": True,
                },
            }
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=personalized_content,
                status=MessageStatus.PENDING,
                scheduled_for=now_sao_paulo(),
                message_metadata=message_metadata,
            )
            db.add(message)
            db.flush()

            now_iso = now_sao_paulo().isoformat()
            flow_state.step_data = flow_state.step_data or {}
            flow_state.step_data["last_message_sent"] = now_iso
            _update_scheduling(flow_state, flow_type_enum, tz, db)
            db.commit()

            from app.tasks.messaging_taskiq import send_scheduled_message

            send_task_result = send_scheduled_message.kiq(str(message.id))
            task_id = str(getattr(send_task_result, "task_id", "unknown"))
            flow_state.step_data["last_task_id"] = task_id
            db.commit()

            return {
                "status": "success",
                "patient_id": str(patient_id),
                "current_day": current_day,
                "flow_type": flow_type_enum.value,
                "message_scheduled": True,
                "task_id": task_id,
                "override": True,
            }
        # ── End override check — fall through to template + AI path ───────

        advancement_result = await flow_engine.advance_patient_flow(patient_id)
        flow_type_enum = normalize_flow_type(flow_state.flow_type)

        message_template = _get_message_template_for_day(
            db, flow_type_enum, current_day
        )

        if not message_template:
            _update_scheduling(flow_state, flow_type_enum, tz, db)
            db.commit()
            return {
                "status": "skipped",
                "reason": "No message template for current day",
                "patient_id": str(patient_id),
                "current_day": current_day,
                "flow_type": flow_type_enum.value,
            }

        personalized_content = await flow_engine.generate_flow_message(
            patient_id,
            current_day,
            message_template,
            use_sync_agents=True,
        )

        step_data = flow_state.step_data or {}
        pending_context = step_data.get("pending_response_context")
        if not isinstance(pending_context, dict):
            pending_context = {}
        prompt_message_id = pending_context.get("prompt_message_id")
        flow_context = {
            "flow_day": current_day,
            "flow_type": flow_type_enum.value,
            "flow_kind": step_data.get("flow_kind", flow_type_enum.value),
            "message_index": step_data.get("current_day_message_index", 0),
            "current_message_index": step_data.get("current_day_message_index", 0),
            "template_id": f"{flow_type_enum.value}_day_{current_day}",
            "personalized": True,
            "awaiting_response": step_data.get("awaiting_response", False),
        }
        if prompt_message_id:
            flow_context["prompt_message_id"] = str(prompt_message_id)
        message_metadata = {
            "generated_at": now_sao_paulo().isoformat(),
            "template_intent": message_template.intent,
            "flow_context": flow_context,
        }

        message = Message(
            patient_id=patient_id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content=personalized_content,
            status=MessageStatus.PENDING,
            scheduled_for=now_sao_paulo(),
            message_metadata=message_metadata,
        )
        db.add(message)
        db.flush()

        now_iso = now_sao_paulo().isoformat()
        flow_state.step_data = flow_state.step_data or {}
        flow_state.step_data["last_message_sent"] = now_iso
        _update_scheduling(flow_state, flow_type_enum, tz, db)
        db.commit()

        from app.tasks.messaging_taskiq import send_scheduled_message

        send_task_result = send_scheduled_message.kiq(str(message.id))
        task_id = str(getattr(send_task_result, "task_id", "unknown"))
        flow_state.step_data["last_task_id"] = task_id
        db.commit()

        return {
            "status": "success",
            "patient_id": str(patient_id),
            "current_day": current_day,
            "flow_type": flow_type_enum.value,
            "message_scheduled": True,
            "task_id": task_id,
            "advancement_result": advancement_result,
        }

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(f"Error processing patient flow {patient_id}: {e}")
        return {"status": "error", "patient_id": str(patient_id), "error": str(e)}


def _get_message_template_for_day(
    db: Session, flow_type: FlowType, day: int
) -> Optional[MessageTemplate]:
    """Look up message template for the given flow type and day."""
    from app.services.template_loader_pkg import TemplateLoaderService

    template_day = _normalize_template_day(flow_type, day)
    flow_type_str = flow_type.value if hasattr(flow_type, "value") else str(flow_type)

    try:
        loader = TemplateLoaderService(db)
        template = loader.get_template_for_day(flow_type_str, template_day)
        return template
    except Exception:
        logger.debug(
            "No message template found for flow_type=%s day=%s",
            flow_type_str,
            template_day,
        )
        return None


def _update_scheduling(
    flow_state: PatientFlowState,
    flow_type: FlowType,
    patient_tz: Any,
    db: Session,
) -> None:
    """Update scheduling fields based on the NEXT MESSAGE DAY in the template."""
    from datetime import timedelta

    if _is_awaiting_response(flow_state):
        logger.info(
            "Skipping scheduling update for patient %s: awaiting response",
            flow_state.patient_id,
        )
        return

    template_days = {
        "onboarding": [1, 2, 3, 5, 7, 9, 11, 13, 15],
        "daily_follow_up": [
            16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 45,
        ],
        "quiz_mensal": [1, 4, 8, 11, 15, 18, 22, 26, 30],
    }

    flow_type_str = flow_type.value if hasattr(flow_type, "value") else str(flow_type)
    days_with_messages = template_days.get(flow_type_str, [1])

    try:
        current_step = int(flow_state.current_step or 1)
    except (TypeError, ValueError):
        current_step = 1
    current_step = max(1, current_step)

    if flow_type_str in _RECURRING_MONTHLY_FLOW_TYPES:
        cycle_day = _normalize_template_day(flow_type, current_step)
    else:
        cycle_day = current_step

    next_message_day = None
    for day in days_with_messages:
        if day > cycle_day:
            next_message_day = day
            break

    if next_message_day is None:
        if flow_type_str in _RECURRING_MONTHLY_FLOW_TYPES:
            first_message_day = days_with_messages[0] if days_with_messages else 1
            days_until_next = (MONTHLY_CYCLE_DAYS - cycle_day) + first_message_day
        else:
            now_utc = now_sao_paulo()
            flow_state.last_interaction_at = now_utc
            flow_state.next_scheduled_at = None
            if flow_state.completed_at is None:
                flow_state.completed_at = now_utc
            if (flow_state.status or "").lower() not in {"completed", "cancelled"}:
                flow_state.status = "completed"
            logger.info(
                "Flow %s completed for patient %s at day %s",
                flow_type_str,
                flow_state.patient_id,
                current_step,
            )
            return
    else:
        days_until_next = next_message_day - cycle_day

    now_utc = now_sao_paulo()
    now_patient = now_utc.astimezone(patient_tz)
    next_date = now_patient.date() + timedelta(days=days_until_next)

    import pytz
    next_scheduled = patient_tz.localize(
        datetime.combine(next_date, datetime.min.time().replace(hour=9))
    )

    flow_state.next_scheduled_at = next_scheduled.astimezone(pytz.UTC)
    flow_state.last_interaction_at = now_utc


# ── send_retry helpers ───────────────────────────────────────────────────────

def _resolve_flow_context(
    message: Message,
    flow_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if flow_context is not None:
        return flow_context

    metadata = message.message_metadata or {}
    stored_context = metadata.get("flow_context")
    return stored_context if isinstance(stored_context, dict) else None


def _record_permanent_delivery_failure(message: Message, db: Any) -> None:
    flow_repo = FlowStateRepository(db)
    active_flow = flow_repo.get_active_flow(message.patient_id)
    if not active_flow:
        return

    state_data = dict(active_flow.state_data or {})
    delivery_failures = list(state_data.get("delivery_failures") or [])
    delivery_failures.append(
        {
            "message_id": str(message.id),
            "failure_timestamp": now_sao_paulo().isoformat(),
            "failure_reason": message.failure_reason,
            "retry_count": message.retry_count,
            "step": active_flow.current_step,
        }
    )

    state_data["delivery_failures"] = delivery_failures
    state_data["skip_waiting_for_message"] = str(message.id)
    state_data["last_delivery_failure"] = now_sao_paulo().isoformat()

    active_flow.state_data = state_data
    db.add(active_flow)


# ── followup_retry helpers ───────────────────────────────────────────────────

def _build_retry_action(
    *,
    action_id: str,
    patient_id: str,
    parameters: dict | None,
    follow_up_type: str,
    priority: str,
) -> FollowUpAction | None:
    if not parameters:
        return None

    return FollowUpAction(
        action_id=UUID(str(action_id)),
        patient_id=UUID(str(patient_id)),
        follow_up_type=FollowUpType(follow_up_type),
        priority=priority,
        scheduled_for=now_sao_paulo(),
        parameters=parameters,
        created_by="followup_retry_task",
    )
