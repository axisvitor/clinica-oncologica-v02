"""
Batch processing tasks and helpers.

This module contains helper functions for batch processing of patient flows,
including single patient processing and message template retrieval.
"""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import get_scoped_session
from app.services.flow.types import FlowType, normalize_flow_type
from app.services.template_loader_pkg import MessageTemplate
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.models.message import (
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)
from app.agents.patient.flow_coordinator.constants import (
    MONTHLY_CYCLE_DAYS,
    MONTHLY_CYCLE_START_DAY,
)
from app.utils.timezone import SAO_PAULO_TZ_NAME, SAO_PAULO_TZ, now_sao_paulo

# Note: send_scheduled_message is imported lazily inside functions to avoid circular imports

logger = logging.getLogger(__name__)

_RECURRING_MONTHLY_FLOW_TYPES = {"quiz_mensal"}


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
    """
    Normalize absolute treatment day to template day when needed.

    Monthly recurring templates restart at treatment day 46, where:
    - day 46 -> template day 1
    - day 47 -> template day 2
    """
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


async def _process_single_patient_flow_by_id(patient_id) -> dict[str, Any]:
    """
    Process flow for a single patient with FULLY ISOLATED session.
    
    This function creates its own database session and flow engine,
    ensuring no shared state between concurrent coroutines.
    
    Args:
        patient_id: UUID of the patient to process
        
    Returns:
        dict[str, Any]: Processing result with status and details
    """
    from app.services.enhanced_flow_engine import get_enhanced_flow_engine
    from app.repositories.flow import FlowStateRepository
    
    async def _run_for_db(db: Session) -> dict[str, Any]:
        # Create isolated engine for this coroutine
        flow_engine = get_enhanced_flow_engine(db)
        flow_repo = FlowStateRepository(db)

        # Re-fetch flow_state in this session
        flow_state = flow_repo.get_active_flow(patient_id)
        if not flow_state:
            return {
                "status": "skipped",
                "patient_id": str(patient_id),
                "reason": "No active flow found",
            }

        # Check if paused
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

        # Process using the isolated session
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
    """
    Process flow for a single patient.

    Args:
        flow_engine: Enhanced flow engine instance
        flow_state (PatientFlowState): Patient flow state object

    Returns:
        dict[str, Any]: Processing result containing:
            - status: Processing status (success, skipped, error)
            - patient_id: Patient identifier
            - current_day: Current flow day
            - flow_type: Flow type
            - message_scheduled: Whether message was scheduled
            - task_id: Celery task ID if message was scheduled
            - advancement_result: Flow advancement result

    Raises:
        Exception: If patient flow processing fails
    """
    # Use provided session when available to keep state consistent with flow_engine.
    # When db is None, process entirely inside a scoped session to avoid using
    # a closed session after context exit.
    if db is None:
        with get_scoped_session() as scoped_db:
            return await _process_single_patient_flow(flow_engine, flow_state, scoped_db)

    try:
        patient_id = flow_state.patient_id

        # Calculate current day
        current_day = await flow_engine.calculate_patient_day(patient_id)

        # Keep current_day synchronized for downstream consumers.
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

        # System timezone fixed to Sao Paulo
        import pytz

        tz = pytz.timezone(SAO_PAULO_TZ_NAME)

        # Check if message should be sent today (in patient's timezone)
        last_message_date = None
        if flow_state.step_data and "last_message_sent" in flow_state.step_data:
            last_message_date = datetime.fromisoformat(
                flow_state.step_data["last_message_sent"]
            )
            # Ensure last_message_date is timezone aware
            if last_message_date.tzinfo is None:
                last_message_date = tz.localize(last_message_date)
            last_message_date = last_message_date.astimezone(tz)

        today_local = datetime.now(tz).date()

        # Define flow_type_enum early - needed for scheduling in skip paths
        flow_type_enum = normalize_flow_type(flow_state.flow_type)

        # Skip if message already sent today (local time)
        if last_message_date and last_message_date.date() == today_local:
            # Still update scheduling to prevent starvation
            _update_scheduling(flow_state, flow_type_enum, tz, db)
            db.commit()
            return {
                "status": "skipped",
                "reason": "Message already sent today",
                "patient_id": str(patient_id),
                "current_day": current_day,
            }

        # Advance patient flow (may transition to a new flow type)
        advancement_result = await flow_engine.advance_patient_flow(patient_id)
        flow_type_enum = normalize_flow_type(flow_state.flow_type)

        # Get message template for current day
        message_template = _get_message_template_for_day(
            db, flow_type_enum, current_day
        )

        if not message_template:
            # Still update scheduling to prevent starvation
            _update_scheduling(flow_state, flow_type_enum, tz, db)
            db.commit()
            return {
                "status": "skipped",
                "reason": "No message template for current day",
                "patient_id": str(patient_id),
                "current_day": current_day,
                "flow_type": flow_type_enum.value,
            }

        # Generate personalized message
        personalized_content = await flow_engine.generate_flow_message(
            patient_id, current_day, message_template
        )

        # Persist message and dispatch via the unified scheduled message pipeline.
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

        # Update step_data and scheduling before dispatch to make retries idempotent.
        now_iso = now_sao_paulo().isoformat()
        flow_state.step_data = flow_state.step_data or {}
        flow_state.step_data["last_message_sent"] = now_iso
        _update_scheduling(flow_state, flow_type_enum, tz, db)
        db.commit()

        from app.tasks.messaging import send_scheduled_message

        send_task = send_scheduled_message.delay(str(message.id))
        flow_state.step_data["last_task_id"] = send_task.id
        db.commit()

        return {
            "status": "success",
            "patient_id": str(patient_id),
            "current_day": current_day,
            "flow_type": flow_type_enum.value,
            "message_scheduled": True,
            "task_id": send_task.id,
            "advancement_result": advancement_result,
        }

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(f"Error processing patient flow {patient_id}: {e}")
        return {"status": "error", "patient_id": str(patient_id), "error": str(e)}


