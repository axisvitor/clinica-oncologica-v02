"""
FlowCore - Base class for all flow operations.
Contains shared functionality extracted from EnhancedFlowEngine and FlowEngineIntegrationService.

Architecture note (QW-021 consolidation):
    This file is the active production base class for day-based treatment flows.
    It is the parent of both EnhancedFlowEngine (AI/ML) and FlowService (V2 API facade).
    It operates on SQLAlchemy PatientFlowState models and the FlowStateRepository.

    The organized ``app.services.flow`` package (QW-021) implements a separate,
    step-based execution engine with Pydantic contexts.  The two systems coexist:
    * flat files (flow_core, enhanced_flow_engine, flow_service, flow_management)
      = active production treatment-flow system
    * app.services.flow.core.manager.FlowManager / FlowEngine
      = new consolidated step-execution engine (QW-021)

    Canonical location for FlowType enum: ``app.services.flow.types.FlowType``
"""

import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.patient import Patient
from app.domain.messaging.core import MessageTemplate


from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.services.flow.event_broadcaster import flow_event_broadcaster
from app.services.flow.flags import is_awaiting_response
from app.utils.timezone import SAO_PAULO_TZ, SAO_PAULO_TZ_NAME, now_sao_paulo

logger = logging.getLogger(__name__)


from app.services.flow.types import FlowType, normalize_flow_type


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


# Import flow-specific exceptions for optimistic locking and conflict signaling
from app.exceptions import ConcurrentModificationError, FlowStateConflictError

from app.services.platform_synchronization import PlatformSynchronizationService
from app.services.template_loader_pkg import EnhancedTemplateLoader
from app.infrastructure.cache import UnifiedCacheManager as UnifiedCacheService


FLOW_ADVANCE_BLOCKED_MESSAGE = "Cannot advance flow while awaiting patient response"
FLOW_ADVANCE_BLOCKED_CODE = "flow_advance_blocked_awaiting_response"
FLOW_ADVANCE_BLOCKED_REASON = "awaiting_response"


