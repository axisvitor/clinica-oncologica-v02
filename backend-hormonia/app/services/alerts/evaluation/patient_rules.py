"""
Patient-specific alert rule evaluators.

This module provides evaluator functions for patient-related alert rules,
migrated from the original AlertService.
"""

import logging
from typing import Dict, Any, TYPE_CHECKING
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from ..rule_engine import RuleEngine

from ..types import (
    AlertRule,
    AlertEvaluation,
    AlertRuleType,
)

logger = logging.getLogger(__name__)


async def evaluate_no_response(
    rule: AlertRule, context: Dict[str, Any]
) -> AlertEvaluation:
    """
    Evaluate if patient hasn't responded within threshold time.

    Context expected keys:
    - patient_id: UUID of the patient
    - last_inbound_message_at: Datetime of last patient message (optional)
    - last_outbound_message_at: Datetime of last system message (optional)
    - outbound_messages_since_response: Count of messages sent since last response
    - patient_created_at: Patient registration datetime

    Rule condition expected keys:
    - threshold_hours: Hours without response before alert (default: 48)

    Args:
        rule: Alert rule configuration
        context: Evaluation context with patient data

    Returns:
        AlertEvaluation with triggered status and details
    """
    logger.debug(f"Evaluating no_response rule: {rule.name}")

    # Extract context
    context.get("patient_id")
    last_inbound_at = context.get("last_inbound_message_at")
    outbound_count = context.get("outbound_messages_since_response", 0)
    patient_created_at = context.get("patient_created_at", datetime.utcnow())

    # Extract rule configuration
    threshold_hours = rule.condition.get("threshold_hours", 48)

    # Calculate cutoff time
    cutoff_time = datetime.utcnow() - timedelta(hours=threshold_hours)

    # Check if we've sent messages without response
    if outbound_count > 0:
        # Determine reference time (last response or patient creation)
        reference_time = last_inbound_at if last_inbound_at else patient_created_at

        # Check if last response is before cutoff
        if reference_time < cutoff_time:
            hours_since = (datetime.utcnow() - reference_time).total_seconds() / 3600

            return AlertEvaluation(
                rule=rule,
                triggered=True,
                context=context,
                reason=f"Patient hasn't responded in {int(hours_since)} hours",
                metadata={
                    "hours_since_response": hours_since,
                    "last_response_at": reference_time.isoformat(),
                    "outbound_messages_sent": outbound_count,
                },
            )

    # Not triggered
    return AlertEvaluation(
        rule=rule,
        triggered=False,
        context=context,
        reason="Patient has responded recently",
        metadata={},
    )


async def evaluate_missed_quiz(
    rule: AlertRule, context: Dict[str, Any]
) -> AlertEvaluation:
    """
    Evaluate if patient has missed scheduled quizzes.

    Context expected keys:
    - patient_id: UUID of the patient
    - quiz_responses_count: Number of quiz responses in time window
    - expected_quiz_count: Expected number of quizzes in time window
    - time_window_hours: Time window to check (optional)

    Rule condition expected keys:
    - threshold: Minimum number of missed quizzes to trigger alert (default: 1)
    - time_window_hours: Hours to look back (default: 168 = 1 week)

    Args:
        rule: Alert rule configuration
        context: Evaluation context with quiz data

    Returns:
        AlertEvaluation with triggered status and details
    """
    logger.debug(f"Evaluating missed_quiz rule: {rule.name}")

    # Extract context
    context.get("patient_id")
    completed_count = context.get("quiz_responses_count", 0)
    expected_count = context.get("expected_quiz_count", 1)

    # Extract rule configuration
    threshold = rule.condition.get("threshold", 1)
    time_window_hours = rule.condition.get("time_window_hours", 168)

    # Calculate missed quizzes
    missed_count = max(0, expected_count - completed_count)

    # Check if missed count exceeds threshold
    if missed_count >= threshold:
        return AlertEvaluation(
            rule=rule,
            triggered=True,
            context=context,
            reason=f"Patient missed {missed_count} quiz(zes) in the last {time_window_hours} hours",
            metadata={
                "missed_count": missed_count,
                "expected_count": expected_count,
                "completed_count": completed_count,
                "time_window_hours": time_window_hours,
            },
        )

    # Not triggered
    return AlertEvaluation(
        rule=rule,
        triggered=False,
        context=context,
        reason=f"Patient completed {completed_count} of {expected_count} expected quizzes",
        metadata={
            "missed_count": missed_count,
            "expected_count": expected_count,
            "completed_count": completed_count,
        },
    )


