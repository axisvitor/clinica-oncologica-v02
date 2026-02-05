"""Flow Domain Service Implementations"""

import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timedelta, timezone

if TYPE_CHECKING:
    from app.services.enhanced_flow_engine import FlowType
    from app.services.template_loader import MessageTemplate

from .domain_services import FlowMessageRequest, FlowEvent
from app.models.flow import PatientFlowState
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository

logger = logging.getLogger(__name__)

# =============================================================================
# CONCRETE IMPLEMENTATIONS
# =============================================================================


class DatabaseFlowProcessor:
    """Concrete implementation focused ONLY on flow processing logic"""

    def __init__(self, db: Any):
        self.db = db
        self.flow_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)

    async def process_patient_flows(self, patient_ids: List[UUID]) -> Dict[str, Any]:
        """Process flows for multiple patients (clean, focused logic)"""
        results = {}

        for patient_id in patient_ids:
            try:
                result = await self.advance_flow_state(patient_id)
                results[str(patient_id)] = result
            except Exception as e:
                logger.error(f"Flow processing failed for {patient_id}: {e}")
                results[str(patient_id)] = {"success": False, "error": str(e)}

        return results

    async def advance_flow_state(self, patient_id: UUID) -> Dict[str, Any]:
        """Advance single patient flow (simplified from 150+ to ~30 lines)"""
        flow_state = self.flow_repo.get_active_flow(patient_id)
        if not flow_state:
            return {"success": False, "error": "No active flow"}

        # Calculate current day
        current_day = self._calculate_current_day(flow_state)

        # Determine flow type transition if needed
        required_flow_type = self._determine_flow_type(current_day)

        # Update flow state
        if flow_state.flow_type != required_flow_type.value:
            flow_state.flow_type = required_flow_type.value

        flow_state.current_step = current_day
        step_data = dict(flow_state.step_data or {})
        step_data["last_advancement"] = datetime.now(timezone.utc).isoformat()
        flow_state.step_data = step_data

        self.db.commit()

        return {
            "success": True,
            "flow_type": flow_state.flow_type,
            "day": current_day,
            "patient_id": str(patient_id),
        }

    def _calculate_current_day(self, flow_state: PatientFlowState) -> int:
        """Calculate current day (extracted helper)"""
        enrollment_date = datetime.fromisoformat(
            flow_state.state_data.get(
                "enrollment_date", flow_state.started_at.isoformat()
            )
        )
        return (datetime.now(timezone.utc) - enrollment_date).days + 1

    def _determine_flow_type(self, current_day: int) -> "FlowType":
        """Determine appropriate flow type (business logic)"""
        from app.services.enhanced_flow_engine import FlowType
        from ..constants import TreatmentFlow

        if current_day <= TreatmentFlow.INITIAL_PERIOD_DAYS:
            return FlowType.INITIAL_15_DAYS
        elif current_day <= TreatmentFlow.INTERMEDIATE_PERIOD_DAYS:
            return FlowType.DAYS_16_45
        else:
            return FlowType.MONTHLY_RECURRING


class DatabaseMessageScheduler:
    """Concrete implementation focused ONLY on message scheduling"""

    def __init__(self, db: Any, scheduler_service, redis_client=None):
        self.db = db
        self.scheduler = scheduler_service
        self.redis = redis_client
        self.patient_repo = PatientRepository(db)

    async def schedule_flow_message(self, message_request: FlowMessageRequest) -> bool:
        """Schedule message (simplified from 170+ to ~40 lines)"""
        try:
            from app.models.message import (
                Message,
                MessageDirection,
                MessageType,
                MessageStatus,
            )

            # Create message record
            message = Message(
                patient_id=message_request.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=message_request.template.personalized_content,
                status=MessageStatus.PENDING,
                message_metadata={
                    "flow_context": {
                        "template_intent": message_request.template.intent,
                        "priority": message_request.priority,
                    }
                },
            )

            self.db.add(message)
            self.db.flush()  # Get ID without committing

            # Schedule via scheduler service
            scheduled = await self.scheduler.schedule_message(
                message_id=message.id,
                send_time=message_request.send_time,
                priority=message_request.priority,
            )

            if scheduled:
                self.db.commit()
                return True
            else:
                self.db.rollback()
                return False

        except Exception as e:
            logger.error(f"Message scheduling failed: {e}")
            self.db.rollback()
            return False

    async def calculate_optimal_send_time(self, patient_id: UUID) -> datetime:
        """Calculate optimal send time (extracted from complex logic)"""
        try:
            patient = self.patient_repo.get(patient_id)
            preferred_hour = getattr(patient, "preferred_message_hour", 10)

            send_time = datetime.now(timezone.utc).replace(
                hour=preferred_hour, minute=0, second=0, microsecond=0
            )

            if send_time <= datetime.now(timezone.utc):
                send_time += timedelta(days=1)

            # Add randomization (±30 minutes)
            import random

            random_minutes = random.randint(-30, 30)
            send_time += timedelta(minutes=random_minutes)

            return send_time

        except Exception as e:
            logger.error(f"Send time calculation failed: {e}")
            return datetime.now(timezone.utc) + timedelta(hours=1)


