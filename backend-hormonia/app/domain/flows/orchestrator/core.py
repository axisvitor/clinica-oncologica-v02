"""
Flow Orchestrator - Core Module

Main FlowOrchestrator class implementing core flow execution logic.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID

from sqlalchemy.orm import Session

# Base orchestrator classes
from app.orchestration.base import (
    BaseOrchestrator,
    ResilientOrchestrator,
    StateAwareOrchestrator,
)

# Core domain models
from app.models.flow import PatientFlowState
from app.models.patient import Patient

# Repository layer
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository

# Service dependencies
from app.services.ai import AIService
from app.services.quiz import QuizTemplateService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.services.template_loader import EnhancedTemplateLoader
from app.services.analytics import FlowAnalyticsService
from app.domain.messaging.scheduling import MessageScheduler
from app.config.flow_templates import FlowTemplateLoader

# Domain modules
from ..state import FlowStateManager, FlowStateValidator
from ..messaging import MessageComposer, MessageSender
from ..scheduling import QuizScheduler, FollowUpScheduler
from ..templates import TemplateRenderer, TemplateContextBuilder
from ..rules import FlowRulesEngine, RuleConditionEvaluator
from ..ab_testing import ABTestManager, VariantSelector
from ..analytics import AnalyticsCollector, FlowMetricsCalculator
from ..error_handling import FlowErrorHandler, ErrorRecoveryManager

# Package modules
from .enums import FlowOperationType
from .models import FlowExecutionContext, FlowExecutionResult
from .utils import calculate_treatment_day
from .lifecycle import FlowLifecycleManager
from .messaging import FlowMessagingOrchestrator
from .scheduling import FlowSchedulingOrchestrator

logger = logging.getLogger(__name__)


class FlowOrchestrator(
    BaseOrchestrator,  # Provides: db, logging, health checks, metrics
    ResilientOrchestrator,  # Provides: circuit breakers, retry logic
    StateAwareOrchestrator,  # Provides: state management, caching
):
    """
    Flow Orchestrator - Coordinates Domain Modules with Base Class Infrastructure.

    This orchestrator now inherits common infrastructure from base classes:
    - BaseOrchestrator: Database session, logging, health checks, metrics
    - ResilientOrchestrator: Circuit breakers, retry logic, fallback handlers
    - StateAwareOrchestrator: State persistence, caching, transitions

    This eliminates ~750 LOC of duplicate code while maintaining 100% backward compatibility.
    """

    def __init__(
        self,
        db: Session,
        ai_service: Optional[AIService] = None,
        quiz_service: Optional[QuizTemplateService] = None,
        whatsapp_service: Optional[UnifiedWhatsAppService] = None,
        template_loader: Optional[EnhancedTemplateLoader] = None,
        analytics_service: Optional[FlowAnalyticsService] = None,
        message_scheduler: Optional[MessageScheduler] = None,
        flow_template_loader: Optional[FlowTemplateLoader] = None,
    ):
        """Initialize FlowOrchestrator with service dependencies and base class infrastructure."""
        # Initialize base classes (provides db, logging, circuit breakers, state management)
        super().__init__(
            db=db,
            service_name="FlowOrchestrator",
            enable_health_checks=True,
            state_cache_enabled=True,
        )

        # Repository dependencies
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)

        # Service dependencies (with defaults)
        self.ai_service = ai_service or AIService()
        self.quiz_service = quiz_service or QuizTemplateService(db)
        self.whatsapp_service = whatsapp_service or UnifiedWhatsAppService(
            db=db, messaging_mode=MessagingMode.HYBRID
        )
        self.template_loader = template_loader or EnhancedTemplateLoader(db=db)
        self.analytics_service = analytics_service or FlowAnalyticsService(db)
        self.message_scheduler = message_scheduler or MessageScheduler(db)
        self.flow_template_loader = flow_template_loader or FlowTemplateLoader()

        # Setup circuit breakers using inherited ResilientOrchestrator methods
        self.whatsapp_circuit_breaker = self.setup_circuit_breaker(
            name="whatsapp_service",
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3,
            timeout=30.0,
            expected_exception=(Exception, ConnectionError, TimeoutError),
        )

        self.ai_circuit_breaker = self.setup_circuit_breaker(
            name="ai_service",
            failure_threshold=3,
            recovery_timeout=45.0,
            success_threshold=2,
            timeout=20.0,
            expected_exception=(Exception, TimeoutError),
        )

        # Initialize domain modules
        self.state_manager = FlowStateManager(db, self.flow_state_repo)
        self.state_validator = FlowStateValidator()
        self.message_composer = MessageComposer(
            self.ai_service, self.ai_circuit_breaker
        )
        self.message_sender = MessageSender(
            db, self.message_scheduler, self.whatsapp_circuit_breaker
        )
        self.quiz_scheduler = QuizScheduler(db)
        self.follow_up_scheduler = FollowUpScheduler()
        self.template_renderer = TemplateRenderer(
            self.template_loader, self.flow_template_loader
        )
        self.context_builder = TemplateContextBuilder()
        self.rules_engine = FlowRulesEngine()
        self.rule_evaluator = RuleConditionEvaluator()
        self.ab_test_manager = ABTestManager()
        self.variant_selector = VariantSelector()
        self.analytics_collector = AnalyticsCollector(self.analytics_service)
        self.metrics_calculator = FlowMetricsCalculator()
        self.error_handler = FlowErrorHandler()
        self.recovery_manager = ErrorRecoveryManager()

        # Initialize orchestrator submodules
        self.lifecycle_manager = FlowLifecycleManager(
            self.patient_repo,
            self.state_manager,
            self.state_validator,
            self.template_renderer,
            self.rules_engine,
            self.analytics_collector,
        )

        self.messaging_orchestrator = FlowMessagingOrchestrator(
            self.message_composer, self.message_sender
        )

        self.scheduling_orchestrator = FlowSchedulingOrchestrator(
            self.quiz_scheduler, self.follow_up_scheduler
        )

        # Flow execution callbacks
        self._flow_callbacks: Dict[str, List[Callable]] = {
            "before_execution": [],
            "after_execution": [],
            "on_error": [],
            "on_state_change": [],
        }

        self.log_info("FlowOrchestrator initialized with all domain modules")

    # ===============================
    # BaseOrchestrator Abstract Method Implementations
    # ===============================

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute orchestrator logic based on operation type.

        Implements BaseOrchestrator.execute() abstract method.
        """
        operation = context.get("operation")
        patient_id = context.get("patient_id")

        if operation == "start":
            result = await self.start_patient_flow(
                patient_id=patient_id,
                flow_type=context.get("flow_type"),
                metadata=context.get("metadata"),
            )
        elif operation == "advance":
            result = await self.advance_patient_flow(
                patient_id=patient_id,
                target_day=context.get("target_day"),
                force_advance=context.get("force_advance", False),
            )
        elif operation == "pause":
            result = await self.pause_patient_flow(
                patient_id=patient_id,
                reason=context.get("reason"),
                metadata=context.get("metadata"),
            )
        elif operation == "resume":
            result = await self.resume_patient_flow(
                patient_id=patient_id, metadata=context.get("metadata")
            )
        elif operation == "stop":
            result = await self.stop_patient_flow(
                patient_id=patient_id,
                reason=context.get("reason"),
                metadata=context.get("metadata"),
            )
        else:
            return {
                "success": False,
                "message": f"Unknown operation: {operation}",
                "error": f"Invalid operation type: {operation}",
            }

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "errors": result.errors,
        }

    def validate(self, context: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate context before execution.

        Implements BaseOrchestrator.validate() abstract method.
        """
        # Check required fields
        if "operation" not in context:
            return False, "Missing required field: operation"

        if "patient_id" not in context:
            return False, "Missing required field: patient_id"

        # Validate operation type
        valid_operations = ["start", "advance", "pause", "resume", "stop"]
        if context["operation"] not in valid_operations:
            return False, f"Invalid operation: {context['operation']}"

        return True, None

    # ===============================
    # StateAwareOrchestrator Abstract Method Implementations
    # ===============================

    async def _persist_to_db(self, entity_id: UUID, state_data: Dict[str, Any]):
        """
        Persist flow state to database.

        Implements StateAwareOrchestrator._persist_to_db() abstract method.
        """
        flow_state = self.flow_state_repo.get_by_patient(entity_id)

        if flow_state:
            # Update existing state
            for key, value in state_data.items():
                if hasattr(flow_state, key):
                    setattr(flow_state, key, value)
                else:
                    # Store in state_data JSON field
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data[key] = value

            self.db.commit()
        else:
            self.log_warning(
                f"Flow state not found for persistence: {entity_id}",
                extra={"entity_id": str(entity_id)},
            )

    async def _fetch_from_db(self, entity_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Fetch flow state from database.

        Implements StateAwareOrchestrator._fetch_from_db() abstract method.
        """
        flow_state = self.flow_state_repo.get_by_patient(entity_id)

        if flow_state:
            return {
                "id": flow_state.id,
                "patient_id": flow_state.patient_id,
                "flow_type": flow_state.flow_type,
                "status": flow_state.status,
                "current_step": flow_state.current_step,
                "state_data": flow_state.state_data or {},
                "created_at": flow_state.created_at.isoformat()
                if flow_state.created_at
                else None,
                "updated_at": flow_state.updated_at.isoformat()
                if flow_state.updated_at
                else None,
            }

        return None

    # ===============================
    # Core Flow Management Operations
    # ===============================

    async def start_patient_flow(
        self,
        patient_id: UUID,
        flow_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FlowExecutionResult:
        """Start a new flow for a patient."""
        return await self.lifecycle_manager.start_flow(
            patient_id=patient_id,
            flow_type=flow_type,
            metadata=metadata,
            flow_step_executor=self._execute_flow_step,
            callback_executor=self._execute_flow_callbacks,
            error_tracker=self.track_error,
            execution_tracker=self.track_execution,
            logger_instance=logger,
        )

    async def advance_patient_flow(
        self,
        patient_id: UUID,
        target_day: Optional[int] = None,
        force_advance: bool = False,
    ) -> FlowExecutionResult:
        """Advance patient flow to next step or specific day."""
        return await self.lifecycle_manager.advance_flow(
            patient_id=patient_id,
            target_day=target_day,
            force_advance=force_advance,
            flow_step_executor=self._execute_flow_step,
            callback_executor=self._execute_flow_callbacks,
            execution_tracker=self.track_execution,
            db_commit=self.db.commit,
            logger_instance=logger,
        )

    async def pause_patient_flow(
        self,
        patient_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FlowExecutionResult:
        """Pause patient flow execution."""
        return await self.lifecycle_manager.pause_flow(
            patient_id=patient_id,
            reason=reason,
            metadata=metadata,
            execution_tracker=self.track_execution,
            logger_instance=logger,
        )

    async def resume_patient_flow(
        self, patient_id: UUID, metadata: Optional[Dict[str, Any]] = None
    ) -> FlowExecutionResult:
        """Resume paused patient flow."""
        return await self.lifecycle_manager.resume_flow(
            patient_id=patient_id,
            metadata=metadata,
            execution_tracker=self.track_execution,
            logger_instance=logger,
        )

    async def stop_patient_flow(
        self,
        patient_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FlowExecutionResult:
        """Stop patient flow execution."""
        return await self.lifecycle_manager.stop_flow(
            patient_id=patient_id,
            reason=reason,
            metadata=metadata,
            execution_tracker=self.track_execution,
            logger_instance=logger,
        )

    # ===============================
    # Flow Execution Helper Methods
    # ===============================

    async def _execute_flow_step(
        self,
        context: FlowExecutionContext,
        flow_state: PatientFlowState,
        template_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single flow step."""
        try:
            # Check if this is a quiz day
            quiz_result = await self.scheduling_orchestrator.execute_quiz_step(
                context.patient_id, flow_state, context.flow_type, context.current_day
            )

            if quiz_result.get("quiz_triggered"):
                return quiz_result

            # Get message template for current day
            message_template = (
                await self.template_renderer.get_message_template_for_day(
                    context.flow_type, context.current_day
                )
            )

            if not message_template:
                self.log_warning(
                    f"No message template for {context.flow_type} day {context.current_day}",
                    extra={"flow_type": context.flow_type, "day": context.current_day},
                )
                return {
                    "success": True,
                    "message": "No message template for this day",
                    "skipped": True,
                }

            # Send flow message
            patient = self.patient_repo.get(context.patient_id)
            return await self.messaging_orchestrator.send_flow_message(
                patient=patient,
                flow_state_id=flow_state.id,
                flow_type=context.flow_type,
                current_day=context.current_day,
                operation=context.operation.value,
                message_template=message_template,
                logger_instance=logger,
            )

        except Exception as e:
            self.log_error(
                "Error executing flow step",
                e,
                extra={
                    "patient_id": str(context.patient_id),
                    "flow_type": context.flow_type,
                    "day": context.current_day,
                },
            )
            return {
                "success": False,
                "message": f"Flow step execution failed: {str(e)}",
                "error": str(e),
            }

    # ===============================
    # Treatment Day Calculation
    # ===============================

    def calculate_treatment_day(
        self, patient: Patient, reference_date: Optional[datetime] = None
    ) -> int:
        """Calculate current treatment day for patient."""
        return calculate_treatment_day(patient, reference_date, logger)

    # ===============================
    # Callback Management
    # ===============================

    def register_flow_callback(self, event_type: str, callback: Callable):
        """Register callback for flow events."""
        if event_type in self._flow_callbacks:
            self._flow_callbacks[event_type].append(callback)
            self.log_info(f"Registered callback for {event_type}")
        else:
            self.log_warning(f"Unknown event type: {event_type}")

    async def _execute_flow_callbacks(
        self, event_type: str, context: FlowExecutionContext, **kwargs
    ):
        """Execute registered callbacks for event type."""
        callbacks = self._flow_callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(context, **kwargs)
                else:
                    callback(context, **kwargs)
            except Exception as e:
                self.log_error(f"Error executing {event_type} callback", e)

    # ===============================
    # Batch Operations and Processing
    # ===============================

    async def process_daily_flows(
        self, limit: int = 1000, flow_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Process daily flows for all active patients."""
        try:
            start_time = datetime.now(timezone.utc)

            # Get active flows
            active_flows = self.flow_state_repo.get_active_flows(limit=limit)

            # Filter by flow types if specified
            if flow_types:
                active_flows = [f for f in active_flows if f.flow_type in flow_types]

            results = {
                "processed_patients": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "skipped_operations": 0,
                "quiz_triggers": 0,
                "messages_scheduled": 0,
                "processing_time": 0,
                "details": [],
            }

            # Process each flow
            for flow_state in active_flows:
                try:
                    patient = self.patient_repo.get(flow_state.patient_id)
                    if not patient:
                        continue

                    current_day = self.calculate_treatment_day(patient)

                    # Check if flow needs advancement
                    if current_day > flow_state.current_step:
                        advancement_result = await self.advance_patient_flow(
                            flow_state.patient_id, target_day=current_day
                        )

                        results["details"].append(
                            {
                                "patient_id": str(flow_state.patient_id),
                                "operation": "advance",
                                "result": advancement_result.__dict__,
                            }
                        )

                        if advancement_result.success:
                            results["successful_operations"] += 1
                            if advancement_result.data.get("quiz_triggered"):
                                results["quiz_triggers"] += 1
                            if advancement_result.data.get("message_scheduled"):
                                results["messages_scheduled"] += 1
                        else:
                            results["failed_operations"] += 1
                    else:
                        results["skipped_operations"] += 1
                        results["details"].append(
                            {
                                "patient_id": str(flow_state.patient_id),
                                "operation": "skip",
                                "reason": "Already at current day",
                            }
                        )

                    results["processed_patients"] += 1

                except Exception as e:
                    self.log_error(
                        f"Error processing patient {flow_state.patient_id}", e
                    )
                    results["failed_operations"] += 1
                    results["details"].append(
                        {
                            "patient_id": str(flow_state.patient_id),
                            "operation": "error",
                            "error": str(e),
                        }
                    )

            results["processing_time"] = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds()

            self.log_info(
                f"Daily flow processing completed: {results['processed_patients']} patients, "
                f"{results['successful_operations']} successful, "
                f"{results['failed_operations']} failed, "
                f"{results['quiz_triggers']} quiz triggers, "
                f"{results['messages_scheduled']} messages scheduled "
                f"in {results['processing_time']:.2f}s"
            )

            return results

        except Exception as e:
            self.log_error("Error in daily flow processing", e)
            return {
                "processed_patients": 0,
                "successful_operations": 0,
                "failed_operations": 1,
                "error": str(e),
                "processing_time": 0,
            }

    # ===============================
    # Health Check (Overrides BaseOrchestrator)
    # ===============================

    async def health_check(self) -> Dict[str, Any]:
        """
        Comprehensive health check for FlowOrchestrator.

        Extends BaseOrchestrator.health_check() with flow-specific checks.
        """
        # Get base health check
        health_results = await super().health_check()

        try:
            # Add circuit breaker status
            health_results["circuit_breakers"] = {
                "whatsapp": self.get_circuit_breaker_status("whatsapp_service"),
                "ai": self.get_circuit_breaker_status("ai_service"),
            }

            # Add cache statistics
            health_results["cache_stats"] = {
                "state_manager": self.state_manager.get_cache_stats(),
                "state_aware_orchestrator": self.get_cache_stats(),
            }

            # Calculate overall health
            healthy_components = sum(
                1
                for comp in health_results["components"].values()
                if comp.get("healthy", False)
            )
            total_components = len(health_results["components"])

            health_percentage = self.metrics_calculator.calculate_health_percentage(
                healthy_components, total_components
            )
            health_results["health_percentage"] = health_percentage

            if health_percentage < 80:
                health_results["overall_healthy"] = False

            self.log_info(
                f"FlowOrchestrator health check: {health_percentage:.1f}% healthy"
            )

            return health_results

        except Exception as e:
            self.log_error("Health check failed", e)
            return {
                "service": "FlowOrchestrator",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_healthy": False,
                "error": str(e),
                "critical_failure": True,
            }

    # ===============================
    # Backward Compatibility
    # ===============================

    async def process_patient_daily_flow(self, patient_id: UUID) -> Dict[str, Any]:
        """Process daily flow for a single patient (backward compatibility)."""
        try:
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {
                    "patient_id": str(patient_id),
                    "status": "error",
                    "error": "Patient not found",
                }

            current_day = self.calculate_treatment_day(patient)

            # Check if advancement is needed
            flow_state = self.state_manager.get_cached_flow_state(patient_id)
            if flow_state and current_day > flow_state.current_step:
                result = await self.advance_patient_flow(
                    patient_id, target_day=current_day
                )

                return {
                    "patient_id": str(patient_id),
                    "status": "success" if result.success else "error",
                    "current_day": current_day,
                    "flow_type": flow_state.flow_type,
                    "messages_scheduled": 1
                    if result.data.get("message_scheduled")
                    else 0,
                    "advancement_result": result.__dict__,
                }
            else:
                return {
                    "patient_id": str(patient_id),
                    "status": "skipped",
                    "reason": "No advancement needed",
                    "current_day": current_day,
                }

        except Exception as e:
            self.log_error("Error in backward compatibility method", e)
            return {"patient_id": str(patient_id), "status": "error", "error": str(e)}

    async def schedule_monthly_assessment(
        self, patient_id: UUID, assessment_date: Optional[datetime] = None
    ) -> FlowExecutionResult:
        """Schedule monthly assessment for patient."""
        patient = self.patient_repo.get(patient_id)
        if not patient:
            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message="Patient not found",
                errors=["Patient not found"],
            )

        return await self.scheduling_orchestrator.schedule_monthly_assessment(
            patient=patient,
            assessment_date=assessment_date,
            flow_state_creator=lambda **kwargs: self.state_manager.create_flow_state(
                patient=kwargs["patient"],
                flow_type=kwargs["flow_type"],
                current_day=kwargs["current_day"],
                operation=kwargs["operation"],
                metadata=kwargs.get("metadata"),
            ),
            analytics_callback=self.analytics_collector.track_flow_event,
            logger_instance=logger,
        )


# ===============================
# Factory Functions
# ===============================


def create_flow_orchestrator(
    db: Session,
    ai_service: Optional[AIService] = None,
    quiz_service: Optional[QuizTemplateService] = None,
    whatsapp_service: Optional[UnifiedWhatsAppService] = None,
    template_loader: Optional[EnhancedTemplateLoader] = None,
    analytics_service: Optional[FlowAnalyticsService] = None,
    message_scheduler: Optional[MessageScheduler] = None,
) -> FlowOrchestrator:
    """Factory function to create FlowOrchestrator with dependency injection."""
    return FlowOrchestrator(
        db=db,
        ai_service=ai_service,
        quiz_service=quiz_service,
        whatsapp_service=whatsapp_service,
        template_loader=template_loader,
        analytics_service=analytics_service,
        message_scheduler=message_scheduler,
    )


# Global instance cache for dependency injection
_orchestrator_cache: Dict[str, FlowOrchestrator] = {}


def get_flow_orchestrator(db: Session, cache_key: str = "default") -> FlowOrchestrator:
    """Get cached FlowOrchestrator instance or create new one."""
    if cache_key not in _orchestrator_cache:
        _orchestrator_cache[cache_key] = create_flow_orchestrator(db)

    return _orchestrator_cache[cache_key]
