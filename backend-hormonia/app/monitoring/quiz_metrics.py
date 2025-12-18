"""
Quiz Metrics Collection

This module provides Prometheus metrics for monitoring the monthly quiz system.
"""

import time
from typing import Optional
from functools import wraps
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    REGISTRY,
)
from fastapi import Response
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# Metric Definitions
# =============================================================================

# Quiz Link Metrics
quiz_links_created = Counter(
    "quiz_links_created_total",
    "Total number of quiz links created",
    ["quiz_type", "month"],
)

quiz_links_completed = Counter(
    "quiz_links_completed_total",
    "Total number of quiz links completed",
    ["quiz_type", "month", "after_reminder"],
)

quiz_links_expired = Counter(
    "quiz_links_expired_total",
    "Total number of quiz links that expired",
    ["quiz_type", "month"],
)

quiz_link_completion_rate = Gauge(
    "quiz_link_completion_rate", "Percentage of quiz links completed", ["quiz_type"]
)

# Reminder Metrics
quiz_reminders_sent = Counter(
    "quiz_reminders_sent_total",
    "Total number of quiz reminders sent",
    ["quiz_type", "reminder_number", "month"],
)

quiz_reminder_success = Counter(
    "quiz_reminder_success_total",
    "Total number of successful reminder deliveries",
    ["quiz_type", "reminder_number", "month"],
)

quiz_reminder_failure = Counter(
    "quiz_reminder_failure_total",
    "Total number of failed reminder deliveries",
    ["quiz_type", "reminder_number", "error_type", "month"],
)

# Fallback Metrics
quiz_fallback_activated = Counter(
    "quiz_fallback_activated_total",
    "Total number of times fallback to WhatsApp was activated",
    ["quiz_type", "reason", "month"],
)

quiz_fallback_completion = Counter(
    "quiz_fallback_completion_total",
    "Total number of fallback completions",
    ["quiz_type", "month"],
)

# Response Time Metrics
quiz_response_time = Histogram(
    "quiz_response_time_seconds",
    "Time taken to complete quiz (from link creation to completion)",
    ["quiz_type"],
    buckets=[300, 600, 1800, 3600, 7200, 14400, 43200, 86400, 172800],  # 5min to 2 days
)

quiz_link_access_time = Histogram(
    "quiz_link_access_time_seconds",
    "Time from link creation to first access",
    ["quiz_type"],
    buckets=[60, 300, 900, 1800, 3600, 7200, 14400, 43200, 86400],  # 1min to 1 day
)

# Token Metrics
quiz_token_expiry_rate = Gauge(
    "quiz_token_expiry_rate", "Rate of token expiration", ["quiz_type"]
)

quiz_active_tokens = Gauge(
    "quiz_active_tokens", "Number of currently active quiz tokens", ["quiz_type"]
)

# System Health Metrics
quiz_api_requests = Counter(
    "quiz_api_requests_total",
    "Total quiz API requests",
    ["endpoint", "method", "status"],
)

