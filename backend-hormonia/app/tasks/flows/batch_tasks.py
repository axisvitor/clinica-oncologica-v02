"""
Batch processing tasks and helpers.

This module contains helper functions for batch processing of patient flows,
including single patient processing and message template retrieval.
"""

import asyncio
import logging
from typing import Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.enhanced_flow_engine import FlowType, MessageTemplate
from app.models.flow import PatientFlowState

# Note: send_flow_message is imported lazily inside functions to avoid circular imports

logger = logging.getLogger(__name__)


async def _process_single_patient_flow_safe(
    engine, flow_state: PatientFlowState, db: Session
) -> dict[str, Any]:
    """
    Process flow for a single patient with error handling and timeout.

    This function wraps the original _process_single_patient_flow with
    additional safety measures to prevent crashes.

    Args:
        engine: Enhanced flow engine instance
        flow_state: Patient flow state object
        db: Database session

    Returns:
        dict[str, Any]: Processing result with status and details
    """
    try:
        result = await _process_single_patient_flow(engine, flow_state)
        return result
    except asyncio.TimeoutError:
        logger.error(f"Flow processing timeout for patient {flow_state.patient_id}")
        return {
            "status": "timeout",
            "patient_id": str(flow_state.patient_id),
            "error": "Processing timeout",
        }
    except Exception as e:
        logger.error(
            f"Flow processing error for patient {flow_state.patient_id}: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "patient_id": str(flow_state.patient_id),
            "error": str(e),
        }


async def _process_single_patient_flow(
    flow_engine, flow_state: PatientFlowState
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
    # Get database session
    db = next(get_db())

    try:
        patient_id = flow_state.patient_id

        # Calculate current day
        current_day = await flow_engine.calculate_patient_day(patient_id)

        # Get patient timezone
        timezone_str = "America/Sao_Paulo"
        if flow_state.patient and hasattr(flow_state.patient, "timezone"):
            timezone_str = flow_state.patient.timezone

        try:
            import pytz

            tz = pytz.timezone(timezone_str)
        except Exception:
            logger.warning(
                f"Invalid timezone {timezone_str} for patient {patient_id}, defaulting to America/Sao_Paulo"
            )
            import pytz

            tz = pytz.timezone("America/Sao_Paulo")

        # Check if message should be sent today (in patient's timezone)
        last_message_date = None
        if flow_state.state_data and "last_message_sent" in flow_state.state_data:
            last_message_date = datetime.fromisoformat(
                flow_state.state_data["last_message_sent"]
            )
            # Ensure last_message_date is timezone aware
            if last_message_date.tzinfo is None:
                last_message_date = pytz.utc.localize(last_message_date)
            last_message_date = last_message_date.astimezone(tz)

        today_local = datetime.now(tz).date()

        # Skip if message already sent today (local time)
        if last_message_date and last_message_date.date() == today_local:
            return {
                "status": "skipped",
                "reason": "Message already sent today",
                "patient_id": str(patient_id),
                "current_day": current_day,
            }

        # Advance patient flow
        advancement_result = await flow_engine.advance_patient_flow(patient_id)

        # Get message template for current day
        flow_type_enum = FlowType(flow_state.flow_type)
        message_template = _get_message_template_for_day(
            db, flow_type_enum, current_day
        )

        if not message_template:
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

        # Schedule message for sending
        message_data = {
            "content": personalized_content,
            "type": "text",
            "flow_day": current_day,
            "flow_type": flow_type_enum.value,
            "template_id": f"{flow_type_enum.value}_day_{current_day}",
            "personalized": True,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "template_intent": message_template.intent,
            },
        }

        # Send message asynchronously (lazy import to avoid circular dependency)
        from .flow_tasks import send_flow_message

        send_task = send_flow_message.delay(str(patient_id), message_data)

        # Update flow state
        flow_state.state_data = flow_state.state_data or {}
        flow_state.state_data["last_message_sent"] = datetime.utcnow().isoformat()
        flow_state.state_data["last_task_id"] = send_task.id
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
        logger.error(f"Error processing patient flow {patient_id}: {e}")
        return {"status": "error", "patient_id": str(patient_id), "error": str(e)}
    finally:
        db.close()


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
            .filter(FlowKind.flow_type == flow_type.value, FlowKind.is_active)
            .first()
        )

        if not flow_kind:
            logger.warning(f"Flow kind not found or inactive: {flow_type.value}")
            return None

        # 2. Find the active Template Version for this kind
        active_version = (
            db.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.kind_id == flow_kind.id,
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

        # 4. Find the specific day's step
        target_step = None
        for step in steps:
            # Check if this step corresponds to the requested day
            # The JSON structure might vary, checking common patterns
            step_day = step.get("day") or step.get("step_id")

            # Handle both string and int comparisons
            if str(step_day) == str(day):
                target_step = step
                break

        if not target_step:
            # Log verbose only if needed, as many days won't have messages
            # logger.debug(f"No step found for day {day} in flow {flow_type.value}")
            return None

        # 5. Convert to MessageTemplate object
        # Extract content and metadata
        content = target_step.get("message") or target_step.get("content") or ""
        if not content:
            return None

        intent = target_step.get("intent", "daily_engagement")
        metadata = target_step.get("metadata", {})
        personalization = metadata.get("personalization_hints", [])
        ai_instructions = metadata.get("ai_instructions", "")

        return MessageTemplate(
            day=day,
            intent=intent,
            base_content=content,
            personalization_hints=personalization,
            ai_instructions=ai_instructions,
            variations=metadata.get("variations", []),
        )

    except Exception as e:
        logger.error(
            f"Error fetching template from DB for {flow_type.value} day {day}: {e}"
        )
        # Fallback to hardcoded safety net only on critical DB error
        return _get_fallback_template(flow_type, day)


def _get_fallback_template(flow_type: FlowType, day: int) -> Optional[MessageTemplate]:
    """
    Fallback hardcoded templates in case of DB failure.

    Args:
        flow_type: Flow type enum
        day: Day number in the flow

    Returns:
        Optional[MessageTemplate]: Fallback template or None

    Note:
        This is a safety mechanism for when database template retrieval fails.
        It should contain minimal templates to keep the system operational.
    """
    # Minimal fallback templates for critical scenarios
    fallback_templates = {
        FlowType.ONBOARDING: {
            1: MessageTemplate(
                day=1,
                intent="welcome",
                base_content="Bem-vindo! Estamos aqui para apoiá-lo em sua jornada.",
                personalization_hints=["nome do paciente"],
                ai_instructions="Mensagem calorosa de boas-vindas",
            )
        },
        FlowType.DAILY_ENGAGEMENT: {
            1: MessageTemplate(
                day=1,
                intent="daily_check",
                base_content="Olá! Como você está se sentindo hoje?",
                personalization_hints=["nome do paciente"],
                ai_instructions="Verificação diária amigável",
            )
        },
    }

    return fallback_templates.get(flow_type, {}).get(day)
