import inspect
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, text

from app.exceptions import ConcurrentModificationError
from app.infrastructure.cache import UnifiedCacheManager as UnifiedCacheService
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.services.flow.event_broadcaster import flow_event_broadcaster
from app.services.flow.flags import is_awaiting_response
from app.services.flow.types import FlowType
from app.services.platform_synchronization import PlatformSynchronizationService
from app.services.template_loader_pkg import EnhancedTemplateLoader
from app.utils.timezone import SAO_PAULO_TZ, SAO_PAULO_TZ_NAME, now_sao_paulo

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


FLOW_ADVANCE_BLOCKED_MESSAGE = "Cannot advance flow while awaiting patient response"
FLOW_ADVANCE_BLOCKED_CODE = "flow_advance_blocked_awaiting_response"
FLOW_ADVANCE_BLOCKED_REASON = "awaiting_response"


class FlowCoreOperationsMixin:
    def __init__(
        self,
        db: Any,
        platform_sync: Optional[PlatformSynchronizationService] = None,
        template_loader: Optional[EnhancedTemplateLoader] = None,
        template_cache: Optional[UnifiedCacheService] = None,
    ):
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.flow_broadcaster = flow_event_broadcaster

        if platform_sync:
            self.platform_sync = platform_sync
        else:
            from app.services.platform_synchronization import get_platform_sync_service

            self.platform_sync = get_platform_sync_service(db)

        if template_loader:
            self.template_loader = template_loader
        else:
            self.template_loader = EnhancedTemplateLoader(db)

        if template_cache:
            self.template_cache = template_cache
        else:
            self.template_cache = UnifiedCacheService()

    async def _resolve(self, maybe_awaitable: Any) -> Any:
        if inspect.isawaitable(maybe_awaitable):
            return await maybe_awaitable
        return maybe_awaitable

    async def _execute(self, statement):
        return await self._resolve(self.db.execute(statement))

    async def _commit(self) -> None:
        await self._resolve(self.db.commit())

    async def _rollback(self) -> None:
        await self._resolve(self.db.rollback())

    async def _refresh(self, instance: Any) -> None:
        refresh = getattr(self.db, "refresh", None)
        if callable(refresh):
            await self._resolve(refresh(instance))

    async def _flush(self) -> None:
        await self._resolve(self.db.flush())

    async def _commit_flow_state_with_lock(
        self, flow_state: PatientFlowState, expected_version: int
    ) -> None:
        result = await self._execute(
            select(PatientFlowState.version).filter(PatientFlowState.id == flow_state.id)
        )
        current_version = result.scalar_one_or_none()

        if current_version is None:
            raise ConcurrentModificationError(
                resource_type="PatientFlowState",
                resource_id=str(flow_state.id),
                expected_version=expected_version,
                actual_version=None,
            )

        if current_version != expected_version:
            raise ConcurrentModificationError(
                resource_type="PatientFlowState",
                resource_id=str(flow_state.id),
                expected_version=expected_version,
                actual_version=current_version,
            )

        flow_state.version = expected_version + 1
        await self._commit()

        logger.debug(
            f"Flow state {flow_state.id} updated with optimistic lock: "
            f"version {expected_version} -> {flow_state.version}"
        )

    async def enroll_patient(
        self,
        patient_id: UUID,
        flow_type: FlowType = FlowType.ONBOARDING,
        auto_commit: bool = True,
    ) -> PatientFlowState:
        result = await self._execute(select(Patient).filter(Patient.id == patient_id))
        patient = result.scalar_one_or_none()
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        result = await self._execute(
            select(PatientFlowState).filter(
                PatientFlowState.patient_id == patient_id,
                PatientFlowState.status == "active",
            )
        )
        existing_flow = result.scalar_one_or_none()
        if existing_flow:
            raise ValidationError("Patient already has active flow")

        result = await self._execute(
            select(FlowKind).filter(FlowKind.kind_key == flow_type.value)
        )
        flow_kind = result.scalar_one_or_none()
        if not flow_kind:
            raise ValidationError(f"No flow kind found for flow type: {flow_type.value}")

        result = await self._execute(
            select(FlowTemplateVersion).filter(
                FlowTemplateVersion.flow_kind_id == flow_kind.id,
                FlowTemplateVersion.is_active,
            )
        )
        active_version = result.scalar_one_or_none()

        if not active_version:
            raise ValidationError(
                f"No active template version found for flow type: {flow_type.value}"
            )

        start_dt = now_sao_paulo()
        if patient.created_at:
            start_dt = patient.created_at
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=SAO_PAULO_TZ)
            else:
                start_dt = start_dt.astimezone(SAO_PAULO_TZ)

        flow_state = PatientFlowState(
            patient_id=patient_id,
            flow_template_version_id=active_version.id,
            current_step=1,
            started_at=start_dt,
            step_data={
                "enrollment_date": start_dt.isoformat(),
                "ai_enabled": True,
                "personalization_level": "high",
            },
        )

        self.db.add(flow_state)
        if auto_commit:
            await self._commit()
        else:
            await self._flush()
        await self._refresh(flow_state)

        logger.info(f"Patient {patient_id} enrolled in flow {flow_type.value}")
        return flow_state

    async def calculate_patient_day(self, patient_id: UUID) -> int:
        result = await self._execute(
            select(PatientFlowState).filter(
                PatientFlowState.patient_id == patient_id,
                PatientFlowState.status == "active",
            )
        )
        flow_state = result.scalar_one_or_none()
        if not flow_state:
            return 1

        step_data = flow_state.step_data or {}
        enrollment_date_str = step_data.get(
            "enrollment_date", flow_state.started_at.isoformat()
        )
        enrollment_dt = datetime.fromisoformat(enrollment_date_str)

        if enrollment_dt.tzinfo is None:
            enrollment_dt = enrollment_dt.replace(tzinfo=SAO_PAULO_TZ)

        enrollment_local = enrollment_dt.astimezone(SAO_PAULO_TZ)
        now_local = now_sao_paulo()

        days_elapsed = (now_local.date() - enrollment_local.date()).days + 1
        return max(1, days_elapsed)

    async def get_flow_state(self, patient_id: UUID) -> dict[str, Any]:
        try:
            result = await self._execute(select(Patient).filter(Patient.id == patient_id))
            patient = result.scalar_one_or_none()
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            result = await self._execute(
                select(PatientFlowState).filter(
                    PatientFlowState.patient_id == patient_id,
                    PatientFlowState.status == "active",
                )
            )
            flow_state = result.scalar_one_or_none()
            if not flow_state:
                return {
                    "status": "no_active_flow",
                    "patient_id": str(patient_id),
                    "patient_name": patient.name,
                }

            current_day = await self.calculate_patient_day(patient_id)
            is_paused = (
                flow_state.state_data.get("paused", False)
                if flow_state.state_data
                else False
            )

            return {
                "status": "active",
                "patient_id": str(patient_id),
                "patient_name": patient.name,
                "flow": {
                    "id": str(flow_state.id),
                    "flow_type": flow_state.flow_type,
                    "current_day": current_day,
                    "current_step": flow_state.current_step,
                    "started_at": flow_state.started_at.isoformat(),
                    "is_paused": is_paused,
                    "step_data": flow_state.step_data,
                },
            }

        except Exception as exc:
            logger.error(f"Failed to get flow state: {exc}")
            raise

    async def calculate_optimal_send_time(
        self, patient: Patient, current_day: int
    ) -> datetime:
        try:
            try:
                preferred_hour = getattr(patient, "preferred_message_hour", 10)
                if (
                    not isinstance(preferred_hour, int)
                    or preferred_hour < 0
                    or preferred_hour > 23
                ):
                    logger.warning(
                        f"Invalid preferred_hour {preferred_hour} for patient {patient.id}, using 10 AM"
                    )
                    preferred_hour = 10
            except Exception as pref_error:
                logger.warning(
                    f"Error reading preferred hour: {pref_error}, using 10 AM default"
                )
                preferred_hour = 10

            now_local = now_sao_paulo()
            send_time_local = now_local.replace(
                hour=preferred_hour, minute=0, second=0, microsecond=0
            )

            if send_time_local <= now_local:
                send_time_local += timedelta(days=1)
                logger.debug(
                    f"Preferred time passed, scheduling for tomorrow: {send_time_local}"
                )

            try:
                import random

                random_minutes = random.randint(-30, 30)
                send_time_local += timedelta(minutes=random_minutes)
            except Exception as rand_error:
                logger.warning(f"Randomization failed: {rand_error}, using exact hour")

            send_time = send_time_local.astimezone(SAO_PAULO_TZ)
            logger.info(
                f"Calculated send time for patient {patient.id} on day {current_day}: "
                f"{send_time.isoformat()} (tz: {SAO_PAULO_TZ_NAME}, hour: {preferred_hour})"
            )
            return send_time

        except Exception as exc:
            logger.error(
                f"Failed to calculate optimal send time for patient {patient.id} day {current_day}: {exc}. "
                f"Using fallback: 1 hour from now",
                exc_info=True,
            )
            return now_sao_paulo().astimezone(SAO_PAULO_TZ) + timedelta(hours=1)

    def is_transient_error(self, error: Exception) -> bool:
        transient_errors = [
            "connection",
            "timeout",
            "temporary",
            "unavailable",
            "deadlock",
        ]
        error_str = str(error).lower()
        return any(term in error_str for term in transient_errors)

    @staticmethod
    def _is_awaiting_response(step_data: Optional[dict[str, Any]]) -> bool:
        return is_awaiting_response(step_data)

    async def health_check(self) -> dict[str, Any]:
        results = {
            "flow_core": True,
            "database": True,
            "template_cache": False,
            "timestamp": now_sao_paulo().isoformat(),
        }

        try:
            await self._execute(text("SELECT 1"))
            results["database"] = True
        except Exception as exc:
            logger.error(f"Database health check failed: {exc}")
            results["database"] = False

        try:
            cache_stats = await self.template_cache.get_cache_stats()
            results["template_cache"] = cache_stats.get("redis_connected", False)
            results["template_cache_stats"] = cache_stats
        except Exception as exc:
            logger.error(f"Template cache health check failed: {exc}")
            results["template_cache"] = False

        results["overall_healthy"] = all(
            [results["flow_core"], results["database"], results["template_cache"]]
        )
        return results