class FlowCore:
    """
    Base class for all flow operations.
    """

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

        # Dependency injection with sensible defaults
        if platform_sync:
            self.platform_sync = platform_sync
        else:
            # Use factory function to ensure all required dependencies are initialized properly
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

    # =============================================================================
    # OPTIMISTIC LOCKING HELPER
    # =============================================================================

    def _commit_flow_state_with_lock(
        self, flow_state: PatientFlowState, expected_version: int
    ) -> None:
        """
        Commit flow state changes with optimistic locking.

        This ensures no concurrent modifications occurred between read and write.
        If another process modified the flow state, raises ConcurrentModificationError.

        Args:
            flow_state: The flow state to commit
            expected_version: The version we expect the record to still have

        Raises:
            ConcurrentModificationError: If the record was modified by another process
        """
        current_version = (
            self.db.query(PatientFlowState.version)
            .filter(PatientFlowState.id == flow_state.id)
            .scalar()
        )

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

        # Increment version and commit
        flow_state.version = expected_version + 1
        self.db.commit()

        logger.debug(
            f"Flow state {flow_state.id} updated with optimistic lock: "
            f"version {expected_version} -> {flow_state.version}"
        )

    # =============================================================================
    # PATIENT ENROLLMENT
    # =============================================================================

    async def enroll_patient(
        self,
        patient_id: UUID,
        flow_type: FlowType = FlowType.ONBOARDING,
        auto_commit: bool = True,
    ) -> PatientFlowState:
        """
        Enroll a patient in a conversation flow.

        Args:
            patient_id: Patient UUID
            flow_type: Type of flow to start
            auto_commit: If True (default), commits the transaction immediately.
                         Set to False when using within a saga/Unit of Work pattern.

        Returns:
            Created flow state

        Raises:
            NotFoundError: If patient not found
            ValidationError: If patient already enrolled
        """
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        # Get patient
        patient = self.patient_repo.get(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        # Check for existing active flow
        existing_flow = self.flow_state_repo.get_active_flow(patient_id)
        if existing_flow:
            raise ValidationError("Patient already has active flow")

        # Get current template version for the flow type
        # NOTE: Use kind_key column (not flow_type - that's just a property alias)
        flow_kind = (
            self.db.query(FlowKind)
            .filter(FlowKind.kind_key == flow_type.value)
            .first()
        )
        if not flow_kind:
            raise ValidationError(
                f"No flow kind found for flow type: {flow_type.value}"
            )

        # Get the active version for this flow kind (query the relationship)
        # NOTE: Use flow_kind_id column (not kind_id - that's just a property alias)
        active_version = (
            self.db.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.flow_kind_id == flow_kind.id,
                FlowTemplateVersion.is_active,
            )
            .first()
        )

        if not active_version:
            raise ValidationError(
                f"No active template version found for flow type: {flow_type.value}"
            )

        # Create new flow state
        # NOTE: Use correct column names matching the database schema:
        # - flow_template_version_id (not template_version_id)
        # - step_data (not state_data)
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
            current_step=1,  # Start at day 1
            started_at=start_dt,
            step_data={
                "enrollment_date": start_dt.isoformat(),
                "ai_enabled": True,
                "personalization_level": "high",
            },
        )

        # Add to session and persist
        self.db.add(flow_state)
        if auto_commit:
            self.db.commit()
        else:
            # Saga/Unit of Work pattern: flush only, caller commits
            self.db.flush()
        self.db.refresh(flow_state)

        logger.info(f"Patient {patient_id} enrolled in flow {flow_type.value}")

        return flow_state

    async def calculate_patient_day(self, patient_id: UUID) -> int:
        """
        Calculate current day for patient based on enrollment and timezone.

        Args:
            patient_id: Patient UUID

        Returns:
            Current day number
        """
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.flow_state_repo to async, use await
        flow_state = self.flow_state_repo.get_active_flow(patient_id)
        if not flow_state:
            return 1

        # Calculate days since enrollment using local time
        step_data = flow_state.step_data or {}
        enrollment_date_str = step_data.get(
            "enrollment_date", flow_state.started_at.isoformat()
        )
        enrollment_dt = datetime.fromisoformat(enrollment_date_str)

        # Ensure enrollment_dt is timezone aware
        if enrollment_dt.tzinfo is None:
            enrollment_dt = enrollment_dt.replace(tzinfo=SAO_PAULO_TZ)

        enrollment_local = enrollment_dt.astimezone(SAO_PAULO_TZ)
        now_local = now_sao_paulo()

        days_elapsed = (now_local.date() - enrollment_local.date()).days + 1

        return max(1, days_elapsed)

    async def determine_flow_type(self, patient_id: UUID, current_day: int) -> FlowType:
        """
        Determine appropriate flow type based on patient day.

        Args:
            patient_id: Patient UUID
            current_day: Current treatment day

        Returns:
            Appropriate flow type
        """
        # NOTE: Canonical flow kind keys are persisted in flow_kinds.kind_key.
        if current_day <= 15:
            return FlowType.ONBOARDING
        elif current_day <= 45:
            return FlowType.DAILY_FOLLOW_UP
        return FlowType.QUIZ_MENSAL

    async def advance_patient_flow(
        self, patient_id: UUID, force_day: Optional[int] = None
    ) -> dict[str, Any]:
        """
        Advance patient flow to next appropriate day/state.

        Args:
            patient_id: Patient UUID
            force_day: Force specific day (optional)

        Returns:
            Flow advancement result
        """
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        try:
            # Get current flow state
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            if self._is_awaiting_response(flow_state.step_data):
                raise FlowStateConflictError(
                    FLOW_ADVANCE_BLOCKED_MESSAGE,
                    details={
                        "patient_id": str(patient_id),
                        "blocked": True,
                        "block_reason": FLOW_ADVANCE_BLOCKED_REASON,
                        "current_step": flow_state.current_step,
                    },
                    code=FLOW_ADVANCE_BLOCKED_CODE,
                )

            # Calculate current day
            current_day = force_day or await self.calculate_patient_day(patient_id)

            # Determine if flow type transition is needed
            current_flow_type = normalize_flow_type(flow_state.flow_type)
            required_flow_type = await self.determine_flow_type(patient_id, current_day)

            # Capture version for optimistic locking before any modifications
            expected_version = flow_state.version

            # Store previous state for broadcasting
            previous_state = {
                "flow_type": current_flow_type.value,
                "current_day": flow_state.current_step,
                "is_paused": flow_state.step_data.get("paused", False)
                if flow_state.step_data
                else False,
            }

            # Handle flow type transition
            if current_flow_type != required_flow_type:
                await self._transition_flow_type(
                    flow_state, required_flow_type, current_day
                )
                logger.info(
                    f"Patient {patient_id} transitioned from {current_flow_type.value} to {required_flow_type.value}"
                )

            # Update current step
            previous_day = flow_state.current_step
            flow_state.current_step = current_day
            step_data = dict(flow_state.step_data or {})
            step_data["last_advancement"] = now_sao_paulo().isoformat()
            step_data["current_flow_day"] = current_day
            step_data["flow_kind"] = required_flow_type.value
            flow_state.step_data = step_data

            # Commit with optimistic locking to prevent race conditions
            self._commit_flow_state_with_lock(flow_state, expected_version)

            # Broadcast flow state change
            await self.flow_broadcaster.broadcast_flow_state_change(
                patient_id=patient_id,
                flow_state=flow_state,
                previous_state=previous_state,
            )

            # Broadcast flow progression if day changed
            if previous_day != current_day:
                milestone = (
                    "flow_transition"
                    if current_flow_type != required_flow_type
                    else None
                )
                await self.flow_broadcaster.broadcast_flow_progression(
                    patient_id=patient_id,
                    from_day=previous_day,
                    to_day=current_day,
                    flow_type=required_flow_type.value,
                    milestone_reached=milestone,
                )

            # Sync flow state change to platform
            await self.platform_sync.sync_patient_record_update(
                patient_id=patient_id,
                flow_interaction_data={
                    "flow_advancement": {
                        "previous_day": previous_day,
                        "current_day": current_day,
                        "flow_type": required_flow_type.value,
                        "transitioned": current_flow_type != required_flow_type,
                        "timestamp": now_sao_paulo().isoformat(),
                    }
                },
            )

            return {
                "status": "success",
                "patient_id": str(patient_id),
                "current_day": current_day,
                "flow_type": required_flow_type.value,
                "previous_flow_type": current_flow_type.value,
                "transitioned": current_flow_type != required_flow_type,
            }

        except Exception as e:
            logger.error(f"Failed to advance patient flow: {e}")
            self.db.rollback()
            raise

    async def pause_patient_flow(
        self, patient_id: UUID, reason: str = None
    ) -> dict[str, Any]:
        """
        Pause patient flow.

        Args:
            patient_id: Patient UUID
            reason: Reason for pausing (optional)

        Returns:
            Pause result
        """
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            # Capture version for optimistic locking before any modifications
            expected_version = flow_state.version

            # Store previous state for broadcasting
            previous_state = {
                "flow_type": flow_state.flow_type,
                "current_day": flow_state.current_step,
                "is_paused": False,
            }

            # Update step data
            step_data = dict(flow_state.step_data or {})
            step_data["paused"] = {
                "timestamp": now_sao_paulo().isoformat(),
                "reason": reason or "Manual pause",
                "current_step": flow_state.current_step,
            }
            flow_state.step_data = step_data
            flow_state.status = "paused"

            # Commit with optimistic locking to prevent race conditions
            self._commit_flow_state_with_lock(flow_state, expected_version)

            # Broadcast flow pause event
            await self.flow_broadcaster.broadcast_flow_state_change(
                patient_id=patient_id,
                flow_state=flow_state,
                previous_state=previous_state,
            )

            logger.info(f"Paused flow for patient {patient_id}")
            return {
                "status": "paused",
                "patient_id": str(patient_id),
                "reason": reason,
                "paused_at": now_sao_paulo().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to pause patient flow: {e}")
            self.db.rollback()
            raise

    async def resume_patient_flow(self, patient_id: UUID) -> dict[str, Any]:
        """
        Resume paused patient flow.

        Args:
            patient_id: Patient UUID

        Returns:
            Resume result
        """
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            # Capture version for optimistic locking before any modifications
            expected_version = flow_state.version

            # Store previous state for broadcasting
            previous_state = {
                "flow_type": flow_state.flow_type,
                "current_day": flow_state.current_step,
                "is_paused": True,
            }

            # Remove pause data
            step_data = dict(flow_state.step_data or {})
            if "paused" in step_data:
                paused_data = step_data.pop("paused")
                step_data["resumed"] = {
                    "timestamp": now_sao_paulo().isoformat(),
                    "was_paused_at": paused_data.get("timestamp"),
                    "pause_reason": paused_data.get("reason"),
                }
                flow_state.step_data = step_data
            flow_state.status = "active"

            # Commit with optimistic locking to prevent race conditions
            self._commit_flow_state_with_lock(flow_state, expected_version)

            # Broadcast flow resume event
            await self.flow_broadcaster.broadcast_flow_state_change(
                patient_id=patient_id,
                flow_state=flow_state,
                previous_state=previous_state,
            )

            logger.info(f"Resumed flow for patient {patient_id}")
            return {
                "status": "resumed",
                "patient_id": str(patient_id),
                "resumed_at": now_sao_paulo().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to resume patient flow: {e}")
            self.db.rollback()
            raise

    async def get_flow_state(self, patient_id: UUID) -> dict[str, Any]:
        """
        Get current flow state for patient.

        Args:
            patient_id: Patient UUID

        Returns:
            Flow state information
        """
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        try:
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                return {
                    "status": "no_active_flow",
                    "patient_id": str(patient_id),
                    "patient_name": patient.name,
                }

            current_day = await self.calculate_patient_day(patient_id)
            is_paused = flow_state.step_data and "paused" in flow_state.step_data

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

        except Exception as e:
            logger.error(f"Failed to get flow state: {e}")
            raise

    # =============================================================================
    # TEMPLATE HANDLING (Shared between both services)
    # =============================================================================

    async def get_message_template_for_day(
        self, flow_type: FlowType, day: int
    ) -> Optional[MessageTemplate]:
        """
        Get message template for specific flow type and day.
        """
        try:
            # Load flow template with proper error handling
            from app.services.template_loader_pkg import TemplateLoadError, FlowTemplateData

            try:
                flow_template: FlowTemplateData = (
                    self.template_loader.load_flow_template(flow_type.value)
                )
            except TemplateLoadError as e:
                logger.error(
                    f"Template load error for {flow_type.value}: {e}."
                )
                raise NotFoundError(f"Template load error for {flow_type.value}") from e
            except FileNotFoundError as e:
                logger.error(
                    f"Template file not found for {flow_type.value}: {e}."
                )
                raise NotFoundError(f"Template file not found for {flow_type.value}") from e
            except Exception as e:
                logger.error(
                    f"Unexpected error loading template {flow_type.value}: {e}.",
                    exc_info=True,
                )
                raise

            # Get message for specific day from FlowTemplateData.messages dict
            if day in flow_template.messages:
                message_template = flow_template.messages[day]
                logger.debug(f"Found message template for {flow_type.value} day {day}")
                return message_template

            logger.warning(
                f"No message template found for {flow_type.value} day {day}."
            )
            raise NotFoundError(
                f"No message template found for {flow_type.value} day {day}"
            )

        except Exception as e:
            logger.error(
                f"Critical error getting message template for {flow_type.value} day {day}: {e}.",
                exc_info=True,
            )
            raise

    async def reload_templates(self, flow_type: Optional[str] = None) -> Dict[str, str]:
        """Reload templates from database and invalidate cache."""
        try:
            results = {}

            if flow_type:
                # Reload specific template
                await self.template_cache.invalidate_template_cache(flow_type)
                template = await self.template_cache.get_template(flow_type)
                results[flow_type] = "reloaded" if template else "not_found"
            else:
                # Reload all templates
                from app.services.flow_template import FlowTemplateService

                template_service = FlowTemplateService(self.db)
                templates = template_service.get_all_templates()
                for template in templates:
                    await self.template_cache.invalidate_template_cache(
                        template.flow_type
                    )
                    results[template.flow_type] = "reloaded"

            logger.info(f"Templates reloaded: {list(results.keys())}")
            return results

        except Exception as e:
            logger.error(f"Failed to reload templates: {e}")
            return {"error": str(e)}

    # =============================================================================
    # MESSAGE OPERATIONS (Shared between both services)
    # =============================================================================

    async def calculate_optimal_send_time(
        self, patient: Patient, current_day: int
    ) -> datetime:
        """
        Calculate optimal send time for patient message with robust error handling.

        Args:
            patient: Patient object with timezone and preferences
            current_day: Current day in flow (for logging context)

        Returns:
            datetime: Optimal send time (always returns valid datetime)
        """
        try:
            # Get patient preferences for message timing with validation
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

            # Calculate send time in Sao Paulo for scheduling
            now_local = now_sao_paulo()
            send_time_local = now_local.replace(
                hour=preferred_hour, minute=0, second=0, microsecond=0
            )

            # If the time has already passed today, schedule for tomorrow
            if send_time_local <= now_local:
                send_time_local += timedelta(days=1)
                logger.debug(
                    f"Preferred time passed, scheduling for tomorrow: {send_time_local}"
                )

            # Add some randomization to avoid all messages at exact same time
            try:
                import random

                random_minutes = random.randint(-30, 30)  # ±30 minutes
                send_time_local += timedelta(minutes=random_minutes)
            except Exception as rand_error:
                logger.warning(f"Randomization failed: {rand_error}, using exact hour")

            send_time = send_time_local.astimezone(SAO_PAULO_TZ)
            logger.info(
                f"Calculated send time for patient {patient.id} on day {current_day}: "
                f"{send_time.isoformat()} (tz: {SAO_PAULO_TZ_NAME}, hour: {preferred_hour})"
            )
            return send_time

        except Exception as e:
            logger.error(
                f"Failed to calculate optimal send time for patient {patient.id} day {current_day}: {e}. "
                f"Using fallback: 1 hour from now",
                exc_info=True,
            )
            # Fallback to 1 hour from now
            return now_sao_paulo().astimezone(SAO_PAULO_TZ) + timedelta(hours=1)

    def is_transient_error(self, error: Exception) -> bool:
        """
        Determine if error is transient and worth retrying.

        Args:
            error: Exception to evaluate

        Returns:
            bool: True if error is transient and retry is recommended
        """
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
        """Interpret awaiting_response with tolerant truthy string handling."""
        return is_awaiting_response(step_data)

    # =============================================================================
    # HEALTH MONITORING (Shared between both services)
    # =============================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on FlowCore components.

        Returns:
            Health check results
        """
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(text("SELECT 1"))
        results = {
            "flow_core": True,
            "database": True,
            "template_cache": False,
            "timestamp": now_sao_paulo().isoformat(),
        }

        try:
            # Test database connection
            self.db.execute("SELECT 1")
            results["database"] = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            results["database"] = False

        try:
            # Test template cache
            cache_stats = await self.template_cache.get_cache_stats()
            results["template_cache"] = cache_stats.get("redis_connected", False)
            results["template_cache_stats"] = cache_stats
        except Exception as e:
            logger.error(f"Template cache health check failed: {e}")
            results["template_cache"] = False

        results["overall_healthy"] = all(
            [results["flow_core"], results["database"], results["template_cache"]]
        )

        return results

    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================

    async def _transition_flow_type(
        self, flow_state: PatientFlowState, new_flow_type: FlowType, current_day: int
    ) -> None:
        """Transition flow to new type."""
        old_flow_type = flow_state.flow_type

        flow_state.flow_type = new_flow_type.value
        flow_state.step_data = flow_state.step_data or {}
        flow_state.step_data["transitions"] = flow_state.step_data.get(
            "transitions", []
        )
        flow_state.step_data["transitions"].append(
            {
                "timestamp": now_sao_paulo().isoformat(),
                "from_flow": old_flow_type,
                "to_flow": new_flow_type.value,
                "at_day": current_day,
            }
        )