class AITemplateResolver:
    """Concrete implementation focused ONLY on template resolution + AI"""

    def __init__(self, template_loader, gemini_client, conversation_memory):
        self.template_loader = template_loader
        self.gemini_client = gemini_client
        self.conversation_memory = conversation_memory

    async def resolve_template(
        self, flow_type: str, day: int
    ) -> Optional["MessageTemplate"]:
        """Resolve template with fallback (extracted from complex logic)"""
        try:
            # Load from template loader
            flow_template = self.template_loader.load_flow_template(flow_type)
            if flow_template and day in flow_template.messages:
                return flow_template.messages[day]

            # Fallback template
            return self._create_fallback_template(flow_type, day)

        except Exception as e:
            logger.error(f"Template resolution failed: {e}")
            return self._create_fallback_template(flow_type, day)

    async def personalize_message(
        self, template: "MessageTemplate", context: Dict
    ) -> str:
        """AI personalization (extracted from generate_flow_message)"""
        try:
            patient_id = context["patient_id"]
            patient_name = context["patient_name"]

            # Check for repetition
            repetition_check = await self.conversation_memory.check_message_repetition(
                patient_id, template.base_content
            )

            if repetition_check["recommendation"] in ["regenerate", "modify"]:
                return await self.gemini_client.generate_varied_question(
                    template.base_content,
                    context.get("conversation_history", []),
                    context,
                )
            else:
                return await self.gemini_client.humanize_flow_message(
                    template=template.base_content,
                    patient_name=patient_name,
                    patient_context=context,
                    conversation_history=context.get("conversation_history", []),
                    personalization_hints=template.personalization_hints,
                )

        except Exception as e:
            logger.error(f"AI personalization failed: {e}")
            return template.base_content.replace(
                "[nome]", context.get("patient_name", "")
            )

    def _create_fallback_template(self, flow_type: str, day: int) -> "MessageTemplate":
        """Create fallback template (extracted from complex fallback logic)"""
        from app.services.template_loader import MessageTemplate

        fallback_content = {
            "initial_15_days": "Olá! Como você está se sentindo hoje?",
            "days_16_45": "Esperamos que você esteja bem. Como está seu tratamento?",
            "monthly_recurring": "Olá! É hora de fazer seu check-in mensal.",
        }.get(flow_type, "Olá! Como podemos ajudá-lo hoje?")

        return MessageTemplate(
            day=day,
            intent=f"{flow_type}_fallback",
            base_content=fallback_content,
            personalization_hints=["patient_name", "care", "support"],
        )


class RedisFlowAnalytics:
    """Concrete implementation focused ONLY on flow analytics"""

    def __init__(self, redis_client, db: Any):
        self.redis = redis_client
        self.db = db

    async def track_flow_event(self, event: FlowEvent) -> None:
        """Track flow event (simplified analytics)"""
        try:
            if self.redis:
                # Store in Redis for real-time metrics
                event_key = f"flow_events:{event.patient_id}:{event.timestamp.date()}"
                await self.redis.lpush(
                    event_key,
                    {
                        "event_type": event.event_type,
                        "flow_type": event.flow_type,
                        "day": event.day,
                        "timestamp": event.timestamp.isoformat(),
                        "metadata": event.metadata,
                    },
                )
                await self.redis.expire(event_key, 86400 * 7)  # Keep for 7 days

            logger.debug(
                f"Tracked flow event: {event.event_type} for {event.patient_id}"
            )

        except Exception as e:
            logger.error(f"Analytics tracking failed: {e}")

    async def get_flow_metrics(self, filters: Dict) -> Dict[str, Any]:
        """Get flow metrics (simplified)"""
        try:
            # Basic metrics from Redis
            if self.redis:
                # Implementation would depend on specific metrics needed
                return {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_events": 0,
                    "by_flow_type": {},
                    "by_event_type": {},
                }
            return {}

        except Exception as e:
            logger.error(f"Metrics retrieval failed: {e}")
            return {}
