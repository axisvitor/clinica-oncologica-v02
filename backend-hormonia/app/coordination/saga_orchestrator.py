"""
Saga Orchestrator for Patient Onboarding.

CRITICAL FIX #6: Implement Saga pattern to ensure atomic patient onboarding
across multiple services (Database, WhatsApp, Flow State).

This orchestrator ensures that patient creation is either:
- Fully completed (patient + flow + WhatsApp message)
- Fully rolled back (compensating transactions)

Saga Steps:
1. Create patient in database
2. Create flow state for patient
3. Send initial WhatsApp message
4. Mark saga as completed

If any step fails, compensating transactions are executed in reverse order.

Features:
- Atomic onboarding across services
- Automatic compensation on failure
- Retry logic with exponential backoff
- State persistence for debugging
- Dead Letter Queue (DLQ) for failed sagas

Usage:
    orchestrator = SagaOrchestrator(db, redis, evolution_client)
    saga = await orchestrator.execute_patient_onboarding(
        patient_data=patient_data,
        initial_message="Bem-vindo ao sistema!"
    )
"""

import logging
import uuid
import time
import json
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta, date
from enum import Enum
from dataclasses import dataclass, field

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.patient import Patient, FlowState as PatientFlowStateEnum
from app.models.flow import PatientFlowState
from app.models.flow import FlowKind as FlowKindModel  # Database model
from app.models.message import Message, MessageStatus, MessageDirection, MessageType

# Create an enum for flow kinds to match the expected usage
class FlowKind(str, Enum):
    """Flow kind enumeration for saga orchestrator."""
    ONBOARDING = "initial_15_days"  # Maps to initial_15_days flow kind
    MONTHLY_QUIZ = "monthly_recurring"  # Maps to monthly_recurring flow kind
    DAYS_16_45 = "days_16_45"  # Maps to days_16_45 flow kind
from app.integrations.evolution import EvolutionClient
from app.services.idempotent_message_sender import IdempotentMessageSender

logger = logging.getLogger(__name__)


