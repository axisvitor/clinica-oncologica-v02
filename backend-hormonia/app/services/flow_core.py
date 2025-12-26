"""
FlowCore - Base class for all flow operations.
Contains shared functionality extracted from EnhancedFlowEngine and FlowEngineIntegrationService.
"""

import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta, timezone
from uuid import UUID
from enum import Enum

from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.patient import Patient
from app.domain.messaging.core import MessageTemplate


from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.domain.flows.events import flow_event_broadcaster

logger = logging.getLogger(__name__)


class FlowType(Enum):
    INITIAL_15_DAYS = "initial_15_days"
    DAYS_16_45 = "days_16_45"
    MONTHLY_RECURRING = "monthly_recurring"


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


# Import ConcurrentModificationError for optimistic locking
from app.exceptions import ConcurrentModificationError

from app.services.platform_synchronization import PlatformSynchronizationService
from app.services.template_loader import EnhancedTemplateLoader
from app.services.unified_cache import UnifiedCacheService


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

        # Dependency Injection with fallback for backward compatibility (optional, but safer during transition)
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
        # Refresh from DB to get latest version
        self.db.refresh(flow_state)

        if flow_state.version != expected_version:
            raise ConcurrentModificationError(
                resource_type="PatientFlowState",
                resource_id=str(flow_state.id),
                expected_version=expected_version,
                actual_version=flow_state.version,
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
        flow_type: FlowType = FlowType.INITIAL_15_DAYS,
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
        flow_state = PatientFlowState(
            patient_id=patient_id,
            flow_template_version_id=active_version.id,
            current_step=1,  # Start at day 1
            started_at=datetime.now(timezone.utc),
            step_data={
                "enrollment_date": datetime.now(timezone.utc).isoformat(),
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
        flow_state = self.flow_state_repo.get_active_flow(patient_id)
        if not flow_state:
            return 1

        # Get patient timezone
        timezone_str = "America/Sao_Paulo"
        if flow_state.patient and hasattr(flow_state.patient, "timezone"):
            timezone_str = flow_state.patient.timezone

        try:
            import pytz

            tz = pytz.timezone(timezone_str)
        except Exception:
            logger.warning(
                f"Invalid timezone {timezone_str} for patient {patient_id}, defaulting to America/Sao_Paulo"
            )
            import pytz

            tz = pytz.timezone("America/Sao_Paulo")

        # Calculate days since enrollment using local time
        enrollment_date_str = flow_state.step_data.get(
            "enrollment_date", flow_state.started_at.isoformat()
        )
        enrollment_dt = datetime.fromisoformat(enrollment_date_str)

        # Ensure enrollment_dt is timezone aware
        if enrollment_dt.tzinfo is None:
            enrollment_dt = pytz.utc.localize(enrollment_dt)

        enrollment_local = enrollment_dt.astimezone(tz)
        now_local = datetime.now(tz)

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
        if current_day <= 15:
            return FlowType.INITIAL_15_DAYS
        elif current_day <= 45:
            return FlowType.DAYS_16_45
        else:
            return FlowType.MONTHLY_RECURRING

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
        try:
            # Get current flow state
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            # Calculate current day
            current_day = force_day or await self.calculate_patient_day(patient_id)

            # Determine if flow type transition is needed
            current_flow_type = FlowType(flow_state.flow_type)
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
            flow_state.step_data = flow_state.step_data or {}
            flow_state.step_data["last_advancement"] = datetime.now(timezone.utc).isoformat()

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
                        "timestamp": datetime.now(timezone.utc).isoformat(),
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
            flow_state.step_data = flow_state.step_data or {}
            flow_state.step_data["paused"] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": reason or "Manual pause",
                "current_step": flow_state.current_step,
            }

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
                "paused_at": datetime.now(timezone.utc).isoformat(),
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
            if flow_state.step_data and "paused" in flow_state.step_data:
                paused_data = flow_state.step_data.pop("paused")
                flow_state.step_data["resumed"] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "was_paused_at": paused_data.get("timestamp"),
                    "pause_reason": paused_data.get("reason"),
                }

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
                "resumed_at": datetime.now(timezone.utc).isoformat(),
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
        Get message template for specific flow type and day with comprehensive error handling.

        Args:
            flow_type: Type of flow
            day: Day number in the flow

        Returns:
            MessageTemplate or None if all fallbacks fail
        """
        try:
            # Load flow template with proper error handling
            from app.services.template_loader import TemplateLoadError, FlowTemplateData

            try:
                flow_template: FlowTemplateData = (
                    self.template_loader.load_flow_template(flow_type.value)
                )
            except TemplateLoadError as e:
                logger.error(
                    f"Template load error for {flow_type.value}: {e}. Using fallback message."
                )
                return await self._get_fallback_template(flow_type, day)
            except FileNotFoundError as e:
                logger.error(
                    f"Template file not found for {flow_type.value}: {e}. Using fallback message."
                )
                return await self._get_fallback_template(flow_type, day)
            except Exception as e:
                logger.error(
                    f"Unexpected error loading template {flow_type.value}: {e}. Using fallback message.",
                    exc_info=True,
                )
                return await self._get_fallback_template(flow_type, day)

            # Get message for specific day from FlowTemplateData.messages dict
            if day in flow_template.messages:
                message_template = flow_template.messages[day]
                logger.debug(f"Found message template for {flow_type.value} day {day}")
                return message_template

            logger.warning(
                f"No message template found for {flow_type.value} day {day}. Using fallback message."
            )
            return await self._get_fallback_template(flow_type, day)

        except Exception as e:
            logger.error(
                f"Critical error getting message template for {flow_type.value} day {day}: {e}. Using fallback message.",
                exc_info=True,
            )
            return await self._get_fallback_template(flow_type, day)

    async def _get_fallback_template(
        self, flow_type: FlowType, day: int
    ) -> Optional[MessageTemplate]:
        """Provide fallback template when primary template loading fails."""
        try:
            from app.services.template_loader import MessageType as TemplateMessageType

            # Create a simple fallback message template in Portuguese
            fallback_messages = {
                FlowType.INITIAL_15_DAYS: {
                    "content": "Olá! Como você está se sentindo hoje?",
                    "intent": "daily_check_initial",
                    "ai_instructions": "Generate a warm, caring message asking about patient well-being",
                },
                FlowType.DAYS_16_45: {
                    "content": "Esperamos que você esteja bem. Como está seu tratamento?",
                    "intent": "treatment_followup",
                    "ai_instructions": "Generate an empathetic message about treatment progress",
                },
                FlowType.MONTHLY_RECURRING: {
                    "content": "Olá! É hora de fazer seu check-in mensal.",
                    "intent": "monthly_checkin",
                    "ai_instructions": "Generate a friendly monthly check-in message",
                },
            }

            fallback_data = fallback_messages.get(
                flow_type,
                {
                    "content": "Olá! Como podemos ajudá-lo hoje?",
                    "intent": "general_checkin",
                    "ai_instructions": "Generate a supportive, caring message",
                },
            )

            logger.warning(f"Using fallback template for {flow_type.value} day {day}")

            return MessageTemplate(
                day=day,
                intent=fallback_data["intent"],
                base_content=fallback_data["content"],
                core_elements={"greeting": True, "care": True, "support": True},
                personalization_hints=[
                    "patient_name",
                    "treatment_type",
                    "patient_condition",
                ],
                ai_instructions=fallback_data["ai_instructions"],
                message_type=TemplateMessageType.TEXT,
                variations=[],  # No variations for fallback
            )
        except Exception as e:
            logger.error(
                f"Critical failure generating fallback template: {e}. Returning None.",
                exc_info=True,
            )
            return None

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
            # Get patient timezone with validation
            try:
                patient_tz = getattr(patient, "timezone", "UTC")
                if not patient_tz or not isinstance(patient_tz, str):
                    logger.warning(
                        f"Invalid timezone for patient {patient.id}, using UTC"
                    )
                    patient_tz = "UTC"
            except Exception as tz_error:
                logger.warning(f"Error reading patient timezone: {tz_error}, using UTC")
                patient_tz = "UTC"

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

            # Calculate send time for today
            now = datetime.now(timezone.utc)
            send_time = now.replace(
                hour=preferred_hour, minute=0, second=0, microsecond=0
            )

            # If the time has already passed today, schedule for tomorrow
            if send_time <= now:
                send_time += timedelta(days=1)
                logger.debug(
                    f"Preferred time passed, scheduling for tomorrow: {send_time}"
                )

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
                exc_info=True,
            )
            # Fallback to 1 hour from now
            return datetime.now(timezone.utc) + timedelta(hours=1)

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

    # =============================================================================
    # HEALTH MONITORING (Shared between both services)
    # =============================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on FlowCore components.

        Returns:
            Health check results
        """
        results = {
            "flow_core": True,
            "database": True,
            "template_cache": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from_flow": old_flow_type,
                "to_flow": new_flow_type.value,
                "at_day": current_day,
            }
        )