async def evaluate_negative_sentiment(
    rule: AlertRule, context: Dict[str, Any]
) -> AlertEvaluation:
    """
    Evaluate if patient messages show concerning negative sentiment.

    Context expected keys:
    - patient_id: UUID of the patient
    - recent_messages: List of recent message dictionaries with sentiment data
    - sentiment_scores: List of sentiment scores (negative values)
    - time_window_hours: Time window analyzed

    Rule condition expected keys:
    - threshold: Minimum average negative sentiment score to trigger (default: 0.5)
    - time_window_hours: Hours to look back (default: 48)
    - min_messages: Minimum messages to analyze (default: 2)

    Args:
        rule: Alert rule configuration
        context: Evaluation context with sentiment data

    Returns:
        AlertEvaluation with triggered status and details
    """
    logger.debug(f"Evaluating negative_sentiment rule: {rule.name}")

    # Extract context
    context.get("patient_id")
    sentiment_scores = context.get("sentiment_scores", [])
    context.get("recent_messages", [])

    # Extract rule configuration
    threshold = rule.condition.get("threshold", 0.5)
    time_window_hours = rule.condition.get("time_window_hours", 48)
    min_messages = rule.condition.get("min_messages", 2)

    # Check if we have enough messages
    if len(sentiment_scores) < min_messages:
        return AlertEvaluation(
            rule=rule,
            triggered=False,
            context=context,
            reason=f"Not enough messages to analyze (need {min_messages}, have {len(sentiment_scores)})",
            metadata={
                "message_count": len(sentiment_scores),
                "min_required": min_messages,
            },
        )

    # Filter negative scores
    negative_scores = [abs(score) for score in sentiment_scores if score < 0]

    if not negative_scores:
        return AlertEvaluation(
            rule=rule,
            triggered=False,
            context=context,
            reason="No negative sentiment detected in recent messages",
            metadata={
                "message_count": len(sentiment_scores),
                "negative_count": 0,
            },
        )

    # Calculate average negative sentiment
    avg_negative_score = sum(negative_scores) / len(negative_scores)

    # Check if average exceeds threshold
    if avg_negative_score >= threshold:
        return AlertEvaluation(
            rule=rule,
            triggered=True,
            context=context,
            reason=f"High negative sentiment detected (score: {avg_negative_score:.2f})",
            metadata={
                "sentiment_score": avg_negative_score,
                "message_count": len(sentiment_scores),
                "negative_message_count": len(negative_scores),
                "time_window_hours": time_window_hours,
            },
        )

    # Not triggered
    return AlertEvaluation(
        rule=rule,
        triggered=False,
        context=context,
        reason=f"Negative sentiment below threshold (score: {avg_negative_score:.2f} < {threshold})",
        metadata={
            "sentiment_score": avg_negative_score,
            "message_count": len(sentiment_scores),
            "negative_message_count": len(negative_scores),
        },
    )


async def evaluate_treatment_adherence(
    rule: AlertRule, context: Dict[str, Any]
) -> AlertEvaluation:
    """
    Evaluate treatment adherence based on quiz responses.

    Context expected keys:
    - patient_id: UUID of the patient
    - adherence_scores: List of adherence scores (0.0 to 1.0)
    - quiz_responses_count: Number of quiz responses analyzed
    - time_window_hours: Time window analyzed

    Rule condition expected keys:
    - threshold: Minimum adherence percentage to pass (default: 0.7 = 70%)
    - time_window_hours: Hours to look back (default: 168 = 1 week)
    - min_responses: Minimum quiz responses to analyze (default: 2)

    Args:
        rule: Alert rule configuration
        context: Evaluation context with adherence data

    Returns:
        AlertEvaluation with triggered status and details
    """
    logger.debug(f"Evaluating treatment_adherence rule: {rule.name}")

    # Extract context
    context.get("patient_id")
    adherence_scores = context.get("adherence_scores", [])
    context.get("quiz_responses_count", 0)

    # Extract rule configuration
    threshold = rule.condition.get("threshold", 0.7)
    time_window_hours = rule.condition.get("time_window_hours", 168)
    min_responses = rule.condition.get("min_responses", 2)

    # Check if we have enough responses
    if len(adherence_scores) < min_responses:
        return AlertEvaluation(
            rule=rule,
            triggered=False,
            context=context,
            reason=f"Not enough quiz responses to analyze (need {min_responses}, have {len(adherence_scores)})",
            metadata={
                "response_count": len(adherence_scores),
                "min_required": min_responses,
            },
        )

    # Calculate average adherence
    avg_adherence = sum(adherence_scores) / len(adherence_scores)

    # Check if adherence is below threshold
    if avg_adherence < threshold:
        adherence_percentage = avg_adherence * 100

        return AlertEvaluation(
            rule=rule,
            triggered=True,
            context=context,
            reason=f"Low treatment adherence detected ({adherence_percentage:.1f}%)",
            metadata={
                "adherence_percentage": avg_adherence,
                "response_count": len(adherence_scores),
                "time_window_hours": time_window_hours,
                "threshold_percentage": threshold * 100,
            },
        )

    # Not triggered
    return AlertEvaluation(
        rule=rule,
        triggered=False,
        context=context,
        reason=f"Treatment adherence is acceptable ({avg_adherence * 100:.1f}%)",
        metadata={
            "adherence_percentage": avg_adherence,
            "response_count": len(adherence_scores),
        },
    )