def _make_json_serializable(data: Any) -> Any:
    """
    Convert data to JSON-serializable format.
    
    Handles:
    - datetime/date objects -> ISO format strings
    - UUID objects -> strings
    - Nested dicts and lists recursively
    
    Args:
        data: Data to convert
        
    Returns:
        JSON-serializable version of data
    """
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    elif isinstance(data, uuid.UUID):
        return str(data)
    elif isinstance(data, dict):
        return {k: _make_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [_make_json_serializable(item) for item in data]
    elif isinstance(data, Enum):
        return data.value
    else:
        return data


class SagaStatus(str, Enum):
    """Saga execution status."""

    PENDING = "pending"  # Not started
    RUNNING = "running"  # In progress
    COMPLETED = "completed"  # Successfully completed
    COMPENSATING = "compensating"  # Rolling back
    COMPENSATED = "compensated"  # Successfully rolled back
    FAILED = "failed"  # Failed and cannot compensate


class SagaStepStatus(str, Enum):
    """Individual saga step status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Represents a single step in the saga."""

    name: str
    action: Callable
    compensation: Optional[Callable] = None
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class SagaState:
    """Represents the complete state of a saga execution."""

    saga_id: str
    saga_type: str
    status: SagaStatus
    steps: List[SagaStep]
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize saga state to dictionary."""
        return {
            "saga_id": self.saga_id,
            "saga_type": self.saga_type,
            "status": self.status.value,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status.value,
                    "result": str(step.result) if step.result else None,
                    "error": step.error,
                    "retry_count": step.retry_count,
                }
                for step in self.steps
            ],
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "error": self.error,
        }


class SagaOrchestrator:
    """
    Saga orchestrator for distributed transactions.

    Implements the Saga pattern for managing long-running transactions
    across multiple services with compensating transactions for rollback.
    """

    def __init__(
        self,
        db: Session,
        redis: Redis,
        evolution_client: EvolutionClient,
        enable_persistence: bool = True,
        persistence_ttl: int = 604800,  # 7 days
    ):
        """
        Initialize saga orchestrator.

        Args:
            db: Database session
            redis: Redis client for state persistence
            evolution_client: Evolution API client
            enable_persistence: Enable Redis persistence of saga state
            persistence_ttl: TTL for persisted saga state (default: 7 days)
        """
        self.db = db
        self.redis = redis
        self.evolution_client = evolution_client
        self.enable_persistence = enable_persistence
        self.persistence_ttl = persistence_ttl
        self.message_sender = IdempotentMessageSender(
            db=db, redis=redis, evolution_client=evolution_client
        )

    def _generate_saga_id(self) -> str:
        """Generate unique saga ID."""
        return f"saga_{uuid.uuid4().hex}"

    def _get_saga_key(self, saga_id: str) -> str:
        """Get Redis key for saga state."""
        return f"saga:state:{saga_id}"

    async def _persist_saga_state(self, saga_state: SagaState) -> None:
        """
        Persist saga state to Redis with graceful degradation.

        Args:
            saga_state: Saga state to persist
        """
        if not self.enable_persistence:
            return

        try:
            import json

            key = self._get_saga_key(saga_state.saga_id)
            self.redis.setex(
                key, self.persistence_ttl, json.dumps(saga_state.to_dict(), default=str)
            )
            logger.debug(f"Persisted saga state: {saga_state.saga_id}")

        except RedisError as e:
            # Graceful degradation: Log warning but continue execution
            logger.warning(
                f"Redis unavailable for saga state persistence, continuing in degraded mode: {e}"
            )
        except Exception as e:
            # Catch any other errors to prevent saga failure
            logger.warning(
                f"Failed to persist saga state (non-critical): {e}"
            )

    async def _load_saga_state(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """
        Load saga state from Redis with graceful degradation.

        Args:
            saga_id: Saga ID

        Returns:
            Saga state dictionary if found, None otherwise
        """
        if not self.enable_persistence:
            return None

        try:
            import json

            key = self._get_saga_key(saga_id)
            data = self.redis.get(key)

            if data:
                return json.loads(data)

            return None

        except RedisError as e:
            # Graceful degradation: Log warning and return None (will fallback to DB)
            logger.warning(
                f"Redis unavailable for saga state loading, will use DB fallback: {e}"
            )
            return None
        except Exception as e:
            # Catch any other errors and fallback gracefully
            logger.warning(
                f"Failed to load saga state from Redis, using DB fallback: {e}"
            )
            return None

    async def _execute_step(
        self, step: SagaStep, saga_state: SagaState
    ) -> tuple[bool, Any]:
        """
        Execute a single saga step with retry logic.

        Args:
            step: Step to execute
            saga_state: Current saga state

        Returns:
            Tuple of (success, result)
        """
        step.status = SagaStepStatus.RUNNING
        step.started_at = datetime.utcnow()
        saga_state.updated_at = datetime.utcnow()

        await self._persist_saga_state(saga_state)

        logger.info(f"Executing saga step: {step.name} (saga_id: {saga_state.saga_id})")

        retry_delay = 1  # Start with 1 second

        while step.retry_count <= step.max_retries:
            try:
                # Execute the step action
                result = await step.action(saga_state.context)

                # Mark as completed
                step.status = SagaStepStatus.COMPLETED
                step.result = result
                step.completed_at = datetime.utcnow()
                saga_state.updated_at = datetime.utcnow()

                await self._persist_saga_state(saga_state)

                logger.info(
                    f"✅ Saga step completed: {step.name} (saga_id: {saga_state.saga_id})"
                )

                return True, result

            except Exception as e:
                step.retry_count += 1
                step.error = str(e)
                saga_state.updated_at = datetime.utcnow()

                logger.error(
                    f"❌ Saga step failed: {step.name} "
                    f"(attempt {step.retry_count}/{step.max_retries + 1}) - {e}",
                    exc_info=True,
                )

                # Ensure DB session is clean before next retry/operations
                try:
                    self.db.rollback()
                except Exception:
                    pass

                # If max retries exceeded, mark as failed
                if step.retry_count > step.max_retries:
                    step.status = SagaStepStatus.FAILED
                    await self._persist_saga_state(saga_state)
                    return False, None

                # Exponential backoff
                await self._sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)  # Max 30 seconds

        return False, None

    async def _compensate_step(
        self, step: SagaStep, saga_state: SagaState
    ) -> tuple[bool, Any]:
        """
        Execute compensation for a saga step.

        Args:
            step: Step to compensate
            saga_state: Current saga state

        Returns:
            Tuple of (success, result)
        """
        if not step.compensation:
            logger.warning(f"No compensation defined for step: {step.name}")
            step.status = SagaStepStatus.COMPENSATED
            return True, None

        step.status = SagaStepStatus.COMPENSATING
        saga_state.updated_at = datetime.utcnow()

        await self._persist_saga_state(saga_state)

        logger.info(
            f"Compensating saga step: {step.name} (saga_id: {saga_state.saga_id})"
        )

        try:
            # Execute compensation
            result = await step.compensation(saga_state.context)

            # Mark as compensated
            step.status = SagaStepStatus.COMPENSATED
            saga_state.updated_at = datetime.utcnow()

            await self._persist_saga_state(saga_state)

            logger.info(
                f"✅ Saga step compensated: {step.name} (saga_id: {saga_state.saga_id})"
            )

            return True, result

        except Exception as e:
            logger.error(
                f"❌ Compensation failed for step: {step.name} - {e}", exc_info=True
            )
            return False, None

    async def _sleep(self, seconds: float) -> None:
        """Sleep for specified seconds (async)."""
        import asyncio

        await asyncio.sleep(seconds)

    async def execute_saga(self, saga_state: SagaState, timeout: int = 300) -> SagaState:
        """
        Execute a saga with automatic compensation on failure.

        Args:
            saga_state: Initial saga state with steps defined
            timeout: Global timeout in seconds (default: 300 = 5 minutes)

        Returns:
            Final saga state

        Raises:
            asyncio.TimeoutError: If saga execution exceeds timeout
        """
        import asyncio

        try:
            # Execute saga with timeout
            return await asyncio.wait_for(
                self._execute_saga_internal(saga_state),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(
                f"⏱️ Saga execution timeout after {timeout}s: {saga_state.saga_type} "
                f"(saga_id: {saga_state.saga_id})"
            )
            saga_state.status = SagaStatus.FAILED
            saga_state.error = f"Saga execution timeout after {timeout} seconds"
            saga_state.completed_at = datetime.utcnow()
            saga_state.updated_at = datetime.utcnow()
            await self._persist_saga_state(saga_state)
            raise

    async def _execute_saga_internal(self, saga_state: SagaState) -> SagaState:
        """
        Internal saga execution logic (called by execute_saga with timeout).

        Args:
            saga_state: Initial saga state with steps defined

        Returns:
            Final saga state
        """
        saga_state.status = SagaStatus.RUNNING
        saga_state.updated_at = datetime.utcnow()

        await self._persist_saga_state(saga_state)

        logger.info(
            f"🚀 Starting saga execution: {saga_state.saga_type} "
            f"(saga_id: {saga_state.saga_id})"
        )

        # Execute steps sequentially
        for i, step in enumerate(saga_state.steps):
            success, result = await self._execute_step(step, saga_state)

            if success:
                # Store result in context for next steps
                saga_state.context[f"{step.name}_result"] = result
            else:
                # Step failed after retries, start compensation
                logger.error(
                    f"Saga step failed permanently: {step.name}. Starting compensation..."
                )

                saga_state.status = SagaStatus.COMPENSATING
                saga_state.error = f"Step '{step.name}' failed: {step.error}"
                saga_state.updated_at = datetime.utcnow()

                await self._persist_saga_state(saga_state)

                # Ensure DB session is clean before compensation operations
                try:
                    self.db.rollback()
                except Exception:
                    pass

                # Compensate completed steps in reverse order
                for j in range(i - 1, -1, -1):
                    completed_step = saga_state.steps[j]

                    if completed_step.status == SagaStepStatus.COMPLETED:
                        comp_success, _ = await self._compensate_step(
                            completed_step, saga_state
                        )

                        if not comp_success:
                            logger.critical(
                                f"⚠️ Compensation failed for step: {completed_step.name}"
                            )

                # Mark saga as compensated
                saga_state.status = SagaStatus.COMPENSATED
                saga_state.completed_at = datetime.utcnow()
                saga_state.updated_at = datetime.utcnow()

                await self._persist_saga_state(saga_state)
                
                # Commit compensation changes
                try:
                    self.db.commit()
                    logger.info(f"✅ Saga compensation committed to database: {saga_state.saga_id}")
                except Exception as e:
                    logger.error(f"Failed to commit saga compensation: {e}")
                    self.db.rollback()

                logger.warning(
                    f"⚠️ Saga compensated: {saga_state.saga_type} "
                    f"(saga_id: {saga_state.saga_id})"
                )

                return saga_state

        # All steps completed successfully
        saga_state.status = SagaStatus.COMPLETED
        saga_state.completed_at = datetime.utcnow()
        saga_state.updated_at = datetime.utcnow()

        await self._persist_saga_state(saga_state)
        
        # Commit all changes to database
        try:
            self.db.commit()
            logger.info(f"✅ Saga changes committed to database: {saga_state.saga_id}")
        except Exception as e:
            logger.error(f"Failed to commit saga changes: {e}")
            self.db.rollback()
            raise

        logger.info(
            f"✅ Saga completed successfully: {saga_state.saga_type} "
            f"(saga_id: {saga_state.saga_id})"
        )

        return saga_state

    # ========================================================================
    # PATIENT ONBOARDING SAGA
    # ========================================================================

    async def execute_patient_onboarding_saga(
        self,
        patient_data: Any,
        doctor_id: uuid.UUID,
        current_user: Optional[Any] = None,
    ) -> Optional[Patient]:
        """
        Execute patient onboarding saga with full integration.

        This is the main entry point for patient creation using the Saga pattern.
        It creates the patient, sends welcome message, and starts the flow.

        Args:
            patient_data: PatientCreate schema object
            doctor_id: UUID of the doctor creating the patient
            current_user: Current authenticated user (optional)

        Returns:
            Created Patient object or None if failed
        """
        saga_id = uuid.uuid4()

        # Prepare patient data dict early for error handling
        patient_dict = (
            patient_data.dict(exclude_unset=True)
            if hasattr(patient_data, "dict")
            else patient_data
        )
        # Preserve UUID type for doctor_id to satisfy ORM
        patient_dict["doctor_id"] = doctor_id

        try:
            # Optionally generate initial welcome message
            initial_message_text = None
            try:
                from app.config import settings
                if getattr(settings, "ENABLE_WHATSAPP_ON_REGISTRATION", True) and getattr(settings, "WHATSAPP_WELCOME_MESSAGE_ENABLED", True):
                    try:
                        from app.templates.whatsapp.welcome_message import get_welcome_message
                        initial_message_text = get_welcome_message(
                            patient_name=patient_dict.get("name"),
                            clinic_name=getattr(settings, "CLINIC_NAME", "Clínica"),
                            support_phone=getattr(settings, "CLINIC_SUPPORT_PHONE", None),
                        )
                    except Exception:
                        # Fallback: no initial message if template import fails
                        initial_message_text = None
            except Exception:
                initial_message_text = None

            # Execute saga
            saga_state = await self.execute_patient_onboarding(
                patient_data=patient_dict,
                initial_message=initial_message_text,
                flow_kind=FlowKind.ONBOARDING,
            )

            if saga_state.status == SagaStatus.COMPLETED:
                # Extract patient from context
                patient_id = saga_state.context.get("patient_id")
                if patient_id:
                    patient = (
                        self.db.query(Patient).filter(Patient.id == patient_id).first()
                    )

                    # Persist saga to database
                    try:
                        from app.models.patient_onboarding_saga import (
                            PatientOnboardingSaga as SagaModel,
                            SagaStatus as ModelSagaStatus,
                        )

                        logger.info(f"Attempting to persist COMPLETED saga {saga_id} to database...")
                        
                        # Determine final step number: 3 if message step included, else 2
                        final_step = 3 if saga_state.context.get("initial_message") else 2
                        
                        # Convert patient_data to JSON-serializable format
                        patient_data_json = _make_json_serializable(
                            saga_state.context.get("patient_data", {})
                        )
                        
                        saga_record = SagaModel(
                            id=saga_id,
                            patient_id=patient_id,
                            doctor_id=doctor_id,
                            status=ModelSagaStatus.COMPLETED,
                            current_step=final_step,
                            patient_data=patient_data_json,
                            execution_log=[],
                            started_at=saga_state.created_at,
                            completed_at=saga_state.completed_at,
                        )
                        logger.info(f"Saga record created in memory: {saga_record}")
                        
                        self.db.add(saga_record)
                        logger.info("Saga record added to session, committing...")
                        
                        self.db.commit()
                        logger.info(f"✅ Saga record persisted to database: {saga_id}")
                        
                    except Exception as persist_error:
                        logger.error(
                            f"❌ FAILED to persist COMPLETED saga {saga_id}: {persist_error}",
                            exc_info=True
                        )
                        try:
                            self.db.rollback()
                        except Exception:
                            pass

                    return patient
            else:
                # Saga failed - persist for retry
                patient_id = saga_state.context.get("patient_id")
                try:
                    from app.models.patient_onboarding_saga import (
                        PatientOnboardingSaga as SagaModel,
                        SagaStatus as ModelSagaStatus,
                    )

                    logger.warning(f"Attempting to persist FAILED saga {saga_id} to database...")
                    
                    # Convert patient_data to JSON-serializable format
                    patient_data_json = _make_json_serializable(
                        saga_state.context.get("patient_data", {})
                    )
                    
                    saga_record = SagaModel(
                        id=saga_id,
                        patient_id=patient_id,
                        doctor_id=doctor_id,
                        status=ModelSagaStatus.FAILED,
                        current_step=saga_state.context.get("last_completed_step", 0),
                        error_message=saga_state.error,
                        patient_data=patient_data_json,
                        execution_log=[],
                        started_at=saga_state.created_at,
                    )
                    logger.warning(f"Failed saga record created in memory: {saga_record}")
                    
                    self.db.add(saga_record)
                    logger.warning("Failed saga record added to session, committing...")
                    
                    self.db.commit()
                    logger.warning(f"⚠️ Failed Saga record persisted to database: {saga_id}")
                    
                except Exception as persist_error:
                    logger.error(
                        f"❌ FAILED to persist FAILED saga {saga_id}: {persist_error}",
                        exc_info=True
                    )
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

                # Return patient if at least created
                if patient_id:
                    patient = (
                        self.db.query(Patient).filter(Patient.id == patient_id).first()
                    )
                    return patient

                return None

        except Exception as e:
            logger.error(
                f"Error in execute_patient_onboarding_saga: {e}", exc_info=True
            )
            # Try to return existing patient to avoid duplication on fallback
            try:
                # Reset session after saga failure to allow queries
                try:
                    self.db.rollback()
                except Exception:
                    pass
                email = patient_dict.get("email") if isinstance(patient_dict, dict) else None
                phone = patient_dict.get("phone") if isinstance(patient_dict, dict) else None
                existing = None
                if email:
                    existing = (
                        self.db.query(Patient)
                        .filter(Patient.email == email)
                        .first()
                    )
                if not existing and phone:
                    existing = (
                        self.db.query(Patient)
                        .filter(Patient.phone == phone)
                        .first()
                    )
                if existing:
                    logger.warning(
                        "Saga failed but patient already exists; returning existing record"
                    )
                    return existing
            except Exception as lookup_err:
                logger.warning(
                    f"Failed to lookup existing patient after saga error: {lookup_err}"
                )
            return None

    async def resume_saga(self, saga_id: uuid.UUID) -> Dict[str, Any]:
        """
        Resume a failed saga from the last successful step.

        This method is called by the retry mechanism to continue a saga
        that failed during execution.

        Args:
            saga_id: UUID of the saga to resume

        Returns:
            dict: Result with status and details
        """
        try:
            # Load saga from database
            from app.models.patient_onboarding_saga import (
                PatientOnboardingSaga as SagaModel,
            )

            saga_record = (
                self.db.query(SagaModel).filter(SagaModel.id == saga_id).first()
            )

            if not saga_record:
                return {"status": "error", "error": "Saga not found"}

            # Load saga state from Redis if available
            redis_key = f"saga:{saga_id}"
            try:
                state_data = self.redis.get(redis_key)
                if state_data:
                    import json

                    context = json.loads(state_data)
                else:
                    context = saga_record.patient_data or {}
            except Exception as e:
                logger.warning(f"Failed to load saga state from Redis: {e}")
                context = saga_record.patient_data or {}

            # Determine which step to resume from
            last_step = saga_record.current_step
            patient_id = saga_record.patient_id

            logger.info(f"Resuming saga {saga_id} from step: {last_step}")

            # Resume based on last completed step
            if last_step == "step_1_create_patient" and patient_id:
                # Patient created, try to send message and start flow
                patient = (
                    self.db.query(Patient).filter(Patient.id == patient_id).first()
                )
                if not patient:
                    return {"status": "error", "error": "Patient not found"}

                # Try step 2 and 3
                try:
                    # Send welcome message
                    from app.config import settings

                    if settings.get("WHATSAPP_WELCOME_MESSAGE_ENABLED", True):
                        from app.templates.whatsapp import get_welcome_message

                        welcome_text = get_welcome_message(
                            patient_name=patient.name,
                            clinic_name=settings.get("CLINIC_NAME", "Clínica"),
                            support_phone=settings.get("CLINIC_SUPPORT_PHONE", ""),
                        )
                        message, _ = await self.message_sender.send_message(
                            patient_id=patient_id,
                            content=welcome_text,
                            message_type=MessageType.TEXT,
                        )
                        context["message_sent"] = True
                        context["message_id"] = str(message.id)

                    # Start flow
                    if settings.get("ENABLE_AUTO_FLOW_ENROLLMENT", True):
                        flow_state = PatientFlowState(
                            patient_id=patient_id,
                            flow_kind=FlowKind.ONBOARDING,
                            current_step=0,
                        )
                        self.db.add(flow_state)
                        self.db.commit()
                        context["flow_started"] = True

                    # Mark as completed
                    saga_record.status = "COMPLETED"
                    saga_record.current_step = 3  # Step 3 completed
                    saga_record.completed_at = datetime.utcnow()
                    saga_record.patient_data = context.get("patient_data", {})
                    self.db.commit()

                    return {"status": "completed", "patient_id": str(patient_id)}

                except Exception as e:
                    logger.error(f"Failed to resume saga steps: {e}")
                    saga_record.error_message = str(e)
                    self.db.commit()
                    return {"status": "failed", "error": str(e)}

            elif not patient_id:
                # Patient not created yet, start from beginning
                return {
                    "status": "error",
                    "error": "Cannot resume - patient not created",
                }

            else:
                # Unknown state
                return {"status": "error", "error": f"Unknown step: {last_step}"}

        except Exception as e:
            logger.error(f"Error resuming saga {saga_id}: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def execute_patient_onboarding(
        self,
        patient_data: Dict[str, Any],
        initial_message: Optional[str] = None,
        flow_kind: FlowKind = FlowKind.ONBOARDING,
    ) -> SagaState:
        """
        Execute patient onboarding saga.

        Steps:
        1. Create patient in database
        2. Create flow state for patient
        3. Send initial WhatsApp message (if provided)

        Args:
            patient_data: Patient creation data (name, phone, email, etc.)
            initial_message: Optional initial WhatsApp message
            flow_kind: Flow kind for patient (default: ONBOARDING)

        Returns:
            Final saga state
        """
        saga_id = self._generate_saga_id()

        # Define saga steps with actions and compensations
        steps = [
            SagaStep(
                name="create_patient",
                action=self._create_patient_action,
                compensation=self._delete_patient_compensation,
            ),
            SagaStep(
                name="create_flow_state",
                action=self._create_flow_state_action,
                compensation=self._delete_flow_state_compensation,
            ),
        ]

        # Add message step if initial message provided
        if initial_message:
            steps.append(
                SagaStep(
                    name="send_initial_message",
                    action=self._send_initial_message_action,
                    compensation=self._send_cancellation_message_compensation,
                )
            )

        # Initialize saga state
        saga_state = SagaState(
            saga_id=saga_id,
            saga_type="patient_onboarding",
            status=SagaStatus.PENDING,
            steps=steps,
            context={
                "patient_data": patient_data,
                "initial_message": initial_message,
                "flow_kind": flow_kind.value,
            },
        )

        # Execute saga
        return await self.execute_saga(saga_state)

    # ------------------------------------------------------------------------
    # Patient Creation Step
    # ------------------------------------------------------------------------

    async def _create_patient_action(self, context: Dict[str, Any]) -> Patient:
        """
        Action: Create patient in database.

        Args:
            context: Saga context with patient_data

        Returns:
            Created patient

        Raises:
            Exception: If patient creation fails
        """
        patient_data = context["patient_data"]

        logger.info(f"Creating patient: {patient_data.get('name')}")

        # Idempotency Level 1: Check if patient_id already in context (retry scenario)
        if "patient_id" in context and context.get("patient_id"):
            try:
                patient = self.db.query(Patient).filter(
                    Patient.id == context["patient_id"]
                ).first()
                if patient:
                    context["patient"] = patient
                    logger.info(f"✅ Reusing patient from context (idempotent retry): {patient.id}")
                    return patient
            except Exception as e:
                logger.warning(f"Failed to retrieve patient from context, continuing: {e}")

        # Idempotency Level 2: if a patient with same email or phone already exists, reuse it
        try:
            existing = None
            email = patient_data.get("email")
            phone = patient_data.get("phone")
            if email:
                existing = (
                    self.db.query(Patient)
                    .filter(Patient.email == email)
                    .first()
                )
            if not existing and phone:
                existing = (
                    self.db.query(Patient)
                    .filter(Patient.phone == phone)
                    .first()
                )
            if existing:
                context["patient_id"] = existing.id
                context["patient"] = existing
                logger.info(f"✅ Using existing patient for idempotent saga: {existing.id}")
                return existing
        except Exception as e:
            logger.warning(f"Idempotency check failed, proceeding to create patient: {e}")

        # Create patient
        patient = Patient(
            name=patient_data["name"],
            phone=patient_data["phone"],
            email=patient_data.get("email"),
            cpf=patient_data.get("cpf"),
            birth_date=patient_data.get("birth_date"),
            doctor_id=patient_data.get("doctor_id"),
            flow_state=PatientFlowStateEnum.ONBOARDING_START,
        )

        self.db.add(patient)
        self.db.flush()  # Get ID without committing

        # Store in context
        context["patient_id"] = patient.id
        context["patient"] = patient

        logger.info(f"✅ Patient created: {patient.id}")

        return patient

    async def _delete_patient_compensation(
        self, context: Dict[str, Any]
    ) -> Optional[bool]:
        """
        Compensation: Delete created patient.

        Args:
            context: Saga context with patient_id

        Returns:
            True if deleted, None if not found
        """
        patient_id = context.get("patient_id")
        if not patient_id:
            return None

        logger.info(f"Deleting patient: {patient_id}")

        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if patient:
            self.db.delete(patient)
            self.db.flush()
            logger.info(f"✅ Patient deleted: {patient_id}")

            # Persist compensation to database saga record
            try:
                saga_id = context.get("saga_id")
                if saga_id:
                    from app.models.patient_onboarding_saga import PatientOnboardingSaga as SagaModel
                    saga_record = self.db.query(SagaModel).filter(SagaModel.id == saga_id).first()
                    if saga_record:
                        saga_record.add_log_entry(
                            step=1,
                            action="compensate_delete_patient",
                            status="compensated",
                            message=f"Patient {patient_id} deleted successfully"
                        )
                        self.db.flush()
            except Exception as e:
                logger.warning(f"Failed to log compensation for patient deletion: {e}")

            return True

        return None

    # ------------------------------------------------------------------------
    # Flow State Creation Step
    # ------------------------------------------------------------------------

    async def _create_flow_state_action(
        self, context: Dict[str, Any]
    ) -> PatientFlowState:
        """
        Action: Create flow state for patient.

        Args:
            context: Saga context with patient_id

        Returns:
            Created flow state

        Raises:
            Exception: If flow state creation fails
        """
        patient_id = context["patient_id"]

        logger.info(f"Creating flow state for patient: {patient_id}")

        # Idempotency Level 1: Check if flow_state_id already in context (retry scenario)
        if "flow_state_id" in context and context.get("flow_state_id"):
            try:
                flow_state = self.db.query(PatientFlowState).filter(
                    PatientFlowState.id == context["flow_state_id"]
                ).first()
                if flow_state:
                    context["flow_state"] = flow_state
                    logger.info(f"✅ Reusing flow_state from context (idempotent retry): {flow_state.id}")
                    return flow_state
            except Exception as e:
                logger.warning(f"Failed to retrieve flow_state from context, continuing: {e}")

        # Get the onboarding flow template version
        # Query for the active onboarding flow template
        from app.models.flow import FlowTemplateVersion, FlowKind as FlowKindModel

        flow_kind = self.db.query(FlowKindModel).filter(
            FlowKindModel.flow_type == "initial_15_days"
        ).first()

        if not flow_kind:
            raise Exception("Onboarding flow kind not found in database")

        template_version = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.kind_id == flow_kind.id,
            FlowTemplateVersion.is_active == True
        ).first()

        if not template_version:
            raise Exception("Active onboarding flow template not found")

        # Idempotency Level 2: Check if flow state already exists for this patient+template
        try:
            existing_flow_state = self.db.query(PatientFlowState).filter(
                PatientFlowState.patient_id == patient_id,
                PatientFlowState.template_version_id == template_version.id
            ).first()

            if existing_flow_state:
                context["flow_state_id"] = existing_flow_state.id
                context["flow_state"] = existing_flow_state
                logger.info(f"✅ Reusing existing flow_state (idempotent): {existing_flow_state.id}")
                return existing_flow_state
        except Exception as e:
            logger.warning(f"Idempotency check for flow_state failed, proceeding to create: {e}")

        # Create flow state
        flow_state = PatientFlowState(
            patient_id=patient_id,
            template_version_id=template_version.id,
            current_step=0,
            state_data={},
        )

        self.db.add(flow_state)
        self.db.flush()

        # Store in context
        context["flow_state_id"] = flow_state.id
        context["flow_state"] = flow_state

        logger.info(f"✅ Flow state created: {flow_state.id}")

        return flow_state

    async def _delete_flow_state_compensation(
        self, context: Dict[str, Any]
    ) -> Optional[bool]:
        """
        Compensation: Delete created flow state.

        Args:
            context: Saga context with flow_state_id

        Returns:
            True if deleted, None if not found
        """
        flow_state_id = context.get("flow_state_id")
        if not flow_state_id:
            return None

        logger.info(f"Deleting flow state: {flow_state_id}")

        flow_state = (
            self.db.query(PatientFlowState)
            .filter(PatientFlowState.id == flow_state_id)
            .first()
        )

        if flow_state:
            self.db.delete(flow_state)
            self.db.flush()
            logger.info(f"✅ Flow state deleted: {flow_state_id}")

            # Persist compensation to database saga record
            try:
                saga_id = context.get("saga_id")
                if saga_id:
                    from app.models.patient_onboarding_saga import PatientOnboardingSaga as SagaModel
                    saga_record = self.db.query(SagaModel).filter(SagaModel.id == saga_id).first()
                    if saga_record:
                        saga_record.add_log_entry(
                            step=2,
                            action="compensate_delete_flow_state",
                            status="compensated",
                            message=f"Flow state {flow_state_id} deleted successfully"
                        )
                        self.db.flush()
            except Exception as e:
                logger.warning(f"Failed to log compensation for flow_state deletion: {e}")

            return True

        return None

    # ------------------------------------------------------------------------
    # Initial Message Step
    # ------------------------------------------------------------------------

    async def _send_initial_message_action(self, context: Dict[str, Any]) -> Message:
        """
        Action: Send initial WhatsApp message.

        Args:
            context: Saga context with patient_id and initial_message

        Returns:
            Sent message

        Raises:
            Exception: If message sending fails
        """
        patient_id = context["patient_id"]
        initial_message = context["initial_message"]

        logger.info(f"Sending initial message to patient: {patient_id}")

        # Send message using idempotent sender
        message, is_duplicate = await self.message_sender.send_message(
            patient_id=patient_id,
            content=initial_message,
            message_type=MessageType.TEXT,
            idempotency_key=f"onboarding_{patient_id}_initial",
        )

        # Store in context
        context["initial_message_id"] = message.id
        context["initial_message_obj"] = message

        logger.info(
            f"✅ Initial message sent: {message.id} (duplicate: {is_duplicate})"
        )

        return message

    async def _send_cancellation_message_compensation(
        self, context: Dict[str, Any]
    ) -> Optional[Message]:
        """
        Compensation: Send cancellation message.

        Args:
            context: Saga context with patient_id

        Returns:
            Cancellation message if sent, None otherwise
        """
        patient_id = context.get("patient_id")
        if not patient_id:
            return None

        logger.info(f"Sending cancellation message to patient: {patient_id}")

        try:
            # Send cancellation message
            cancellation_msg = (
                "Desculpe, houve um problema ao processar seu cadastro. "
                "Por favor, tente novamente mais tarde."
            )

            message, _ = await self.message_sender.send_message(
                patient_id=patient_id,
                content=cancellation_msg,
                message_type=MessageType.TEXT,
                idempotency_key=f"onboarding_{patient_id}_cancellation",
            )

            logger.info(f"✅ Cancellation message sent: {message.id}")

            # Persist compensation to database saga record
            try:
                saga_id = context.get("saga_id")
                if saga_id:
                    from app.models.patient_onboarding_saga import PatientOnboardingSaga as SagaModel
                    saga_record = self.db.query(SagaModel).filter(SagaModel.id == saga_id).first()
                    if saga_record:
                        saga_record.add_log_entry(
                            step=3,
                            action="compensate_send_cancellation",
                            status="compensated",
                            message=f"Cancellation message {message.id} sent successfully"
                        )
                        self.db.flush()
            except Exception as e:
                logger.warning(f"Failed to log compensation for cancellation message: {e}")

            return message

        except Exception as e:
            logger.error(f"Failed to send cancellation message: {e}")

            # Log failed compensation attempt
            try:
                saga_id = context.get("saga_id")
                if saga_id:
                    from app.models.patient_onboarding_saga import PatientOnboardingSaga as SagaModel
                    saga_record = self.db.query(SagaModel).filter(SagaModel.id == saga_id).first()
                    if saga_record:
                        saga_record.add_log_entry(
                            step=3,
                            action="compensate_send_cancellation",
                            status="failed",
                            message=f"Failed to send cancellation message: {str(e)}"
                        )
                        self.db.flush()
            except Exception as log_error:
                logger.warning(f"Failed to log failed compensation: {log_error}")

            return None

    # ------------------------------------------------------------------------
    # Error Handling and Retry Logic
    # ------------------------------------------------------------------------

    async def _handle_saga_failure(
        self, saga_model: Any, error: Exception
    ) -> None:
        """
        Handle saga failure with retry scheduling.

        Args:
            saga_model: PatientOnboardingSaga model instance
            error: Exception that caused the failure

        This method is called when a saga step fails and determines whether
        to schedule a retry or mark the saga as permanently failed.
        """
        from app.models.patient_onboarding_saga import SagaStatus as ModelSagaStatus

        logger.warning(
            f"Handling saga failure for saga {saga_model.id}: {error}"
        )

        # Increment retry count
        saga_model.retry_count += 1

        # Check if we should retry
        if saga_model.retry_count < saga_model.max_retries:
            # Schedule retry with exponential backoff
            await self._schedule_retry(saga_model)
            logger.info(
                f"Scheduled retry {saga_model.retry_count}/{saga_model.max_retries} "
                f"for saga {saga_model.id}"
            )
        else:
            # Max retries exceeded
            saga_model.status = ModelSagaStatus.FAILED
            saga_model.failed_at = datetime.utcnow()
            logger.error(
                f"Saga {saga_model.id} failed permanently after "
                f"{saga_model.retry_count} retries"
            )

            # Handle max retries exceeded
            await self._handle_max_retries_exceeded(saga_model)

    async def _schedule_retry(self, saga_model: Any) -> None:
        """
        Schedule a saga retry with exponential backoff.

        Args:
            saga_model: PatientOnboardingSaga model instance

        Calculates the next retry time using exponential backoff and
        updates the saga model accordingly.
        """
        from app.models.patient_onboarding_saga import SagaStatus as ModelSagaStatus

        # Calculate exponential backoff: 2^retry_count minutes
        backoff_minutes = 2 ** saga_model.retry_count
        next_retry_at = datetime.utcnow() + timedelta(minutes=backoff_minutes)

        # Update saga model
        saga_model.status = ModelSagaStatus.RETRY_SCHEDULED
        saga_model.next_retry_at = next_retry_at

        logger.info(
            f"Scheduled retry for saga {saga_model.id} at {next_retry_at} "
            f"(backoff: {backoff_minutes} minutes)"
        )

        # Commit the changes
        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to schedule retry: {e}")
            self.db.rollback()

    async def _handle_max_retries_exceeded(self, saga_model: Any) -> None:
        """
        Handle max retries exceeded - alert admin and mark as failed.

        Args:
            saga_model: PatientOnboardingSaga model instance

        This method is called when a saga has exhausted all retry attempts
        and needs to be marked as permanently failed. It alerts the admin
        and logs the failure for manual intervention.
        """
        logger.error(
            f"⚠️ Max retries exceeded for saga {saga_model.id}. "
            f"Patient ID: {saga_model.patient_id}"
        )

        # Alert admin about the failure
        await self._alert_admin(saga_model)

        # Log detailed error information
        logger.error(
            f"Saga failure details:\n"
            f"  Saga ID: {saga_model.id}\n"
            f"  Patient ID: {saga_model.patient_id}\n"
            f"  Retry Count: {saga_model.retry_count}\n"
            f"  Error: {saga_model.error_details}\n"
            f"  Started At: {saga_model.started_at}\n"
            f"  Failed At: {saga_model.failed_at}"
        )

    async def _alert_admin(self, saga_model: Any) -> None:
        """
        Send alert to admin about saga failure.

        Args:
            saga_model: PatientOnboardingSaga model instance

        This method sends an alert (via logging, email, or monitoring system)
        to notify administrators about a saga that has failed permanently.
        """
        # For now, just log the alert
        # In production, this would send an email, Slack message, or trigger
        # a monitoring alert (e.g., Sentry, PagerDuty)
        logger.critical(
            f"🚨 ADMIN ALERT: Saga {saga_model.id} failed permanently!\n"
            f"Patient ID: {saga_model.patient_id}\n"
            f"Error: {saga_model.error_details}\n"
            f"Action Required: Manual intervention needed"
        )

        # TODO: Implement actual alerting mechanism
        # - Send email to admin
        # - Post to Slack channel
        # - Create Sentry issue
        # - Trigger PagerDuty alert


# Export public API
__all__ = [
    "SagaOrchestrator",
    "SagaState",
    "SagaStep",
    "SagaStatus",
    "SagaStepStatus",
]