quiz_api_latency = Histogram(
    "quiz_api_latency_seconds",
    "Quiz API request latency",
    ["endpoint", "method"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

quiz_database_queries = Histogram(
    "quiz_database_query_duration_seconds",
    "Quiz database query duration",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

# Business Metrics
quiz_participation_rate = Gauge(
    "quiz_participation_rate",
    "Percentage of eligible patients participating in quiz",
    ["month"],
)

average_quiz_score = Gauge(
    "average_quiz_score", "Average quiz completion score", ["quiz_type", "month"]
)

quiz_patient_segments = Gauge(
    "quiz_patient_segments", "Number of patients by segment", ["segment", "quiz_type"]
)

# Info Metric
quiz_system_info = Info("quiz_system", "Information about the quiz system")

# Initialize system info
quiz_system_info.info(
    {
        "version": "1.0.0",
        "feature": "monthly_quiz",
        "link_expiry_hours": "72",
        "max_reminders": "2",
    }
)

# =============================================================================
# Helper Functions
# =============================================================================


def track_quiz_link_created(
    patient_id: str, quiz_type: str = "monthly", month: str = None
):
    """Track when a quiz link is created"""
    try:
        if month is None:
            from datetime import datetime

            month = datetime.now().strftime("%Y-%m")

        quiz_links_created.labels(quiz_type=quiz_type, month=month).inc()

        # Update active tokens gauge
        quiz_active_tokens.labels(quiz_type=quiz_type).inc()

        logger.debug(
            f"Tracked quiz link creation for quiz_type {quiz_type}, month {month}"
        )
    except Exception as e:
        logger.error(f"Error tracking quiz link creation: {e}")


def track_quiz_link_completed(
    patient_id: str,
    quiz_type: str = "monthly",
    after_reminder: bool = False,
    response_time_seconds: Optional[float] = None,
    month: str = None,
):
    """Track when a quiz link is completed"""
    try:
        if month is None:
            from datetime import datetime

            month = datetime.now().strftime("%Y-%m")

        quiz_links_completed.labels(
            quiz_type=quiz_type, month=month, after_reminder=str(after_reminder).lower()
        ).inc()

        # Update active tokens gauge
        quiz_active_tokens.labels(quiz_type=quiz_type).dec()

        # Track response time if provided
        if response_time_seconds:
            quiz_response_time.labels(quiz_type=quiz_type).observe(
                response_time_seconds
            )

        logger.debug(
            f"Tracked quiz link completion for quiz_type {quiz_type}, month {month}"
        )
    except Exception as e:
        logger.error(f"Error tracking quiz link completion: {e}")


def track_quiz_link_expired(
    patient_id: str, quiz_type: str = "monthly", month: str = None
):
    """Track when a quiz link expires"""
    try:
        if month is None:
            from datetime import datetime

            month = datetime.now().strftime("%Y-%m")

        quiz_links_expired.labels(quiz_type=quiz_type, month=month).inc()

        # Update active tokens gauge
        quiz_active_tokens.labels(quiz_type=quiz_type).dec()

        logger.debug(
            f"Tracked quiz link expiry for quiz_type {quiz_type}, month {month}"
        )
    except Exception as e:
        logger.error(f"Error tracking quiz link expiry: {e}")


def track_quiz_reminder_sent(
    patient_id: str,
    reminder_number: int,
    quiz_type: str = "monthly",
    success: bool = True,
    error_type: Optional[str] = None,
    month: str = None,
):
    """Track when a quiz reminder is sent"""
    try:
        if month is None:
            from datetime import datetime

            month = datetime.now().strftime("%Y-%m")

        quiz_reminders_sent.labels(
            quiz_type=quiz_type, reminder_number=str(reminder_number), month=month
        ).inc()

        if success:
            quiz_reminder_success.labels(
                quiz_type=quiz_type, reminder_number=str(reminder_number), month=month
            ).inc()
        else:
            quiz_reminder_failure.labels(
                quiz_type=quiz_type,
                reminder_number=str(reminder_number),
                error_type=error_type or "unknown",
                month=month,
            ).inc()

        logger.debug(
            f"Tracked reminder {reminder_number} for quiz_type {quiz_type}, month {month}"
        )
    except Exception as e:
        logger.error(f"Error tracking quiz reminder: {e}")


def track_quiz_fallback_activated(
    patient_id: str,
    quiz_type: str = "monthly",
    reason: str = "expired",
    completed: bool = False,
    month: str = None,
):
    """Track when fallback to WhatsApp is activated"""
    try:
        if month is None:
            from datetime import datetime

            month = datetime.now().strftime("%Y-%m")

        quiz_fallback_activated.labels(
            quiz_type=quiz_type, reason=reason, month=month
        ).inc()

        if completed:
            quiz_fallback_completion.labels(quiz_type=quiz_type, month=month).inc()

        logger.debug(
            f"Tracked fallback activation for quiz_type {quiz_type}, month {month}"
        )
    except Exception as e:
        logger.error(f"Error tracking quiz fallback: {e}")


def track_quiz_link_access(quiz_type: str, access_time_seconds: float):
    """Track when a quiz link is first accessed"""
    try:
        quiz_link_access_time.labels(quiz_type=quiz_type).observe(access_time_seconds)
        logger.debug(f"Tracked quiz link access time: {access_time_seconds}s")
    except Exception as e:
        logger.error(f"Error tracking quiz link access: {e}")


def update_completion_rate(quiz_type: str = "monthly", month: str = None):
    """Calculate and update the quiz completion rate"""
    try:
        from datetime import datetime

        if month is None:
            month = datetime.now().strftime("%Y-%m")

        # Calculate completion rate based on aggregated metrics
        # This would need to be implemented based on your specific data aggregation logic
        # For now, just update the gauge with a placeholder calculation

        # Example: You could aggregate from your database here
        # rate = calculate_rate_from_database(quiz_type, month)
        # quiz_link_completion_rate.labels(quiz_type=quiz_type).set(rate)

        logger.debug(f"Updated completion rate for {quiz_type}, month {month}")
    except Exception as e:
        logger.error(f"Error updating completion rate: {e}")


# =============================================================================
# Decorators
# =============================================================================


def track_api_request(endpoint: str):
    """Decorator to track API request metrics"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time

                # Track request
                quiz_api_requests.labels(
                    endpoint=endpoint,
                    method="POST",  # Most quiz endpoints are POST
                    status=status,
                ).inc()

                # Track latency
                quiz_api_latency.labels(endpoint=endpoint, method="POST").observe(
                    duration
                )

        return wrapper

    return decorator


def track_database_query(query_type: str):
    """Decorator to track database query metrics"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                quiz_database_queries.labels(query_type=query_type).observe(duration)

        return wrapper

    return decorator


# =============================================================================
# Metrics Exposition
# =============================================================================


class QuizMetrics:
    """Quiz metrics handler for FastAPI"""

    @staticmethod
    async def get_metrics():
        """Get Prometheus metrics in exposition format"""
        try:
            metrics = generate_latest(REGISTRY)
            return Response(
                content=metrics, media_type="text/plain; version=0.0.4; charset=utf-8"
            )
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return Response(
                content=f"# Error generating metrics: {str(e)}\n",
                media_type="text/plain",
                status_code=500,
            )

    @staticmethod
    def get_quiz_summary():
        """Get a summary of quiz metrics as JSON"""
        try:
            summary = {
                "links": {
                    "created": quiz_links_created._metrics,
                    "completed": quiz_links_completed._metrics,
                    "expired": quiz_links_expired._metrics,
                },
                "reminders": {
                    "sent": quiz_reminders_sent._metrics,
                    "success": quiz_reminder_success._metrics,
                    "failure": quiz_reminder_failure._metrics,
                },
                "fallback": {
                    "activated": quiz_fallback_activated._metrics,
                    "completed": quiz_fallback_completion._metrics,
                },
            }

            return summary
        except Exception as e:
            logger.error(f"Error generating quiz summary: {e}")
            return {"error": str(e)}


# =============================================================================
# Metrics Update Tasks
# =============================================================================


async def update_metrics_task():
    """Background task to update calculated metrics"""
    try:
        # Update completion rates for all quiz types
        for quiz_type in ["monthly", "wellness", "custom"]:
            update_completion_rate(quiz_type)

        logger.debug("Updated calculated metrics")
    except Exception as e:
        logger.error(f"Error updating metrics task: {e}")


# =============================================================================
# Export Metrics Registry
# =============================================================================


def get_registry():
    """Get the Prometheus registry"""
    return REGISTRY
