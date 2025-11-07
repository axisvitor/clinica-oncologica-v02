"""
Flow Orchestrator - Thin Coordinator for Domain Modules

Coordinates all flow domain modules to provide unified flow management.
This is a thin orchestrator that delegates to specialized domain modules.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

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
from app.services.flow_analytics import FlowAnalyticsService
from app.services.message_scheduler import MessageScheduler
from app.config.flow_templates import FlowTemplateLoader

# Circuit breaker
from app.resilience.circuit_breaker.breaker import CircuitBreaker, CircuitBreakerConfig

# Utility functions
from app.utils.date_helpers import (
    _calculate_treatment_day,
    calculate_flow_type_from_day,
    get_next_scheduled_time
)

# Domain modules
from .state import FlowStateManager, FlowStateValidator
from .messaging import MessageComposer, MessageSender
from .scheduling import QuizScheduler, FollowUpScheduler
from .templates import TemplateRenderer, TemplateContextBuilder
from .rules import FlowRulesEngine, RuleConditionEvaluator
from .ab_testing import ABTestManager, VariantSelector
from .analytics import AnalyticsCollector, FlowMetricsCalculator
from .error_handling import FlowErrorHandler, ErrorRecoveryManager


logger = logging.getLogger(__name__)


class FlowExecutionState(str, Enum):
    """Flow execution states."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FlowOperationType(str, Enum):
    """Types of flow operations."""
    START = "start"
    ADVANCE = "advance"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    RESTART = "restart"


