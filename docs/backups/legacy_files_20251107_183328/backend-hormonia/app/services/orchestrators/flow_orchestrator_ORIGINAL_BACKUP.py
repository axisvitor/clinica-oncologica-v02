"""
FlowOrchestrator Service - Centralized Flow Management for Clínica Oncológica

This service centralizes all flow management logic previously scattered across multiple services,
providing a unified interface for flow execution, state management, and service integration.

Key Features:
- Centralizes flow management logic from multiple services
- Integrates with WhatsApp, Quiz, and AI services through dependency injection
- Handles flow step execution, conditional logic, and state transitions
- Implements circuit breaker pattern for external service calls
- Uses flow_templates.yaml configuration for template loading
- Calculates treatment days in a single utility function
- Manages quiz scheduling and monthly assessments
- Provides clear interfaces for start/stop/advance flow operations
- Includes comprehensive error handling and recovery
- Maintains backward compatibility with existing FlowService
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Core domain models
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.models.message import Message, MessageType, MessageStatus, MessageDirection

# Repository layer
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository

# Service dependencies (will be injected)
from app.services.ai import AIService, PatientContext
from app.services.quiz import QuizTemplateService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.services.template_loader import EnhancedTemplateLoader, MessageTemplate
from app.services.flow_analytics import FlowAnalyticsService
from app.services.message_scheduler import MessageScheduler

# Utility functions
from app.utils.date_helpers import (
    _calculate_treatment_day,
    get_treatment_phase_info,
    calculate_flow_type_from_day,
    get_next_scheduled_time,
    is_business_day,
    format_treatment_day_info
)

# Circuit breaker for resilience
from app.resilience.circuit_breaker.breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerStates

# Configuration and exceptions
from app.config.flow_templates import FlowTemplateLoader
from app.exceptions import NotFoundError, ValidationError, ExternalServiceError


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
    Centralized Flow Management Orchestrator for Clínica Oncológica.

    This service provides a unified interface for all flow-related operations,
    consolidating logic from multiple services into a single, cohesive orchestrator.

    Design Principles:
    1. Single Responsibility: Centralized flow management
    2. Dependency Injection: All services injected for testability
    3. Circuit Breaker: Resilient external service calls
    4. Template-Driven: Configuration from flow_templates.yaml
    5. Backward Compatibility: Works with existing FlowService
    6. Error Recovery: Comprehensive error handling with fallbacks
    """

    def __init__(
        self,
        db: Session,
        ai_service: Optional[AIHumanizer] = None,
        quiz_service: Optional[QuizTemplateService] = None,
        whatsapp_service: Optional[UnifiedWhatsAppService] = None,
        template_loader: Optional[EnhancedTemplateLoader] = None,
        analytics_service: Optional[FlowAnalyticsService] = None,
        message_scheduler: Optional[MessageScheduler] = None,
        flow_template_loader: Optional[FlowTemplateLoader] = None
    ):
        """
        Initialize FlowOrchestrator with service dependencies.

        Args:
            db: Database session
            ai_service: AI humanization service
            quiz_service: Quiz management service
            whatsapp_service: WhatsApp messaging service
            template_loader: Template loading service
            analytics_service: Flow analytics service
            message_scheduler: Message scheduling service
            flow_template_loader: Flow template configuration loader
        """
        # Core dependencies
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)

        # Service dependencies (with defaults)
        self.ai_service = ai_service or AIHumanizer()
        self.quiz_service = quiz_service or QuizTemplateService(db)
        self.whatsapp_service = whatsapp_service or UnifiedWhatsAppService(
            db=db,
            messaging_mode=MessagingMode.HYBRID
        )
        self.template_loader = template_loader or EnhancedTemplateLoader(db=db)
        self.analytics_service = analytics_service or FlowAnalyticsService(db)
        self.message_scheduler = message_scheduler or MessageScheduler(db)
        self.flow_template_loader = flow_template_loader or FlowTemplateLoader()

        # Circuit breaker for external services (especially WhatsApp)
        self._setup_circuit_breakers()

        # Flow state cache for performance
        self._flow_state_cache: Dict[UUID, PatientFlowState] = {}
        self._cache_ttl = timedelta(minutes=10)
        self._last_cache_clear = datetime.utcnow()

        # Flow execution callbacks
        self._flow_callbacks: Dict[str, List[Callable]] = {
            'before_execution': [],
            'after_execution': [],
            'on_error': [],
            'on_state_change': []
        }

        logger.info("FlowOrchestrator initialized with all service dependencies")

    def _setup_circuit_breakers(self):
        """Setup circuit breakers for external service calls."""
        # WhatsApp service circuit breaker
        whatsapp_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3,
            timeout=30.0,
            expected_exception=(ExternalServiceError, ConnectionError, TimeoutError)
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
            expected_exception=(ExternalServiceError, TimeoutError)
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
        """
        Start a new flow for a patient.

        Args:
            patient_id: Patient UUID
            flow_type: Flow type (auto-detected if not provided)
            metadata: Additional metadata for flow initialization

        Returns:
            FlowExecutionResult with operation status
        """
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
                context.flow_type = calculate_flow_type_from_day(current_day)

            # Check if patient already has an active flow
            existing_flow = self.flow_state_repo.get_active_flow(patient_id)
            if existing_flow and existing_flow.state_data.get('status') != 'completed':
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.START,
                    message=f"Patient already has active flow: {existing_flow.flow_type}",
                    warnings=[f"Active flow exists: {existing_flow.flow_type}"]
                )

            # Create new flow state
            flow_state = self._create_flow_state(patient, context)

            # Load and validate flow template
            template_config = await self._load_flow_template(context.flow_type)
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
            await self._track_flow_event(
                patient_id=patient_id,
                event_type="flow_started",
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
        """
        Advance patient flow to next step or specific day.

        Args:
            patient_id: Patient UUID
            target_day: Specific day to advance to (optional)
            force_advance: Force advancement even if conditions not met

        Returns:
            FlowExecutionResult with advancement status
        """
        try:
            # Get current flow state
            flow_state = self._get_cached_flow_state(patient_id)
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

            context = FlowExecutionContext(
                patient_id=patient_id,
                flow_type=flow_state.flow_type,
                operation=FlowOperationType.ADVANCE,
                current_day=current_day,
                target_day=target_day
            )

            await self._execute_flow_callbacks('before_execution', context)

            # Check if advancement is needed
            if current_day >= target_day and not force_advance:
                return FlowExecutionResult(
                    success=True,
                    patient_id=patient_id,
                    operation=FlowOperationType.ADVANCE,
                    message="Flow already at target day",
                    data={'current_day': current_day, 'target_day': target_day}
                )

            # Check if flow type should change
            new_flow_type = calculate_flow_type_from_day(target_day)
            if new_flow_type != flow_state.flow_type:
                # Transition to new flow type
                transition_result = await self._transition_flow_type(
                    flow_state, new_flow_type, context
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
            self._invalidate_flow_cache(patient_id)

            # Load template for new day
            template_config = await self._load_flow_template(flow_state.flow_type)
            if template_config:
                # Execute flow step for new day
                execution_result = await self._execute_flow_step(context, flow_state, template_config)
            else:
                execution_result = {'success': True, 'message': 'Advanced without template execution'}

            # Track analytics
            await self._track_flow_event(
                patient_id=patient_id,
                event_type="flow_advanced",
                flow_type=flow_state.flow_type,
                current_day=target_day,
                metadata={'from_day': current_day, 'to_day': target_day}
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
        """
        Pause patient flow execution.

        Args:
            patient_id: Patient UUID
            reason: Reason for pausing
            metadata: Additional pause metadata

        Returns:
            FlowExecutionResult with pause status
        """
        try:
            flow_state = self._get_cached_flow_state(patient_id)
            if not flow_state:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.PAUSE,
                    message="No active flow found",
                    errors=["No active flow state"]
                )

            # Update flow state to paused
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data.update({
                'status': 'paused',
                'paused_at': datetime.utcnow().isoformat(),
                'pause_reason': reason,
                'pause_metadata': metadata or {}
            })

            self.db.commit()
            self._invalidate_flow_cache(patient_id)

            # Track analytics
            await self._track_flow_event(
                patient_id=patient_id,
                event_type="flow_paused",
                flow_type=flow_state.flow_type,
                current_day=flow_state.current_step,
                metadata={'reason': reason, 'metadata': metadata}
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
        """
        Resume paused patient flow.

        Args:
            patient_id: Patient UUID
            metadata: Additional resume metadata

        Returns:
            FlowExecutionResult with resume status
        """
        try:
            flow_state = self._get_cached_flow_state(patient_id)
            if not flow_state:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.RESUME,
                    message="No flow found",
                    errors=["No flow state found"]
                )

            if flow_state.state_data.get('status') != 'paused':
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.RESUME,
                    message="Flow is not paused",
                    warnings=["Flow is not in paused state"]
                )

            # Update flow state to active
            flow_state.state_data.update({
                'status': 'active',
                'resumed_at': datetime.utcnow().isoformat(),
                'resume_metadata': metadata or {}
            })

            self.db.commit()
            self._invalidate_flow_cache(patient_id)

            # Track analytics
            await self._track_flow_event(
                patient_id=patient_id,
                event_type="flow_resumed",
                flow_type=flow_state.flow_type,
                current_day=flow_state.current_step,
                metadata=metadata
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
        """
        Stop patient flow execution.

        Args:
            patient_id: Patient UUID
            reason: Reason for stopping
            metadata: Additional stop metadata

        Returns:
            FlowExecutionResult with stop status
        """
        try:
            flow_state = self._get_cached_flow_state(patient_id)
            if not flow_state:
                return FlowExecutionResult(
                    success=False,
                    patient_id=patient_id,
                    operation=FlowOperationType.STOP,
                    message="No active flow found",
                    errors=["No active flow state"]
                )

            # Update flow state to completed
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data.update({
                'status': 'completed',
                'completed_at': datetime.utcnow().isoformat(),
                'completion_reason': reason,
                'completion_metadata': metadata or {}
            })

            self.db.commit()
            self._invalidate_flow_cache(patient_id)

            # Track analytics
            await self._track_flow_event(
                patient_id=patient_id,
                event_type="flow_stopped",
                flow_type=flow_state.flow_type,
                current_day=flow_state.current_step,
                metadata={'reason': reason, 'metadata': metadata}
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
    # Flow Execution and Step Management
    # ===============================

    async def _execute_flow_step(
        self,
        context: FlowExecutionContext,
        flow_state: PatientFlowState,
        template_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single flow step with comprehensive error handling.

        Args:
            context: Flow execution context
            flow_state: Current flow state
            template_config: Template configuration for the flow

        Returns:
            Execution result dictionary
        """
        try:
            # Check if this is a quiz day
            if await self._should_trigger_quiz(context, flow_state):
                return await self._execute_quiz_step(context, flow_state)

            # Get message template for current day
            message_template = await self._get_message_template_for_day(
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
            personalized_message = await self._generate_personalized_message(
                patient, message_template, context
            )

            # Schedule message delivery
            message_result = await self._schedule_flow_message(
                context, flow_state, message_template, personalized_message
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

    async def _execute_quiz_step(
        self,
        context: FlowExecutionContext,
        flow_state: PatientFlowState
    ) -> Dict[str, Any]:
        """
        Execute quiz-specific flow step.

        Args:
            context: Flow execution context
            flow_state: Current flow state

        Returns:
            Quiz execution result
        """
        try:
            # Import quiz-specific services
            from app.services.quiz_flow_integration import QuizTriggerService

            quiz_trigger_service = QuizTriggerService(self.db)

            # Calculate monthly cycle for quiz
            patient = self.patient_repo.get(context.patient_id)
            enrollment_date = patient.enrollment_date or patient.created_at
            days_since_enrollment = (datetime.utcnow() - enrollment_date).days

            # Determine quiz type based on flow phase
            if days_since_enrollment <= 45:
                quiz_type = "initial_assessment"
                monthly_cycle = 1
            else:
                days_in_monthly_phase = days_since_enrollment - 45
                monthly_cycle = (days_in_monthly_phase // 30) + 1
                quiz_type = "monthly_assessment"

            quiz_info = {
                'monthly_cycle': monthly_cycle,
                'template_name': f'{quiz_type}_cycle_{monthly_cycle}',
                'trigger_reason': f'Scheduled quiz for day {context.current_day}',
                'quiz_type': quiz_type
            }

            # Trigger quiz
            result = await quiz_trigger_service._trigger_patient_quiz(
                flow_state=flow_state,
                quiz_info=quiz_info
            )

            return {
                'success': result.get('success', False),
                'message': 'Quiz step executed',
                'quiz_triggered': True,
                'quiz_session_id': result.get('session_id'),
                'delivery_method': result.get('delivery_method'),
                'quiz_type': quiz_type,
                'monthly_cycle': monthly_cycle
            }

        except Exception as e:
            logger.error(f"Error executing quiz step: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Quiz step execution failed: {str(e)}',
                'error': str(e)
            }

    # ===============================
    # Template and Configuration Management
    # ===============================

    async def _load_flow_template(self, flow_type: str) -> Optional[Dict[str, Any]]:
        """
        Load flow template configuration from flow_templates.yaml.

        Args:
            flow_type: Flow type identifier

        Returns:
            Template configuration dictionary or None
        """
        try:
            return self.flow_template_loader.get_flow_config(flow_type)
        except Exception as e:
            logger.error(f"Error loading flow template {flow_type}: {e}")
            return None

    async def _get_message_template_for_day(
        self,
        flow_type: str,
        day: int
    ) -> Optional[MessageTemplate]:
        """
        Get message template for specific flow type and day.

        Args:
            flow_type: Flow type identifier
            day: Day number in flow

        Returns:
            MessageTemplate or None if not found
        """
        try:
            # Load flow template using enhanced template loader
            from app.services.enhanced_flow_engine import FlowType

            flow_type_enum = FlowType(flow_type)
            flow_template = self.template_loader.load_flow_template(flow_type_enum.value)

            if day in flow_template.messages:
                return flow_template.messages[day]

            logger.warning(f"No message template for {flow_type} day {day}")
            return None

        except Exception as e:
            logger.error(f"Error getting message template: {e}")
            return None

    # ===============================
    # AI and Message Personalization
    # ===============================

    async def _generate_personalized_message(
        self,
        patient: Patient,
        message_template: MessageTemplate,
        context: FlowExecutionContext
    ) -> str:
        """
        Generate personalized message using AI service with circuit breaker.

        Args:
            patient: Patient object
            message_template: Message template
            context: Flow execution context

        Returns:
            Personalized message content
        """
        try:
            # Create patient context for AI
            patient_context = PatientContext(
                patient_id=str(patient.id),
                name=patient.name,
                treatment_type=patient.treatment_type or "general",
                treatment_day=context.current_day,
                age=patient.age,
                recent_responses=[],  # Could be populated from message history
                medical_history={},
                preferences={}
            )

            # Use circuit breaker for AI service call
            async def ai_call():
                response = await self.ai_service.humanize_message(
                    template_message=message_template.base_content,
                    patient_context=patient_context,
                    message_type=message_template.intent
                )
                return response.personalized_message

            personalized_content = await self.ai_circuit_breaker.call(ai_call)

            logger.info(f"Generated personalized message for patient {patient.id}")
            return personalized_content

        except Exception as e:
            logger.warning(f"AI personalization failed, using template: {e}")
            # Fallback to template content with basic personalization
            return message_template.base_content.replace("{patient_name}", patient.name or "")

    # ===============================
    # Message Scheduling and Delivery
    # ===============================

    async def _schedule_flow_message(
        self,
        context: FlowExecutionContext,
        flow_state: PatientFlowState,
        message_template: MessageTemplate,
        personalized_content: str
    ) -> Dict[str, Any]:
        """
        Schedule message delivery with WhatsApp service using circuit breaker.

        Args:
            context: Flow execution context
            flow_state: Current flow state
            message_template: Message template used
            personalized_content: Personalized message content

        Returns:
            Scheduling result dictionary
        """
        try:
            # Create message record
            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=personalized_content,
                status=MessageStatus.PENDING,
                message_metadata={
                    'flow_context': {
                        'flow_state_id': str(flow_state.id),
                        'flow_type': context.flow_type,
                        'current_day': context.current_day,
                        'template_intent': message_template.intent,
                        'operation': context.operation.value
                    },
                    'template_data': {
                        'intent': message_template.intent,
                        'day': message_template.day,
                        'ai_generated': True
                    }
                }
            )

            self.db.add(message)
            self.db.flush()  # Get ID without committing

            # Calculate send time
            patient = self.patient_repo.get(context.patient_id)
            send_time = self._calculate_optimal_send_time(patient, context.current_day)

            # Schedule message with circuit breaker protection
            async def schedule_call():
                return await self.message_scheduler.schedule_message(
                    message_id=message.id,
                    send_time=send_time,
                    priority='normal'
                )

            scheduled = await self.whatsapp_circuit_breaker.call(schedule_call)

            if scheduled:
                self.db.commit()
                self.db.refresh(message)

                logger.info(f"Message scheduled for patient {context.patient_id} at {send_time}")

                return {
                    'success': True,
                    'message_id': message.id,
                    'scheduled_for': send_time.isoformat(),
                    'send_time': send_time
                }
            else:
                self.db.rollback()
                return {
                    'success': False,
                    'error': 'Message scheduling failed'
                }

        except Exception as e:
            logger.error(f"Error scheduling flow message: {e}", exc_info=True)
            self.db.rollback()
            return {
                'success': False,
                'error': str(e)
            }

    def _calculate_optimal_send_time(
        self,
        patient: Patient,
        current_day: int
    ) -> datetime:
        """
        Calculate optimal send time for patient message.

        Args:
            patient: Patient object
            current_day: Current treatment day

        Returns:
            Optimal send time as datetime
        """
        try:
            # Get patient preferences
            preferred_hour = getattr(patient, 'preferred_message_hour', 10)
            timezone = getattr(patient, 'timezone', 'America/Sao_Paulo')

            # Calculate send time for today or next business day
            now = datetime.utcnow()
            send_time = now.replace(hour=preferred_hour, minute=0, second=0, microsecond=0)

            # If time has passed, schedule for next business day
            if send_time <= now:
                send_time = get_next_scheduled_time("daily", send_time, timezone)

            # Add randomization to avoid system overload
            import random
            random_minutes = random.randint(-15, 15)
            send_time += timedelta(minutes=random_minutes)

            return send_time

        except Exception as e:
            logger.warning(f"Error calculating send time: {e}, using default")
            return datetime.utcnow() + timedelta(hours=1)

    # ===============================
    # Treatment Day Calculation
    # ===============================

    def calculate_treatment_day(
        self,
        patient: Patient,
        reference_date: Optional[datetime] = None
    ) -> int:
        """
        Calculate current treatment day for patient.

        This centralizes treatment day calculation logic that was previously
        duplicated across multiple services.

        Args:
            patient: Patient object
            reference_date: Reference date for calculation (defaults to now)

        Returns:
            Current treatment day (1-based)
        """
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

    def get_treatment_phase_info(
        self,
        patient: Patient,
        reference_date: Optional[datetime] = None
    ) -> Tuple[int, str]:
        """
        Get comprehensive treatment phase information.

        Args:
            patient: Patient object
            reference_date: Reference date for calculation

        Returns:
            Tuple of (treatment_day, flow_type)
        """
        treatment_day = self.calculate_treatment_day(patient, reference_date)
        flow_type = calculate_flow_type_from_day(treatment_day)
        return treatment_day, flow_type

    # ===============================
    # Quiz Scheduling and Management
    # ===============================

    async def _should_trigger_quiz(
        self,
        context: FlowExecutionContext,
        flow_state: PatientFlowState
    ) -> bool:
        """
        Determine if quiz should be triggered for current flow step.

        Args:
            context: Flow execution context
            flow_state: Current flow state

        Returns:
            True if quiz should be triggered
        """
        try:
            # Import quiz constants
            from app.utils.constants import QUIZ_FLOW_CONSTANTS

            # Check if this is a monthly flow on quiz day
            if (context.flow_type == 'monthly' and
                context.current_day % QUIZ_FLOW_CONSTANTS.get('MONTHLY_QUIZ_DAY', 30) == 0):
                return True

            # Check for initial assessment quiz (day 15)
            if context.flow_type == 'day_1_15' and context.current_day == 15:
                return True

            # Check for mid-treatment assessment (day 45)
            if context.flow_type == 'day_16_45' and context.current_day == 45:
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking quiz trigger: {e}")
            return False

    async def schedule_monthly_assessment(
        self,
        patient_id: UUID,
        assessment_date: Optional[datetime] = None
    ) -> FlowExecutionResult:
        """
        Schedule monthly assessment for patient.

        Args:
            patient_id: Patient UUID
            assessment_date: Specific assessment date (optional)

        Returns:
            FlowExecutionResult with scheduling status
        """
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

            # Create quiz-specific flow context
            context = FlowExecutionContext(
                patient_id=patient_id,
                flow_type="quiz_monthly",
                operation=FlowOperationType.START,
                current_day=1,  # Quiz flows start at day 1
                metadata={
                    'assessment_type': 'monthly',
                    'scheduled_for': assessment_date.isoformat(),
                    'auto_scheduled': True
                }
            )

            # Get or create flow state for quiz
            quiz_flow_state = self._get_cached_flow_state(patient_id)
            if not quiz_flow_state or quiz_flow_state.flow_type != "quiz_monthly":
                quiz_flow_state = self._create_flow_state(patient, context)

            # Execute quiz step
            quiz_result = await self._execute_quiz_step(context, quiz_flow_state)

            # Track analytics
            await self._track_flow_event(
                patient_id=patient_id,
                event_type="monthly_assessment_scheduled",
                flow_type="quiz_monthly",
                current_day=1,
                metadata={
                    'assessment_date': assessment_date.isoformat(),
                    'quiz_result': quiz_result
                }
            )

            return FlowExecutionResult(
                success=quiz_result.get('success', False),
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message="Monthly assessment scheduled",
                data={
                    'assessment_date': assessment_date.isoformat(),
                    'quiz_session_id': quiz_result.get('quiz_session_id'),
                    'delivery_method': quiz_result.get('delivery_method')
                }
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
    # State Management and Caching
    # ===============================

    def _get_cached_flow_state(self, patient_id: UUID) -> Optional[PatientFlowState]:
        """Get flow state from cache or database."""
        # Clean expired cache entries
        if datetime.utcnow() - self._last_cache_clear > self._cache_ttl:
            self._flow_state_cache.clear()
            self._last_cache_clear = datetime.utcnow()

        # Check cache first
        if patient_id in self._flow_state_cache:
            return self._flow_state_cache[patient_id]

        # Load from database
        flow_state = self.flow_state_repo.get_active_flow(patient_id)
        if flow_state:
            self._flow_state_cache[patient_id] = flow_state

        return flow_state

    def _invalidate_flow_cache(self, patient_id: UUID):
        """Invalidate cached flow state for patient."""
        self._flow_state_cache.pop(patient_id, None)

    def _create_flow_state(
        self,
        patient: Patient,
        context: FlowExecutionContext
    ) -> PatientFlowState:
        """
        Create new flow state for patient.

        Args:
            patient: Patient object
            context: Flow execution context

        Returns:
            Created PatientFlowState
        """
        flow_state = PatientFlowState(
            patient_id=patient.id,
            flow_type=context.flow_type,
            current_step=context.current_day,
            started_at=datetime.utcnow(),
            state_data={
                'status': 'active',
                'created_by': 'flow_orchestrator',
                'operation': context.operation.value,
                'metadata': context.metadata,
                'created_at': datetime.utcnow().isoformat()
            }
        )

        self.db.add(flow_state)
        self.db.commit()
        self.db.refresh(flow_state)

        # Cache the new flow state
        self._flow_state_cache[patient.id] = flow_state

        logger.info(f"Created flow state {flow_state.id} for patient {patient.id}")
        return flow_state

    async def _transition_flow_type(
        self,
        flow_state: PatientFlowState,
        new_flow_type: str,
        context: FlowExecutionContext
    ) -> Dict[str, Any]:
        """
        Transition flow to new type.

        Args:
            flow_state: Current flow state
            new_flow_type: New flow type to transition to
            context: Flow execution context

        Returns:
            Transition result dictionary
        """
        try:
            old_flow_type = flow_state.flow_type

            # Update flow state
            flow_state.flow_type = new_flow_type
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data.update({
                'transitioned_from': old_flow_type,
                'transitioned_to': new_flow_type,
                'transition_date': datetime.utcnow().isoformat(),
                'status': 'active'
            })

            self.db.commit()
            self._invalidate_flow_cache(context.patient_id)

            # Track transition
            await self._track_flow_event(
                patient_id=context.patient_id,
                event_type="flow_type_transition",
                flow_type=new_flow_type,
                current_day=context.current_day,
                metadata={
                    'from_flow_type': old_flow_type,
                    'to_flow_type': new_flow_type
                }
            )

            logger.info(f"Flow transitioned from {old_flow_type} to {new_flow_type} for patient {context.patient_id}")

            return {
                'success': True,
                'from_flow_type': old_flow_type,
                'to_flow_type': new_flow_type
            }

        except Exception as e:
            logger.error(f"Error transitioning flow type: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    # ===============================
    # Analytics and Event Tracking
    # ===============================

    async def _track_flow_event(
        self,
        patient_id: UUID,
        event_type: str,
        flow_type: str,
        current_day: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track flow event in analytics service.

        Args:
            patient_id: Patient UUID
            event_type: Type of event
            flow_type: Flow type identifier
            current_day: Current day in flow
            metadata: Additional event metadata
        """
        try:
            await self.analytics_service.track_flow_event(
                patient_id=patient_id,
                event_type=event_type,
                flow_type=flow_type,
                flow_day=current_day,
                additional_data=metadata or {}
            )
        except Exception as e:
            logger.warning(f"Analytics tracking failed (non-critical): {e}")

    # ===============================
    # Callback and Event Management
    # ===============================

    def register_flow_callback(
        self,
        event_type: str,
        callback: Callable
    ):
        """
        Register callback for flow events.

        Args:
            event_type: Event type (before_execution, after_execution, on_error, on_state_change)
            callback: Callback function
        """
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
        """
        Process daily flows for all active patients.

        Args:
            limit: Maximum number of patients to process
            flow_types: Specific flow types to process (optional)

        Returns:
            Processing results summary
        """
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

                    # Create execution context
                    context = FlowExecutionContext(
                        patient_id=flow_state.patient_id,
                        flow_type=flow_state.flow_type,
                        operation=FlowOperationType.ADVANCE,
                        current_day=current_day
                    )

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
        """
        Comprehensive health check for FlowOrchestrator.

        Returns:
            Health status with component details
        """
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

            # Check service dependencies
            services = {
                'ai_service': self.ai_service,
                'quiz_service': self.quiz_service,
                'whatsapp_service': self.whatsapp_service,
                'template_loader': self.template_loader,
                'analytics_service': self.analytics_service,
                'message_scheduler': self.message_scheduler
            }

            for service_name, service in services.items():
                try:
                    if hasattr(service, 'health_check'):
                        service_health = await service.health_check()
                        health_results['components'][service_name] = service_health
                        if not service_health.get('healthy', True):
                            health_results['error_count'] += 1
                    else:
                        health_results['components'][service_name] = {'healthy': True, 'method': 'not_available'}
                except Exception as e:
                    health_results['components'][service_name] = {'healthy': False, 'error': str(e)}
                    health_results['error_count'] += 1

            # Check circuit breakers
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
            health_results['cache_stats'] = {
                'flow_state_cache_size': len(self._flow_state_cache),
                'cache_ttl_minutes': self._cache_ttl.total_seconds() / 60,
                'last_cache_clear': self._last_cache_clear.isoformat()
            }

            # Overall health determination
            total_components = len(health_results['components'])
            healthy_components = sum(
                1 for comp in health_results['components'].values()
                if comp.get('healthy', False)
            )

            health_percentage = (healthy_components / total_components * 100) if total_components > 0 else 0
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
        """
        Process daily flow for a single patient (backward compatibility).

        This method maintains compatibility with existing FlowService interfaces.

        Args:
            patient_id: Patient UUID

        Returns:
            Processing result dictionary
        """
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
            flow_state = self._get_cached_flow_state(patient_id)
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


# ===============================
# Factory Function and Global Instance
# ===============================

def create_flow_orchestrator(
    db: Session,
    ai_service: Optional[AIHumanizer] = None,
    quiz_service: Optional[QuizTemplateService] = None,
    whatsapp_service: Optional[UnifiedWhatsAppService] = None,
    template_loader: Optional[EnhancedTemplateLoader] = None,
    analytics_service: Optional[FlowAnalyticsService] = None,
    message_scheduler: Optional[MessageScheduler] = None
) -> FlowOrchestrator:
    """
    Factory function to create FlowOrchestrator with dependency injection.

    Args:
        db: Database session
        ai_service: AI service instance (optional)
        quiz_service: Quiz service instance (optional)
        whatsapp_service: WhatsApp service instance (optional)
        template_loader: Template loader instance (optional)
        analytics_service: Analytics service instance (optional)
        message_scheduler: Message scheduler instance (optional)

    Returns:
        Configured FlowOrchestrator instance
    """
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
    """
    Get cached FlowOrchestrator instance or create new one.

    Args:
        db: Database session
        cache_key: Cache key for instance management

    Returns:
        FlowOrchestrator instance
    """
    if cache_key not in _orchestrator_cache:
        _orchestrator_cache[cache_key] = create_flow_orchestrator(db)

    return _orchestrator_cache[cache_key]
