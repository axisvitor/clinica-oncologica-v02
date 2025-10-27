"""
Flow engine for processing patient daily flows.
Enhanced with AI-powered message humanization.
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import logging
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.repositories.flow_template import FlowTemplateRepository
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.repositories.quiz import QuizResponseRepository
from app.services.template_loader import FlowTemplateData, FlowStep
from app.services.flow_template import FlowTemplateService
from app.services.state_machine import StateMachine, StateTransition, TransitionResult
from app.services.message import MessageService
from app.services.quiz import QuizSessionService, QuizResponseService
from app.schemas.quiz import QuizSessionCreate, QuizResponseCreate, QuestionType
from app.models.message import MessageType
from app.exceptions import NotFoundError, ValidationError
from app.core.event_loop_manager import EventLoopManager, AsyncFlowEngineBase
from app.core.async_context_manager import safe_create_task, ensure_async_context
from app.services.ai import get_ai_humanizer, get_context_builder, PatientContext
from app.services.ai.ai_service import get_ai_service
from app.config import is_ai_humanization_enabled, should_humanize_message, get_humanization_config
from app.utils.db_retry import with_db_retry
from app.services.question_humanizer import get_question_humanizer
from app.utils.distributed_lock import async_flow_state_lock, LockAcquisitionError, LockTimeoutError

logger = logging.getLogger(__name__)


class FlowContext:
    """Context builder for flow execution."""
    
    def __init__(self, db: Session):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.quiz_repo = QuizResponseRepository(db)
    
    def build_context(
        self,
        patient: Patient,
        flow_state: PatientFlowState,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Build execution context for flow processing.
        
        Args:
            patient: Patient model
            flow_state: Current flow state
            additional_context: Additional context data
            
        Returns:
            Dict containing all context data
        """
        context = {
            "patient_id": patient.id,
            "patient_data": {
                "name": patient.name,
                "phone": patient.phone,
                "treatment_type": patient.treatment_type,
                "treatment_start_date": patient.treatment_start_date,
                "current_day": patient.current_day,
                "flow_state": patient.flow_state.value,
                "metadata": patient.patient_metadata or {}
            },
            "flow_start_time": flow_state.started_at,
            "current_time": datetime.utcnow(),
            "flow_data": flow_state.state_data or {},
            "quiz_responses": self._get_recent_quiz_responses(patient.id),
            "message_count": self._get_message_count(patient.id),
            "recent_messages": self._get_recent_messages(patient.id)
        }
        
        if additional_context:
            context.update(additional_context)
        
        return context
    
    def _get_recent_quiz_responses(self, patient_id: UUID) -> dict[str, Any]:
        """Get recent quiz responses for the patient."""
        # Get responses from last 7 days
        since_date = datetime.utcnow() - timedelta(days=7)
        responses = self.quiz_repo.get_by_patient_since(patient_id, since_date)
        
        # Convert to dict format for easy access
        quiz_data = {}
        for response in responses:
            quiz_data[response.question_id] = response.response_value
        
        return quiz_data
    
    def _get_message_count(self, patient_id: UUID) -> int:
        """Get total message count for the patient."""
        return self.message_repo.count_by_patient(patient_id)
    
    def _get_recent_messages(self, patient_id: UUID) -> List[dict[str, Any]]:
        """Get recent messages for the patient."""
        messages = self.message_repo.get_by_patient(patient_id, limit=10)
        
        return [
            {
                "id": str(msg.id),
                "direction": msg.direction.value,
                "type": msg.type.value,
                "content": msg.content,
                "status": msg.status.value,
                "created_at": msg.created_at
            }
            for msg in messages
        ]


