"""
Batch processing tasks and helpers.

This module contains helper functions for batch processing of patient flows,
including single patient processing and message template retrieval.
"""

import asyncio
import logging
from typing import Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database import get_db, get_scoped_session
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
        result = await _process_single_patient_flow(engine, flow_state, db)
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
    
    try:
        with get_scoped_session() as db:
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
            if flow_state.step_data and flow_state.step_data.get("paused"):
                return {
                    "status": "skipped",
                    "patient_id": str(patient_id),
                    "reason": "Flow is paused",
                }
            
            # Process using the isolated session
            result = await _process_single_patient_flow(flow_engine, flow_state, db)
            return result
        
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
    own_session = False
    if db is None:
        with get_scoped_session() as db:
            own_session = True

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
        if flow_state.step_data and "last_message_sent" in flow_state.step_data:
            last_message_date = datetime.fromisoformat(
                flow_state.step_data["last_message_sent"]
            )
            # Ensure last_message_date is timezone aware
            if last_message_date.tzinfo is None:
                last_message_date = pytz.utc.localize(last_message_date)
            last_message_date = last_message_date.astimezone(tz)

        today_local = datetime.now(tz).date()

        # Define flow_type_enum early - needed for scheduling in skip paths
        flow_type_enum = FlowType(flow_state.flow_type)

        # Skip if message already sent today (local time)
        if last_message_date and last_message_date.date() == today_local:
            # Still update scheduling to prevent starvation
            _update_scheduling(flow_state, flow_type_enum, tz, db)
            return {
                "status": "skipped",
                "reason": "Message already sent today",
                "patient_id": str(patient_id),
                "current_day": current_day,
            }

        # Advance patient flow (may transition to a new flow type)
        advancement_result = await flow_engine.advance_patient_flow(patient_id)
        flow_type_enum = FlowType(flow_state.flow_type)

        # Get message template for current day
        message_template = _get_message_template_for_day(
            db, flow_type_enum, current_day
        )

        if not message_template:
            # Still update scheduling to prevent starvation
            _update_scheduling(flow_state, flow_type_enum, tz, db)
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
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "template_intent": message_template.intent,
            },
        }

        # Send message asynchronously (lazy import to avoid circular dependency)
        from .flow_tasks import send_flow_message

        send_task = send_flow_message.delay(str(patient_id), message_data)

        # Update step_data with message info
        flow_state.step_data = flow_state.step_data or {}
        flow_state.step_data["last_message_sent"] = datetime.now(timezone.utc).isoformat()
        flow_state.step_data["last_task_id"] = send_task.id
        
        # Update scheduling fields for fair ordering with proper cadence
        _update_scheduling(flow_state, flow_type_enum, tz, db)

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
        if own_session:
            db.close()


def _update_scheduling(
    flow_state: PatientFlowState,
    flow_type: FlowType,
    patient_tz: Any,
    db: Session
) -> None:
    """
    Update scheduling fields based on the NEXT MESSAGE DAY in the template.
    
    Templates define specific days with messages (not daily):
    - initial_15_days: days 1,2,3,5,7,9,11,13,15
    - days_16_45: days 16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,45
    - monthly_recurring: days 1,4,8,11,15,18,22,26,30
    
    This function calculates when the next message day occurs and 
    schedules at 9 AM patient timezone.
    
    Args:
        flow_state: Flow state to update
        flow_type: Flow type for template lookup
        patient_tz: Patient's timezone
        db: Database session
    """
    from datetime import timedelta
    
    # Template message days based on the actual flow documentation
    template_days = {
        "initial_15_days": [1, 2, 3, 5, 7, 9, 11, 13, 15],
        "days_16_45": [16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 45],
        "monthly_recurring": [1, 4, 8, 11, 15, 18, 22, 26, 30],
        # Enum values
        "onboarding": [1, 2, 3, 5, 7, 9, 11, 13, 15],
        "daily_engagement": [1, 2, 3, 5, 7, 9, 11, 13, 15],
    }
    
    # Get flow type string
    flow_type_str = flow_type.value if hasattr(flow_type, 'value') else str(flow_type)
    days_with_messages = template_days.get(flow_type_str, [1])  # Default daily
    
    # Get current day in the flow
    current_step = flow_state.current_step or 1
    
    # For monthly_recurring, use modulo to cycle through 30-day template
    # Example: step 46 -> (46-1) % 30 + 1 = 16 (day 16 of the cycle)
    if flow_type_str == "monthly_recurring":
        cycle_length = 30
        cycle_day = ((current_step - 1) % cycle_length) + 1
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
        if flow_type_str == "monthly_recurring":
            # Days until first message of next cycle
            first_message_day = days_with_messages[0] if days_with_messages else 1
            days_until_next = (cycle_length - cycle_day) + first_message_day
        else:
            # For non-recurring flows, default to tomorrow
            days_until_next = 1
    else:
        days_until_next = next_message_day - cycle_day
    
    # Calculate next scheduled time in patient's timezone
    now_utc = datetime.now(timezone.utc)
    now_patient = now_utc.astimezone(patient_tz)
    
    # Schedule for next message day at 9 AM patient time
    next_date = now_patient.date() + timedelta(days=days_until_next)
    next_scheduled_patient = patient_tz.localize(
        datetime.combine(next_date, datetime.min.time().replace(hour=9))
    )
    next_scheduled_utc = next_scheduled_patient.astimezone(timezone.utc)
    
    flow_state.last_interaction_at = now_utc
    flow_state.next_scheduled_at = next_scheduled_utc
    db.commit()


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