async def evaluate_emergency_keywords(
    rule: AlertRule, context: Dict[str, Any]
) -> AlertEvaluation:
    """
    Evaluate if emergency keywords are present in recent messages.

    Context expected keys:
    - patient_id: UUID of the patient
    - recent_messages: List of recent message dictionaries with 'content' key
    - time_window_hours: Time window analyzed

    Rule condition expected keys:
    - keywords: List of emergency keywords (optional, uses defaults if not provided)
    - time_window_hours: Hours to look back (default: 24)
    - case_sensitive: Whether keyword matching is case-sensitive (default: False)

    Args:
        rule: Alert rule configuration
        context: Evaluation context with message data

    Returns:
        AlertEvaluation with triggered status and details
    """
    logger.debug(f"Evaluating emergency_keywords rule: {rule.name}")

    # Extract context
    context.get("patient_id")
    recent_messages = context.get("recent_messages", [])

    # Extract rule configuration
    default_keywords = [
        "emergency",
        "urgent",
        "help",
        "pain",
        "bleeding",
        "dizzy",
        "chest pain",
        "can't breathe",
        "cannot breathe",
        "suicide",
        "hurt myself",
        "kill myself",
        "severe pain",
        "extreme pain",
        "unbearable",
        "hospital",
        "ambulance",
        "dying",
    ]

    keywords = rule.condition.get("keywords", default_keywords)
    time_window_hours = rule.condition.get("time_window_hours", 24)
    case_sensitive = rule.condition.get("case_sensitive", False)

    # Check messages for keywords
    found_keywords = []
    messages_with_keywords = []

    for message in recent_messages:
        content = message.get("content", "")

        if not case_sensitive:
            content = content.lower()
            keywords_to_check = [kw.lower() for kw in keywords]
        else:
            keywords_to_check = keywords

        for keyword in keywords_to_check:
            if keyword in content:
                found_keywords.append(keyword)
                messages_with_keywords.append(
                    {
                        "message_id": message.get("id"),
                        "content": message.get("content"),
                        "keyword": keyword,
                        "created_at": message.get("created_at"),
                    }
                )

    # Check if any keywords found
    if found_keywords:
        unique_keywords = list(set(found_keywords))

        return AlertEvaluation(
            rule=rule,
            triggered=True,
            context=context,
            reason=f"Emergency keywords detected: {', '.join(unique_keywords)}",
            metadata={
                "keywords": unique_keywords,
                "keyword_occurrences": len(found_keywords),
                "message_count": len(recent_messages),
                "messages_with_keywords": len(messages_with_keywords),
                "time_window_hours": time_window_hours,
                "details": messages_with_keywords[:5],  # Limit to first 5
            },
        )

    # Not triggered
    return AlertEvaluation(
        rule=rule,
        triggered=False,
        context=context,
        reason="No emergency keywords detected in recent messages",
        metadata={
            "message_count": len(recent_messages),
            "keywords_checked": len(keywords),
        },
    )


# Registry of patient rule evaluators
PATIENT_EVALUATORS = {
    AlertRuleType.NO_RESPONSE: evaluate_no_response,
    AlertRuleType.MISSED_QUIZ: evaluate_missed_quiz,
    AlertRuleType.NEGATIVE_SENTIMENT: evaluate_negative_sentiment,
    AlertRuleType.TREATMENT_ADHERENCE: evaluate_treatment_adherence,
    AlertRuleType.EMERGENCY_KEYWORDS: evaluate_emergency_keywords,
}


def register_patient_evaluators(rule_engine: "RuleEngine") -> None:
    """
    Register all patient rule evaluators with the rule engine.

    Args:
        rule_engine: RuleEngine instance to register evaluators with
    """
    for rule_type, evaluator in PATIENT_EVALUATORS.items():
        rule_engine.register_evaluator(rule_type, evaluator)
        logger.info(f"Registered patient evaluator: {rule_type.value}")

    logger.info(f"Registered {len(PATIENT_EVALUATORS)} patient rule evaluators")
