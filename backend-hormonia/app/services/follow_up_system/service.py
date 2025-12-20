"""
Main orchestrator for the Follow-up Action System.
Coordinates follow-up processing, scheduling, and execution via specialized components.
"""

import logging
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from uuid import UUID

from .context.manager import ContextManager
from .context.builder import ContextBuilder
from .generators.empathy import EmpathyGenerator
from .generators.medical import MedicalConcernGenerator
from .scheduling.scheduler import ActionScheduler
from .scheduling.message import MessageScheduler as FollowUpMessageScheduler
from .scheduling.escalation import EscalationScheduler
from .execution.message import MessageExecutor
from .models import FollowUpAction, EscalationAlert
from .escalation import EscalationManager
from .notifications import NotificationService
from app.services.response_processor import ResponseProcessingResult
from app.services.ai.ai_service import get_ai_service
from app.repositories.message import MessageRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.domain.messaging.delivery import MessageSender
from app.domain.messaging.scheduling import MessageScheduler
from app.services.follow_up.redis_store import FollowUpRedisStore
from app.core.redis_unified import get_sync_redis
from app.integrations.evolution import EvolutionClient

logger = logging.getLogger(__name__)


class FollowUpSystemService:
    """
    Follow-up action system orchestrator.
    Coordinates specialized components for context, generation, scheduling, and execution.
    """

    def __init__(self, db: Any):
        """Initialize follow-up system service with specialized components."""
        self.db = db
        self.message_repo = MessageRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self._ai_service = None

        # Domain services - initialize with required dependencies
        logger.info("Initializing MessageSender with db, redis_client, evolution_client...")
        redis_client = get_sync_redis()
        evolution_client = EvolutionClient()
        self.message_sender = MessageSender(db, redis_client, evolution_client)
        logger.info("MessageSender initialized successfully")
        self.message_scheduler = MessageScheduler(db)

        # Redis with in-memory fallback
        self.redis_store = FollowUpRedisStore()
        self.pending_actions: dict[UUID, FollowUpAction] = {}
        self.active_alerts: dict[UUID, EscalationAlert] = {}
        self.conversation_contexts: dict = {}

        # Initialize specialized components
        self.context_manager = ContextManager(
            self.redis_store, self.conversation_contexts
        )
        self.context_builder = ContextBuilder(self.message_repo, self.flow_state_repo)
        self.escalation_manager = EscalationManager(
            self.redis_store, self.active_alerts
        )
        self.notification_service = NotificationService()
        self.action_scheduler = ActionScheduler(self.redis_store, self.pending_actions)
        self.message_action_scheduler = FollowUpMessageScheduler(
            db, self.message_scheduler
        )
        self.escalation_scheduler = EscalationScheduler(
            self.notification_service, self.patient_repo, self.active_alerts
        )
        self.action_executor = MessageExecutor(self.redis_store, self.pending_actions)

        logger.info("Follow-up System Service initialized with modular components")

    async def rehydrate_from_redis(self) -> Dict[str, int]:
        """
        Rehydrate in-memory state from Redis after service restart.

        This method loads persisted data from Redis back into the in-memory
        dictionaries to restore state that would otherwise be lost.

        Returns:
            Dict with counts of rehydrated items
        """
        rehydrated = {"pending_actions": 0, "active_alerts": 0, "errors": 0}

        try:
            # Rehydrate pending actions
            pending_action_dicts = await self.redis_store.get_pending_actions(
                limit=1000
            )
            for action_dict in pending_action_dicts:
                try:
                    action = self._dict_to_follow_up_action(action_dict)
                    if action:
                        self.pending_actions[action.action_id] = action
                        rehydrated["pending_actions"] += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to rehydrate action {action_dict.get('action_id')}: {e}"
                    )
                    rehydrated["errors"] += 1

            # Rehydrate active alerts
            active_alert_dicts = await self.redis_store.get_active_alerts()
            for alert_dict in active_alert_dicts:
                try:
                    alert = self._dict_to_escalation_alert(alert_dict)
                    if alert:
                        self.active_alerts[alert.alert_id] = alert
                        rehydrated["active_alerts"] += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to rehydrate alert {alert_dict.get('alert_id')}: {e}"
                    )
                    rehydrated["errors"] += 1

            # Note: conversation_contexts have 7-day TTL and are loaded on-demand
            # via context_manager.get_context(), so no bulk rehydration needed

            logger.info(
                f"Rehydration complete: {rehydrated['pending_actions']} actions, "
                f"{rehydrated['active_alerts']} alerts, {rehydrated['errors']} errors"
            )
            return rehydrated

        except Exception as e:
            logger.error(f"Failed to rehydrate from Redis: {e}", exc_info=True)
            return rehydrated

    def _dict_to_follow_up_action(
        self, data: Dict[str, Any]
    ) -> Optional[FollowUpAction]:
        """Convert dictionary to FollowUpAction object."""
        try:
            from .enums import FollowUpType

            action = FollowUpAction(
                action_id=UUID(data["action_id"]),
                patient_id=UUID(data["patient_id"]),
                follow_up_type=FollowUpType(data["follow_up_type"]),
                priority=data["priority"],
                scheduled_for=datetime.fromisoformat(data["scheduled_for"]),
                parameters=data.get("parameters", {}),
                created_by=data.get("created_by", "system"),
            )
            action.status = data.get("status", "pending")
            action.created_at = datetime.fromisoformat(data["created_at"])
            if data.get("executed_at"):
                action.executed_at = datetime.fromisoformat(data["executed_at"])
            action.execution_result = data.get("execution_result")
            return action
        except Exception as e:
            logger.warning(f"Failed to convert dict to FollowUpAction: {e}")
            return None

    def _dict_to_escalation_alert(
        self, data: Dict[str, Any]
    ) -> Optional[EscalationAlert]:
        """Convert dictionary to EscalationAlert object."""
        try:
            from .enums import EscalationLevel, NotificationChannel
            from app.services.analytics.data_extraction import MedicalConcernType

            alert = EscalationAlert(
                alert_id=UUID(data["alert_id"]),
                patient_id=UUID(data["patient_id"]),
                escalation_level=EscalationLevel(data["escalation_level"]),
                concern_type=MedicalConcernType(data["concern_type"]),
                description=data["description"],
                original_message=data["original_message"],
                recommended_actions=data.get("recommended_actions", []),
                notification_channels=[
                    NotificationChannel(ch)
                    for ch in data.get("notification_channels", [])
                ],
                requires_immediate_response=data.get(
                    "requires_immediate_response", False
                ),
            )
            alert.created_at = datetime.fromisoformat(data["created_at"])
            if data.get("acknowledged_at"):
                alert.acknowledged_at = datetime.fromisoformat(data["acknowledged_at"])
            if data.get("resolved_at"):
                alert.resolved_at = datetime.fromisoformat(data["resolved_at"])
            alert.assigned_to = data.get("assigned_to")
            return alert
        except Exception as e:
            logger.warning(f"Failed to convert dict to EscalationAlert: {e}")
            return None

    async def _get_ai_service(self):
        """Get AI service instance (lazy initialization)."""
        if self._ai_service is None:
            self._ai_service = await get_ai_service()
        return self._ai_service

    async def process_response_follow_up(
        self, response_result: ResponseProcessingResult
    ) -> List[FollowUpAction]:
        """Process follow-up actions for a patient response."""
        try:
            follow_up_actions = []
            patient_id = response_result.patient_id
            structured_response = response_result.structured_response

            # Update conversation context
            await self.context_manager.update_context(patient_id, structured_response)

            # Generate empathetic follow-up
            patient = self.patient_repo.get(patient_id)
            if patient:
                ai_service = await self._get_ai_service()
                empathy_gen = EmpathyGenerator(ai_service)
                patient_context = self.context_builder.build_patient_context(
                    patient_id, patient
                )
                empathetic_action = await empathy_gen.create_empathetic_follow_up(
                    patient_id, patient, structured_response, patient_context
                )
                if empathetic_action:
                    follow_up_actions.append(empathetic_action)

            # Handle medical concerns
            if structured_response.medical_concerns:
                medical_gen = MedicalConcernGenerator()
                concern_actions = await medical_gen.handle_medical_concerns(
                    patient_id,
                    structured_response.medical_concerns,
                    structured_response.original_message,
                )
                follow_up_actions.extend(concern_actions)

            # Handle escalation
            if response_result.escalation_required:
                escalation_action = (
                    await self.escalation_manager.create_escalation_alert(
                        patient_id, structured_response
                    )
                )
                if escalation_action:
                    follow_up_actions.append(escalation_action)

            # Handle response type specific actions
            medical_gen = MedicalConcernGenerator()
            type_specific_actions = (
                await medical_gen.handle_response_type_specific_actions(
                    patient_id, structured_response
                )
            )
            follow_up_actions.extend(type_specific_actions)

            # Schedule all actions
            for action in follow_up_actions:
                await self._schedule_action_by_type(action)

            logger.info(
                f"Created {len(follow_up_actions)} follow-up actions for patient {patient_id}"
            )
            return follow_up_actions

        except Exception as e:
            logger.error(f"Failed to process response follow-up: {e}")
            raise

    async def _schedule_action_by_type(self, action: FollowUpAction) -> bool:
        """Schedule action based on its type."""
        try:
            # Store action first
            await self.action_scheduler.schedule_action(action)

            # Schedule execution based on type
            from .enums import FollowUpType

            if action.follow_up_type == FollowUpType.EMPATHETIC_RESPONSE:
                await self.message_action_scheduler.schedule_message_action(action)
            elif action.follow_up_type == FollowUpType.ESCALATION_NOTIFICATION:
                await self.escalation_scheduler.schedule_escalation_action(action)
            elif action.follow_up_type == FollowUpType.PROVIDER_ALERT:
                await self.escalation_scheduler.schedule_provider_notification(action)

            return True
        except Exception as e:
            logger.error(f"Failed to schedule action: {e}")
            return False

    async def execute_pending_actions(self, limit: int = 100) -> Dict[str, Any]:
        """Execute pending follow-up actions."""
        return await self.action_executor.execute_pending_actions(limit)

    async def get_active_alerts(
        self, patient_id: Optional[UUID] = None
    ) -> List[EscalationAlert]:
        """Get active escalation alerts."""
        try:
            alert_dicts = await self.redis_store.get_active_alerts(
                patient_id=patient_id
            )

            if not alert_dicts and self.active_alerts:
                alerts = list(self.active_alerts.values())
                if patient_id:
                    alerts = [
                        alert for alert in alerts if alert.patient_id == patient_id
                    ]
                return [alert for alert in alerts if alert.resolved_at is None]

            # Convert dicts to objects
            from .enums import EscalationLevel, NotificationChannel
            from app.services.analytics.data_extraction import MedicalConcernType

            active_alerts = []
            for alert_dict in alert_dicts:
                alert = EscalationAlert(
                    alert_id=UUID(alert_dict["alert_id"]),
                    patient_id=UUID(alert_dict["patient_id"]),
                    escalation_level=EscalationLevel(alert_dict["escalation_level"]),
                    concern_type=MedicalConcernType(alert_dict["concern_type"]),
                    description=alert_dict["description"],
                    original_message=alert_dict["original_message"],
                    recommended_actions=alert_dict["recommended_actions"],
                    notification_channels=[
                        NotificationChannel(ch)
                        for ch in alert_dict["notification_channels"]
                    ],
                    requires_immediate_response=alert_dict[
                        "requires_immediate_response"
                    ],
                )
                alert.created_at = datetime.fromisoformat(alert_dict["created_at"])
                alert.acknowledged_at = (
                    datetime.fromisoformat(alert_dict["acknowledged_at"])
                    if alert_dict.get("acknowledged_at")
                    else None
                )
                alert.resolved_at = (
                    datetime.fromisoformat(alert_dict["resolved_at"])
                    if alert_dict.get("resolved_at")
                    else None
                )
                alert.assigned_to = alert_dict.get("assigned_to")
                active_alerts.append(alert)

            return active_alerts

        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []

    async def acknowledge_alert(self, alert_id: UUID, acknowledged_by: str) -> bool:
        """Acknowledge an escalation alert."""
        try:
            acknowledged_at = datetime.now(timezone.utc)
            success = await self.redis_store.update_alert_status(
                alert_id=alert_id,
                acknowledged_at=acknowledged_at,
                assigned_to=acknowledged_by,
            )

            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.acknowledged_at = acknowledged_at
                alert.assigned_to = acknowledged_by

            if success:
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return success

        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            return False

    async def resolve_alert(self, alert_id: UUID, resolved_by: str) -> bool:
        """Resolve an escalation alert."""
        try:
            resolved_at = datetime.now(timezone.utc)
            success = await self.redis_store.update_alert_status(
                alert_id=alert_id, resolved_at=resolved_at, assigned_to=resolved_by
            )

            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved_at = resolved_at
                if not alert.assigned_to:
                    alert.assigned_to = resolved_by

            if success:
                logger.info(f"Alert {alert_id} resolved by {resolved_by}")
            return success

        except Exception as e:
            logger.error(f"Failed to resolve alert: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on follow-up system."""
        try:
            redis_health = await self.redis_store.health_check()

            if redis_health.get("healthy") and redis_health.get("backend") == "redis":
                stats = redis_health.get("stats", {})
            else:
                stats = {
                    "pending_actions": len(
                        [
                            a
                            for a in self.pending_actions.values()
                            if a.status == "pending"
                        ]
                    ),
                    "active_alerts": len(
                        [
                            a
                            for a in self.active_alerts.values()
                            if a.resolved_at is None
                        ]
                    ),
                    "total_actions": len(self.pending_actions),
                    "total_alerts": len(self.active_alerts),
                }

            return {
                "service": "FollowUpSystemService",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "healthy": True,
                "storage": redis_health,
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service": "FollowUpSystemService",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "healthy": False,
                "error": str(e),
            }


def get_follow_up_system_service(db: Any) -> FollowUpSystemService:
    """Get follow-up system service instance."""
    return FollowUpSystemService(db)
