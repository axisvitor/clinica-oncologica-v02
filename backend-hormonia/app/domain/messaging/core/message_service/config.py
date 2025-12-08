"""
Message Service Configuration - Enums and Constants (QW-022).

This module contains configuration classes, enums, and constants
used throughout the message service package.
"""

from enum import Enum
from datetime import time


class MessageTemplate(Enum):
    """Pre-defined message templates."""

    QUIZ_INTRODUCTION = "quiz_introduction"
    QUIZ_QUESTION = "quiz_question"
    QUIZ_COMPLETION = "quiz_completion"
    QUIZ_CLARIFICATION = "quiz_clarification"
    QUIZ_PAUSED = "quiz_paused"
    FLOW_MESSAGE = "flow_message"
    ALERT_MESSAGE = "alert_message"
    REMINDER = "reminder"
    FOLLOW_UP = "follow_up"
    MONTHLY_QUIZ_LINK_INVITATION = "monthly_quiz_link_invitation"
    MONTHLY_QUIZ_LINK_REMINDER = "monthly_quiz_link_reminder"
    MONTHLY_QUIZ_LINK_EXPIRED = "monthly_quiz_link_expired"
    MONTHLY_QUIZ_LINK_COMPLETED = "monthly_quiz_link_completed"


class SchedulingWindow(Enum):
    """Predefined scheduling windows for message delivery."""

    MORNING = "morning"  # 9:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 17:00
    EVENING = "evening"  # 17:00 - 20:00
    BUSINESS_HOURS = "business_hours"  # 9:00 - 18:00
    EXTENDED_HOURS = "extended_hours"  # 8:00 - 21:00


class MessageSchedulerConfig:
    """Configuration constants for MessageScheduler."""

    # Scheduling windows (start_time, end_time)
    SCHEDULING_WINDOWS = {
        SchedulingWindow.MORNING: (time(9, 0), time(12, 0)),
        SchedulingWindow.AFTERNOON: (time(12, 0), time(17, 0)),
        SchedulingWindow.EVENING: (time(17, 0), time(20, 0)),
        SchedulingWindow.BUSINESS_HOURS: (time(9, 0), time(18, 0)),
        SchedulingWindow.EXTENDED_HOURS: (time(8, 0), time(21, 0)),
    }

    # Message constraints
    MAX_MESSAGE_LENGTH = 4096  # WhatsApp message limit
    MIN_SCHEDULING_BUFFER_MINUTES = 15  # Minimum time before sending
    FALLBACK_DELAY_MINUTES = 30  # Fallback delay when calculation fails

    # Default timezone
    DEFAULT_TIMEZONE = "America/Sao_Paulo"

    # Retry configuration
    MAX_TASK_RETRIES = 3
    RETRY_DELAY_SECONDS = 60
