"""
PatientFlowService - Flow management for patients.

This service handles patient flow lifecycle management including
activation, pausing, completion, and template selection.

File: backend-hormonia/app/services/patient/flow_service.py
LOC: ~150
Responsibility: Patient flow management
"""

from __future__ import annotations

# Standard library imports
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

# Third-party imports
from sqlalchemy import select

# Local application imports
from app.config import settings
from app.models.flow import FlowKind, PatientFlowState
from app.models.patient import FlowState, Patient
from app.schemas.websocket import WebSocketEventType
from app.services.flow.types import FlowType  # canonical location
from app.repositories.flow_kind import FlowKindRepository
# Production websocket_events lives in app.services.websocket_events (lazy-init global)
import app.services.websocket_events as _ws_events_mod
from app.utils.db_retry import with_db_retry
from app.utils.timezone import now_sao_paulo, SAO_PAULO_TZ

# TYPE_CHECKING import to avoid circular import at runtime
if TYPE_CHECKING:
    from app.services.enhanced_flow_engine import EnhancedFlowEngine

logger = logging.getLogger(__name__)


class PatientFlowService:
    """
    Service for managing patient flows.

    Responsibilities:
    - Initialize default flows for new patients
    - Activate patient flows
    - Pause patient flows
    - Complete patient treatment
    - Check flow status
    - Template selection based on treatment type
    """

    def __init__(
        self,
        db: Any,
        flow_engine: Optional["EnhancedFlowEngine"] = None,
    ):
        self.db = db
        if flow_engine is None:
            # Lazy import to avoid circular dependency
            from app.services.enhanced_flow_engine import get_enhanced_flow_engine

            self.flow_engine = get_enhanced_flow_engine(db)
        else:
            self.flow_engine = flow_engine
        self._logger = logging.getLogger(__name__)

    @staticmethod
    async def _maybe_await(result: Any) -> Any:
        if inspect.isawaitable(result):
            return await result
        return result

    def _uses_async_session(self) -> bool:
        return not hasattr(self.db, "query") and hasattr(self.db, "execute")

    async def _db_commit(self) -> None:
        await self._maybe_await(self.db.commit())

    async def _db_flush(self) -> None:
        await self._maybe_await(self.db.flush())

    async def _db_refresh(self, instance: Any) -> None:
        refresh = getattr(self.db, "refresh", None)
        if callable(refresh):
            await self._maybe_await(refresh(instance))

    async def _db_rollback(self) -> None:
        rollback = getattr(self.db, "rollback", None)
        if callable(rollback):
            await self._maybe_await(rollback())

    async def _get_patient(self, patient_id: UUID) -> Optional[Patient]:
        if not self._uses_async_session():
            from app.repositories.patient import PatientRepository

            repository = PatientRepository(self.db)
            return repository.get_by_id(patient_id)

        result = await self._maybe_await(
            self.db.execute(
                select(Patient).where(
                    Patient.id == patient_id,
                    Patient.deleted_at.is_(None),
                )
            )
        )
        return result.scalars().first()

    async def _update_patient(
        self,
        patient: Patient,
        update_data: dict[str, Any],
        *,
        auto_commit: bool,
    ) -> Patient:
        if not self._uses_async_session():
            from app.repositories.patient import PatientRepository

            repository = PatientRepository(self.db)
            return repository.update(patient, update_data, auto_commit=auto_commit)

        data = dict(update_data)
        patient_data_updates = data.pop("patient_data", None)
        if patient_data_updates:
            merged_patient_data = dict(patient.patient_data or {})
            merged_patient_data.update(patient_data_updates)
            patient.patient_data = merged_patient_data

        for field, value in data.items():
            if hasattr(patient, field):
                setattr(patient, field, value)

        self.db.add(patient)
        if auto_commit:
            await self._db_commit()
            await self._db_refresh(patient)
        else:
            await self._db_flush()

        return patient

    async def _get_flow_kind_by_key(self, kind_key: Optional[str]) -> Optional[FlowKind]:
        if not kind_key:
            return None

        normalized = str(kind_key).strip()
        if not normalized:
            return None

        if not self._uses_async_session():
            flow_kind_repo = FlowKindRepository(self.db)
            return flow_kind_repo.get_by_kind_key(normalized)

        result = await self._maybe_await(
            self.db.execute(
                select(FlowKind).where(
                    FlowKind.kind_key == normalized,
                    FlowKind.is_active,
                )
            )
        )
        return result.scalars().first()

    async def _list_active_flow_kinds(self) -> list[FlowKind]:
        if not self._uses_async_session():
            flow_kind_repo = FlowKindRepository(self.db)
            return list(flow_kind_repo.list_active())

        result = await self._maybe_await(
            self.db.execute(
                select(FlowKind)
                .where(FlowKind.is_active)
                .order_by(FlowKind.kind_key.asc())
            )
        )
        return list(result.scalars().all())

    async def initialize_default_flow(
        self,
        patient: Patient,
        current_user_id: Optional[UUID] = None,
        auto_commit: bool = True,
    ) -> Optional[PatientFlowState]:
        """
        Initialize default flow for patient based on treatment type.

        Args:
            patient: Patient to initialize flow for
            current_user_id: ID of user creating the flow
            auto_commit: If True (default), commits the transaction immediately.
                         Set to False when using within a saga/Unit of Work pattern
                         where the caller manages the transaction commit.

        Returns:
            Created PatientFlowState or None if auto-enrollment disabled
        """
        if not settings.FLOW_ENABLE_AUTO_ENROLLMENT:
            self._logger.info(f"Auto-enrollment disabled for patient {patient.id}")
            return None

        try:
            flow_type = await self._select_flow_type(patient)

            if not flow_type:
                self._logger.warning(
                    "No eligible flow type found for patient %s (treatment_type: %s)",
                    patient.id,
                    patient.treatment_type,
                )
                return None

            # Enroll patient using the new engine
            # Pass auto_commit to support saga/Unit of Work pattern
            flow_state = await self.flow_engine.enroll_patient(
                patient_id=patient.id, flow_type=flow_type, auto_commit=auto_commit
            )

            self._logger.info(
                f"Flow started for patient {patient.id} with type {flow_type.value}"
            )

            # Update patient metadata
            if not patient.patient_data:
                patient.patient_data = {}

            patient.patient_data.update(
                {
                    "auto_flow_started": True,
                    "requested_template": flow_type.value,
                    "actual_flow_type": flow_type.value,
                    "flow_start_time": flow_state.started_at.isoformat(),
                    "initialized_by": str(current_user_id)
                    if current_user_id
                    else "system",
                }
            )
            # Respect auto_commit for saga/Unit of Work pattern support
            if auto_commit:
                await self._db_commit()
            else:
                await self._db_flush()

            return flow_state

        except Exception as e:
            self._logger.error(f"Failed to start flow for patient {patient.id}: {e}")
            # Store error in metadata but don't fail the request
            if not patient.patient_data:
                patient.patient_data = {}

            patient.patient_data.update(
                {
                    "auto_flow_error": str(e),
                    "flow_start_attempted": True,
                    "flow_start_failed": True,
                    "error_timestamp": now_sao_paulo().isoformat(),
                }
            )

            try:
                # Respect auto_commit for saga/Unit of Work pattern support
                if auto_commit:
                    await self._db_commit()
                else:
                    await self._db_flush()
            except Exception as commit_error:
                self._logger.error(
                    f"Failed to save flow error metadata for patient {patient.id}: "
                    f"{commit_error}"
                )

            # Re-raise the exception when in saga mode so the saga can handle compensation
            if not auto_commit:
                raise e

            return None

    @with_db_retry(max_retries=3)
    async def activate_patient(
        self, patient_id: UUID, auto_commit: bool = True
    ) -> Optional[Patient]:
        """
        Activate patient and set flow state to active.

        Args:
            patient_id: UUID of the patient to activate.
            auto_commit: If True (default), commits immediately.
                         Set to False when using within a saga/Unit of Work pattern.
        """
        patient = await self._get_patient(patient_id)
        if not patient:
            return None

        update_data = {"flow_state": FlowState.ACTIVE}

        flow_start_time = None
        if patient.patient_data:
            flow_start_time = patient.patient_data.get("flow_start_time")

        start_dt = None
        if flow_start_time:
            try:
                start_dt = datetime.fromisoformat(flow_start_time)
            except ValueError:
                logger.warning(
                    "Invalid flow_start_time; using created_at instead",
                    extra={"patient_id": str(patient_id), "flow_start_time": flow_start_time},
                )

        if start_dt is None and patient.created_at:
            start_dt = patient.created_at

        if start_dt is None:
            start_dt = now_sao_paulo()

        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=SAO_PAULO_TZ)
        else:
            start_dt = start_dt.astimezone(SAO_PAULO_TZ)

        if (patient.current_day or 0) <= 0:
            today = now_sao_paulo().date()
            start_date = start_dt.date()
            if start_date > today:
                start_date = today
            update_data["current_day"] = max(1, (today - start_date).days + 1)

        if not flow_start_time:
            update_data["patient_data"] = {
                "flow_start_time": start_dt.isoformat()
            }
        updated_patient = await self._update_patient(
            patient, update_data, auto_commit=auto_commit
        )

        if auto_commit:
            # Publish WebSocket event (non-blocking, best-effort) only after commit
            try:
                websocket_events = _ws_events_mod.websocket_events
                if websocket_events:
                    await websocket_events.broadcast_flow_event(
                        event_type=WebSocketEventType.PATIENT_FLOW_CHANGED,
                        patient_id=patient_id,
                        flow_data={
                            "flow_state": FlowState.ACTIVE.value,
                            "action": "activated",
                            "patient_name": updated_patient.name,
                            "doctor_id": str(updated_patient.doctor_id),
                            "changes": {"flow_state": FlowState.ACTIVE.value},
                            "metadata": {"action": "activated"},
                        },
                    )
            except Exception as ws_error:
                # WebSocket events are non-critical - log and continue
                logger.warning(
                    f"Failed to broadcast flow event for patient {patient_id}: {ws_error}"
                )

        return updated_patient

    @with_db_retry(max_retries=3)
    async def pause_patient(self, patient_id: UUID) -> Optional[Patient]:
        """Pause patient flow."""
        patient = await self._get_patient(patient_id)
        if not patient:
            return None

        update_data = {"flow_state": FlowState.PAUSED}
        updated_patient = await self._update_patient(
            patient, update_data, auto_commit=True
        )

        # Publish WebSocket event (non-blocking, best-effort)
        try:
            websocket_events = _ws_events_mod.websocket_events
            if websocket_events:
                await websocket_events.broadcast_flow_event(
                    event_type=WebSocketEventType.PATIENT_FLOW_CHANGED,
                    patient_id=patient_id,
                    flow_data={
                        "flow_state": FlowState.PAUSED.value,
                        "action": "paused",
                        "patient_name": updated_patient.name,
                        "doctor_id": str(updated_patient.doctor_id),
                        "changes": {"flow_state": FlowState.PAUSED.value},
                        "metadata": {"action": "paused"},
                    },
                )
        except Exception as ws_error:
            # WebSocket events are non-critical - log and continue
            logger.warning(
                f"Failed to broadcast flow event for patient {patient_id}: {ws_error}"
            )

        return updated_patient

    @with_db_retry(max_retries=3)
    def complete_patient_treatment(self, patient_id: UUID) -> Optional[Patient]:
        """Mark patient treatment as completed."""
        from app.repositories.patient import PatientRepository

        repository = PatientRepository(self.db)
        patient = repository.get_by_id(patient_id)
        if not patient:
            return None

        update_data = {"flow_state": "COMPLETED"}
        return repository.update(patient, update_data)

    async def _select_flow_type(self, patient: Patient) -> Optional[FlowType]:
        """
        Select flow type using DB-backed flow_kinds only.

        Prefers an explicit patient current_flow_type if present, then tries
        treatment_type as a kind_key alias. Defaults to onboarding when available.
        """
        candidate_keys = [patient.current_flow_type, patient.treatment_type]

        for key in candidate_keys:
            if not key:
                continue
            flow_kind = await self._get_flow_kind_by_key(key)
            if flow_kind:
                try:
                    return FlowType(flow_kind.kind_key)
                except ValueError:
                    self._logger.warning(
                        "Flow kind '%s' not registered in FlowType enum",
                        flow_kind.kind_key,
                    )

        onboarding_kind = await self._get_flow_kind_by_key(FlowType.ONBOARDING.value)
        if onboarding_kind:
            return FlowType.ONBOARDING

        active_kinds = await self._list_active_flow_kinds()
        if active_kinds:
            try:
                return FlowType(active_kinds[0].kind_key)
            except ValueError:
                self._logger.warning(
                    "Active flow kind '%s' not registered in FlowType enum",
                    active_kinds[0].kind_key,
                )
                return FlowType.ONBOARDING

        return None

    @with_db_retry(max_retries=3)
    async def delete_flow(self, patient_id: UUID) -> bool:
        """
        Delete active flow for a patient.
        Used primarily for saga compensation.
        """
        try:
            if self._uses_async_session():
                result = await self._maybe_await(
                    self.db.execute(
                        select(PatientFlowState).where(
                            PatientFlowState.patient_id == patient_id
                        )
                    )
                )
                flow_states = list(result.scalars().all())
            else:
                flow_states = (
                    self.db.query(PatientFlowState)
                    .filter(PatientFlowState.patient_id == patient_id)
                    .all()
                )

            if flow_states:
                for state in flow_states:
                    await self._maybe_await(self.db.delete(state))
                await self._db_commit()
                self._logger.info(
                    f"Deleted {len(flow_states)} flow states for patient {patient_id}"
                )
                return True
            return False
        except Exception as e:
            await self._db_rollback()
            self._logger.error(f"Failed to delete flow for patient {patient_id}: {e}")
            raise e
