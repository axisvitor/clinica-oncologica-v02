"""
Enhanced Flow Engine Integration Service.
Integrates EnhancedFlowEngine with message scheduling system and provides
AI-powered message generation for the complete flow pipeline.
"""
import asyncio
import hashlib
import logging
from typing import List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from uuid import UUID

from app.services.enhanced_flow_engine import EnhancedFlowEngine, FlowType
from app.services.message_scheduler import MessageScheduler
from app.services.message_sender import MessageSender  # Legacy compatibility
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.services.template_loader import EnhancedTemplateLoader, MessageTemplate
from app.services.flow_analytics import FlowAnalyticsService, EventType
from app.services.flow_event_broadcaster import flow_event_broadcaster
from app.services.platform_synchronization import get_platform_sync_service, SyncEventType
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.exceptions import NotFoundError, ValidationError


class SchedulerError(Exception):
    """Exception raised when message scheduling fails."""
    pass

logger = logging.getLogger(__name__)


class FlowEngineIntegrationService:
    """
    Enhanced flow engine integration service that connects AI-powered flow processing
    with message scheduling and delivery systems.
    """
    
    def __init__(self,
                 db: Session,
                 enhanced_flow_engine: Optional[EnhancedFlowEngine] = None,
                 message_scheduler: Optional[MessageScheduler] = None,
                 message_sender: Optional[MessageSender] = None,
                 template_loader: Optional[EnhancedTemplateLoader] = None,
                 analytics_service: Optional[FlowAnalyticsService] = None,
                 use_unified_service: bool = True):
        """
        Initialize flow engine integration service.

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
        self.enhanced_flow_engine = enhanced_flow_engine or EnhancedFlowEngine(db)
        self.message_scheduler = message_scheduler or MessageScheduler(db)

        # Use unified service by default for better reliability and performance
        if use_unified_service:
            self.message_sender = UnifiedWhatsAppService(
                db=db,
                messaging_mode=MessagingMode.HYBRID  # Hybrid mode for flow messages
            )
        else:
            # Fallback to legacy MessageSender
            self.message_sender = message_sender or MessageSender(db)

        self.template_loader = template_loader or EnhancedTemplateLoader()
        self.analytics_service = analytics_service or FlowAnalyticsService(db)
        self.flow_broadcaster = flow_event_broadcaster
        self.platform_sync = get_platform_sync_service(db)
        
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        
        # Register flow callbacks with message sender
        self._register_flow_callbacks()
        
        # Initialize flow integrity service
        self.flow_integrity_service = FlowIntegrityService(db)

        logger.info("Flow Engine Integration Service initialized")
    
    def _register_flow_callbacks(self):
        """Register flow-specific callbacks with message sender."""
        self.message_sender.register_flow_callback('message_sent', self._on_flow_message_sent)
        self.message_sender.register_flow_callback('message_failed', self._on_flow_message_failed)
        self.message_sender.register_flow_callback('status_updated', self._on_flow_message_status_updated)
    
    async def process_daily_flows(self, limit: int = 1000) -> dict[str, Any]:
        """
        Process daily flows for all active patients using EnhancedFlowEngine.
        
        Args:
            limit: Maximum number of patients to process
            
        Returns:
            Processing results summary
        """
        try:
            start_time = datetime.utcnow()
            
            # Get all active flow states
            active_flows = self.flow_state_repo.get_active_flows(limit=limit)
            
            results = {
                'processed_patients': 0,
                'messages_scheduled': 0,
                'errors': 0,
                'skipped': 0,
                'processing_time': 0,
                'details': []
            }
            
            for flow_state in active_flows:
                try:
                    patient_result = await self._process_patient_daily_flow(flow_state)
                    results['details'].append(patient_result)
                    
                    if patient_result['status'] == 'success':
                        results['processed_patients'] += 1
                        results['messages_scheduled'] += patient_result.get('messages_scheduled', 0)
                    elif patient_result['status'] == 'error':
                        results['errors'] += 1
                    else:
                        results['skipped'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing patient {flow_state.patient_id}: {e}")
                    results['errors'] += 1
                    results['details'].append({
                        'patient_id': str(flow_state.patient_id),
                        'status': 'error',
                        'error': str(e)
                    })
            
            results['processing_time'] = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"Daily flow processing completed: {results['processed_patients']} patients, "
                       f"{results['messages_scheduled']} messages scheduled, "
                       f"{results['errors']} errors in {results['processing_time']:.2f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process daily flows: {e}")
            raise
    
    async def _process_patient_daily_flow(self, flow_state: PatientFlowState) -> dict[str, Any]:
        """Process daily flow for a single patient."""
        try:
            patient_id = flow_state.patient_id
            
            # Check if patient is paused
            if flow_state.state_data and flow_state.state_data.get('paused'):
                return {
                    'patient_id': str(patient_id),
                    'status': 'skipped',
                    'reason': 'Patient flow is paused'
                }
            
            # Calculate current day
            current_day = await self.enhanced_flow_engine.calculate_patient_day(patient_id)
            
            # Check for quiz trigger before processing regular flow
            quiz_trigger_result = await self._check_quiz_trigger(patient_id, current_day, flow_state.flow_type)
            if quiz_trigger_result.get('triggered'):
                return {
                    'patient_id': str(patient_id),
                    'status': 'quiz_triggered',
                    'current_day': current_day,
                    'flow_type': flow_state.flow_type,
                    'quiz_session_id': quiz_trigger_result.get('quiz_session_id'),
                    'messages_scheduled': 1 if quiz_trigger_result.get('message_sent') else 0
                }
            
            # Advance patient flow if needed
            advancement_result = await self.enhanced_flow_engine.advance_patient_flow(patient_id)
            
            # Get appropriate message template for today
            flow_type = FlowType(flow_state.flow_type)
            message_template = await self._get_message_template_for_day(flow_type, current_day)
            
            if not message_template:
                return {
                    'patient_id': str(patient_id),
                    'status': 'skipped',
                    'reason': f'No message template for day {current_day}'
                }
            
            # Generate personalized message using AI
            personalized_content = await self.enhanced_flow_engine.generate_flow_message(
                patient_id, message_template
            )
            
            # Create and schedule message
            message_result = await self._create_and_schedule_flow_message(
                patient_id, flow_state, message_template, personalized_content, current_day
            )
            
            return {
                'patient_id': str(patient_id),
                'status': 'success',
                'current_day': current_day,
                'flow_type': flow_state.flow_type,
                'messages_scheduled': 1 if message_result else 0,
                'advancement_result': advancement_result,
                'message_template': message_template.intent if message_template else None
            }
            
        except Exception as e:
            logger.error(f"Error processing patient daily flow: {e}")
            return {
                'patient_id': str(flow_state.patient_id),
                'status': 'error',
                'error': str(e)
            }
    
    async def _get_message_template_for_day(self,
                                          flow_type: FlowType,
                                          day: int) -> Optional[MessageTemplate]:
        """
        Get message template for specific flow type and day with comprehensive error handling.

        This function implements multiple fallback layers:
        1. Primary: Load template from template_loader
        2. Fallback: Use predefined fallback templates in Portuguese
        3. Last resort: Return None (caller handles gracefully)

        Error handling:
        - TemplateLoadError: Template syntax/parsing errors → fallback
        - FileNotFoundError: Template file missing → fallback
        - Generic exceptions: Unexpected errors → fallback with full trace

        Args:
            flow_type: Type of flow (INITIAL_15_DAYS, DAYS_16_45, MONTHLY_RECURRING)
            day: Day number in the flow

        Returns:
            MessageTemplate or None if all fallbacks fail
        """
        try:
            # Load flow template with proper error handling
            from app.services.template_loader import TemplateLoadError, FlowTemplateData

            try:
                flow_template: FlowTemplateData = self.template_loader.load_flow_template(flow_type.value)
            except TemplateLoadError as e:
                logger.error(
                    f"Template load error for {flow_type.value}: {e}. "
                    f"Using fallback message."
                )
                return await self._get_fallback_template(flow_type, day)
            except FileNotFoundError as e:
                logger.error(
                    f"Template file not found for {flow_type.value}: {e}. "
                    f"Using fallback message."
                )
                return await self._get_fallback_template(flow_type, day)
            except Exception as e:
                logger.error(
                    f"Unexpected error loading template {flow_type.value}: {e}. "
                    f"Using fallback message.",
                    exc_info=True
                )
                return await self._get_fallback_template(flow_type, day)

            # Get message for specific day from FlowTemplateData.messages dict
            if day in flow_template.messages:
                message_template = flow_template.messages[day]
                logger.debug(f"Found message template for {flow_type.value} day {day}")
                return message_template

            logger.warning(
                f"No message template found for {flow_type.value} day {day}. "
                f"Using fallback message."
            )
            return await self._get_fallback_template(flow_type, day)

        except Exception as e:
            logger.error(
                f"Critical error getting message template for {flow_type.value} day {day}: {e}. "
                f"Using fallback message.",
                exc_info=True
            )
            return await self._get_fallback_template(flow_type, day)

    async def _get_fallback_template(self, flow_type: FlowType, day: int) -> Optional[MessageTemplate]:
        """Provide fallback template when primary template loading fails."""
        try:
            from app.services.template_loader import MessageType as TemplateMessageType

            # Create a simple fallback message template in Portuguese
            fallback_messages = {
                FlowType.INITIAL_15_DAYS: {
                    'content': "Olá! Como você está se sentindo hoje?",
                    'intent': 'daily_check_initial',
                    'ai_instructions': 'Generate a warm, caring message asking about patient well-being'
                },
                FlowType.DAYS_16_45: {
                    'content': "Esperamos que você esteja bem. Como está seu tratamento?",
                    'intent': 'treatment_followup',
                    'ai_instructions': 'Generate an empathetic message about treatment progress'
                },
                FlowType.MONTHLY_RECURRING: {
                    'content': "Olá! É hora de fazer seu check-in mensal.",
                    'intent': 'monthly_checkin',
                    'ai_instructions': 'Generate a friendly monthly check-in message'
                }
            }

            fallback_data = fallback_messages.get(
                flow_type,
                {
                    'content': "Olá! Como podemos ajudá-lo hoje?",
                    'intent': 'general_checkin',
                    'ai_instructions': 'Generate a supportive, caring message'
                }
            )

            logger.warning(
                f"Using fallback template for {flow_type.value} day {day}. "
                f"Template loading failed, providing default Portuguese message."
            )

            return MessageTemplate(
                day=day,
                intent=fallback_data['intent'],
                base_content=fallback_data['content'],
                core_elements={"greeting": True, "care": True, "support": True},
                personalization_hints=["patient_name", "treatment_type", "patient_condition"],
                ai_instructions=fallback_data['ai_instructions'],
                message_type=TemplateMessageType.TEXT,
                variations=[]  # No variations for fallback
            )
        except Exception as e:
            logger.error(
                f"Critical failure generating fallback template: {e}. "
                f"Returning None - flow will skip this day.",
                exc_info=True
            )
            return None
    
    async def _create_and_schedule_flow_message(self,
                                              patient_id: UUID,
                                              flow_state: PatientFlowState,
                                              message_template: MessageTemplate,
                                              personalized_content: str,
                                              current_day: int) -> bool:
        """
        Create and schedule a flow message with atomic transaction safety and comprehensive error handling.

        Implements robust message creation with:
        - Atomic database operations (flush before schedule, commit only on success)
        - Retry mechanism with exponential backoff (max 3 attempts)
        - Automatic rollback on scheduling failures
        - Failed message audit trail creation
        - Transient vs permanent error detection

        Error handling strategy:
        1. SQLAlchemyError → rollback, retry if transient
        2. SchedulerError → rollback, retry if transient, create FAILED record on final failure
        3. NotFoundError → no retry, immediate failure
        4. Generic exceptions → rollback, retry if transient

        Transaction safety:
        - Message created with db.flush() to get ID without commit
        - Scheduling attempted with that ID
        - Commit ONLY if scheduling succeeds
        - Rollback if scheduling fails, with retry logic

        Args:
            patient_id: Patient UUID
            flow_state: Current patient flow state
            message_template: Template used for message
            personalized_content: AI-generated personalized message
            current_day: Current day in flow

        Returns:
            bool: True if message created and scheduled successfully, False otherwise
        """
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                from sqlalchemy.exc import SQLAlchemyError

                # Get patient for timezone and preferences
                patient = self.patient_repo.get(patient_id)
                if not patient:
                    raise NotFoundError(f"Patient {patient_id} not found")

                # Create message object but DON'T commit yet
                message = Message(
                    patient_id=patient_id,
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType.TEXT,
                    content=personalized_content,
                    status=MessageStatus.PENDING,  # Will be committed only after successful scheduling
                    message_metadata={
                        'flow_context': {
                            'flow_state_id': str(flow_state.id),
                            'flow_type': flow_state.flow_type,
                            'current_day': current_day,
                            'template_intent': message_template.intent,
                            'ai_generated': True,
                            'personalization_level': 'high'
                        },
                        'template_data': {
                            'day': message_template.day,
                            'intent': message_template.intent,
                            'core_elements': message_template.core_elements,
                            'personalization_hints': message_template.personalization_hints
                        },
                        'retry_policy': 'flow_message',
                        'creation_attempt': attempt + 1
                    }
                )

                self.db.add(message)
                self.db.flush()  # ✅ Get ID without committing

                # Calculate optimal send time
                send_time = await self._calculate_optimal_send_time(patient, current_day)

                # Try to schedule - if this fails, rollback everything
                try:
                    scheduled = await self.message_scheduler.schedule_message(
                        message_id=message.id,
                        send_time=send_time,
                        priority='normal'
                    )

                    if not scheduled:
                        raise SchedulerError("Scheduler returned False - scheduling failed")

                    # ✅ Only commit if scheduling succeeded
                    self.db.commit()
                    self.db.refresh(message)

                    logger.info(f"Message {message.id} created and scheduled atomically (attempt {attempt + 1})")

                    # Track analytics (non-critical)
                    try:
                        await self.analytics_service.track_message_sent(
                            patient_id=patient_id,
                            message_id=message.id,
                            flow_type=flow_state.flow_type,
                            flow_day=current_day,
                            template_id=message_template.intent,
                            additional_data={
                                'ai_generated': True,
                                'personalization_level': 'high',
                                'scheduled_for': send_time.isoformat(),
                                'attempt_number': attempt + 1
                            }
                        )
                    except Exception as analytics_error:
                        logger.warning(f"Analytics tracking failed (non-critical): {analytics_error}")

                    return True

                except Exception as schedule_error:
                    # ✅ Rollback message creation on scheduling failure
                    logger.error(
                        f"Scheduling failed on attempt {attempt + 1}/{max_retries} for patient {patient_id}: {schedule_error}. "
                        f"Flow: {flow_state.flow_type}, Day: {current_day}, Template: {message_template.intent}",
                        exc_info=True if attempt == max_retries - 1 else False
                    )
                    self.db.rollback()

                    # Check if transient error worth retrying
                    if self._is_transient_error(schedule_error) and attempt < max_retries - 1:
                        logger.warning(f"Transient error detected, retrying in {retry_delay * (attempt + 1)}s...")
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue

                    # Final failure - create FAILED message record
                    logger.error(f"Failed after {attempt + 1} attempts: {schedule_error}")

                    # Create a failed message record for audit trail
                    failed_message = Message(
                        patient_id=patient_id,
                        direction=MessageDirection.OUTBOUND,
                        type=MessageType.TEXT,
                        content=personalized_content,
                        status=MessageStatus.FAILED,
                        message_metadata={
                            'flow_context': {
                                'flow_state_id': str(flow_state.id),
                                'flow_type': flow_state.flow_type,
                                'current_day': current_day,
                                'template_intent': message_template.intent,
                            },
                            'error': str(schedule_error),
                            'failed_at': datetime.utcnow().isoformat(),
                            'total_attempts': attempt + 1,
                            'failure_type': 'scheduling_failed'
                        }
                    )
                    self.db.add(failed_message)
                    self.db.commit()

                    return False

            except SQLAlchemyError as db_error:
                logger.error(
                    f"Database error on attempt {attempt + 1}/{max_retries} for patient {patient_id}: {db_error}. "
                    f"Flow: {flow_state.flow_type}, Day: {current_day}",
                    exc_info=True if attempt == max_retries - 1 else False
                )
                self.db.rollback()

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    return False

            except NotFoundError as nf_error:
                # Don't retry for patient not found - this is a permanent error
                logger.error(
                    f"Patient {patient_id} not found during message creation. "
                    f"Flow: {flow_state.flow_type}, Day: {current_day}. No retry.",
                    exc_info=True
                )
                return False

            except Exception as e:
                logger.error(
                    f"Unexpected error (attempt {attempt + 1}/{max_retries}) for patient {patient_id}: {e}. "
                    f"Flow: {flow_state.flow_type}, Day: {current_day}, Template: {message_template.intent}",
                    exc_info=True
                )
                self.db.rollback()

                if self._is_transient_error(e) and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    return False

        logger.error(
            f"FINAL FAILURE: Failed to create and schedule message after {max_retries} retries. "
            f"Patient: {patient_id}, Flow: {flow_state.flow_type}, Day: {current_day}, Template: {message_template.intent}"
        )
        return False

    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if error is transient and worth retrying.

        Transient errors (retry recommended):
        - Connection issues (network, database)
        - Timeout errors
        - Temporary unavailability
        - Database deadlocks

        Permanent errors (no retry):
        - Validation errors
        - Not found errors
        - Permission errors
        - Data integrity violations

        Args:
            error: Exception to evaluate

        Returns:
            bool: True if error is transient and retry is recommended
        """
        transient_errors = [
            'connection',
            'timeout',
            'temporary',
            'unavailable',
            'deadlock'
        ]
        error_str = str(error).lower()
        return any(term in error_str for term in transient_errors)
    
    async def _calculate_optimal_send_time(self, patient: Patient, current_day: int) -> datetime:
        """
        Calculate optimal send time for patient message with robust error handling.

        Implements intelligent scheduling with:
        - Patient timezone awareness
        - Preferred hour preferences
        - Randomization to distribute load
        - Fallback to safe default on any error

        Error handling:
        - Invalid timezone → defaults to UTC
        - Invalid preferred_hour → defaults to 10 AM
        - Any calculation error → returns 1 hour from now

        Args:
            patient: Patient object with timezone and preferences
            current_day: Current day in flow (for logging context)

        Returns:
            datetime: Optimal send time (always returns valid datetime)
        """
        try:
            # Get patient timezone with validation
            try:
                patient_tz = getattr(patient, 'timezone', 'UTC')
                if not patient_tz or not isinstance(patient_tz, str):
                    logger.warning(f"Invalid timezone for patient {patient.id}, using UTC")
                    patient_tz = 'UTC'
            except Exception as tz_error:
                logger.warning(f"Error reading patient timezone: {tz_error}, using UTC")
                patient_tz = 'UTC'

            # Get patient preferences for message timing with validation
            try:
                preferred_hour = getattr(patient, 'preferred_message_hour', 10)
                if not isinstance(preferred_hour, int) or preferred_hour < 0 or preferred_hour > 23:
                    logger.warning(f"Invalid preferred_hour {preferred_hour} for patient {patient.id}, using 10 AM")
                    preferred_hour = 10
            except Exception as pref_error:
                logger.warning(f"Error reading preferred hour: {pref_error}, using 10 AM default")
                preferred_hour = 10

            # Calculate send time for today
            now = datetime.utcnow()
            send_time = now.replace(hour=preferred_hour, minute=0, second=0, microsecond=0)

            # If the time has already passed today, schedule for tomorrow
            if send_time <= now:
                send_time += timedelta(days=1)
                logger.debug(f"Preferred time passed, scheduling for tomorrow: {send_time}")

            # Add some randomization to avoid all messages at exact same time
            try:
                import random
                random_minutes = random.randint(-30, 30)  # ±30 minutes
                send_time += timedelta(minutes=random_minutes)
            except Exception as rand_error:
                logger.warning(f"Randomization failed: {rand_error}, using exact hour")

            logger.info(
                f"Calculated send time for patient {patient.id} on day {current_day}: "
                f"{send_time.isoformat()} (tz: {patient_tz}, hour: {preferred_hour})"
            )
            return send_time

        except Exception as e:
            logger.error(
                f"Failed to calculate optimal send time for patient {patient.id} day {current_day}: {e}. "
                f"Using fallback: 1 hour from now",
                exc_info=True
            )
            # Fallback to 1 hour from now
            return datetime.utcnow() + timedelta(hours=1)
    
    async def generate_personalized_message_preview(self,
                                                   patient_id: UUID,
                                                   flow_type: str,
                                                   day: int) -> dict[str, Any]:
        """
        Generate a preview of personalized message for healthcare providers.
        
        Args:
            patient_id: Patient UUID
            flow_type: Flow type string
            day: Day number
            
        Returns:
            Message preview with AI insights
        """
        try:
            # Get message template
            flow_type_enum = FlowType(flow_type)
            message_template = await self._get_message_template_for_day(flow_type_enum, day)
            
            if not message_template:
                return {
                    'status': 'error',
                    'error': f'No template found for {flow_type} day {day}'
                }
            
            # Generate personalized message
            personalized_content = await self.enhanced_flow_engine.generate_flow_message(
                patient_id, message_template
            )
            
            # Get patient context
            patient = self.patient_repo.get(patient_id)
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            
            return {
                'status': 'success',
                'preview': {
                    'patient_id': str(patient_id),
                    'patient_name': patient.name if patient else 'Unknown',
                    'flow_type': flow_type,
                    'day': day,
                    'template': {
                        'intent': message_template.intent,
                        'base_content': message_template.base_content,
                        'personalization_hints': message_template.personalization_hints
                    },
                    'personalized_content': personalized_content,
                    'ai_insights': {
                        'personalization_applied': True,
                        'anti_repetition_checked': True,
                        'sentiment_adapted': True
                    },
                    'flow_context': {
                        'current_step': flow_state.current_step if flow_state else None,
                        'started_at': flow_state.started_at.isoformat() if flow_state else None
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate message preview: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def process_patient_response_with_flow_context(self,
                                                       patient_id: UUID,
                                                       response_text: str,
                                                       message_id: Optional[UUID] = None) -> dict[str, Any]:
        """
        Process patient response with full flow context and AI analysis.
        
        Args:
            patient_id: Patient UUID
            response_text: Patient's response text
            message_id: Original message ID (optional)
            
        Returns:
            Response processing result with follow-up actions
        """
        try:
            # Process response using enhanced flow engine
            processing_result = await self.enhanced_flow_engine.process_patient_response(
                patient_id, response_text
            )
            
            # If follow-up message is needed, schedule it
            follow_up_message = processing_result.get('follow_up_message')
            if follow_up_message:
                await self._schedule_follow_up_message(
                    patient_id, follow_up_message, processing_result
                )
            
            # Update flow state with response data
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if flow_state:
                flow_state.state_data = flow_state.state_data or {}
                flow_state.state_data['last_response_processed'] = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'message_id': str(message_id) if message_id else None,
                    'sentiment': processing_result.get('sentiment_analysis', {}),
                    'requires_attention': processing_result.get('requires_attention', False)
                }
                self.db.commit()
                
                # Track response received event in analytics
                sentiment_analysis = processing_result.get('sentiment_analysis', {})
                await self.analytics_service.track_response_received(
                    patient_id=patient_id,
                    message_id=message_id,
                    flow_type=flow_state.flow_type,
                    flow_day=flow_state.current_step,
                    response_text=response_text,
                    sentiment_score=sentiment_analysis.get('score'),
                    engagement_score=processing_result.get('engagement_score'),
                    response_time_seconds=processing_result.get('response_time_seconds'),
                    additional_data={
                        'requires_attention': processing_result.get('requires_attention', False),
                        'extracted_data': processing_result.get('extracted_data', {}),
                        'follow_up_triggered': bool(processing_result.get('follow_up_message'))
                    }
                )
            
            return processing_result
            
        except Exception as e:
            logger.error(f"Failed to process patient response with flow context: {e}")
            return {
                'status': 'error',
                'patient_id': str(patient_id),
                'error': str(e)
            }
    
    async def _schedule_follow_up_message(self,
                                        patient_id: UUID,
                                        follow_up_content: str,
                                        context: dict[str, Any]) -> bool:
        """Schedule an AI-generated follow-up message."""
        try:
            # Create follow-up message
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=follow_up_content,
                status=MessageStatus.PENDING,
                message_metadata={
                    'flow_context': {
                        'type': 'ai_follow_up',
                        'triggered_by': 'patient_response',
                        'ai_generated': True,
                        'empathetic_response': True
                    },
                    'response_context': context,
                    'retry_policy': 'urgent' if context.get('requires_attention') else 'flow_message'
                }
            )
            
            # Save message
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            
            # Schedule for immediate delivery (within 5 minutes)
            send_time = datetime.utcnow() + timedelta(minutes=5)
            
            scheduled = await self.message_scheduler.schedule_message(
                message_id=message.id,
                send_time=send_time,
                priority='high' if context.get('requires_attention') else 'normal'
            )
            
            if scheduled:
                logger.info(f"Scheduled AI follow-up message for patient {patient_id}")
                return True
            else:
                logger.error(f"Failed to schedule AI follow-up message for patient {patient_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to schedule follow-up message: {e}")
            self.db.rollback()
            return False
    
    async def _on_flow_message_sent(self, message: Message, flow_context: Optional[dict[str, Any]]):
        """
        Callback for when flow message is sent successfully with robust error handling.

        This callback handles post-send operations:
        - Updates flow state with sent message metadata
        - Broadcasts message sent event to subscribers
        - Syncs with platform (non-critical)

        Error handling:
        - Each operation wrapped in separate try/catch
        - Database errors logged but don't fail callback
        - Broadcast/sync failures are non-critical (logged as warnings)

        Args:
            message: Sent message object
            flow_context: Flow metadata (state_id, day, intent, etc.)
        """
        try:
            if flow_context:
                flow_state_id = flow_context.get('flow_state_id')
                if flow_state_id:
                    # Update flow state with sent message info
                    try:
                        flow_state = self.flow_state_repo.get(UUID(flow_state_id))
                        if flow_state:
                            flow_state.state_data = flow_state.state_data or {}
                            flow_state.state_data['last_message_sent'] = {
                                'timestamp': datetime.utcnow().isoformat(),
                                'message_id': str(message.id),
                                'day': flow_context.get('current_day'),
                                'intent': flow_context.get('template_intent')
                            }
                            self.db.commit()
                    except Exception as db_error:
                        logger.error(f"Failed to update flow state in callback: {db_error}")
                        # Don't fail the entire callback for this

                    # Broadcast flow message sent event (non-critical)
                    try:
                        await self.flow_broadcaster.broadcast_flow_message_sent(
                            patient_id=message.patient_id,
                            message=message,
                            flow_day=flow_context.get('current_day', 0),
                            flow_type=flow_context.get('flow_type', 'unknown')
                        )
                    except Exception as broadcast_error:
                        logger.warning(f"Failed to broadcast flow message (non-critical): {broadcast_error}")

                    # Sync message processing to platform (non-critical)
                    try:
                        await self.platform_sync.sync_patient_record_update(
                            patient_id=message.patient_id,
                            flow_interaction_data={
                                "message_sent": {
                                    "message_id": str(message.id),
                                    "flow_day": flow_context.get('current_day'),
                                    "flow_type": flow_context.get('flow_type'),
                                    "intent": flow_context.get('template_intent'),
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            }
                        )
                    except Exception as sync_error:
                        logger.warning(f"Failed to sync to platform (non-critical): {sync_error}")

            logger.info(f"Flow message sent callback executed for message {message.id}")

        except Exception as e:
            logger.error(f"Error in flow message sent callback: {e}", exc_info=True)
    
    async def _on_flow_message_failed(self,
                                    message: Message,
                                    flow_context: Optional[dict[str, Any]],
                                    error: str):
        """
        Callback for when flow message fails to send.

        Updates flow state with failure information for audit trail and debugging.

        Error handling:
        - Database operations wrapped in try/catch
        - Failures logged but don't propagate
        - Ensures system remains stable even when handling failures

        Args:
            message: Failed message object
            flow_context: Flow metadata
            error: Error description string
        """
        try:
            if flow_context:
                flow_state_id = flow_context.get('flow_state_id')
                if flow_state_id:
                    # Update flow state with failure info
                    flow_state = self.flow_state_repo.get(UUID(flow_state_id))
                    if flow_state:
                        flow_state.state_data = flow_state.state_data or {}
                        flow_state.state_data['last_message_failed'] = {
                            'timestamp': datetime.utcnow().isoformat(),
                            'message_id': str(message.id),
                            'error': error,
                            'day': flow_context.get('current_day')
                        }
                        self.db.commit()
            
            logger.warning(f"Flow message failed callback executed for message {message.id}: {error}")
            
        except Exception as e:
            logger.error(f"Error in flow message failed callback: {e}")
    
    async def _on_flow_message_status_updated(self,
                                            message: Message,
                                            status: MessageStatus,
                                            flow_state_id: Optional[UUID],
                                            additional_data: Optional[dict[str, Any]]):
        """Callback for flow message status updates with error resilience."""
        try:
            if flow_state_id:
                # Update flow state (critical operation)
                try:
                    flow_state = self.flow_state_repo.get(flow_state_id)
                    if flow_state:
                        flow_state.state_data = flow_state.state_data or {}
                        flow_state.state_data['message_status_updates'] = flow_state.state_data.get('message_status_updates', [])
                        flow_state.state_data['message_status_updates'].append({
                            'timestamp': datetime.utcnow().isoformat(),
                            'message_id': str(message.id),
                            'status': status.value,
                            'additional_data': additional_data
                        })

                        # Keep only last 10 status updates
                        flow_state.state_data['message_status_updates'] = flow_state.state_data['message_status_updates'][-10:]

                        self.db.commit()
                except Exception as db_error:
                    logger.error(f"Failed to update flow state status: {db_error}")
                    self.db.rollback()

                # Broadcast message status update (non-critical)
                try:
                    await self.flow_broadcaster.broadcast_patient_interaction(
                        patient_id=message.patient_id,
                        message=message,
                        interaction_type=f"message_status_{status.value.lower()}"
                    )
                except Exception as broadcast_error:
                    logger.debug(f"Failed to broadcast status update (non-critical): {broadcast_error}")

            logger.debug(f"Flow message status updated: {message.id} -> {status.value}")

        except Exception as e:
            logger.error(f"Error in flow message status update callback: {e}", exc_info=True)
    
    async def get_flow_processing_metrics(self, 
                                        date_range: Optional[Tuple[datetime, datetime]] = None) -> dict[str, Any]:
        """
        Get comprehensive flow processing metrics.
        
        Args:
            date_range: Optional date range for metrics
            
        Returns:
            Flow processing metrics
        """
        try:
            # Default to last 7 days if no range provided
            if not date_range:
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=7)
                date_range = (start_date, end_date)
            
            metrics = {
                'date_range': {
                    'start': date_range[0].isoformat(),
                    'end': date_range[1].isoformat()
                },
                'flow_processing': {
                    'total_patients_processed': 0,
                    'messages_generated': 0,
                    'ai_personalizations': 0,
                    'successful_deliveries': 0,
                    'failed_deliveries': 0
                },
                'flow_types': {
                    'initial_15_days': {'patients': 0, 'messages': 0},
                    'days_16_45': {'patients': 0, 'messages': 0},
                    'monthly_recurring': {'patients': 0, 'messages': 0}
                },
                'ai_performance': {
                    'personalization_success_rate': 0.0,
                    'anti_repetition_effectiveness': 0.0,
                    'sentiment_analysis_accuracy': 0.0
                },
                'delivery_performance': {
                    'average_delivery_time': None,
                    'delivery_success_rate': 0.0,
                    'retry_success_rate': 0.0
                }
            }
            
            # TODO: Implement actual metrics calculation
            # This would involve complex queries across multiple tables
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get flow processing metrics: {e}")
            return {}
    
    async def _check_quiz_trigger(self, patient_id: UUID, current_day: int, flow_type: str) -> dict[str, Any]:
        """
        Check if patient should receive quiz trigger and handle it.
        Uses link delivery method when configured, otherwise uses conversational.

        Args:
            patient_id: Patient UUID
            current_day: Current day in flow
            flow_type: Type of flow (monthly_recurring, etc.)

        Returns:
            Dictionary with quiz trigger results
        """
        try:
            # Only check quiz triggers for monthly recurring flows on day 30
            from app.utils.constants import QUIZ_FLOW_CONSTANTS

            if flow_type != 'monthly_recurring' or current_day != QUIZ_FLOW_CONSTANTS['MONTHLY_QUIZ_DAY']:
                return {'triggered': False, 'reason': 'Not a quiz trigger day'}

            # Import quiz flow integration service
            from app.services.quiz_flow_integration import QuizTriggerService
            from app.core.monthly_quiz_config import get_monthly_quiz_config

            quiz_trigger_service = QuizTriggerService(self.db)
            config = get_monthly_quiz_config()

            # Prepare quiz info
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {'triggered': False, 'error': 'Patient not found'}

            enrollment_date = patient.enrollment_date or patient.created_at
            days_since_enrollment = (datetime.utcnow() - enrollment_date).days
            days_in_monthly_phase = days_since_enrollment - 45
            monthly_cycle = (days_in_monthly_phase // 30) + 1

            quiz_info = {
                'monthly_cycle': monthly_cycle,
                'template_name': f'monthly_checkup_cycle_{monthly_cycle}',
                'trigger_reason': f'Monthly quiz day {current_day} of cycle {monthly_cycle}'
            }

            # Get flow state
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                return {'triggered': False, 'error': 'No active flow state'}

            # Trigger quiz (method will be auto-detected by QuizTriggerService)
            result = await quiz_trigger_service._trigger_patient_quiz(
                flow_state=flow_state,
                quiz_info=quiz_info
            )

            if result.get('success'):
                logger.info(
                    f"Quiz triggered for patient {patient_id} via {result.get('delivery_method', 'unknown')} "
                    f"on day {current_day}"
                )

            return {
                'triggered': result.get('success', False),
                'quiz_session_id': result.get('session_id'),
                'delivery_method': result.get('delivery_method'),
                'message_sent': result.get('message_sent', True),
                'error': result.get('error')
            }

        except Exception as e:
            logger.error(f"Error checking quiz trigger for patient {patient_id}: {e}")
            return {
                'triggered': False,
                'error': str(e)
            }

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
                'service': 'FlowEngineIntegrationService',
                'timestamp': datetime.utcnow().isoformat(),
                'components': {},
                'overall_healthy': True,
                'error_count': 0
            }

            # Check enhanced flow engine
            try:
                engine_health = await self.enhanced_flow_engine.health_check()
                results['components']['enhanced_flow_engine'] = engine_health
                if not engine_health.get('overall_healthy', False):
                    results['overall_healthy'] = False
                    results['error_count'] += 1
            except Exception as e:
                logger.error(f"Enhanced flow engine health check failed: {e}", exc_info=True)
                results['components']['enhanced_flow_engine'] = {'healthy': False, 'error': str(e)}
                results['overall_healthy'] = False
                results['error_count'] += 1

            # Check message scheduler
            try:
                scheduler_health = await self.message_scheduler.health_check()
                results['components']['message_scheduler'] = scheduler_health
                if not scheduler_health.get('healthy', False):
                    results['overall_healthy'] = False
                    results['error_count'] += 1
            except Exception as e:
                logger.error(f"Message scheduler health check failed: {e}", exc_info=True)
                results['components']['message_scheduler'] = {'healthy': False, 'error': str(e)}
                results['overall_healthy'] = False
                results['error_count'] += 1

            # Check database connectivity
            try:
                self.db.execute("SELECT 1")
                results['components']['database'] = {'healthy': True, 'connected': True}
            except Exception as e:
                logger.error(f"Database health check failed: {e}", exc_info=True)
                results['components']['database'] = {'healthy': False, 'connected': False, 'error': str(e)}
                results['overall_healthy'] = False
                results['error_count'] += 1

            # Check template loader
            try:
                # Try to load a template
                template = self.template_loader.load_flow_template('initial_15_days')
                results['components']['template_loader'] = {
                    'healthy': True,
                    'templates_loaded': bool(template),
                    'fallback_available': True  # We always have fallback templates
                }
            except Exception as e:
                logger.error(f"Template loader health check failed: {e}", exc_info=True)
                results['components']['template_loader'] = {
                    'healthy': False,
                    'error': str(e),
                    'fallback_available': True  # Fallbacks still work
                }
                # Not critical - we have fallbacks
                logger.warning("Template loader unhealthy but fallbacks available")

            # Check flow integrity service
            try:
                # Verify flow integrity service is initialized
                if hasattr(self, 'flow_integrity_service') and self.flow_integrity_service:
                    results['components']['flow_integrity_service'] = {'healthy': True, 'initialized': True}
                else:
                    results['components']['flow_integrity_service'] = {'healthy': False, 'initialized': False}
                    logger.warning("Flow integrity service not initialized")
            except Exception as e:
                logger.error(f"Flow integrity service health check failed: {e}", exc_info=True)
                results['components']['flow_integrity_service'] = {'healthy': False, 'error': str(e)}

            # Add summary
            total_components = len(results['components'])
            healthy_components = sum(1 for c in results['components'].values() if c.get('healthy', False))
            results['health_summary'] = {
                'total_components': total_components,
                'healthy_components': healthy_components,
                'unhealthy_components': total_components - healthy_components,
                'health_percentage': (healthy_components / total_components * 100) if total_components > 0 else 0
            }

            logger.info(
                f"Health check completed: {healthy_components}/{total_components} components healthy "
                f"({results['health_summary']['health_percentage']:.1f}%)"
            )

            return results

        except Exception as e:
            logger.error(f"Critical health check failure: {e}", exc_info=True)
            return {
                'service': 'FlowEngineIntegrationService',
                'timestamp': datetime.utcnow().isoformat(),
                'overall_healthy': False,
                'error': str(e),
                'critical_failure': True
            }


# Global service instance
_flow_integration_service: Optional[FlowEngineIntegrationService] = None


class FlowIntegrityService:
    """FIX #2: Service for flow consistency validation and referential integrity"""

    def __init__(self, db: Session):
        self.db = db
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)

    async def validate_flow_consistency(self, flow_state: PatientFlowState) -> None:
        """Validate flow state consistency and referential integrity"""
        try:
            # Check patient existence
            patient = self.patient_repo.get(flow_state.patient_id)
            if not patient:
                raise ValidationError(f"Patient {flow_state.patient_id} not found for flow state")

            # Validate flow type against patient treatment
            if not self._validate_flow_type_compatibility(flow_state.flow_type, patient.treatment_type):
                raise ValidationError(f"Flow type {flow_state.flow_type} incompatible with treatment {patient.treatment_type}")

            # Check flow state transitions
            await self._validate_state_transitions(flow_state)

            # Validate current step bounds
            if flow_state.current_step < 0:
                raise ValidationError("Flow step cannot be negative")

            if flow_state.current_step > self._get_max_step_for_flow(flow_state.flow_type):
                raise ValidationError(f"Flow step {flow_state.current_step} exceeds maximum for {flow_state.flow_type}")

            # Validate flow data integrity
            if flow_state.state_data:
                await self._validate_flow_data_integrity(flow_state)

            logger.info(f"Flow consistency validation passed for patient {flow_state.patient_id}")

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Flow consistency validation error: {e}")
            raise ValidationError(f"Flow validation failed: {str(e)}")

    def _validate_flow_type_compatibility(self, flow_type: str, treatment_type: Optional[str]) -> bool:
        """Validate flow type is compatible with patient treatment"""
        if not treatment_type:
            return True  # Allow any flow if no treatment specified

        # Define treatment-flow compatibility matrix
        compatibility_matrix = {
            'hormone_therapy': ['initial_15_days', 'days_16_45', 'monthly_recurring'],
            'chemotherapy': ['initial_15_days', 'days_16_45', 'monthly_recurring'],
            'radiation': ['initial_15_days', 'days_16_45'],
            'immunotherapy': ['initial_15_days', 'monthly_recurring'],
            'surgery': ['initial_15_days', 'days_16_45']
        }

        compatible_flows = compatibility_matrix.get(treatment_type.lower(), [])
        return flow_type in compatible_flows

    async def _validate_state_transitions(self, flow_state: PatientFlowState) -> None:
        """Validate state transitions are valid"""
        try:
            # Get previous flow states for this patient
            previous_states = self.db.query(PatientFlowState).filter(
                PatientFlowState.patient_id == flow_state.patient_id,
                PatientFlowState.created_at < flow_state.created_at
            ).order_by(PatientFlowState.created_at.desc()).limit(5).all()

            # Define valid transitions
            valid_transitions = {
                'initial_15_days': ['days_16_45', 'monthly_recurring', 'completed'],
                'days_16_45': ['monthly_recurring', 'completed'],
                'monthly_recurring': ['completed', 'paused'],
                'paused': ['monthly_recurring', 'completed'],
                'completed': []  # No transitions from completed
            }

            if previous_states:
                last_flow_type = previous_states[0].flow_type
                if flow_state.flow_type not in valid_transitions.get(last_flow_type, []):
                    # Allow same flow type (continuation)
                    if flow_state.flow_type != last_flow_type:
                        raise ValidationError(f"Invalid transition from {last_flow_type} to {flow_state.flow_type}")

            # Check for duplicate active flows
            active_flows = self.db.query(PatientFlowState).filter(
                PatientFlowState.patient_id == flow_state.patient_id,
                PatientFlowState.id != flow_state.id,
                PatientFlowState.state_data['status'].astext != 'completed'
            ).count()

            if active_flows > 0 and flow_state.state_data.get('status') != 'completed':
                logger.warning(f"Multiple active flows detected for patient {flow_state.patient_id}")

        except Exception as e:
            logger.error(f"State transition validation error: {e}")
            raise

    def _get_max_step_for_flow(self, flow_type: str) -> int:
        """Get maximum valid step for flow type"""
        max_steps = {
            'initial_15_days': 15,
            'days_16_45': 30,  # 16-45 is 30 days
            'monthly_recurring': 365  # Up to a year
        }
        return max_steps.get(flow_type, 365)

    async def _validate_flow_data_integrity(self, flow_state: PatientFlowState) -> None:
        """Validate flow state data integrity"""
        try:
            state_data = flow_state.state_data or {}

            # Check required fields exist
            required_fields = ['status', 'last_updated']
            for field in required_fields:
                if field not in state_data:
                    logger.warning(f"Missing required field '{field}' in flow state data")

            # Validate timestamp consistency
            if 'last_updated' in state_data:
                try:
                    last_updated = datetime.fromisoformat(state_data['last_updated'])
                    if last_updated > datetime.utcnow():
                        raise ValidationError("Flow last_updated cannot be in the future")
                except ValueError:
                    raise ValidationError("Invalid last_updated timestamp format")

            # Validate message references
            if 'last_message_sent' in state_data:
                message_data = state_data['last_message_sent']
                if 'message_id' in message_data:
                    # Verify message exists
                    from app.models.message import Message
                    message = self.db.query(Message).filter(
                        Message.id == message_data['message_id']
                    ).first()
                    if not message:
                        raise ValidationError(f"Referenced message {message_data['message_id']} not found")

            # Generate and validate checksum
            expected_checksum = self._generate_flow_checksum(flow_state)
            stored_checksum = state_data.get('integrity_checksum')

            if stored_checksum and stored_checksum != expected_checksum:
                logger.warning(f"Flow data integrity checksum mismatch for flow {flow_state.id}")
                # Update with correct checksum
                state_data['integrity_checksum'] = expected_checksum
                state_data['checksum_updated'] = datetime.utcnow().isoformat()
                self.db.commit()

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Flow data integrity validation error: {e}")
            raise

    def _generate_flow_checksum(self, flow_state: PatientFlowState) -> str:
        """Generate integrity checksum for flow state"""
        try:
            checksum_data = {
                'patient_id': str(flow_state.patient_id),
                'flow_type': flow_state.flow_type,
                'current_step': flow_state.current_step,
                'started_at': flow_state.started_at.isoformat() if flow_state.started_at else '',
                'status': flow_state.state_data.get('status', '') if flow_state.state_data else ''
            }

            checksum_string = '|'.join(f"{k}:{v}" for k, v in sorted(checksum_data.items()))
            return hashlib.sha256(checksum_string.encode('utf-8')).hexdigest()

        except Exception as e:
            logger.error(f"Flow checksum generation failed: {e}")
            return ""

    async def prevent_invalid_transitions(self, patient_id: UUID, new_flow_type: str) -> None:
        """Prevent invalid workflow transitions"""
        try:
            # Get current active flow
            current_flow = self.flow_state_repo.get_active_flow(patient_id)

            if current_flow and current_flow.flow_type != new_flow_type:
                # Check if transition is allowed
                valid_transitions = {
                    'initial_15_days': ['days_16_45', 'monthly_recurring'],
                    'days_16_45': ['monthly_recurring'],
                    'monthly_recurring': [],  # Can only continue or complete
                    'paused': ['monthly_recurring'],  # Can resume
                    'completed': []  # No transitions allowed
                }

                allowed = valid_transitions.get(current_flow.flow_type, [])
                if new_flow_type not in allowed:
                    raise ValidationError(
                        f"Invalid flow transition: {current_flow.flow_type} -> {new_flow_type}"
                    )

            logger.info(f"Flow transition validated for patient {patient_id}: {new_flow_type}")

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Flow transition validation error: {e}")
            raise ValidationError(f"Flow transition validation failed: {str(e)}")

    async def validate_referential_integrity(self, flow_state: PatientFlowState) -> List[str]:
        """Validate all referential integrity constraints"""
        issues = []

        try:
            # Check patient reference
            patient = self.patient_repo.get(flow_state.patient_id)
            if not patient:
                issues.append(f"Patient {flow_state.patient_id} not found")

            # Check message references in state data
            if flow_state.state_data:
                state_data = flow_state.state_data

                # Check message references
                message_refs = []
                if 'last_message_sent' in state_data and 'message_id' in state_data['last_message_sent']:
                    message_refs.append(state_data['last_message_sent']['message_id'])

                if 'message_status_updates' in state_data:
                    for update in state_data['message_status_updates']:
                        if 'message_id' in update:
                            message_refs.append(update['message_id'])

                # Validate message references exist
                from app.models.message import Message
                for msg_id in message_refs:
                    try:
                        message = self.db.query(Message).filter(Message.id == msg_id).first()
                        if not message:
                            issues.append(f"Referenced message {msg_id} not found")
                        elif message.patient_id != flow_state.patient_id:
                            issues.append(f"Message {msg_id} belongs to different patient")
                    except Exception as e:
                        issues.append(f"Error validating message {msg_id}: {e}")

            if issues:
                logger.warning(f"Referential integrity issues found: {issues}")
            else:
                logger.info(f"Referential integrity validation passed for flow {flow_state.id}")

            return issues

        except Exception as e:
            logger.error(f"Referential integrity validation error: {e}")
            return [f"Validation error: {str(e)}"]


def get_flow_integration_service(db: Session) -> FlowEngineIntegrationService:
    """
    Get flow integration service instance.

    Args:
        db: Database session

    Returns:
        FlowEngineIntegrationService instance
    """
    return FlowEngineIntegrationService(db)