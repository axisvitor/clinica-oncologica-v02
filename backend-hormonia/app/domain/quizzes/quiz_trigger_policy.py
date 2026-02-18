"""
Quiz Trigger Policy - Centralized quiz day logic and trigger rules.

This module provides a single source of truth for quiz trigger policies,
ensuring consistent behavior across all quiz-related services and schedulers.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class QuizTriggerPolicy:
    """
    Centralized policy for quiz triggers and scheduling.

    This class provides a single source of truth for all quiz trigger logic,
    ensuring consistent behavior across:
    - QuizScheduler (domain/flows/scheduling/)
    - QuizTriggerService (domain/quizzes/integration/)
    - FlowScheduler (domain/flows/core/)
    - Celery tasks (tasks/quiz_flow/)

    Attributes:
        MONTHLY_QUIZ_DAY: Day of the month when quiz should trigger (1-30)
        INITIAL_ASSESSMENT_DAY: Day for initial assessment quiz
        MID_TREATMENT_DAY: Day for mid-treatment assessment quiz
        MAX_ADAPTATION_RETRIES: Maximum number of adaptation attempts
    """

    # Quiz trigger day constants
    MONTHLY_QUIZ_DAY = 30  # Centralized: day 30 of each monthly cycle
    INITIAL_ASSESSMENT_DAY = 15  # Day 15 of initial flow
    MID_TREATMENT_DAY = 45  # Day 45 for mid-treatment assessment

    # Adaptation limits
    MAX_ADAPTATION_RETRIES = 3  # Maximum adaptation attempts to prevent infinite loops

    @classmethod
    def is_quiz_day(
        cls, current_day: int, flow_type: str, days_since_enrollment: int | None = None
    ) -> bool:
        """
        Determine if current day should trigger a quiz based on flow type.

        Args:
            current_day: Current day in the flow
            flow_type: Canonical flow kind (quiz_mensal, onboarding, daily_follow_up)
            days_since_enrollment: Optional total days since patient enrollment

        Returns:
            True if quiz should be triggered on this day

        Example:
            >>> QuizTriggerPolicy.is_quiz_day(30, "quiz_mensal")
            True
            >>> QuizTriggerPolicy.is_quiz_day(15, "onboarding")
            True
            >>> QuizTriggerPolicy.is_quiz_day(20, "quiz_mensal")
            False
        """
        try:
            flow_kind = str(flow_type or "").strip()

            # Monthly recurring flow - triggers on day 30 of each cycle
            if flow_kind == "quiz_mensal":
                # For monthly cycles, check if we're on day 30 of the current 30-day cycle
                if days_since_enrollment is not None and days_since_enrollment >= 45:
                    # Patient is in monthly phase (after day 45)
                    days_in_monthly_phase = days_since_enrollment - 45
                    day_in_current_cycle = (days_in_monthly_phase % 30) + 1
                    return day_in_current_cycle == cls.MONTHLY_QUIZ_DAY
                else:
                    # Direct day check for flow day counter
                    return current_day == cls.MONTHLY_QUIZ_DAY

            # Initial assessment flow (days 1-15)
            if flow_kind == "onboarding":
                return current_day == cls.INITIAL_ASSESSMENT_DAY

            # Mid-treatment assessment flow (days 16-45)
            if flow_kind == "daily_follow_up":
                return current_day == cls.MID_TREATMENT_DAY

            logger.debug(
                f"No quiz trigger rule for flow_type={flow_type}, current_day={current_day}"
            )
            return False

        except Exception as e:
            logger.error(
                f"Error checking quiz day: {e}",
                extra={
                    "current_day": current_day,
                    "flow_type": flow_type,
                    "days_since_enrollment": days_since_enrollment,
                },
            )
            return False

    @classmethod
    def calculate_monthly_cycle(cls, days_since_enrollment: int) -> tuple[int, int]:
        """
        Calculate which monthly cycle the patient is in and which day.

        Args:
            days_since_enrollment: Total days since patient enrollment

        Returns:
            Tuple of (monthly_cycle_number, day_in_current_cycle)

        Example:
            >>> QuizTriggerPolicy.calculate_monthly_cycle(50)
            (1, 6)  # Cycle 1, day 6
            >>> QuizTriggerPolicy.calculate_monthly_cycle(75)
            (2, 1)  # Cycle 2, day 1
        """
        try:
            if days_since_enrollment < 45:
                # Patient is still in initial/mid-treatment phase
                return 0, days_since_enrollment

            # Patient is in monthly recurring phase
            days_in_monthly_phase = days_since_enrollment - 45
            monthly_cycle = (days_in_monthly_phase // 30) + 1
            day_in_cycle = (days_in_monthly_phase % 30) + 1

            return monthly_cycle, day_in_cycle

        except Exception as e:
            logger.error(f"Error calculating monthly cycle: {e}")
            return 0, 0

    @classmethod
    def should_trigger_quiz(
        cls,
        flow_type: str,
        current_day: int,
        days_since_enrollment: int | None = None,
        has_active_session: bool = False,
    ) -> dict[str, Any]:
        """
        Comprehensive check if quiz should be triggered with detailed reasoning.

        Args:
            flow_type: Current flow type
            current_day: Current day in flow
            days_since_enrollment: Optional days since enrollment
            has_active_session: Whether patient already has an active quiz session

        Returns:
            Dictionary with trigger decision and metadata:
            {
                "should_trigger": bool,
                "reason": str,
                "quiz_type": str,
                "monthly_cycle": int or None,
                "metadata": dict
            }

        Example:
            >>> QuizTriggerPolicy.should_trigger_quiz("quiz_mensal", 30, 74)
            {
                "should_trigger": True,
                "reason": "Monthly quiz day (day 30 of cycle 1)",
                "quiz_type": "monthly_assessment",
                "monthly_cycle": 1,
                "metadata": {"day_in_cycle": 30}
            }
        """
        result = {
            "should_trigger": False,
            "reason": "No trigger condition met",
            "quiz_type": None,
            "monthly_cycle": None,
            "metadata": {},
        }

        try:
            # Check if patient already has active session
            if has_active_session:
                result["reason"] = "Patient already has active quiz session"
                return result

            # Check if it's a quiz day
            is_trigger_day = cls.is_quiz_day(
                current_day, flow_type, days_since_enrollment
            )

            if not is_trigger_day:
                result["reason"] = f"Not a quiz trigger day (day {current_day})"
                return result

            # Determine quiz type and cycle
            flow_kind = str(flow_type or "").strip()
            if flow_kind == "quiz_mensal":
                if days_since_enrollment is not None:
                    monthly_cycle, day_in_cycle = cls.calculate_monthly_cycle(
                        days_since_enrollment
                    )
                    result.update(
                        {
                            "should_trigger": True,
                            "reason": f"Monthly quiz day (day {cls.MONTHLY_QUIZ_DAY} of cycle {monthly_cycle})",
                            "quiz_type": "monthly_assessment",
                            "monthly_cycle": monthly_cycle,
                            "metadata": {
                                "day_in_cycle": day_in_cycle,
                                "days_since_enrollment": days_since_enrollment,
                            },
                        }
                    )
                else:
                    result.update(
                        {
                            "should_trigger": True,
                            "reason": f"Monthly quiz day {current_day}",
                            "quiz_type": "monthly_assessment",
                            "monthly_cycle": 1,
                        }
                    )

            elif flow_kind == "onboarding":
                result.update(
                    {
                        "should_trigger": True,
                        "reason": "Initial assessment quiz (day 15)",
                        "quiz_type": "initial_assessment",
                        "monthly_cycle": None,
                    }
                )

            elif flow_kind == "daily_follow_up":
                result.update(
                    {
                        "should_trigger": True,
                        "reason": "Mid-treatment assessment quiz (day 45)",
                        "quiz_type": "mid_treatment_assessment",
                        "monthly_cycle": None,
                    }
                )

            return result

        except Exception as e:
            logger.error(
                f"Error in should_trigger_quiz: {e}",
                extra={
                    "flow_type": flow_type,
                    "current_day": current_day,
                    "days_since_enrollment": days_since_enrollment,
                },
            )
            result["reason"] = f"Error checking trigger: {str(e)}"
            return result

    @classmethod
    def get_next_quiz_day(
        cls, current_day: int, flow_type: str
    ) -> tuple[int | None, str]:
        """
        Calculate the next quiz trigger day for a given flow.

        Args:
            current_day: Current day in flow
            flow_type: Type of flow

        Returns:
            Tuple of (next_quiz_day, reason)

        Example:
            >>> QuizTriggerPolicy.get_next_quiz_day(10, "quiz_mensal")
            (30, "Next monthly quiz")
        """
        try:
            flow_kind = str(flow_type or "").strip()

            if flow_kind == "quiz_mensal":
                if current_day < cls.MONTHLY_QUIZ_DAY:
                    return cls.MONTHLY_QUIZ_DAY, "Next monthly quiz"
                else:
                    # Next cycle
                    return (
                        cls.MONTHLY_QUIZ_DAY + 30,
                        "Next monthly quiz (next cycle)",
                    )

            elif flow_kind == "onboarding":
                if current_day < cls.INITIAL_ASSESSMENT_DAY:
                    return cls.INITIAL_ASSESSMENT_DAY, "Initial assessment"
                else:
                    return None, "Initial assessment already passed"

            elif flow_kind == "daily_follow_up":
                if current_day < cls.MID_TREATMENT_DAY:
                    return cls.MID_TREATMENT_DAY, "Mid-treatment assessment"
                else:
                    return None, "Mid-treatment assessment already passed"

            return None, "No next quiz day defined for this flow type"

        except Exception as e:
            logger.error(f"Error calculating next quiz day: {e}")
            return None, f"Error: {str(e)}"


class AdaptationLimitError(Exception):
    """Raised when adaptation retry limit is exceeded."""

    pass


def check_adaptation_limit(adaptation_count: int) -> None:
    """
    Check if adaptation count exceeds maximum allowed retries.

    Args:
        adaptation_count: Current number of adaptations

    Raises:
        AdaptationLimitError: If adaptation count exceeds limit
    """
    if adaptation_count >= QuizTriggerPolicy.MAX_ADAPTATION_RETRIES:
        raise AdaptationLimitError(
            f"Maximum adaptation retries ({QuizTriggerPolicy.MAX_ADAPTATION_RETRIES}) exceeded"
        )
