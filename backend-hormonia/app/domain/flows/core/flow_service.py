"""
Flow Service Orchestrator.
Main service that coordinates all flow operations using specialized modules.
"""

import logging
from typing import Optional, Any, Tuple
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session

from app.services.enhanced_flow_engine import EnhancedFlowEngine, FlowType
from app.domain.messaging.scheduling import MessageScheduler
from app.domain.messaging.delivery import MessageSender
from app.services.template_loader import EnhancedTemplateLoader
from app.services.analytics import FlowAnalyticsService
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository

# Import our new focused modules
from .state_machine import FlowIntegrityService
from .message_handler import MessageHandler
from .scheduling import FlowScheduler
from .message_template_loader import MessageTemplateLoader
from .analytics_tracker import AnalyticsTracker

logger = logging.getLogger(__name__)


class FlowService:
    """
    Enhanced flow engine integration service that connects AI-powered flow processing
    with message scheduling and delivery systems.

    This is the main orchestrator that delegates to specialized modules:
    - StateMachine: Flow state validation and transitions
    - MessageHandler: Message creation and delivery
    - FlowScheduler: Timing and scheduling logic
    - TemplateManager: Template loading and fallbacks
    - AnalyticsTracker: Metrics and response processing
    """

    def __init__(
        self,
        db: Session,
        enhanced_flow_engine: Optional[EnhancedFlowEngine] = None,
        message_scheduler: Optional[MessageScheduler] = None,
        message_sender: Optional[MessageSender] = None,
        template_loader: Optional[EnhancedTemplateLoader] = None,
        analytics_service: Optional[FlowAnalyticsService] = None,
        use_unified_service: bool = True,
    ):
        """
        Initialize flow service with all dependencies.

        Args:
            db: Database session
            enhanced_flow_engine: Enhanced flow engine instance
            message_scheduler: Message scheduler instance
            message_sender: Message sender instance (deprecated)
            template_loader: Template loader instance
            analytics_service: Flow analytics service instance
            use_unified_service: Whether to use UnifiedWhatsAppService (recommended)
        """
        self.db = db

        # Initialize core dependencies
        self.enhanced_flow_engine = enhanced_flow_engine or EnhancedFlowEngine(db)

        # Initialize specialized modules
        self.state_machine = FlowIntegrityService(db)
        self.message_handler = MessageHandler(
            db=db,
            message_scheduler=message_scheduler,
            message_sender=message_sender,
            analytics_service=analytics_service,
            use_unified_service=use_unified_service,
        )
        self.scheduler = FlowScheduler(db)
        self.template_manager = MessageTemplateLoader(db, template_loader)
        self.analytics_tracker = AnalyticsTracker(
            db=db,
            enhanced_flow_engine=self.enhanced_flow_engine,
            analytics_service=analytics_service,
        )

        # Keep references to repositories
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)

        logger.info("Flow Service initialized with specialized modules")

    async def process_daily_flows(self, limit: int = 1000) -> dict[str, Any]:
        """
        Process daily flows for all active patients using EnhancedFlowEngine.

        Args:
            limit: Maximum number of patients to process

        Returns:
            Processing results summary
        """
        try:
            start_time = datetime.now(timezone.utc)

            # Get all active flow states
            active_flows = await self.scheduler.get_active_flows(limit=limit)

            results = {
                "processed_patients": 0,
                "messages_scheduled": 0,
                "errors": 0,
                "skipped": 0,
                "processing_time": 0,
                "details": [],
            }

            for flow_state in active_flows:
                try:
                    patient_result = await self._process_patient_daily_flow(flow_state)
                    results["details"].append(patient_result)

                    if patient_result["status"] == "success":
                        results["processed_patients"] += 1
                        results["messages_scheduled"] += patient_result.get(
                            "messages_scheduled", 0
                        )
                    elif patient_result["status"] == "error":
                        results["errors"] += 1
                    else:
                        results["skipped"] += 1

                except Exception as e:
                    logger.error(
                        f"Error processing patient {flow_state.patient_id}: {e}"
                    )
                    results["errors"] += 1
                    results["details"].append(
                        {
                            "patient_id": str(flow_state.patient_id),
                            "status": "error",
                            "error": str(e),
                        }
                    )

            results["processing_time"] = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds()

            logger.info(
                f"Daily flow processing completed: {results['processed_patients']} patients, "
                f"{results['messages_scheduled']} messages scheduled, "
                f"{results['errors']} errors in {results['processing_time']:.2f}s"
            )

            return results

        except Exception as e:
            logger.error(f"Failed to process daily flows: {e}")
            raise

    async def _process_patient_daily_flow(self, flow_state) -> dict[str, Any]:
        """Process daily flow for a single patient."""
        try:
            patient_id = flow_state.patient_id

            # Check if we should skip this patient
            should_skip, skip_reason = await self.scheduler.should_skip_patient_flow(
                flow_state
            )
            if should_skip:
                return {
                    "patient_id": str(patient_id),
                    "status": "skipped",
                    "reason": skip_reason,
                }

            # Calculate current day
            current_day = await self.enhanced_flow_engine.calculate_patient_day(
                patient_id
            )

            # Check for quiz trigger before processing regular flow
            quiz_trigger_result = await self.scheduler.check_quiz_trigger(
                patient_id, current_day, flow_state.flow_type
            )
            if quiz_trigger_result.get("triggered"):
                return {
                    "patient_id": str(patient_id),
                    "status": "quiz_triggered",
                    "current_day": current_day,
                    "flow_type": flow_state.flow_type,
                    "quiz_session_id": quiz_trigger_result.get("quiz_session_id"),
                    "messages_scheduled": 1
                    if quiz_trigger_result.get("message_sent")
                    else 0,
                }

            # Advance patient flow if needed
            advancement_result = await self.enhanced_flow_engine.advance_patient_flow(
                patient_id
            )

            # Get appropriate message template for today
            flow_type = FlowType(flow_state.flow_type)
            message_template = await self.template_manager.get_message_template_for_day(
                flow_type, current_day
            )

            if not message_template:
                return {
                    "patient_id": str(patient_id),
                    "status": "skipped",
                    "reason": f"No message template for day {current_day}",
                }

            # Generate personalized message using AI
            personalized_content = (
                await self.enhanced_flow_engine.generate_flow_message(
                    patient_id, message_template
                )
            )

            # Calculate optimal send time
            patient = self.patient_repo.get(patient_id)
            send_time = await self.scheduler.calculate_optimal_send_time(
                patient, current_day
            )

            # Create and schedule message
            message_result = (
                await self.message_handler.create_and_schedule_flow_message(
                    patient_id,
                    flow_state,
                    message_template,
                    personalized_content,
                    current_day,
                    send_time,
                )
            )

            return {
                "patient_id": str(patient_id),
                "status": "success",
                "current_day": current_day,
                "flow_type": flow_state.flow_type,
                "messages_scheduled": 1 if message_result else 0,
                "advancement_result": advancement_result,
                "message_template": message_template.intent
                if message_template
                else None,
            }

        except Exception as e:
            logger.error(f"Error processing patient daily flow: {e}")
            return {
                "patient_id": str(flow_state.patient_id),
                "status": "error",
                "error": str(e),
            }

    async def generate_personalized_message_preview(
        self, patient_id: UUID, flow_type: str, day: int
    ) -> dict[str, Any]:
        """
        Generate a preview of personalized message for healthcare providers.

        Args:
            patient_id: Patient UUID
            flow_type: Flow type string
            day: Day number

        Returns:
            Message preview with AI insights
        """
        return await self.analytics_tracker.generate_personalized_message_preview(
            patient_id, flow_type, day, self.template_manager
        )

    async def process_patient_response_with_flow_context(
        self, patient_id: UUID, response_text: str, message_id: Optional[UUID] = None
    ) -> dict[str, Any]:
        """
        Process patient response with full flow context and AI analysis.

        Args:
            patient_id: Patient UUID
            response_text: Patient's response text
            message_id: Original message ID (optional)

        Returns:
            Response processing result with follow-up actions
        """
        return await self.analytics_tracker.process_patient_response_with_flow_context(
            patient_id, response_text, message_id, self.message_handler
        )

    async def get_flow_processing_metrics(
        self, date_range: Optional[Tuple[datetime, datetime]] = None
    ) -> dict[str, Any]:
        """
        Get comprehensive flow processing metrics.

        Args:
            date_range: Optional date range for metrics

        Returns:
            Flow processing metrics
        """
        return await self.analytics_tracker.get_flow_processing_metrics(date_range)

    async def validate_flow_consistency(self, patient_id: UUID) -> dict[str, Any]:
        """
        Validate flow consistency for a patient.

        Args:
            patient_id: Patient UUID

        Returns:
            Validation results
        """
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                return {"valid": False, "error": "No active flow state found"}

            await self.state_machine.validate_flow_consistency(flow_state)

            return {"valid": True, "message": "Flow consistency validated successfully"}

        except Exception as e:
            logger.error(f"Flow consistency validation failed: {e}")
            return {"valid": False, "error": str(e)}

    async def health_check(self) -> dict[str, Any]:
        """
        Perform comprehensive health check on flow integration service.

        Checks all critical components:
        - Enhanced flow engine (AI processing)
        - Message scheduler (task queue)
        - Database connectivity
        - Template loader (template files)
        - Flow integrity service

        Each component checked independently - one failure doesn't prevent other checks.

        Returns:
            dict: Health status with component details and overall status
        """
        try:
            results = {
                "service": "FlowService",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "components": {},
                "overall_healthy": True,
                "error_count": 0,
            }

            # Check enhanced flow engine
            try:
                engine_health = await self.enhanced_flow_engine.health_check()
                results["components"]["enhanced_flow_engine"] = engine_health
                if not engine_health.get("overall_healthy", False):
                    results["overall_healthy"] = False
                    results["error_count"] += 1
            except Exception as e:
                logger.error(
                    f"Enhanced flow engine health check failed: {e}", exc_info=True
                )
                results["components"]["enhanced_flow_engine"] = {
                    "healthy": False,
                    "error": str(e),
                }
                results["overall_healthy"] = False
                results["error_count"] += 1

            # Check message scheduler
            try:
                scheduler_health = (
                    await self.message_handler.message_scheduler.health_check()
                )
                results["components"]["message_scheduler"] = scheduler_health
                if not scheduler_health.get("healthy", False):
                    results["overall_healthy"] = False
                    results["error_count"] += 1
            except Exception as e:
                logger.error(
                    f"Message scheduler health check failed: {e}", exc_info=True
                )
                results["components"]["message_scheduler"] = {
                    "healthy": False,
                    "error": str(e),
                }
                results["overall_healthy"] = False
                results["error_count"] += 1

            # Check database connectivity
            try:
                self.db.execute("SELECT 1")
                results["components"]["database"] = {"healthy": True, "connected": True}
            except Exception as e:
                logger.error(f"Database health check failed: {e}", exc_info=True)
                results["components"]["database"] = {
                    "healthy": False,
                    "connected": False,
                    "error": str(e),
                }
                results["overall_healthy"] = False
                results["error_count"] += 1

            # Check template loader
            try:
                template = self.template_manager.template_loader.load_flow_template(
                    "initial_15_days"
                )
                results["components"]["template_loader"] = {
                    "healthy": True,
                    "templates_loaded": bool(template),
                    "fallback_available": True,
                }
            except Exception as e:
                logger.error(f"Template loader health check failed: {e}", exc_info=True)
                results["components"]["template_loader"] = {
                    "healthy": False,
                    "error": str(e),
                    "fallback_available": True,
                }
                logger.warning("Template loader unhealthy but fallbacks available")

            # Check flow integrity service
            try:
                if hasattr(self, "state_machine") and self.state_machine:
                    results["components"]["flow_integrity_service"] = {
                        "healthy": True,
                        "initialized": True,
                    }
                else:
                    results["components"]["flow_integrity_service"] = {
                        "healthy": False,
                        "initialized": False,
                    }
                    logger.warning("Flow integrity service not initialized")
            except Exception as e:
                logger.error(
                    f"Flow integrity service health check failed: {e}", exc_info=True
                )
                results["components"]["flow_integrity_service"] = {
                    "healthy": False,
                    "error": str(e),
                }

            # Add summary
            total_components = len(results["components"])
            healthy_components = sum(
                1 for c in results["components"].values() if c.get("healthy", False)
            )
            results["health_summary"] = {
                "total_components": total_components,
                "healthy_components": healthy_components,
                "unhealthy_components": total_components - healthy_components,
                "health_percentage": (healthy_components / total_components * 100)
                if total_components > 0
                else 0,
            }

            logger.info(
                f"Health check completed: {healthy_components}/{total_components} components healthy "
                f"({results['health_summary']['health_percentage']:.1f}%)"
            )

            return results

        except Exception as e:
            logger.error(f"Critical health check failure: {e}", exc_info=True)
            return {
                "service": "FlowService",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_healthy": False,
                "error": str(e),
                "critical_failure": True,
            }


# Factory function for compatibility
def get_flow_integration_service(db: Session) -> FlowService:
    """
    Get flow integration service instance.

    Args:
        db: Database session

    Returns:
        FlowService instance
    """
    return FlowService(db)


# Legacy alias for backward compatibility
FlowEngineIntegrationService = FlowService