def _update_scheduling(
    flow_state: PatientFlowState,
    flow_type: FlowType,
    patient_tz: Any,
    db: Session
) -> None:
    """
    Update scheduling fields based on the NEXT MESSAGE DAY in the template.
    
    Templates define specific days with messages (not daily):
    - onboarding: days 1,2,3,5,7,9,11,13,15
    - daily_follow_up: days 16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,45
    - quiz_mensal: days 1,4,8,11,15,18,22,26,30
    
    This function calculates when the next message day occurs and 
    schedules at 9 AM patient timezone.
    
    Args:
        flow_state: Flow state to update
        flow_type: Flow type for template lookup
        patient_tz: Patient's timezone
        db: Database session
    """
    from datetime import timedelta

    if _is_awaiting_response(flow_state):
        logger.info(
            "Skipping scheduling update for patient %s: awaiting response",
            flow_state.patient_id,
        )
        return
    
    # Template message days based on canonical flow kinds.
    template_days = {
        "onboarding": [1, 2, 3, 5, 7, 9, 11, 13, 15],
        "daily_follow_up": [
            16,
            18,
            20,
            22,
            24,
            26,
            28,
            30,
            32,
            34,
            36,
            38,
            40,
            42,
            44,
            45,
        ],
        "quiz_mensal": [1, 4, 8, 11, 15, 18, 22, 26, 30],
    }
    
    # Get flow type string
    flow_type_str = flow_type.value if hasattr(flow_type, 'value') else str(flow_type)
    days_with_messages = template_days.get(flow_type_str, [1])  # Default daily
    
    # Get current day in the flow
    try:
        current_step = int(flow_state.current_step or 1)
    except (TypeError, ValueError):
        current_step = 1
    current_step = max(1, current_step)
    
    # For recurring monthly templates, normalize absolute day to cycle day.
    # Example: treatment day 46 -> cycle day 1.
    if flow_type_str in _RECURRING_MONTHLY_FLOW_TYPES:
        cycle_length = MONTHLY_CYCLE_DAYS
        cycle_day = _normalize_template_day(flow_type, current_step)
    else:
        cycle_day = current_step
    
    # Find the next day with a message after cycle_day
    next_message_day = None
    for day in days_with_messages:
        if day > cycle_day:
            next_message_day = day
            break
    
    # If no more days in this cycle, wrap to first day of next cycle
    if next_message_day is None:
        if flow_type_str in _RECURRING_MONTHLY_FLOW_TYPES:
            # Days until first message of next cycle
            first_message_day = days_with_messages[0] if days_with_messages else 1
            days_until_next = (cycle_length - cycle_day) + first_message_day
        else:
            # Non-recurring flow reached end of template; mark as completed.
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
    
    # Calculate next scheduled time in patient's timezone
    now_utc = now_sao_paulo()
    now_patient = now_utc.astimezone(patient_tz)
    
    # Schedule for next message day at 9 AM patient time
    next_date = now_patient.date() + timedelta(days=days_until_next)
    next_scheduled_patient = patient_tz.localize(
        datetime.combine(next_date, datetime.min.time().replace(hour=9))
    )
    next_scheduled_utc = next_scheduled_patient.astimezone(SAO_PAULO_TZ)
    
    flow_state.last_interaction_at = now_utc
    flow_state.next_scheduled_at = next_scheduled_utc


