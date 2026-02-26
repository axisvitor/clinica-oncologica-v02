"""Saga orchestration for patient onboarding."""

import hashlib
import logging
import time
import uuid
from typing import Optional, Any, List
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session
from typing import Any as _AnyType  # noqa: F401 - used for db type hint

from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.schemas.patient import PatientCreate
from app.repositories.patient import PatientRepository
from app.services.patient.flow_service import PatientFlowService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.domain.messaging.core import MessageService
from app.core.redis_manager import get_sync_redis_client as get_redis_client
from app.core.distributed_lock import acquire_lock, LockAcquisitionError
from app.integrations.evolution import EvolutionClient
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

from .metrics import (
    METRICS_AVAILABLE,
    SAGA_COMPENSATIONS_TOTAL,
    SAGA_COMPLETIONS_TOTAL,
    SAGA_DURATION_SECONDS,
    SAGA_FAILURES_TOTAL,
    SAGA_LOCK_ACQUISITION_SECONDS,
    SAGA_PHONE_NORMALIZATION_TOTAL,
    SAGA_STARTS_TOTAL,
    SAGA_STEP_DURATION_SECONDS,
    SAGA_TRANSACTION_DURATION_SECONDS,
    _detect_phone_format,
)
from .steps import SagaStepExecutor
from .compensation import SagaCompensator
from .persistence import SagaPersistence
from .query_helpers import metadata_key_equals
from .types import SagaStatusInfo, FailedSagaSummary, ResumeResult
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class SagaOrchestrator:
    """Saga orchestrator for patient onboarding transactions."""

    def __init__(
        self,
        db: Any,  # Accept AsyncSession or Session; sub-components (steps/compensator) use AsyncSession
        redis_client: Optional[Any] = None,
        evolution_client: Optional[EvolutionClient] = None,
    ):
        self.db = db
        self.redis = redis_client or get_redis_client()
        self.evolution_client = evolution_client

        self.patient_repo = PatientRepository(db)
        self.flow_service = PatientFlowService(db)
        self.whatsapp_service = UnifiedWhatsAppService(db)
        self.message_service = MessageService(db)

        self.step_executor = SagaStepExecutor(
            db=db,
            patient_repo=self.patient_repo,
            flow_service=self.flow_service,
            whatsapp_service=self.whatsapp_service,
            message_service=self.message_service,
        )
        self.compensator = SagaCompensator(
            db=db,
            patient_repo=self.patient_repo,
            redis_client=self.redis,
        )
        self.persistence = SagaPersistence(db)

    def _sync_compensator_dependencies(self) -> None:
        """Keep compensator aligned with the latest orchestrator dependencies."""
        self.compensator.db = self.db
        self.compensator.patient_repo = self.patient_repo
        self.compensator.redis = self.redis

    async def execute_patient_onboarding_saga(
        self,
        patient_data: PatientCreate,
        doctor_id: Optional[UUID] = None,
        current_user: Any = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[Patient]:
        """Execute patient onboarding saga with compensation on failures."""
        original_phone = patient_data.phone
        normalized_phone = normalize_phone(
            original_phone,
            mode=PhoneValidationMode.BR_TO_E164,
            allow_none=False,
        )
        logger.info(
            "Phone normalized for patient creation",
            extra={
                "phone_original": original_phone,
                "phone_normalized": normalized_phone,
                "validation_mode": "BR_TO_E164",
                "context": "saga_orchestrator",
            },
        )
        if METRICS_AVAILABLE:
            SAGA_PHONE_NORMALIZATION_TOTAL.labels(
                format_detected=_detect_phone_format(original_phone)
            ).inc()
        phone_hash = hashlib.sha256(normalized_phone.encode()).hexdigest()[:32]
        doctor_part = str(doctor_id) if doctor_id else "no-doctor"
        lock_key = f"saga:onboarding:{doctor_part}:{phone_hash}"

        lock_start = time.time()
        async with acquire_lock(lock_key, timeout=5.0, ttl=300):
            if METRICS_AVAILABLE:
                SAGA_LOCK_ACQUISITION_SECONDS.labels(lock_type="onboarding").observe(
                    time.time() - lock_start
                )
            tx_start = time.time()
            saga_id = uuid.uuid4()
            step_data = {"idempotency_key": idempotency_key} if idempotency_key else {}

            saga = PatientOnboardingSaga(
                id=saga_id,
                doctor_id=doctor_id,
                patient_data=patient_data.model_dump(mode="json"),
                step_data=step_data,
                status=SagaStatus.STARTED,
                current_step=0,
                started_at=now_sao_paulo(),
            )
            self.db.add(saga)
            self.db.flush()

            if METRICS_AVAILABLE:
                SAGA_STARTS_TOTAL.labels(
                    doctor_id=str(doctor_id) if doctor_id else "none"
                ).inc()

            logger.info(
                f"Starting patient onboarding saga {saga_id} for doctor {doctor_id}"
            )

            try:
                step_start = time.time()
                patient = await self.step_executor.step_create_patient(
                    saga, patient_data, doctor_id, idempotency_key
                )
                if METRICS_AVAILABLE:
                    SAGA_STEP_DURATION_SECONDS.labels(
                        step_name="create_patient"
                    ).observe(time.time() - step_start)
                if not patient:
                    raise Exception("Failed to create patient")

                step_start = time.time()
                await self.step_executor.step_initialize_flow(
                    saga, patient, current_user, idempotency_key=idempotency_key
                )
                if METRICS_AVAILABLE:
                    SAGA_STEP_DURATION_SECONDS.labels(
                        step_name="initialize_flow"
                    ).observe(time.time() - step_start)

                step_start = time.time()
                await self.step_executor.step_send_welcome_message(
                    saga, patient, idempotency_key=idempotency_key
                )
                if METRICS_AVAILABLE:
                    SAGA_STEP_DURATION_SECONDS.labels(
                        step_name="schedule_message"
                    ).observe(time.time() - step_start)

                warning_statuses = {
                    "failed_nonfatal",
                    "skipped_auto_enrollment_disabled",
                    "skipped_no_flow",
                }
                has_warnings = any(
                    isinstance(entry, dict)
                    and entry.get("status") in warning_statuses
                    for entry in (saga.execution_log or [])
                )

                saga.status = (
                    SagaStatus.COMPLETED_WITH_WARNINGS
                    if has_warnings
                    else SagaStatus.COMPLETED
                )
                saga.completed_at = now_sao_paulo()

                tx_duration = time.time() - tx_start
                logger.info(
                    f"Transaction duration: {tx_duration:.2f}s",
                    extra={"saga_id": saga_id},
                )

                self.db.commit()

                if METRICS_AVAILABLE:
                    status_label = (
                        "completed_with_warnings"
                        if has_warnings
                        else "completed"
                    )
                    SAGA_COMPLETIONS_TOTAL.labels(
                        doctor_id=str(doctor_id) if doctor_id else "none"
                    ).inc()
                    SAGA_DURATION_SECONDS.labels(status=status_label).observe(
                        tx_duration
                    )
                    SAGA_TRANSACTION_DURATION_SECONDS.labels(step="complete").observe(
                        tx_duration
                    )

                logger.info(f"Saga {saga_id} completed successfully")
                return patient

            except Exception as e:
                tx_duration = time.time() - tx_start
                logger.error(
                    f"Saga {saga_id} failed with {type(e).__name__}",
                    exc_info=True,
                )

                self.db.rollback()

                if METRICS_AVAILABLE:
                    SAGA_FAILURES_TOTAL.labels(
                        doctor_id=str(doctor_id) if doctor_id else "none",
                        step=str(saga.current_step),
                        error_type=type(e).__name__,
                    ).inc()
                    SAGA_DURATION_SECONDS.labels(status="failed").observe(tx_duration)

                try:
                    patient_id = saga.patient_id
                    if patient_id:
                        patient_exists = (
                            self.db.query(Patient.id)
                            .filter(Patient.id == patient_id)
                            .first()
                        )
                        if not patient_exists:
                            patient_id = None
                    failure_saga = PatientOnboardingSaga(
                        id=saga_id,
                        doctor_id=doctor_id,
                        patient_data=patient_data.model_dump(mode="json"),
                        status=SagaStatus.FAILED,
                        current_step=saga.current_step,
                        step_data=saga.step_data,
                        execution_log=saga.execution_log,
                        patient_id=patient_id,
                        started_at=saga.started_at,
                        failed_at=now_sao_paulo(),
                        error_message=str(e),
                        error_type=type(e).__name__,
                    )
                    self.db.add(failure_saga)
                    self.db.commit()
                    logger.info(
                        f"Saga {saga_id} failure record created",
                        extra={
                            "current_step": saga.current_step,
                            "patient_id": str(saga.patient_id) if saga.patient_id else None,
                            "has_idempotency_key": bool(saga.step_data.get("idempotency_key") if saga.step_data else False),
                        },
                    )

                    try:
                        await self.compensator.compensate_saga(failure_saga)
                        if METRICS_AVAILABLE:
                            SAGA_COMPENSATIONS_TOTAL.labels(
                                step=str(saga.current_step), result="success"
                            ).inc()
                    except Exception as comp_err:
                        logger.error(
                            f"Saga {saga_id} compensation failed: {comp_err}"
                        )
                        if METRICS_AVAILABLE:
                            SAGA_COMPENSATIONS_TOTAL.labels(
                                step=str(saga.current_step), result="failed"
                            ).inc()

                except Exception as record_err:
                    logger.error(
                        f"Failed to create saga {saga_id} failure record: {record_err}",
                        exc_info=True,
                    )

                return None


    async def resume_saga(self, saga_id: UUID) -> ResumeResult:
        """Resume a failed or interrupted saga under distributed lock."""
        lock_key = f"saga:resume:{saga_id}"
        try:
            async with acquire_lock(lock_key, timeout=5.0, ttl=300):
                saga = self.persistence.get_saga_by_id(saga_id)
                if not saga:
                    return ResumeResult(
                        status="error",
                        message=None,
                        error="Saga not found",
                    )

                return await self._resume_saga_internal(saga)
        except LockAcquisitionError:
            logger.warning(f"Could not acquire lock for saga resume: {saga_id}")
            return ResumeResult(
                status="error",
                message=None,
                error="Saga resume already in progress",
            )

    async def _resume_saga_internal(self, saga: PatientOnboardingSaga) -> ResumeResult:
        """Internal resume logic (called within lock context)."""
        if saga.status == SagaStatus.COMPLETED:
            return ResumeResult(
                status="completed",
                message="Saga already completed",
                error=None,
            )

        logger.info(f"Resuming saga {saga.id} from step {saga.current_step}")

        try:
            patient = None
            if saga.patient_id:
                patient = self.patient_repo.get_by_id(saga.patient_id)

            patient_data_dict = saga.patient_data
            idempotency_key = None
            if saga.step_data:
                idempotency_key = saga.step_data.get("idempotency_key")

            if not patient:
                patient_create = PatientCreate(**patient_data_dict)
                patient = await self.step_executor.step_create_patient(
                    saga,
                    patient_create,
                    saga.doctor_id,
                    idempotency_key=idempotency_key,
                )
                if not patient:
                    raise Exception("Failed to recover patient creation")

            if not patient:
                raise Exception("Patient not found for resumption")

            if saga.current_step <= 2:
                from app.models.flow import PatientFlowState
                existing_flow = (
                    self.db.query(PatientFlowState)
                    .filter(PatientFlowState.patient_id == patient.id)
                    .first()
                )
                if not existing_flow:
                    await self.step_executor.step_initialize_flow(
                        saga, patient, None, idempotency_key=idempotency_key
                    )
                else:
                    saga.current_step = 3
                    saga.add_log_entry(2, "flow_init", "skipped_existing_flow")
                    self.db.flush()

            if saga.current_step < 4:
                from app.models.message import Message
                existing_message = (
                    self.db.query(Message)
                    .filter(
                        Message.patient_id == patient.id,
                        metadata_key_equals(
                            Message.message_metadata,
                            "saga_id",
                            str(saga.id),
                        ),
                    )
                    .first()
                )
                if existing_message:
                    logger.info(
                        f"Saga {saga.id}: Welcome message already exists "
                        f"(message_id={existing_message.id}), skipping send"
                    )
                    saga.add_log_entry(3, "welcome_message", "skipped_existing_message")
                    saga.current_step = 4
                    self.db.flush()
                else:
                    await self.step_executor.step_send_welcome_message(
                        saga, patient, idempotency_key=idempotency_key
                    )

            saga.status = SagaStatus.COMPLETED
            saga.completed_at = now_sao_paulo()
            self.db.commit()

            return ResumeResult(
                status="completed",
                message=None,
                error=None,
            )

        except Exception as e:
            logger.error(f"Failed to resume saga {saga.id}: {e}", exc_info=True)
            self.db.rollback()
            saga.error_message = str(e)
            self.db.commit()
            return ResumeResult(
                status="failed",
                message=None,
                error=str(e),
            )

    async def get_saga_status(self, saga_id: UUID) -> Optional[SagaStatusInfo]:
        """Get current saga status for monitoring."""
        return self.persistence.get_saga_status(saga_id)

    async def list_failed_sagas(
        self, doctor_id: Optional[UUID] = None, limit: int = 50
    ) -> List[FailedSagaSummary]:
        """List failed sagas for manual review or retry."""
        return self.persistence.list_failed_sagas(doctor_id, limit)

    async def _compensate_saga_internal(self, saga: PatientOnboardingSaga) -> None:
        """Delegate internal compensation logic to SagaCompensator."""
        self._sync_compensator_dependencies()
        await self.compensator._compensate_saga_internal(saga)

    async def _compensate_step_with_retry(
        self,
        saga: PatientOnboardingSaga,
        step_num: int,
        step_name: str,
        compensate_fn,
        compensation_errors: List[Any],
        max_retries: int = 3,
    ) -> None:
        """Delegate step compensation retry logic to SagaCompensator."""
        self._sync_compensator_dependencies()
        await self.compensator._compensate_step_with_retry(
            saga=saga,
            step_num=step_num,
            step_name=step_name,
            compensate_fn=compensate_fn,
            compensation_errors=compensation_errors,
            max_retries=max_retries,
        )

    async def _compensate_message(self, saga: PatientOnboardingSaga) -> None:
        """Delegate message compensation to SagaCompensator."""
        self._sync_compensator_dependencies()
        await self.compensator._compensate_message(saga)

    async def _compensate_flow(self, saga: PatientOnboardingSaga) -> None:
        """Delegate flow compensation to SagaCompensator."""
        self._sync_compensator_dependencies()
        await self.compensator._compensate_flow(saga)

    async def _compensate_patient(self, saga: PatientOnboardingSaga) -> None:
        """Delegate patient compensation to SagaCompensator."""
        self._sync_compensator_dependencies()
        await self.compensator._compensate_patient(saga)

    async def _compensate_saga(self, saga: PatientOnboardingSaga) -> None:
        """Execute compensation steps in reverse order via compensator."""
        self._sync_compensator_dependencies()
        await self.compensator.compensate_saga(saga)

    async def _track_compensation_failure(
        self, saga_id: UUID, step: int, error: Exception
    ) -> None:
        """Track compensation failures via SagaCompensator."""
        self._sync_compensator_dependencies()
        await self.compensator._track_compensation_failure(saga_id, step, error)
