"""
Message scheduling configuration (canonical source).
"""

from app.domain.messaging.core.message_service.config import MessageSchedulerConfig

from .models import SchedulingWindow

__all__ = ["MessageSchedulerConfig", "SchedulingWindow"]