def _get_message_template_for_day(
    db: Session, flow_type: FlowType, day: int
) -> Optional[MessageTemplate]:
    """
    Get message template for specific flow type and day from database.

    Args:
        db (Session): Database session
        flow_type (FlowType): Flow type enum value
        day (int): Current day in the flow

    Returns:
        Optional[MessageTemplate]: Message template for the specified day or None if not found
    """
    try:
        from app.models.flow import FlowKind, FlowTemplateVersion

        # 1. Find the Flow Kind
        flow_kind = (
            db.query(FlowKind)
            .filter(FlowKind.kind_key == flow_type.value, FlowKind.is_active)
            .first()
        )

        if not flow_kind:
            logger.warning(f"Flow kind not found or inactive: {flow_type.value}")
            return None

        # 2. Find the active Template Version for this kind
        active_version = (
            db.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.flow_kind_id == flow_kind.id,
                FlowTemplateVersion.is_active,
            )
            .first()
        )

        if not active_version:
            logger.warning(f"No active template version found for: {flow_type.value}")
            return None

        # 3. Extract steps/messages
        # The 'messages' column is mapped to 'steps' in DB (JSONB)
        steps = active_version.messages or []

        template_day = _normalize_template_day(flow_type, day)

        # 4. Find the specific day's step
        target_step = None
        for step in steps:
            # Check if this step corresponds to the requested day
            # The JSON structure might vary, checking common patterns
            step_day = step.get("day") or step.get("step_id")

            # Handle both string and int comparisons
            if str(step_day) == str(template_day):
                target_step = step
                break

        if not target_step:
            # Log verbose only if needed, as many days won't have messages
            # logger.debug(f"No step found for day {day} in flow {flow_type.value}")
            return None

        # 5. Convert to MessageTemplate object.
        # Prefer step.messages[] when present (current DB schema).
        selected_message = None
        expects_response = False
        send_mode = str(target_step.get("send_mode") or "").strip().lower()
        nested_messages = target_step.get("messages")

        if isinstance(nested_messages, list):
            ordered_messages = [
                message
                for message in nested_messages
                if isinstance(message, Mapping)
            ]

            def _order_value(message: Mapping[str, Any]) -> int:
                try:
                    return int(message.get("order") or 0)
                except (TypeError, ValueError):
                    return 0

            ordered_messages.sort(key=_order_value)

            if send_mode in {"wait_response", "wait_each"}:
                for message in ordered_messages:
                    content_candidate = (
                        message.get("content") or message.get("message") or ""
                    )
                    if content_candidate and bool(message.get("expects_response")):
                        selected_message = message
                        break

            if selected_message is None:
                for message in ordered_messages:
                    content_candidate = (
                        message.get("content") or message.get("message") or ""
                    )
                    if content_candidate:
                        selected_message = message
                        break

        content = ""
        if isinstance(selected_message, Mapping):
            content = selected_message.get("content") or selected_message.get("message") or ""
            expects_response = bool(selected_message.get("expects_response"))

        if not content:
            content = target_step.get("message") or target_step.get("content") or ""
            expects_response = bool(target_step.get("expects_response"))

        if not content:
            return None

        intent = target_step.get("intent") or ("question" if expects_response else "flow_message")

        metadata = target_step.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        if isinstance(selected_message, Mapping):
            message_metadata = selected_message.get("metadata")
            if isinstance(message_metadata, Mapping):
                metadata = {**metadata, **message_metadata}

        personalization = metadata.get("personalization_hints", [])
        ai_instructions = metadata.get("ai_instructions", "")

        return MessageTemplate(
            day=template_day,
            intent=intent,
            base_content=content,
            core_elements={"expects_response": expects_response},
            personalization_hints=personalization,
            ai_instructions=ai_instructions,
            variations=metadata.get("variations", []),
        )

    except Exception as e:
        logger.error(
            f"Error fetching template from DB for {flow_type.value} day {day}: {e}"
        )
        raise