@dataclass
class FlowExecutionContext:
    """Context for flow execution operations."""
    patient_id: UUID
    flow_type: str
    operation: FlowOperationType
    current_day: int
    target_day: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class FlowExecutionResult:
    """Result of flow execution operation."""
    success: bool
    patient_id: UUID
    operation: FlowOperationType
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class FlowOrchestrator:
    """
    Thin Flow Orchestrator - Coordinates Domain Modules.

    This orchestrator delegates to specialized domain modules rather than
    implementing all logic directly. It focuses on coordination and workflow.
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
        flow_template_loader: Optional[FlowTemplateLoader] = None
    ):
        """Initialize FlowOrchestrator with service dependencies."""
        # Core dependencies
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)

        # Service dependencies (with defaults)
        self.ai_service = ai_service or AIService()
        self.quiz_service = quiz_service or QuizTemplateService(db)
        self.whatsapp_service = whatsapp_service or UnifiedWhatsAppService(
            db=db,
            messaging_mode=MessagingMode.HYBRID
        )
        self.template_loader = template_loader or EnhancedTemplateLoader(db=db)
        self.analytics_service = analytics_service or FlowAnalyticsService(db)
        self.message_scheduler = message_scheduler or MessageScheduler(db)
        self.flow_template_loader = flow_template_loader or FlowTemplateLoader()

        # Setup circuit breakers
        self._setup_circuit_breakers()

        # Initialize domain modules
        self.state_manager = FlowStateManager(db, self.flow_state_repo)
        self.state_validator = FlowStateValidator()
        self.message_composer = MessageComposer(self.ai_service, self.ai_circuit_breaker)
        self.message_sender = MessageSender(db, self.message_scheduler, self.whatsapp_circuit_breaker)
        self.quiz_scheduler = QuizScheduler(db)
        self.follow_up_scheduler = FollowUpScheduler()
        self.template_renderer = TemplateRenderer(self.template_loader, self.flow_template_loader)
        self.context_builder = TemplateContextBuilder()
        self.rules_engine = FlowRulesEngine()
        self.rule_evaluator = RuleConditionEvaluator()
        self.ab_test_manager = ABTestManager()
        self.variant_selector = VariantSelector()
        self.analytics_collector = AnalyticsCollector(self.analytics_service)
        self.metrics_calculator = FlowMetricsCalculator()
        self.error_handler = FlowErrorHandler()
        self.recovery_manager = ErrorRecoveryManager()

        # Flow execution callbacks
        self._flow_callbacks: Dict[str, List[Callable]] = {
            'before_execution': [],
            'after_execution': [],
            'on_error': [],
            'on_state_change': []
        }

        logger.info("FlowOrchestrator initialized with all domain modules")

    def _setup_circuit_breakers(self):
        """Setup circuit breakers for external service calls."""
        # WhatsApp service circuit breaker
        whatsapp_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3,
            timeout=30.0,
            expected_exception=(Exception, ConnectionError, TimeoutError)
        )
        self.whatsapp_circuit_breaker = CircuitBreaker(
            name="whatsapp_service",
            config=whatsapp_config
        )

        # AI service circuit breaker
        ai_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=45.0,
            success_threshold=2,
            timeout=20.0,
            expected_exception=(Exception, TimeoutError)
        )
        self.ai_circuit_breaker = CircuitBreaker(
            name="ai_service",
            config=ai_config
        )

        logger.info("Circuit breakers configured for external services")

    # ===============================
    # Core Flow Management Operations
    # ===============================

    async def start_patient_flow(
        self,
        patient_id: UUID,
        flow_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FlowExecutionResult:
        """Start a new flow for a patient."""
        context = FlowExecutionContext(
            patient_id=patient_id,
            flow_type=flow_type or "auto_detect",
            operation=FlowOperationType.START,
            current_day=0,
            metadata=metadata or {}
        )

        try:
            await self._execute_flow_callbacks('before_execution', context)

            # Get patient information
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.START,
                    message="Patient not found",
                    errors=["Patient not found"]
                )

            # Calculate current treatment day
            current_day = self.calculate_treatment_day(patient)
            context.current_day = current_day

            # Auto-detect flow type if not provided
            if context.flow_type == "auto_detect":
                context.flow_type = self.rules_engine.determine_flow_type(current_day)

            # Validate flow start
            existing_flow = self.state_manager.get_cached_flow_state(patient_id)
            is_valid, error_msg = self.state_validator.validate_flow_start(
                patient, existing_flow, context.flow_type
            )

            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.START,
                    message=error_msg,
                    errors=[error_msg]
                )

            # Create new flow state
            flow_state = self.state_manager.create_flow_state(
                patient=patient,
                flow_type=context.flow_type,
                current_day=current_day,
                operation=context.operation.value,
                metadata=context.metadata
            )

            # Load and validate flow template
            template_config = await self.template_renderer.load_flow_template(context.flow_type)
            if not template_config:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.START,
                    message=f"Flow template not found for type: {context.flow_type}",
                    errors=[f"Template not found: {context.flow_type}"]
                )

            # Execute initial flow step
            execution_result = await self._execute_flow_step(context, flow_state, template_config)

            # Track analytics
            await self.analytics_collector.track_flow_start(
                patient_id=patient_id,
                flow_type=context.flow_type,
                current_day=current_day,
                metadata=context.metadata
            )

            await self._execute_flow_callbacks('after_execution', context)

            return FlowExecutionResult(
                success=execution_result.get('success', False),
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message=f"Flow started successfully: {context.flow_type}",
                data={
                    'flow_state_id': str(flow_state.id),
                    'flow_type': context.flow_type,
                    'current_day': current_day,
                    'execution_result': execution_result
                }
            )

        except Exception as e:
            logger.error(f"Error starting flow for patient {patient_id}: {e}", exc_info=True)
            await self._execute_flow_callbacks('on_error', context, error=e)

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message=f"Flow start failed: {str(e)}",
                errors=[str(e)]
            )

    async def advance_patient_flow(
        self,
        patient_id: UUID,
        target_day: Optional[int] = None,
        force_advance: bool = False
    ) -> FlowExecutionResult:
        """Advance patient flow to next step or specific day."""
        try:
            # Get current flow state
            flow_state = self.state_manager.get_cached_flow_state(patient_id)
            if not flow_state:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.ADVANCE,
                    message="No active flow found",
                    errors=["No active flow state"]
                )

            # Get patient for day calculation
            patient = self.patient_repo.get(patient_id)
            current_day = self.calculate_treatment_day(patient)

            # Determine target day
            if target_day is None:
                target_day = current_day + 1

            # Validate advancement
            is_valid, error_msg = self.state_validator.validate_flow_advancement(
                current_day, target_day, force_advance, flow_state
            )

            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.ADVANCE,
                    message=error_msg,
                    errors=[error_msg]
                )

            context = FlowExecutionContext(
                patient_id=patient_id,
                flow_type=flow_state.flow_type,
                operation=FlowOperationType.ADVANCE,
                current_day=current_day,
                target_day=target_day
            )

            await self._execute_flow_callbacks('before_execution', context)

            # Check if flow type should change
            needs_transition, new_flow_type = self.rules_engine.should_transition_flow_type(
                flow_state.flow_type, target_day
            )

            if needs_transition:
                # Transition to new flow type
                transition_result = await self.state_manager.transition_flow_type(
                    flow_state, new_flow_type, patient_id, target_day,
                    analytics_callback=self.analytics_collector.track_flow_event
                )
                if not transition_result.get('success'):
                    return FlowExecutionResult(
                        success=False,
                        patient_id=patient_id,
                        operation=FlowOperationType.ADVANCE,
                        message="Flow type transition failed",
                        errors=transition_result.get('errors', [])
                    )

            # Update flow state
            flow_state.current_step = target_day
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data.update({
                'last_advanced': datetime.utcnow().isoformat(),
                'advanced_to_day': target_day,
                'status': 'active'
            })

            self.db.commit()
            self.state_manager.invalidate_flow_cache(patient_id)

            # Load template for new day
            template_config = await self.template_renderer.load_flow_template(flow_state.flow_type)
            if template_config:
                # Execute flow step for new day
                execution_result = await self._execute_flow_step(context, flow_state, template_config)
            else:
                execution_result = {'success': True, 'message': 'Advanced without template execution'}

            # Track analytics
            await self.analytics_collector.track_flow_advance(
                patient_id=patient_id,
                flow_type=flow_state.flow_type,
                from_day=current_day,
                to_day=target_day
            )

            await self._execute_flow_callbacks('after_execution', context)

            return FlowExecutionResult(
                success=True,
                patient_id=patient_id,
                operation=FlowOperationType.ADVANCE,
                message=f"Flow advanced to day {target_day}",
                data={
                    'from_day': current_day,
                    'to_day': target_day,
                    'flow_type': flow_state.flow_type,
                    'execution_result': execution_result
                }
            )

        except Exception as e:
            logger.error(f"Error advancing flow for patient {patient_id}: {e}", exc_info=True)

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.ADVANCE,
                message=f"Flow advancement failed: {str(e)}",
                errors=[str(e)]
            )

    async def pause_patient_flow(
        self,
        patient_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FlowExecutionResult:
        """Pause patient flow execution."""
        try:
            flow_state = self.state_manager.get_cached_flow_state(patient_id)

            is_valid, error_msg = self.state_validator.validate_flow_pause(flow_state)
            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.PAUSE,
                    message=error_msg,
                    errors=[error_msg]
                )

            # Update flow state to paused
            success = self.state_manager.update_flow_state_status(
                flow_state, 'paused', reason, metadata
            )

            if success:
                # Track analytics
                await self.analytics_collector.track_flow_pause(
                    patient_id=patient_id,
                    flow_type=flow_state.flow_type,
                    current_day=flow_state.current_step,
                    reason=reason
                )

                return FlowExecutionResult(
                    success=True,
                    patient_id=patient_id,
                    operation=FlowOperationType.PAUSE,
                    message="Flow paused successfully",
                    data={
                        'flow_type': flow_state.flow_type,
                        'current_day': flow_state.current_step,
                        'reason': reason
                    }
                )
            else:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.PAUSE,
                    message="Failed to update flow state",
                    errors=["State update failed"]
                )

        except Exception as e:
            logger.error(f"Error pausing flow for patient {patient_id}: {e}", exc_info=True)

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.PAUSE,
                message=f"Flow pause failed: {str(e)}",
                errors=[str(e)]
            )

    async def resume_patient_flow(
        self,
        patient_id: UUID,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FlowExecutionResult:
        """Resume paused patient flow."""
        try:
            flow_state = self.state_manager.get_cached_flow_state(patient_id)

            is_valid, error_msg = self.state_validator.validate_flow_resume(flow_state)
            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.RESUME,
                    message=error_msg,
                    warnings=[error_msg] if flow_state else [],
                    errors=[error_msg] if not flow_state else []
                )

            # Update flow state to active
            success = self.state_manager.update_flow_state_status(
                flow_state, 'active', None, metadata
            )

            if success:
                # Track analytics
                await self.analytics_collector.track_flow_resume(
                    patient_id=patient_id,
                    flow_type=flow_state.flow_type,
                    current_day=flow_state.current_step
                )

                return FlowExecutionResult(
                    success=True,
                    patient_id=patient_id,
                    operation=FlowOperationType.RESUME,
                    message="Flow resumed successfully",
                    data={
                        'flow_type': flow_state.flow_type,
                        'current_day': flow_state.current_step
                    }
                )
            else:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.RESUME,
                    message="Failed to update flow state",
                    errors=["State update failed"]
                )

        except Exception as e:
            logger.error(f"Error resuming flow for patient {patient_id}: {e}", exc_info=True)

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.RESUME,
                message=f"Flow resume failed: {str(e)}",
                errors=[str(e)]
            )

    async def stop_patient_flow(
        self,
        patient_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FlowExecutionResult:
        """Stop patient flow execution."""
        try:
            flow_state = self.state_manager.get_cached_flow_state(patient_id)

            is_valid, error_msg = self.state_validator.validate_flow_stop(flow_state)
            if not is_valid:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.STOP,
                    message=error_msg,
                    errors=[error_msg]
                )

            # Update flow state to completed
            success = self.state_manager.update_flow_state_status(
                flow_state, 'completed', reason, metadata
            )

            if success:
                # Track analytics
                await self.analytics_collector.track_flow_stop(
                    patient_id=patient_id,
                    flow_type=flow_state.flow_type,
                    final_day=flow_state.current_step,
                    reason=reason
                )

                return FlowExecutionResult(
                    success=True,
                    patient_id=patient_id,
                    operation=FlowOperationType.STOP,
                    message="Flow stopped successfully",
                    data={
                        'flow_type': flow_state.flow_type,
                        'final_day': flow_state.current_step,
                        'reason': reason
                    }
                )
            else:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.STOP,
                    message="Failed to update flow state",
                    errors=["State update failed"]
                )

        except Exception as e:
            logger.error(f"Error stopping flow for patient {patient_id}: {e}", exc_info=True)

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.STOP,
                message=f"Flow stop failed: {str(e)}",
                errors=[str(e)]
            )

    # ===============================
    # Flow Execution Helper Methods
    # ===============================

    async def _execute_flow_step(
        self,
        context: FlowExecutionContext,
        flow_state: PatientFlowState,
        template_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single flow step."""
        try:
            # Check if this is a quiz day
            if await self.quiz_scheduler.should_trigger_quiz(
                context.flow_type, context.current_day, flow_state
            ):
                return await self.quiz_scheduler.execute_quiz_step(
                    context.patient_id, flow_state, context.flow_type, context.current_day
                )

            # Get message template for current day
            message_template = await self.template_renderer.get_message_template_for_day(
                context.flow_type, context.current_day
            )

            if not message_template:
                logger.warning(f"No message template for {context.flow_type} day {context.current_day}")
                return {
                    'success': True,
                    'message': 'No message template for this day',
                    'skipped': True
                }

            # Generate personalized message using AI
            patient = self.patient_repo.get(context.patient_id)
            personalized_message = await self.message_composer.generate_personalized_message(
                patient, message_template, context.current_day, context.flow_type
            )

            # Schedule message delivery
            message_result = await self.message_sender.schedule_flow_message(
                patient_id=context.patient_id,
                patient=patient,
                flow_state_id=flow_state.id,
                flow_type=context.flow_type,
                current_day=context.current_day,
                operation=context.operation.value,
                message_template_intent=message_template.intent,
                message_template_day=message_template.day,
                personalized_content=personalized_message
            )

            return {
                'success': message_result.get('success', False),
                'message': 'Flow step executed',
                'message_scheduled': message_result.get('message_id') is not None,
                'message_id': message_result.get('message_id'),
                'template_intent': message_template.intent,
                'personalized': True
            }

        except Exception as e:
            logger.error(f"Error executing flow step: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Flow step execution failed: {str(e)}',
                'error': str(e)
            }

    # ===============================
    # Treatment Day Calculation
    # ===============================

    def calculate_treatment_day(
        self,
        patient: Patient,
        reference_date: Optional[datetime] = None
    ) -> int:
        """Calculate current treatment day for patient."""
        try:
            treatment_start = patient.enrollment_date or patient.created_at
            return _calculate_treatment_day(
                treatment_start_date=treatment_start,
                reference_date=reference_date,
                timezone=getattr(patient, 'timezone', 'America/Sao_Paulo')
            )
        except Exception as e:
            logger.error(f"Error calculating treatment day for patient {patient.id}: {e}")
            return 1  # Safe default

    # ===============================
    # Callback Management
    # ===============================

    def register_flow_callback(self, event_type: str, callback: Callable):
        """Register callback for flow events."""
        if event_type in self._flow_callbacks:
            self._flow_callbacks[event_type].append(callback)
            logger.info(f"Registered callback for {event_type}")
        else:
            logger.warning(f"Unknown event type: {event_type}")

    async def _execute_flow_callbacks(
        self,
        event_type: str,
        context: FlowExecutionContext,
        **kwargs
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
                logger.error(f"Error executing {event_type} callback: {e}")

    # ===============================
    # Batch Operations and Processing
    # ===============================

    async def process_daily_flows(
        self,
        limit: int = 1000,
        flow_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Process daily flows for all active patients."""
        try:
            start_time = datetime.utcnow()

            # Get active flows
            active_flows = self.flow_state_repo.get_active_flows(limit=limit)

            # Filter by flow types if specified
            if flow_types:
                active_flows = [f for f in active_flows if f.flow_type in flow_types]

            results = {
                'processed_patients': 0,
                'successful_operations': 0,
                'failed_operations': 0,
                'skipped_operations': 0,
                'quiz_triggers': 0,
                'messages_scheduled': 0,
                'processing_time': 0,
                'details': []
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
                            flow_state.patient_id,
                            target_day=current_day
                        )

                        results['details'].append({
                            'patient_id': str(flow_state.patient_id),
                            'operation': 'advance',
                            'result': advancement_result.__dict__
                        })

                        if advancement_result.success:
                            results['successful_operations'] += 1
                            if advancement_result.data.get('quiz_triggered'):
                                results['quiz_triggers'] += 1
                            if advancement_result.data.get('message_scheduled'):
                                results['messages_scheduled'] += 1
                        else:
                            results['failed_operations'] += 1
                    else:
                        results['skipped_operations'] += 1
                        results['details'].append({
                            'patient_id': str(flow_state.patient_id),
                            'operation': 'skip',
                            'reason': 'Already at current day'
                        })

                    results['processed_patients'] += 1

                except Exception as e:
                    logger.error(f"Error processing patient {flow_state.patient_id}: {e}")
                    results['failed_operations'] += 1
                    results['details'].append({
                        'patient_id': str(flow_state.patient_id),
                        'operation': 'error',
                        'error': str(e)
                    })

            results['processing_time'] = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"Daily flow processing completed: {results['processed_patients']} patients, "
                f"{results['successful_operations']} successful, "
                f"{results['failed_operations']} failed, "
                f"{results['quiz_triggers']} quiz triggers, "
                f"{results['messages_scheduled']} messages scheduled "
                f"in {results['processing_time']:.2f}s"
            )

            return results

        except Exception as e:
            logger.error(f"Error in daily flow processing: {e}", exc_info=True)
            return {
                'processed_patients': 0,
                'successful_operations': 0,
                'failed_operations': 1,
                'error': str(e),
                'processing_time': 0
            }

    # ===============================
    # Health Check and Diagnostics
    # ===============================

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for FlowOrchestrator."""
        try:
            health_results = {
                'service': 'FlowOrchestrator',
                'timestamp': datetime.utcnow().isoformat(),
                'overall_healthy': True,
                'components': {},
                'circuit_breakers': {},
                'cache_stats': {},
                'error_count': 0
            }

            # Check database connectivity
            try:
                self.db.execute("SELECT 1")
                health_results['components']['database'] = {'healthy': True}
            except Exception as e:
                health_results['components']['database'] = {'healthy': False, 'error': str(e)}
                health_results['overall_healthy'] = False
                health_results['error_count'] += 1

            # Circuit breaker status
            health_results['circuit_breakers'] = {
                'whatsapp': {
                    'state': self.whatsapp_circuit_breaker.state.value,
                    'failure_count': self.whatsapp_circuit_breaker.failure_count,
                    'success_count': self.whatsapp_circuit_breaker.success_count
                },
                'ai': {
                    'state': self.ai_circuit_breaker.state.value,
                    'failure_count': self.ai_circuit_breaker.failure_count,
                    'success_count': self.ai_circuit_breaker.success_count
                }
            }

            # Cache statistics
            health_results['cache_stats'] = self.state_manager.get_cache_stats()

            # Overall health determination
            healthy_components = sum(
                1 for comp in health_results['components'].values()
                if comp.get('healthy', False)
            )
            total_components = len(health_results['components'])

            health_percentage = self.metrics_calculator.calculate_health_percentage(
                healthy_components, total_components
            )
            health_results['health_percentage'] = health_percentage

            if health_percentage < 80:
                health_results['overall_healthy'] = False

            logger.info(f"FlowOrchestrator health check: {health_percentage:.1f}% healthy")

            return health_results

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                'service': 'FlowOrchestrator',
                'timestamp': datetime.utcnow().isoformat(),
                'overall_healthy': False,
                'error': str(e),
                'critical_failure': True
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
                    'patient_id': str(patient_id),
                    'status': 'error',
                    'error': 'Patient not found'
                }

            current_day = self.calculate_treatment_day(patient)

            # Check if advancement is needed
            flow_state = self.state_manager.get_cached_flow_state(patient_id)
            if flow_state and current_day > flow_state.current_step:
                result = await self.advance_patient_flow(patient_id, target_day=current_day)

                return {
                    'patient_id': str(patient_id),
                    'status': 'success' if result.success else 'error',
                    'current_day': current_day,
                    'flow_type': flow_state.flow_type,
                    'messages_scheduled': 1 if result.data.get('message_scheduled') else 0,
                    'advancement_result': result.__dict__
                }
            else:
                return {
                    'patient_id': str(patient_id),
                    'status': 'skipped',
                    'reason': 'No advancement needed',
                    'current_day': current_day
                }

        except Exception as e:
            logger.error(f"Error in backward compatibility method: {e}")
            return {
                'patient_id': str(patient_id),
                'status': 'error',
                'error': str(e)
            }

    async def schedule_monthly_assessment(
        self,
        patient_id: UUID,
        assessment_date: Optional[datetime] = None
    ) -> FlowExecutionResult:
        """Schedule monthly assessment for patient."""
        try:
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.START,
                    message="Patient not found",
                    errors=["Patient not found"]
                )

            # Calculate assessment timing
            if assessment_date is None:
                assessment_date = get_next_scheduled_time("monthly")

            # Schedule assessment
            result = await self.quiz_scheduler.schedule_monthly_assessment(
                patient=patient,
                assessment_date=assessment_date,
                flow_state_creator=lambda **kwargs: self.state_manager.create_flow_state(
                    patient=kwargs['patient'],
                    flow_type=kwargs['flow_type'],
                    current_day=kwargs['current_day'],
                    operation=kwargs['operation'],
                    metadata=kwargs.get('metadata')
                ),
                analytics_callback=self.analytics_collector.track_flow_event
            )

            return FlowExecutionResult(
                success=result.get('success', False),
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message=result.get('message', 'Monthly assessment scheduled'),
                data=result
            )

        except Exception as e:
            logger.error(f"Error scheduling monthly assessment: {e}", exc_info=True)

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message=f"Monthly assessment scheduling failed: {str(e)}",
                errors=[str(e)]
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
    message_scheduler: Optional[MessageScheduler] = None
) -> FlowOrchestrator:
    """Factory function to create FlowOrchestrator with dependency injection."""
    return FlowOrchestrator(
        db=db,
        ai_service=ai_service,
        quiz_service=quiz_service,
        whatsapp_service=whatsapp_service,
        template_loader=template_loader,
        analytics_service=analytics_service,
        message_scheduler=message_scheduler
    )


# Global instance cache for dependency injection
_orchestrator_cache: Dict[str, FlowOrchestrator] = {}


def get_flow_orchestrator(
    db: Session,
    cache_key: str = "default"
) -> FlowOrchestrator:
    """Get cached FlowOrchestrator instance or create new one."""
    if cache_key not in _orchestrator_cache:
        _orchestrator_cache[cache_key] = create_flow_orchestrator(db)

    return _orchestrator_cache[cache_key]
