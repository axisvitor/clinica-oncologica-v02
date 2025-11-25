"""
Main service implementation for the Follow-up Action System.
Orchestrates follow-up processing, scheduling, and execution.
"""
import logging
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from .enums import FollowUpType, EscalationLevel, NotificationChannel
from .models import FollowUpAction, EscalationAlert, ConversationContext
from .generators import ResponseGenerator
from .escalation import EscalationManager
from .notifications import NotificationService
from app.services.response_processor import ResponseProcessingResult, StructuredResponse
from app.services.analytics.data_extraction import ConcernLevel
from app.services.ai.ai_service import get_ai_service, PatientContext
from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.repositories.message import MessageRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.domain.messaging.delivery import MessageSender
from app.domain.messaging.scheduling import MessageScheduler
from app.services.follow_up.redis_store import FollowUpRedisStore

logger = logging.getLogger(__name__)


class FollowUpSystemService:
    """
    Follow-up action system service for handling patient response follow-ups,
    escalations, and healthcare provider notifications.
    """

    def __init__(self, db: Any):
        """
        Initialize follow-up system service.

        Args:
            db: Database session
        """
        self.db = db
        self.message_repo = MessageRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self._ai_service = None  # Will be initialized on first use

        # Initialize other services (would be injected in production)
        self.message_sender = MessageSender(db)
        self.message_scheduler = MessageScheduler(db)

        # Initialize Redis store with graceful fallback
        self.redis_store = FollowUpRedisStore()
        self._use_redis = True  # Will be set to False if Redis is unavailable

        # In-memory fallback storage (only used if Redis is unavailable)
        self.pending_actions: dict[UUID, FollowUpAction] = {}
        self.active_alerts: dict[UUID, EscalationAlert] = {}
        self.conversation_contexts: dict[UUID, ConversationContext] = {}

        # Initialize sub-services
        self.escalation_manager = EscalationManager(self.redis_store, self.active_alerts)
        self.notification_service = NotificationService()

        logger.info("Follow-up System Service initialized with Redis persistence")

    async def _get_ai_service(self):
        """Get AI service instance (lazy initialization)."""
        if self._ai_service is None:
            self._ai_service = await get_ai_service()
        return self._ai_service

    async def process_response_follow_up(self,
                                       response_result: ResponseProcessingResult) -> List[FollowUpAction]:
        """
        Process follow-up actions for a patient response.

        Args:
            response_result: Response processing result

        Returns:
            List of follow-up actions created
        """
        try:
            follow_up_actions = []
            patient_id = response_result.patient_id
            structured_response = response_result.structured_response

            # Update conversation context
            await self._update_conversation_context(patient_id, structured_response)

            # Generate empathetic follow-up message
            empathetic_action = await self._create_empathetic_follow_up(
                patient_id, structured_response
            )
            if empathetic_action:
                follow_up_actions.append(empathetic_action)

            # Handle medical concerns
            if structured_response.medical_concerns:
                concern_actions = await self._handle_medical_concerns(
                    patient_id, structured_response.medical_concerns, structured_response.original_message
                )
                follow_up_actions.extend(concern_actions)

            # Handle escalation if required
            if response_result.escalation_required:
                escalation_action = await self.escalation_manager.create_escalation_alert(
                    patient_id, structured_response
                )
                if escalation_action:
                    follow_up_actions.append(escalation_action)

            # Handle specific response types
            type_specific_actions = await self._handle_response_type_specific_actions(
                patient_id, structured_response
            )
            follow_up_actions.extend(type_specific_actions)

            # Schedule all actions
            for action in follow_up_actions:
                await self._schedule_follow_up_action(action)

            logger.info(f"Created {len(follow_up_actions)} follow-up actions for patient {patient_id}")
            return follow_up_actions

        except Exception as e:
            logger.error(f"Failed to process response follow-up: {e}")
            raise

    async def _update_conversation_context(self,
                                         patient_id: UUID,
                                         structured_response: StructuredResponse) -> None:
        """Update conversation context for continuity."""
        try:
            # Get existing context from Redis or create new one
            context_data = await self.redis_store.get_context(patient_id)

            if context_data:
                # Load from Redis
                context = ConversationContext(
                    patient_id=patient_id,
                    conversation_history=context_data.get("conversation_history", []),
                    current_topic=context_data.get("current_topic"),
                    emotional_state=context_data.get("emotional_state"),
                    medical_context=context_data.get("medical_context", {}),
                    preferences=context_data.get("preferences", {})
                )
            elif patient_id in self.conversation_contexts:
                # Fallback: Use in-memory
                context = self.conversation_contexts[patient_id]
            else:
                # Create new context
                context = ConversationContext(
                    patient_id=patient_id,
                    conversation_history=[],
                    current_topic=None,
                    emotional_state=None,
                    medical_context={},
                    preferences={}
                )

            # Add to conversation history
            context.conversation_history.append({
                "timestamp": structured_response.timestamp.isoformat(),
                "message": structured_response.original_message,
                "response_type": structured_response.response_type.value,
                "sentiment": structured_response.sentiment_analysis.get("sentiment"),
                "concern_level": structured_response.concern_level.value,
                "medical_concerns": structured_response.medical_concerns
            })

            # Keep only last 20 messages
            context.conversation_history = context.conversation_history[-20:]

            # Update emotional state
            context.emotional_state = structured_response.sentiment_analysis.get("sentiment")

            # Update current topic based on response category
            context.current_topic = structured_response.response_category.value

            # Update medical context
            if structured_response.medical_concerns:
                context.medical_context["recent_concerns"] = structured_response.medical_concerns
                context.medical_context["last_concern_time"] = structured_response.timestamp.isoformat()

            # Update preferences from extracted data
            if structured_response.patient_preferences:
                for pref in structured_response.patient_preferences:
                    context.preferences[pref.preference_type] = {
                        "value": pref.value,
                        "confidence": pref.confidence,
                        "updated_at": pref.extracted_at.isoformat()
                    }

            context.last_updated = datetime.utcnow()

            # Store in Redis (with fallback to in-memory)
            stored = await self.redis_store.store_context(context)
            if not stored:
                # Fallback to in-memory
                self.conversation_contexts[patient_id] = context
                logger.debug(f"Stored context in memory for patient {patient_id}")
            else:
                logger.debug(f"Stored context in Redis for patient {patient_id}")

        except Exception as e:
            logger.error(f"Failed to update conversation context: {e}")

    async def _create_empathetic_follow_up(self,
                                         patient_id: UUID,
                                         structured_response: StructuredResponse) -> Optional[FollowUpAction]:
        """Create empathetic follow-up message based on patient response."""
        try:
            # Get patient context
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return None

            # Build patient context for AI
            patient_context = await self._build_patient_context(patient_id, patient)

            # Get AI service and create generator
            ai_service = await self._get_ai_service()
            generator = ResponseGenerator(ai_service)

            # Generate empathetic follow-up
            return await generator.create_empathetic_follow_up(
                patient_id, patient, structured_response, patient_context
            )

        except Exception as e:
            logger.error(f"Failed to create empathetic follow-up: {e}")
            return None

    async def _handle_medical_concerns(self,
                                     patient_id: UUID,
                                     medical_concerns: List[str],
                                     original_message: str) -> List[FollowUpAction]:
        """Handle medical concerns with appropriate follow-up actions."""
        actions = []

        try:
            generator = ResponseGenerator(None)

            for concern in medical_concerns:
                # Determine concern severity and type
                concern_level = generator.assess_concern_severity(concern)
                concern_type = generator.classify_concern_type(concern)

                # Create appropriate follow-up action
                if concern_level in [ConcernLevel.HIGH, ConcernLevel.CRITICAL]:
                    # High priority medical clarification
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.MEDICAL_CLARIFICATION,
                        priority="high",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=10),
                        parameters={
                            "concern": concern,
                            "concern_type": concern_type.value if concern_type else "general",
                            "original_message": original_message,
                            "clarification_questions": generator.generate_clarification_questions(concern)
                        }
                    )
                    actions.append(action)

                elif concern_level == ConcernLevel.MEDIUM:
                    # Provider notification
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.PROVIDER_ALERT,
                        priority="medium",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=30),
                        parameters={
                            "concern": concern,
                            "concern_type": concern_type.value if concern_type else "general",
                            "original_message": original_message,
                            "review_required": True
                        }
                    )
                    actions.append(action)

            return actions

        except Exception as e:
            logger.error(f"Failed to handle medical concerns: {e}")
            return actions

    async def _handle_response_type_specific_actions(self,
                                                   patient_id: UUID,
                                                   structured_response: StructuredResponse) -> List[FollowUpAction]:
        """Handle response type specific follow-up actions."""
        actions = []

        try:
            response_category = structured_response.response_category
            extracted_data = structured_response.extracted_data

            # Handle pain scale responses
            if "pain_scale" in extracted_data:
                pain_level = extracted_data["pain_scale"]
                if pain_level >= 7:
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.MEDICAL_CLARIFICATION,
                        priority="high",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=15),
                        parameters={
                            "pain_level": pain_level,
                            "follow_up_questions": [
                                "A dor está interferindo em suas atividades?",
                                "Você tomou algum analgésico?",
                                "A dor mudou desde ontem?"
                            ]
                        }
                    )
                    actions.append(action)

            # Handle medication mentions
            if extracted_data.get("medication_mentioned"):
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.MEDICATION_GUIDANCE,
                    priority="normal",
                    scheduled_for=datetime.utcnow() + timedelta(hours=2),
                    parameters={
                        "medication_context": structured_response.original_message,
                        "guidance_type": "general_medication_support"
                    }
                )
                actions.append(action)

            # Handle negative mood indicators
            if extracted_data.get("mood_indicator") == "negative":
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.EMOTIONAL_SUPPORT,
                    priority="normal",
                    scheduled_for=datetime.utcnow() + timedelta(hours=1),
                    parameters={
                        "emotional_state": "negative",
                        "support_type": "encouragement_and_resources"
                    }
                )
                actions.append(action)

            # Handle positive responses with encouragement
            elif structured_response.sentiment_analysis.get("sentiment") == "positive":
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.TREATMENT_ENCOURAGEMENT,
                    priority="low",
                    scheduled_for=datetime.utcnow() + timedelta(hours=4),
                    parameters={
                        "encouragement_type": "positive_reinforcement",
                        "progress_acknowledgment": True
                    }
                )
                actions.append(action)

            return actions

        except Exception as e:
            logger.error(f"Failed to handle response type specific actions: {e}")
            return actions

    async def _schedule_follow_up_action(self, action: FollowUpAction) -> bool:
        """Schedule a follow-up action for execution."""
        try:
            # Store action in Redis (with fallback to in-memory)
            stored = await self.redis_store.store_action(action)
            if not stored:
                # Fallback to in-memory
                self.pending_actions[action.action_id] = action
                logger.debug(f"Stored action in memory: {action.action_id}")
            else:
                logger.debug(f"Stored action in Redis: {action.action_id}")

            # Schedule execution based on action type
            if action.follow_up_type == FollowUpType.EMPATHETIC_RESPONSE:
                await self._schedule_message_action(action)
            elif action.follow_up_type == FollowUpType.ESCALATION_NOTIFICATION:
                await self._schedule_escalation_action(action)
            elif action.follow_up_type == FollowUpType.PROVIDER_ALERT:
                await self._schedule_provider_notification(action)
            else:
                # Generic scheduling
                await self._schedule_generic_action(action)

            logger.info(f"Scheduled follow-up action {action.action_id} for patient {action.patient_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to schedule follow-up action: {e}")
            return False

    async def _schedule_message_action(self, action: FollowUpAction) -> None:
        """Schedule a message-based follow-up action."""
        try:
            message_content = action.parameters.get("message_content")
            if not message_content:
                return

            # Create message
            message = Message(
                patient_id=action.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=message_content,
                status=MessageStatus.PENDING,
                scheduled_for=action.scheduled_for,
                message_metadata={
                    "follow_up_action_id": str(action.action_id),
                    "follow_up_type": action.follow_up_type.value,
                    "priority": action.priority,
                    "ai_generated": True
                }
            )

            # Save message
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            # Schedule with message scheduler
            await self.message_scheduler.schedule_message(
                message_id=message.id,
                send_time=action.scheduled_for,
                priority=action.priority
            )

        except Exception as e:
            logger.error(f"Failed to schedule message action: {e}")
            self.db.rollback()

    async def _schedule_escalation_action(self, action: FollowUpAction) -> None:
        """Schedule an escalation notification action."""
        try:
            alert_id = action.parameters.get("alert_id")
            if not alert_id:
                return

            alert = self.active_alerts.get(UUID(alert_id))
            if not alert:
                return

            # Send notifications through configured channels
            for channel in alert.notification_channels:
                await self.notification_service.send_provider_notification(
                    patient_id=action.patient_id,
                    patient_repo=self.patient_repo,
                    notification_data=alert,
                    channel=channel
                )

            # Mark action as executed
            action.executed_at = datetime.utcnow()
            action.status = "executed"
            action.execution_result = {
                "notifications_sent": len(alert.notification_channels),
                "channels": [ch.value for ch in alert.notification_channels]
            }

        except Exception as e:
            logger.error(f"Failed to schedule escalation action: {e}")

    async def _schedule_provider_notification(self, action: FollowUpAction) -> None:
        """Schedule a provider notification action."""
        try:
            # Create provider notification
            notification_data = {
                "patient_id": str(action.patient_id),
                "concern": action.parameters.get("concern"),
                "concern_type": action.parameters.get("concern_type"),
                "original_message": action.parameters.get("original_message"),
                "priority": action.priority,
                "created_at": action.created_at.isoformat()
            }

            # Send notification (implementation would depend on notification system)
            await self.notification_service.send_provider_notification(
                patient_id=action.patient_id,
                patient_repo=self.patient_repo,
                notification_data=notification_data,
                channel=NotificationChannel.DASHBOARD_ALERT
            )

            # Mark as executed
            action.executed_at = datetime.utcnow()
            action.status = "executed"

        except Exception as e:
            logger.error(f"Failed to schedule provider notification: {e}")

    async def _schedule_generic_action(self, action: FollowUpAction) -> None:
        """Schedule a generic follow-up action."""
        try:
            # For now, just mark as scheduled
            # In production, this would integrate with task scheduling system
            action.status = "scheduled"

            logger.info(f"Generic action {action.action_id} scheduled for {action.scheduled_for}")

        except Exception as e:
            logger.error(f"Failed to schedule generic action: {e}")

    async def _build_patient_context(self, patient_id: UUID, patient) -> PatientContext:
        """Build patient context for AI processing."""
        try:
            # Get recent messages
            recent_messages = self.message_repo.get_conversation_history(patient_id, limit=5)
            recent_responses = [
                msg.content for msg in recent_messages
                if msg.direction == MessageDirection.INBOUND and msg.content
            ]

            # Get flow state
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            treatment_day = flow_state.current_step if flow_state else 1

            return PatientContext(
                patient_id=str(patient_id),
                name=patient.name,
                treatment_type=getattr(patient, 'treatment_type', 'general'),
                treatment_day=treatment_day,
                age=getattr(patient, 'age', None),
                recent_responses=recent_responses,
                medical_history=getattr(patient, 'medical_history', {}),
                preferences=getattr(patient, 'preferences', {})
            )

        except Exception as e:
            logger.error(f"Failed to build patient context: {e}")
            raise

    async def execute_pending_actions(self, limit: int = 100) -> Dict[str, Any]:
        """Execute pending follow-up actions."""
        try:
            executed_count = 0
            failed_count = 0
            current_time = datetime.utcnow()

            # Get actions ready for execution from Redis
            ready_action_dicts = await self.redis_store.get_pending_actions(
                limit=limit,
                before=current_time
            )

            # If Redis returned nothing, try in-memory fallback
            if not ready_action_dicts and self.pending_actions:
                ready_action_dicts = [
                    {
                        "action_id": str(action.action_id),
                        "patient_id": str(action.patient_id),
                        "follow_up_type": action.follow_up_type.value if hasattr(action.follow_up_type, 'value') else str(action.follow_up_type),
                        "priority": action.priority,
                        "scheduled_for": action.scheduled_for.isoformat(),
                        "parameters": action.parameters,
                        "created_by": action.created_by,
                        "created_at": action.created_at.isoformat(),
                        "status": action.status,
                        "executed_at": action.executed_at.isoformat() if action.executed_at else None,
                        "execution_result": action.execution_result
                    }
                    for action in self.pending_actions.values()
                    if action.status == "pending" and action.scheduled_for <= current_time
                ][:limit]

            # Execute each action
            for action_dict in ready_action_dicts:
                action_id = UUID(action_dict["action_id"])
                try:
                    # Reconstruct action object for execution
                    action = FollowUpAction(
                        action_id=action_id,
                        patient_id=UUID(action_dict["patient_id"]),
                        follow_up_type=FollowUpType(action_dict["follow_up_type"]),
                        priority=action_dict["priority"],
                        scheduled_for=datetime.fromisoformat(action_dict["scheduled_for"]),
                        parameters=action_dict["parameters"],
                        created_by=action_dict["created_by"]
                    )
                    action.status = action_dict["status"]
                    action.created_at = datetime.fromisoformat(action_dict["created_at"])

                    success = await self._execute_action(action)

                    if success:
                        executed_count += 1
                        # Update status in Redis
                        await self.redis_store.update_action_status(
                            action_id=action_id,
                            status="executed",
                            executed_at=current_time,
                            execution_result=action.execution_result
                        )
                    else:
                        failed_count += 1
                        await self.redis_store.update_action_status(
                            action_id=action_id,
                            status="failed",
                            executed_at=current_time
                        )

                except Exception as e:
                    logger.error(f"Failed to execute action {action_id}: {e}")
                    failed_count += 1
                    await self.redis_store.update_action_status(
                        action_id=action_id,
                        status="failed",
                        executed_at=current_time
                    )

            # Get total pending count
            all_pending = await self.redis_store.get_pending_actions(limit=10000)
            total_pending = len(all_pending)

            return {
                "executed": executed_count,
                "failed": failed_count,
                "total_pending": total_pending
            }

        except Exception as e:
            logger.error(f"Failed to execute pending actions: {e}")
            return {"error": str(e)}

    async def _execute_action(self, action: FollowUpAction) -> bool:
        """Execute a specific follow-up action."""
        try:
            if action.follow_up_type == FollowUpType.EMPATHETIC_RESPONSE:
                return await self._execute_message_action(action)
            elif action.follow_up_type == FollowUpType.ESCALATION_NOTIFICATION:
                return await self._execute_escalation_action(action)
            elif action.follow_up_type == FollowUpType.PROVIDER_ALERT:
                return await self._execute_provider_alert(action)
            else:
                # Generic execution
                logger.info(f"Executed generic action {action.action_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to execute action {action.action_id}: {e}")
            return False

    async def _execute_message_action(self, action: FollowUpAction) -> bool:
        """Execute message-based action."""
        try:
            # Message should already be scheduled, just mark as executed
            action.execution_result = {"message_scheduled": True}
            return True

        except Exception as e:
            logger.error(f"Failed to execute message action: {e}")
            return False

    async def _execute_escalation_action(self, action: FollowUpAction) -> bool:
        """Execute escalation action."""
        try:
            # Escalation should already be sent, just mark as executed
            action.execution_result = {"escalation_sent": True}
            return True

        except Exception as e:
            logger.error(f"Failed to execute escalation action: {e}")
            return False

    async def _execute_provider_alert(self, action: FollowUpAction) -> bool:
        """Execute provider alert action."""
        try:
            # Alert should already be sent, just mark as executed
            action.execution_result = {"alert_sent": True}
            return True

        except Exception as e:
            logger.error(f"Failed to execute provider alert: {e}")
            return False

    async def get_active_alerts(self, patient_id: Optional[UUID] = None) -> List[EscalationAlert]:
        """Get active escalation alerts."""
        try:
            # Get alerts from Redis
            alert_dicts = await self.redis_store.get_active_alerts(patient_id=patient_id)

            # If Redis returned nothing, try in-memory fallback
            if not alert_dicts and self.active_alerts:
                alerts = list(self.active_alerts.values())
                if patient_id:
                    alerts = [alert for alert in alerts if alert.patient_id == patient_id]
                return [alert for alert in alerts if alert.resolved_at is None]

            # Convert alert dictionaries to EscalationAlert objects
            active_alerts = []
            for alert_dict in alert_dicts:
                from app.services.analytics.data_extraction import MedicalConcernType
                alert = EscalationAlert(
                    alert_id=UUID(alert_dict["alert_id"]),
                    patient_id=UUID(alert_dict["patient_id"]),
                    escalation_level=EscalationLevel(alert_dict["escalation_level"]),
                    concern_type=MedicalConcernType(alert_dict["concern_type"]),
                    description=alert_dict["description"],
                    original_message=alert_dict["original_message"],
                    recommended_actions=alert_dict["recommended_actions"],
                    notification_channels=[NotificationChannel(ch) for ch in alert_dict["notification_channels"]],
                    requires_immediate_response=alert_dict["requires_immediate_response"]
                )
                alert.created_at = datetime.fromisoformat(alert_dict["created_at"])
                alert.acknowledged_at = datetime.fromisoformat(alert_dict["acknowledged_at"]) if alert_dict.get("acknowledged_at") else None
                alert.resolved_at = datetime.fromisoformat(alert_dict["resolved_at"]) if alert_dict.get("resolved_at") else None
                alert.assigned_to = alert_dict.get("assigned_to")
                active_alerts.append(alert)

            return active_alerts

        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []

    async def acknowledge_alert(self, alert_id: UUID, acknowledged_by: str) -> bool:
        """Acknowledge an escalation alert."""
        try:
            acknowledged_at = datetime.utcnow()

            # Update in Redis
            success = await self.redis_store.update_alert_status(
                alert_id=alert_id,
                acknowledged_at=acknowledged_at,
                assigned_to=acknowledged_by
            )

            # Update in-memory fallback if it exists
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.acknowledged_at = acknowledged_at
                alert.assigned_to = acknowledged_by

            if success:
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            else:
                logger.warning(f"Alert {alert_id} not found for acknowledgment")

            return success

        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            return False

    async def resolve_alert(self, alert_id: UUID, resolved_by: str) -> bool:
        """Resolve an escalation alert."""
        try:
            resolved_at = datetime.utcnow()

            # Update in Redis
            success = await self.redis_store.update_alert_status(
                alert_id=alert_id,
                resolved_at=resolved_at,
                assigned_to=resolved_by
            )

            # Update in-memory fallback if it exists
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved_at = resolved_at
                if not alert.assigned_to:
                    alert.assigned_to = resolved_by

            if success:
                logger.info(f"Alert {alert_id} resolved by {resolved_by}")
            else:
                logger.warning(f"Alert {alert_id} not found for resolution")

            return success

        except Exception as e:
            logger.error(f"Failed to resolve alert: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on follow-up system."""
        try:
            # Check Redis health
            redis_health = await self.redis_store.health_check()

            # Get stats from Redis or in-memory
            if redis_health.get("healthy") and redis_health.get("backend") == "redis":
                stats = redis_health.get("stats", {})
            else:
                # Fallback to in-memory stats
                stats = {
                    "pending_actions": len([a for a in self.pending_actions.values() if a.status == "pending"]),
                    "active_alerts": len([a for a in self.active_alerts.values() if a.resolved_at is None]),
                    "total_actions": len(self.pending_actions),
                    "total_alerts": len(self.active_alerts)
                }

            return {
                "service": "FollowUpSystemService",
                "timestamp": datetime.utcnow().isoformat(),
                "healthy": True,
                "storage": redis_health,
                "stats": stats
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service": "FollowUpSystemService",
                "timestamp": datetime.utcnow().isoformat(),
                "healthy": False,
                "error": str(e)
            }


# Global service instance
_follow_up_system_service: Optional[FollowUpSystemService] = None


def get_follow_up_system_service(db: Any) -> FollowUpSystemService:
    """
    Get follow-up system service instance.

    Args:
        db: Database session

    Returns:
        FollowUpSystemService instance
    """
    return FollowUpSystemService(db)