class FlowEngine(AsyncFlowEngineBase):
    """Engine for processing patient daily flows."""

    def __init__(self, db: Session):
        # Initialize parent class for proper async handling
        super().__init__()

        self.db = db
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.template_service = FlowTemplateService(db)
        self.context_builder = FlowContext(db)
        self.message_service = MessageService(db)
        self.quiz_session_service = QuizSessionService(db)
        self.quiz_response_service = QuizResponseService(db)

        # AI Humanization services (lazy initialization)
        self.ai_service = None
        self.ai_context_builder = None
        self.humanization_config = get_humanization_config()

        # Redis client for caching (optional)
        self.redis_client = None
        try:
            from app.config import settings
            import redis.asyncio as redis
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=10
            )
            logger.info("FlowEngine initialized with Redis cache support")
        except Exception as e:
            logger.warning(f"FlowEngine initialized without Redis cache: {e}")

        logger.info("FlowEngine initialized with memory leak protection")

    async def _ensure_ai_services(self):
        """Ensure AI services are initialized (lazy loading)."""
        if self.ai_service is None:
            self.ai_service = await get_ai_service()
        if self.ai_context_builder is None:
            self.ai_context_builder = await get_ai_service()

    def _get_flow_type_from_state(self, flow_state: PatientFlowState) -> str:
        """
        Helper method to get flow_type from a PatientFlowState using template_version_id.

        Args:
            flow_state: The patient flow state

        Returns:
            The flow_type string

        Raises:
            ValidationError: If template version or flow kind not found
        """
        template_version = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == flow_state.template_version_id
        ).first()

        if not template_version:
            raise ValidationError(f"Template version not found for flow state {flow_state.id}")

        flow_kind = self.db.query(FlowKind).filter(
            FlowKind.id == template_version.kind_id
        ).first()

        if not flow_kind:
            raise ValidationError(f"Flow kind not found for template version {template_version.id}")

        return flow_kind.flow_type

    @with_db_retry(max_retries=3)
    def list_flows(self) -> List[dict[str, Any]]:
        """Return available flow templates."""
        templates = self.template_service.get_all_templates()
        return [
            {
                "flow_type": t.flow_type,
                "name": t.name,
                "version": t.version,
                "description": t.description,
            }
            for t in templates
        ]

    @with_db_retry(max_retries=3)
    def get_current_flow(self, patient_id: UUID) -> dict[str, Any]:
        """Get current flow status for a patient."""
        return self.get_flow_status(patient_id)

    @with_db_retry(max_retries=3)
    def get_flow_history(
        self, patient_id: UUID
    ) -> Tuple[List[PatientFlowState], Optional[PatientFlowState]]:
        """Return all flow states for a patient and the active one if exists."""
        flows = self.flow_state_repo.get_by_patient(patient_id)
        current = self.flow_state_repo.get_active_flow(patient_id)
        return flows, current

    async def _humanize_message_content(
        self,
        content: str,
        patient_id: UUID,
        message_type: str = "general"
    ) -> str:
        """
        Humanize message content using AI with safety controls and fallback.

        Args:
            content: Original message content
            patient_id: Patient UUID
            message_type: Type of message (welcome, check_in, reminder, etc.)

        Returns:
            Humanized message content or original content if AI fails/disabled
        """
        # Check if AI humanization is enabled
        if not is_ai_humanization_enabled():
            logger.debug("AI humanization disabled, using original content")
            return content

        # Safety check: Don't humanize critical medical content
        if not should_humanize_message(content):
            logger.info(f"Message contains critical keywords, skipping AI humanization: {content[:100]}...")
            return content

        try:
            # Get patient for context
            patient = self.patient_repo.get(patient_id)
            if not patient:
                logger.warning(f"Patient {patient_id} not found for humanization")
                return content

            # Check patient-level opt-out flags
            # Use patient_data (mapped to 'metadata' column) or patient_metadata
            metadata = patient.patient_data or patient.patient_metadata or {}
            if metadata.get('no_ai_messages', False):
                logger.info(f"Patient {patient_id} has AI restriction (no_ai_messages) - skipping humanization")
                return content
            if metadata.get('critical_condition', False):
                logger.info(f"Patient {patient_id} in critical condition - skipping AI humanization")
                return content

            # Check cache first (deterministic caching)
            import hashlib
            cache_key = None
            cached_humanized = None

            try:
                # Generate cache key based on patient, content, type, and day
                content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
                treatment_day = getattr(patient, 'current_day', 1)
                cache_key = f"ai:humanized:{patient_id}:{content_hash}:{message_type}:{treatment_day}"

                # Try to get from cache (Redis)
                if hasattr(self, 'redis_client') and self.redis_client:
                    cached_humanized = await self.redis_client.get(cache_key)
                    if cached_humanized:
                        logger.info(f"Cache HIT for humanization: {cache_key}")
                        return cached_humanized
                    else:
                        logger.debug(f"Cache MISS for humanization: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache read error for humanization: {e}")

            # Get recent messages for context
            recent_messages = self.context_builder._get_recent_messages(patient_id)

            # Build patient context for AI
            patient_context = await self.ai_context_builder.build_patient_context(
                patient_id=str(patient_id),
                patient_data={
                    "name": patient.name,
                    "treatment_type": getattr(patient, 'treatment_type', 'hormone_therapy'),
                    "current_day": getattr(patient, 'current_day', 1),
                    "treatment_start_date": patient.treatment_start_date.isoformat() if hasattr(patient, 'treatment_start_date') and patient.treatment_start_date else None
                },
                recent_messages=recent_messages
            )

            # Attempt AI humanization with retries
            max_retries = self.humanization_config["max_retries"]
            timeout = self.humanization_config["timeout"]

            for attempt in range(max_retries + 1):
                try:
                    # Call AI humanizer with timeout
                    humanization_task = self.ai_service.humanize_message(
                        template_message=content,
                        patient_context=patient_context,
                        message_type=message_type
                    )

                    # Apply timeout to the AI call
                    humanized_response = await asyncio.wait_for(
                        humanization_task,
                        timeout=timeout
                    )

                    # Extract humanized content
                    humanized_content = humanized_response.humanized_message

                    # POST-GENERATION SAFETY CHECK: Verify no critical keywords were introduced
                    if not should_humanize_message(humanized_content):
                        logger.warning(f"AI output contains critical keywords - using original content for patient {patient_id}")
                        return content

                    # Log successful humanization
                    logger.info(f"Message successfully humanized for patient {patient_id} (attempt {attempt + 1})")

                    # Store humanization metadata
                    humanization_metadata = {
                        "ai_humanized": True,
                        "original_length": len(content),
                        "humanized_length": len(humanized_content),
                        "attempt_count": attempt + 1,
                        "personalization_notes": getattr(humanized_response, 'personalization_notes', [])
                    }

                    # Cache the humanized content (24 hours TTL)
                    if cache_key and hasattr(self, 'redis_client') and self.redis_client:
                        try:
                            await self.redis_client.setex(cache_key, 86400, humanized_content)  # 24h TTL
                            logger.debug(f"Cached humanized content: {cache_key}")
                        except Exception as e:
                            logger.warning(f"Cache write error for humanization: {e}")

                    return humanized_content

                except asyncio.TimeoutError:
                    logger.warning(f"AI humanization timeout on attempt {attempt + 1} for patient {patient_id}")
                    if attempt == max_retries:
                        break
                    await asyncio.sleep(0.5 * (attempt + 1))  # Progressive delay

                except Exception as e:
                    logger.warning(f"AI humanization failed on attempt {attempt + 1} for patient {patient_id}: {e}")
                    if attempt == max_retries:
                        break
                    await asyncio.sleep(0.5 * (attempt + 1))  # Progressive delay

            # All retry attempts failed
            logger.error(f"AI humanization failed after {max_retries + 1} attempts for patient {patient_id}")

        except Exception as e:
            logger.error(f"Critical error in AI humanization for patient {patient_id}: {e}")

        # Fallback to original content
        if self.humanization_config["fallback_enabled"]:
            logger.info(f"Using fallback to original content for patient {patient_id}")
            return content
        else:
            logger.warning(f"Fallback disabled, returning empty content for patient {patient_id}")
            return "Mensagem temporariamente indisponível. Entre em contato se precisar de assistência."

    def _determine_question_type(self, step: FlowStep) -> str:
        """
        Determine the type of question for selective humanization.

        Args:
            step: Flow step containing question/message

        Returns:
            Question type identifier for humanization control
        """
        # Check step metadata for question type
        if hasattr(step, 'metadata') and step.metadata:
            if 'question_type' in step.metadata:
                return step.metadata['question_type']

            # Check for critical keywords in metadata
            if any(key in str(step.metadata).lower() for key in ['medication', 'dosage', 'emergency', 'consent']):
                return 'medication_verification'

        # Analyze step content for patterns
        content_lower = step.content.lower() if step.content else ""

        # Critical patterns (never humanize)
        if any(word in content_lower for word in ['medicação', 'medicamento', 'dose', 'mg', 'ml', 'emergência']):
            return 'medication_verification'

        if any(word in content_lower for word in ['cirurgia', 'procedimento', 'exame', 'jejum']):
            return 'surgery_preparation'

        if any(word in content_lower for word in ['consentimento', 'autorizo', 'concordo']):
            return 'consent_collection'

        # Safe patterns (can humanize)
        if any(word in content_lower for word in ['como você está', 'como se sente', 'sentindo']):
            return 'daily_checkin'

        if any(word in content_lower for word in ['humor', 'ânimo', 'emocional', 'ansiedade']):
            return 'mood_assessment'

        if any(word in content_lower for word in ['sintoma', 'dor', 'desconforto', 'náusea']):
            return 'symptom_tracking'

        if any(word in content_lower for word in ['sono', 'dormiu', 'descanso']):
            return 'sleep_quality'

        if any(word in content_lower for word in ['apetite', 'alimentação', 'comendo']):
            return 'appetite_check'

        # Check step type
        if step.type == 'quiz':
            # Quiz questions default to feedback unless marked critical
            return 'feedback_request'

        # Default to general wellbeing (safe to humanize)
        return 'general_wellbeing'

    @with_db_retry(max_retries=3)
    async def _schedule_step(
        self,
        flow_state: PatientFlowState,
        step: FlowStep,
        base_time: datetime,
    ) -> None:
        """Schedule actions for the given step based on its type with intelligent humanization."""
        scheduled_for = base_time + timedelta(hours=step.delay_hours)

        if step.type == "message" or step.type == "quiz":
            # Get original content
            original_content = step.content

            # Determine question type for selective humanization
            question_type = self._determine_question_type(step)

            # Apply intelligent question humanization if enabled
            try:
                patient_repo = PatientRepository(self.db)
                patient = patient_repo.get(flow_state.patient_id)

                humanized_content = original_content

                if patient and is_ai_humanization_enabled():
                    question_humanizer = get_question_humanizer()

                    if step.type == "quiz":
                        question_id = getattr(step, 'name', f"quiz_step_{flow_state.current_step}")
                        humanized_content = await question_humanizer.humanize_quiz_question(
                            question=original_content,
                            question_id=question_id,
                            patient_id=str(flow_state.patient_id),
                            quiz_type=flow_state.state_data.get('requested_flow_type', 'monthly')
                        )
                    else:
                        humanized_content = await question_humanizer.humanize_question(
                            question=original_content,
                            question_type=question_type,
                            patient=patient,
                            context={
                                'step_type': step.type,
                                'step_name': getattr(step, 'name', 'unknown'),
                                'flow_data': flow_state.state_data
                            }
                        )
            except Exception as e:
                logger.error(f"Error in question humanization: {e}")
                humanized_content = original_content  # Safe fallback

            # Schedule outbound message for both message and quiz steps
            message = self.message_service.schedule_message(
                flow_state.patient_id,
                humanized_content,
                scheduled_for,
                message_type=MessageType.TEXT,
                message_metadata={
                    'original_content': original_content,
                    'humanized': humanized_content != original_content,
                    'step_type': step.type,
                    'question_type': question_type,
                    'flow_step_id': step.name if hasattr(step, 'name') else 'unknown',
                    'ai_processing': 'question_humanizer'
                }
            )
            from app.tasks.messaging import send_scheduled_message
            send_scheduled_message.apply_async((str(message.id),), eta=scheduled_for)


        if step.type == "quiz" and step.quiz_template:
            # Start quiz session so responses can be collected
            template = self.quiz_session_service.template_repository.get_by_name(step.quiz_template)
            if template:
                from app.schemas.quiz import QuizSessionCreate

                session_data = QuizSessionCreate(
                    patient_id=flow_state.patient_id,
                    quiz_template_id=template.id,
                )
                # Create safe async task for quiz session start
                safe_create_task(
                    self.quiz_session_service.start_quiz_session(session_data),
                    name=f"quiz_session_start_{flow_state.patient_id}",
                    context={"step_type": step.type, "patient_id": str(flow_state.patient_id)}
                )
    
    def _validate_patient_data(self, patient: Patient) -> dict[str, Any]:
        """
        Validate patient data completeness before starting flow.

        Args:
            patient: Patient model instance

        Returns:
            Dict containing validation results with 'valid' flag and any errors

        Raises:
            ValidationError: If critical patient data is missing
        """
        errors = []
        warnings = []

        # Critical fields that MUST be present
        critical_fields = {
            'cpf': (patient.cpf, "CPF não informado"),
            'treatment_type': (patient.treatment_type, "Tipo de tratamento não informado"),
            'phone': (patient.phone, "Telefone não informado"),
        }

        # Check critical fields
        for field_name, (field_value, error_msg) in critical_fields.items():
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                errors.append({
                    'field': field_name,
                    'message': error_msg,
                    'severity': 'error'
                })

        # Recommended fields for better flow execution
        recommended_fields = {
            'name': (patient.name, "Nome do paciente não informado"),
            'treatment_start_date': (patient.treatment_start_date, "Data de início do tratamento não informada"),
            'diagnosis': (patient.diagnosis, "Diagnóstico não informado"),
        }

        # Check recommended fields
        for field_name, (field_value, warning_msg) in recommended_fields.items():
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                warnings.append({
                    'field': field_name,
                    'message': warning_msg,
                    'severity': 'warning'
                })

        # Additional validations
        if patient.phone:
            # Basic phone validation (Brazilian format)
            phone_digits = ''.join(filter(str.isdigit, patient.phone))
            if len(phone_digits) < 10 or len(phone_digits) > 11:
                errors.append({
                    'field': 'phone',
                    'message': f"Telefone com formato inválido: {patient.phone}",
                    'severity': 'error'
                })

        if patient.cpf:
            # Basic CPF validation (11 digits)
            cpf_digits = ''.join(filter(str.isdigit, patient.cpf))
            if len(cpf_digits) != 11:
                errors.append({
                    'field': 'cpf',
                    'message': f"CPF com formato inválido (deve ter 11 dígitos): {patient.cpf}",
                    'severity': 'error'
                })

        # Build validation result
        validation_result = {
            'valid': len(errors) == 0,
            'patient_id': str(patient.id),
            'errors': errors,
            'warnings': warnings,
            'checked_fields': {
                'critical': list(critical_fields.keys()),
                'recommended': list(recommended_fields.keys())
            }
        }

        # If there are critical errors, raise ValidationError
        if errors:
            error_messages = [f"{err['field']}: {err['message']}" for err in errors]
            raise ValidationError(
                f"Dados do paciente incompletos ou inválidos. Erros: {'; '.join(error_messages)}"
            )

        # Log warnings if any
        if warnings:
            warning_messages = [f"{warn['field']}: {warn['message']}" for warn in warnings]
            logger.warning(
                f"Paciente {patient.id} tem campos recomendados ausentes: {'; '.join(warning_messages)}"
            )

        return validation_result

    @with_db_retry(max_retries=3)
    def start_flow(
        self,
        patient_id: UUID,
        flow_type: str,
        initial_data: Optional[dict[str, Any]] = None,
        fallback_to_default: bool = True
    ) -> PatientFlowState:
        """
        Start a new flow for a patient with graceful template fallback.

        Args:
            patient_id: Patient UUID
            flow_type: Type of flow to start
            initial_data: Initial state data
            fallback_to_default: Whether to fallback to default template if specified template not found

        Returns:
            PatientFlowState: Created flow state

        Raises:
            NotFoundError: If patient not found or no suitable template available
            ValidationError: If flow validation fails or patient data incomplete
        """
        # Get patient
        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        # CRITICAL FIX #1: Pre-flight validation
        # Validate patient data completeness before starting flow
        validation_result = self._validate_patient_data(patient)
        logger.info(
            f"Patient {patient_id} data validation passed. "
            f"Warnings: {len(validation_result.get('warnings', []))}"
        )

        # Get template with fallback handling
        template_data = self._get_template_with_fallback(flow_type, fallback_to_default)
        if not template_data:
            # Log the missing template for monitoring
            logger.error(f"No suitable template found for flow_type '{flow_type}' and patient {patient_id}")

            if not fallback_to_default:
                raise NotFoundError(f"Flow template '{flow_type}' not found")
            else:
                raise NotFoundError(f"Flow template '{flow_type}' not found and no default template available")

        # Log if we're using a fallback template
        if template_data.flow_type != flow_type:
            logger.warning(f"Using fallback template '{template_data.flow_type}' instead of requested '{flow_type}' for patient {patient_id}")

        # Validate template
        state_machine = StateMachine(template_data)
        validation_errors = state_machine.validate_flow()
        if validation_errors:
            raise ValidationError(f"Flow template validation failed: {validation_errors}")

        # Check if patient already has an active flow
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if active_flow:
            raise ValidationError(f"Patient already has an active flow")

        # Get the FlowKind and current version for this template
        flow_kind = self.db.query(FlowKind).filter(
            FlowKind.flow_type == template_data.flow_type
        ).first()

        if not flow_kind:
            raise ValidationError(f"Flow kind not found for flow type: {template_data.flow_type}")

        # Get the current (is_current=true) template version
        from app.repositories.flow_template_version import FlowTemplateVersionRepository
        template_version_repo = FlowTemplateVersionRepository(self.db)
        current_version = template_version_repo.get_current_version_by_flow_type(template_data.flow_type)

        if not current_version:
            raise ValidationError(f"No current version found for flow type: {template_data.flow_type}")

        # Determine the first step (entry point) from the template
        entry_step = min(template_data.steps, key=lambda s: s.id).id if template_data.steps else 0

        # Create new flow state with template_version_id
        flow_state = PatientFlowState(
            patient_id=patient_id,
            template_version_id=current_version.id,
            current_step=entry_step,  # Start at first step in template
            started_at=datetime.utcnow(),
            state_data={
                **(initial_data or {}),
                "requested_flow_type": flow_type,  # Track original request
                "actual_flow_type": template_data.flow_type,  # Track actual template used
                "fallback_used": template_data.flow_type != flow_type,
                "template_source": "fallback" if template_data.flow_type != flow_type else "requested",
                "entry_step": entry_step  # Track entry point
            }
        )

        # Add to database session and flush to get ID
        self.db.add(flow_state)
        self.db.flush()
        created_flow = flow_state

        # Schedule initial step actions (async)
        safe_create_task(
            self._schedule_step_actions(patient, created_flow.current_step, state_machine),
            name=f"schedule_step_actions_{patient_id}",
            context={"flow_type": template_data.flow_type, "step": created_flow.current_step}
        )

        # Schedule initial step (async)
        first_step = state_machine.get_current_step(0)
        if first_step:
            safe_create_task(
                self._schedule_step(created_flow, first_step, created_flow.started_at),
                name=f"schedule_initial_step_{patient_id}",
                context={"flow_type": template_data.flow_type, "step": 0}
            )

        return created_flow

    def _get_template_with_fallback(self, flow_type: str, enable_fallback: bool = True) -> Optional[Any]:
        """
        Get template with fallback handling for missing templates.

        Args:
            flow_type: Requested flow type
            enable_fallback: Whether to try fallback templates

        Returns:
            Template data or None if not found
        """
        # Try to get the requested template first
        template_data = self.template_service.get_template_data(flow_type)
        if template_data:
            return template_data

        # If not found and fallback is enabled, try fallback options
        if not enable_fallback:
            return None

        # Define fallback hierarchy based on template names from patient service
        fallback_hierarchy = {
            # Specific cancer type templates fallback to general hormone therapy
            "hormonia_fluxo_mama": ["hormonia_fluxo_hormonal", "hormonia_fluxo_padrao"],
            "hormonia_fluxo_prostata": ["hormonia_fluxo_hormonal", "hormonia_fluxo_padrao"],
            "hormonia_fluxo_pulmao": ["hormonia_fluxo_padrao"],
            "hormonia_fluxo_coloretal": ["hormonia_fluxo_padrao"],

            # Treatment type templates fallback to general
            "hormonia_fluxo_hormonal": ["hormonia_fluxo_padrao"],
            "hormonia_fluxo_quimio": ["hormonia_fluxo_padrao"],
            "hormonia_fluxo_radio": ["hormonia_fluxo_padrao"],

            # System templates fallback hierarchy
            "initial_15_days": ["monthly_recurring", "hormonia_fluxo_padrao"],
            "days_16_45": ["monthly_recurring", "hormonia_fluxo_padrao"],
            "monthly_recurring": ["hormonia_fluxo_padrao"],
        }

        # Try fallbacks for this specific flow type
        fallbacks = fallback_hierarchy.get(flow_type, [])
        for fallback_type in fallbacks:
            template_data = self.template_service.get_template_data(fallback_type)
            if template_data:
                logger.info(f"Using fallback template '{fallback_type}' for requested '{flow_type}'")
                return template_data

        # Final fallback: try any available active template
        try:
            available_templates = self.template_service.get_all_templates(limit=1)
            if available_templates:
                fallback_template = available_templates[0]
                template_data = self.template_service.get_template_data(fallback_template.flow_type)
                if template_data:
                    logger.warning(f"Using emergency fallback template '{fallback_template.flow_type}' for requested '{flow_type}'")
                    return template_data
        except Exception as e:
            logger.error(f"Error during emergency fallback: {e}")

        # No suitable template found
        return None

    async def process_patient_day_async(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Async version of process_patient_day for proper async chain."""
        return await self._process_patient_day_internal(patient_id, force_transition, additional_context)

    @with_db_retry(max_retries=3)
    def process_patient_day(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Process a patient's daily flow progression (sync wrapper).

        Args:
            patient_id: Patient UUID
            force_transition: Force transition ignoring conditions
            additional_context: Additional context for evaluation

        Returns:
            Dict containing processing results

        Raises:
            NotFoundError: If patient or flow not found
        """
        # Sync wrapper that delegates to async version
        import asyncio
        try:
            return asyncio.run(self._process_patient_day_internal(patient_id, force_transition, additional_context))
        except RuntimeError:
            # Already in event loop, use safe task creation
            task = safe_create_task(
                self._process_patient_day_internal(patient_id, force_transition, additional_context),
                name=f"process_patient_day_{patient_id}",
                context={"force_transition": force_transition}
            )
            if task:
                return asyncio.get_event_loop().run_until_complete(task)
            else:
                # Task creation failed, run with fallback
                from app.core.async_context_manager import safe_run_coroutine
                return safe_run_coroutine(
                    self._process_patient_day_internal(patient_id, force_transition, additional_context),
                    timeout=300,
                    fallback_sync=True
                )

    @with_db_retry(max_retries=3)
    async def _process_patient_day_internal(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Internal async implementation of patient day processing.

        Args:
            patient_id: Patient UUID
            force_transition: Force transition ignoring conditions
            additional_context: Additional context for evaluation

        Returns:
            Dict containing processing results

        Raises:
            NotFoundError: If patient or flow not found
        """
        # Get patient and active flow
        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")
        
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            return {
                "status": "no_active_flow",
                "message": "Patient has no active flow",
                "patient_id": str(patient_id)
            }
        
        # Get flow type and template
        try:
            flow_type = self._get_flow_type_from_state(active_flow)
        except ValidationError as e:
            return {
                "status": "template_version_error",
                "message": str(e),
                "patient_id": str(patient_id),
                "flow_id": str(active_flow.id)
            }

        # Get template and create state machine
        template_data = self.template_service.get_template_data(flow_type)
        if not template_data:
            return {
                "status": "template_not_found",
                "message": f"Template '{flow_type}' not found",
                "patient_id": str(patient_id),
                "flow_id": str(active_flow.id)
            }
        
        state_machine = StateMachine(template_data)
        
        # Build context
        context = self.context_builder.build_context(patient, active_flow, additional_context)
        
        # Attempt transition
        transition = state_machine.transition(
            from_step_id=active_flow.current_step,
            context=context,
            force=force_transition
        )

        # Update flow state based on transition result and schedule next step if needed
        result = await self._handle_transition_result(active_flow, transition, context, state_machine)
        
        return result

    @with_db_retry(max_retries=3)
    async def _schedule_step_actions(
        self,
        patient: Patient,
        step_id: int,
        state_machine: StateMachine
    ) -> None:
        """Schedule actions for a specific flow step with AI humanization."""
        step = state_machine.get_current_step(step_id)
        if not step:
            return

        scheduled_for = datetime.utcnow() + timedelta(hours=step.delay_hours)

        # Get original content
        original_content = step.content

        # Apply AI humanization if enabled
        try:
            # FIXED: Direct async/await call - no more event loop creation
            humanized_content = await self._humanize_message_content(
                content=original_content,
                patient_id=patient.id,
                message_type=getattr(step, 'type', 'general')
            )
        except Exception as e:
            logger.error(f"Error in step action humanization: {e}")
            humanized_content = original_content  # Fallback to original

        # Always schedule the step content as a message
        self.message_service.schedule_message(
            patient_id=patient.id,
            content=humanized_content,
            scheduled_for=scheduled_for,
            message_metadata={
                **(step.metadata or {}),
                "original_content": original_content,
                "humanized": humanized_content != original_content,
                "ai_processing_applied": True
            },
        )

        # For quiz steps, start a session and log placeholder response
        if step.type == "quiz" and step.quiz_template:
            template = self.quiz_session_service.template_repository.get_by_name(step.quiz_template)
            if template:
                session_data = QuizSessionCreate(
                    patient_id=patient.id,
                    quiz_template_id=template.id,
                )
                # Create safe async tasks for quiz operations
                safe_create_task(
                    self.quiz_session_service.start_quiz_session(session_data),
                    name=f"quiz_session_{patient.id}",
                    context={"patient_id": str(patient.id), "template_id": str(template.id)}
                )

                # Use humanized content for quiz question text
                placeholder = QuizResponseCreate(
                    patient_id=patient.id,
                    quiz_template_id=template.id,
                    question_id="__start__",
                    question_text=humanized_content,  # Use humanized content
                    response_type=QuestionType.OPEN_TEXT,
                    response_value="",
                    response_metadata={
                        "scheduled": True,
                        "original_question": original_content,
                        "humanized": humanized_content != original_content
                    },
                    responded_at=scheduled_for,
                )
                safe_create_task(
                    self.quiz_response_service.create_response(placeholder),
                    name=f"quiz_response_{patient.id}",
                    context={"patient_id": str(patient.id), "question_id": "__start__"}
                )
    
    @with_db_retry(max_retries=3)
    async def advance_flow(
        self,
        patient_id: UUID,
        to_step: Optional[int] = None,
        force: bool = False
    ) -> dict[str, Any]:
        """
        Manually advance a patient's flow.
        
        Args:
            patient_id: Patient UUID
            to_step: Specific step to advance to (optional)
            force: Force advancement ignoring conditions
            
        Returns:
            Dict containing advancement results
        """
        # Get active flow
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            raise NotFoundError(f"No active flow found for patient {patient_id}")
        
        # Get patient for context
        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")
        
        # Get flow type and template
        flow_type = self._get_flow_type_from_state(active_flow)
        template_data = self.template_service.get_template_data(flow_type)
        if not template_data:
            raise NotFoundError(f"Template '{flow_type}' not found")
        
        state_machine = StateMachine(template_data)
        context = self.context_builder.build_context(patient, active_flow)
        
        if to_step is not None:
            # Manual step override
            if not state_machine.get_current_step(to_step):
                raise ValidationError(f"Step {to_step} does not exist in flow")
            
            # Update flow state directly
            active_flow.current_step = to_step
            active_flow.state_data = active_flow.state_data or {}
            active_flow.state_data["manual_override"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "previous_step": active_flow.current_step,
                "forced": force
            }
            
            self.db.commit()
            
            return {
                "status": "manual_override",
                "message": f"Flow manually advanced to step {to_step}",
                "patient_id": str(patient_id),
                "flow_id": str(active_flow.id),
                "current_step": to_step,
                "previous_step": active_flow.current_step
            }
        else:
            # Normal advancement (async)
            return await self.process_patient_day_async(patient_id, force_transition=force)
    
    @with_db_retry(max_retries=3)
    def reset_flow(
        self,
        patient_id: UUID,
        to_step: int = 0,
        preserve_data: bool = True
    ) -> dict[str, Any]:
        """
        Reset a patient's flow to a specific step.
        
        Args:
            patient_id: Patient UUID
            to_step: Step to reset to (default: 0)
            preserve_data: Whether to preserve existing state data
            
        Returns:
            Dict containing reset results
        """
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            raise NotFoundError(f"No active flow found for patient {patient_id}")
        
        # Get flow type and validate target step exists
        flow_type = self._get_flow_type_from_state(active_flow)
        template_data = self.template_service.get_template_data(flow_type)
        if not template_data:
            raise NotFoundError(f"Template '{flow_type}' not found")
        
        state_machine = StateMachine(template_data)
        if not state_machine.get_current_step(to_step):
            raise ValidationError(f"Step {to_step} does not exist in flow")
        
        # Store reset information
        reset_data = {
            "reset_timestamp": datetime.utcnow().isoformat(),
            "previous_step": active_flow.current_step,
            "reset_to_step": to_step,
            "preserve_data": preserve_data
        }
        
        # Update flow state
        active_flow.current_step = to_step
        active_flow.completed_at = None  # Ensure flow is not marked as completed
        
        if preserve_data:
            active_flow.state_data = active_flow.state_data or {}
            active_flow.state_data["reset_history"] = active_flow.state_data.get("reset_history", [])
            active_flow.state_data["reset_history"].append(reset_data)
        else:
            active_flow.state_data = {"reset_history": [reset_data]}
        
        self.db.commit()
        
        return {
            "status": "flow_reset",
            "message": f"Flow reset to step {to_step}",
            "patient_id": str(patient_id),
            "flow_id": str(active_flow.id),
            "current_step": to_step,
            "previous_step": reset_data["previous_step"],
            "data_preserved": preserve_data
        }
    
    @with_db_retry(max_retries=3)
    def complete_flow(self, patient_id: UUID) -> dict[str, Any]:
        """
        Mark a patient's flow as completed.
        
        Args:
            patient_id: Patient UUID
            
        Returns:
            Dict containing completion results
        """
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            raise NotFoundError(f"No active flow found for patient {patient_id}")
        
        # Mark as completed
        active_flow.completed_at = datetime.utcnow()
        active_flow.state_data = active_flow.state_data or {}
        active_flow.state_data["completion"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "final_step": active_flow.current_step,
            "manual_completion": True
        }
        
        self.db.commit()
        
        return {
            "status": "flow_completed",
            "message": "Flow marked as completed",
            "patient_id": str(patient_id),
            "flow_id": str(active_flow.id),
            "final_step": active_flow.current_step,
            "completed_at": active_flow.completed_at
        }
    
    @with_db_retry(max_retries=3)
    def get_flow_status(self, patient_id: UUID) -> dict[str, Any]:
        """
        Get current flow status for a patient.
        
        Args:
            patient_id: Patient UUID
            
        Returns:
            Dict containing flow status information
        """
        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")
        
        active_flow = self.flow_state_repo.get_active_flow(patient_id)
        if not active_flow:
            return {
                "status": "no_active_flow",
                "patient_id": str(patient_id),
                "patient_name": patient.name,
                "has_active_flow": False
            }
        
        # Get template version and flow kind info
        template_version = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == active_flow.template_version_id
        ).first()

        if not template_version:
            raise ValidationError(f"Template version not found for flow state")

        flow_kind = self.db.query(FlowKind).filter(
            FlowKind.id == template_version.kind_id
        ).first()

        flow_type = flow_kind.flow_type if flow_kind else "unknown"

        # Get template and current step info
        template_data = self.template_service.get_template_data(flow_type)
        current_step = None
        available_transitions = []

        if template_data:
            state_machine = StateMachine(template_data)
            current_step = state_machine.get_current_step(active_flow.current_step)
            
            # Build context for transition evaluation
            context = self.context_builder.build_context(patient, active_flow)
            available_transitions = state_machine.get_available_transitions(
                active_flow.current_step, context
            )
        
        return {
            "status": "active_flow",
            "patient_id": str(patient_id),
            "patient_name": patient.name,
            "has_active_flow": True,
            "flow": {
                "id": str(active_flow.id),
                "flow_type": active_flow.flow_type,
                "template_version": active_flow.template_version,
                "current_step": active_flow.current_step,
                "current_step_name": current_step.name if current_step else "Unknown",
                "current_step_type": current_step.type if current_step else "Unknown",
                "started_at": active_flow.started_at,
                "state_data": active_flow.state_data,
                "available_transitions": available_transitions
            }
        }
    
    @with_db_retry(max_retries=3)
    async def _handle_transition_result(
        self,
        flow_state: PatientFlowState,
        transition: StateTransition,
        context: dict[str, Any],
        state_machine: StateMachine,
    ) -> dict[str, Any]:
        """
        Handle the result of a state transition with distributed locking.

        Uses distributed locks to prevent race conditions between concurrent
        flow state updates and message scheduling operations.
        """
        result = {
            "status": transition.result.value,
            "message": transition.message,
            "patient_id": str(flow_state.patient_id),
            "flow_id": str(flow_state.id),
            "from_step": transition.from_step,
            "to_step": transition.to_step,
            "conditions_evaluated": transition.conditions_evaluated,
            "timestamp": transition.timestamp
        }

        # Acquire distributed lock for flow state transition
        try:
            async with async_flow_state_lock(flow_state.patient_id, timeout=30) as lock:
                logger.debug(f"Acquired flow state lock for patient {flow_state.patient_id}")

                if transition.result == TransitionResult.SUCCESS:
                    # Update flow state
                    flow_state.current_step = transition.to_step
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["last_transition"] = {
                        "timestamp": transition.timestamp.isoformat(),
                        "from_step": transition.from_step,
                        "to_step": transition.to_step,
                        "conditions": transition.conditions_evaluated
                    }

                    self.db.commit()
                    result["current_step"] = transition.to_step

                    # Schedule next step actions (async) - still protected by lock
                    next_step = state_machine.get_current_step(transition.to_step)
                    if next_step:
                        await self._schedule_step(flow_state, next_step, transition.timestamp)

                elif transition.result == TransitionResult.FLOW_COMPLETED:
                    # Mark flow as completed
                    flow_state.completed_at = transition.timestamp
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["completion"] = {
                        "timestamp": transition.timestamp.isoformat(),
                        "final_step": transition.from_step,
                        "auto_completion": True
                    }

                    self.db.commit()
                    result["completed_at"] = transition.timestamp

                elif transition.result == TransitionResult.CONDITION_NOT_MET:
                    # Log the failed transition attempt
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["failed_transitions"] = flow_state.state_data.get("failed_transitions", [])
                    flow_state.state_data["failed_transitions"].append({
                        "timestamp": transition.timestamp.isoformat(),
                        "from_step": transition.from_step,
                        "to_step": transition.to_step,
                        "reason": "conditions_not_met",
                        "conditions": transition.conditions_evaluated
                    })

                    self.db.commit()

                # Log lock metrics for monitoring
                lock_metrics = lock.get_metrics()
                if lock_metrics.get("contention_count", 0) > 0:
                    logger.info(
                        f"Flow state lock contention detected: "
                        f"{lock_metrics['contention_count']} contentions, "
                        f"avg wait: {lock_metrics['average_wait_time']:.3f}s"
                    )

        except LockTimeoutError as e:
            logger.error(
                f"Lock timeout during flow transition for patient {flow_state.patient_id}: {e}"
            )
            result["status"] = "lock_timeout"
            result["error"] = str(e)

        except LockAcquisitionError as e:
            logger.error(
                f"Failed to acquire lock for flow transition for patient {flow_state.patient_id}: {e}"
            )
            result["status"] = "lock_failed"
            result["error"] = str(e)

        return result

    def cleanup(self) -> None:
        """
        Cleanup FlowEngine resources and prevent memory leaks.
        Called by dependency injection system on shutdown.
        """
        try:
            logger.info("FlowEngine cleanup started")

            # Call parent cleanup for async resources
            super().cleanup()

            # No specific cleanup needed for this service
            # EventLoopManager handles all async cleanup automatically

            logger.info("FlowEngine cleanup completed successfully")

        except Exception as e:
            logger.error(f"FlowEngine cleanup failed: {e}", exc_info=True)

    def __del__(self) -> None:
        """
        Destructor to ensure cleanup on garbage collection.
        Safety net for proper resource cleanup.
        """
        try:
            self.cleanup()
        except Exception:
            # Ignore errors in destructor
            pass
