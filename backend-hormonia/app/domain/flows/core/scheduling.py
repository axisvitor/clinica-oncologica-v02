"""
Scheduling Module.
Handles flow scheduling, optimal send time calculation, and daily flow processing.
"""
import logging
from typing import Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository

logger = logging.getLogger(__name__)


class FlowScheduler:
    """Manages flow scheduling, timing, and daily processing coordination."""

    def __init__(self, db: Session):
        """
        Initialize flow scheduler.

        Args:
            db: Database session
        """
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)

    async def calculate_optimal_send_time(self, patient: Patient, current_day: int) -> datetime:
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

    async def check_quiz_trigger(self, patient_id: UUID, current_day: int, flow_type: str) -> dict[str, Any]:
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
            from app.domain.quizzes.integration.flow_integration import QuizTriggerService
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

    async def get_active_flows(self, limit: int = 1000) -> list[PatientFlowState]:
        """
        Get all active flow states for processing.

        Args:
            limit: Maximum number of flows to retrieve

        Returns:
            List of active flow states
        """
        try:
            return self.flow_state_repo.get_active_flows(limit=limit)
        except Exception as e:
            logger.error(f"Failed to get active flows: {e}")
            return []

    async def should_skip_patient_flow(self, flow_state: PatientFlowState) -> tuple[bool, Optional[str]]:
        """
        Determine if patient flow should be skipped.

        Args:
            flow_state: Patient flow state

        Returns:
            Tuple of (should_skip, reason)
        """
        try:
            # Check if patient is paused
            if flow_state.state_data and flow_state.state_data.get('paused'):
                return True, 'Patient flow is paused'

            # Check if flow is completed
            if flow_state.state_data and flow_state.state_data.get('status') == 'completed':
                return True, 'Flow is completed'

            # Check if patient exists
            patient = self.patient_repo.get(flow_state.patient_id)
            if not patient:
                return True, 'Patient not found'

            return False, None

        except Exception as e:
            logger.error(f"Error checking if flow should be skipped: {e}")
            return True, f'Error: {str(e)}'

    def calculate_processing_batch_size(self, total_flows: int, time_window_hours: int = 24) -> int:
        """
        Calculate optimal batch size for processing flows.

        Args:
            total_flows: Total number of flows to process
            time_window_hours: Time window in hours

        Returns:
            Optimal batch size
        """
        try:
            # Distribute processing evenly across time window
            # Aim for ~100 flows per batch as baseline
            baseline_batch = 100

            if total_flows <= baseline_batch:
                return total_flows

            # Calculate batches needed
            num_batches = (total_flows // baseline_batch) + 1

            # Ensure we don't create too many small batches
            if num_batches > time_window_hours:
                num_batches = time_window_hours

            batch_size = (total_flows // num_batches) + 1

            logger.info(
                f"Calculated batch size: {batch_size} for {total_flows} flows "
                f"over {time_window_hours}h window ({num_batches} batches)"
            )

            return batch_size

        except Exception as e:
            logger.error(f"Error calculating batch size: {e}")
            return 100  # Safe default

    async def validate_send_time(self, send_time: datetime, patient: Patient) -> tuple[bool, Optional[str]]:
        """
        Validate that send time is appropriate.

        Args:
            send_time: Proposed send time
            patient: Patient object

        Returns:
            Tuple of (is_valid, reason)
        """
        try:
            now = datetime.utcnow()

            # Check if time is in the past
            if send_time < now:
                return False, 'Send time is in the past'

            # Check if time is too far in the future (>7 days)
            if send_time > now + timedelta(days=7):
                return False, 'Send time is too far in the future'

            # Check if it's during reasonable hours (8 AM - 10 PM in patient's timezone)
            hour = send_time.hour
            if hour < 8 or hour > 22:
                logger.warning(f"Send time {send_time} is outside reasonable hours (8-22)")

            return True, None

        except Exception as e:
            logger.error(f"Error validating send time: {e}")
            return False, f'Validation error: {str(e)}'

    async def reschedule_failed_flow(self,
                                    flow_state: PatientFlowState,
                                    retry_delay_hours: int = 1) -> datetime:
        """
        Calculate reschedule time for failed flow.

        Args:
            flow_state: Failed flow state
            retry_delay_hours: Hours to delay retry

        Returns:
            New scheduled time
        """
        try:
            now = datetime.utcnow()

            # Get retry count from state data
            state_data = flow_state.state_data or {}
            retry_count = state_data.get('retry_count', 0)

            # Exponential backoff: 1h, 2h, 4h, 8h
            delay_hours = retry_delay_hours * (2 ** min(retry_count, 3))

            reschedule_time = now + timedelta(hours=delay_hours)

            logger.info(
                f"Rescheduling flow {flow_state.id} for patient {flow_state.patient_id} "
                f"in {delay_hours}h (attempt {retry_count + 1})"
            )

            return reschedule_time

        except Exception as e:
            logger.error(f"Error calculating reschedule time: {e}")
            return datetime.utcnow() + timedelta(hours=1)
