"""
Progress Tracker - Monitors patient engagement, mood, and stress levels.

Handles progress tracking, mood analysis, stress assessment, and intervention triggers.
"""

from __future__ import annotations

# Standard library imports
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from app.domain.agents.quiz.types import QuizContext


class ProgressTracker:
    """
    Tracks patient progress, engagement, and emotional state during quiz sessions.

    Monitors quiz progress and analyzes patient state to enable
    adaptive quiz behavior and intervention triggers.

    Attributes:
        stress_threshold: Threshold for high stress detection.
        engagement_threshold: Minimum acceptable engagement score.
        adaptation_distress_threshold: Distress threshold for quiz adaptation.
        intervention_distress_threshold: Threshold for triggering interventions.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize progress tracker.

        Args:
            logger: Logger instance. Creates new logger if not provided.
        """
        self._logger = logger or logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Thresholds
        self.stress_threshold = 0.7
        self.engagement_threshold = 0.4
        self.adaptation_distress_threshold = 0.7
        self.intervention_distress_threshold = 0.9

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Convert arbitrary values to float without raising."""
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    async def analyze_current_mood(self, context: QuizContext) -> Dict[str, Any]:
        """
        Analyze current mood indicators from context.

        Args:
            context: Quiz context with knowledge graph patterns.

        Returns:
            Dictionary with mood trend, distress level, and confidence.
        """
        mood_data = {"trend": 0.0, "distress": 0.0, "confidence": 0.5}

        # Use knowledge graph patterns
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                pattern_type = pattern.get("pattern_type", "")
                if "mood" in pattern_type:
                    if "improvement" in pattern_type:
                        mood_data["trend"] = 0.7
                    elif "decline" in pattern_type:
                        mood_data["trend"] = -0.7
                        mood_data["distress"] = 0.6

                    mood_data["confidence"] = pattern.get("confidence", 0.5)
                    break

        return mood_data

    async def assess_stress_level(self, context: "QuizContext") -> float:
        """Assess patient stress level from context."""
        stress_indicators = 0.0

        # Check for stress patterns in knowledge graph
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if any(
                    keyword in pattern.get("description", "")
                    for keyword in [
                        "anxiety",
                        "stress",
                        "worried",
                        "ansiedade",
                        "preocup",
                    ]
                ):
                    stress_indicators += 0.3

        # Check recent interaction frequency (low frequency might indicate stress)
        # This would analyze actual interaction data

        return min(1.0, stress_indicators)

    async def calculate_engagement_score(self, context: "QuizContext") -> float:
        """Calculate patient engagement score."""
        engagement = 1.0

        # Reduce score based on knowledge patterns
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if "low_engagement" in pattern.get("pattern_type", ""):
                    engagement -= 0.3

        return max(0.0, engagement)

    async def assess_completion_quality(self, context: "QuizContext") -> Dict[str, Any]:
        """Assess the quality of quiz completion."""
        return {
            "completeness": 1.0
            if len(context.responses_so_far) >= 5
            else len(context.responses_so_far) / 5,
            "response_clarity": sum(
                r.get("confidence", 1.0) for r in context.responses_so_far
            )
            / len(context.responses_so_far)
            if context.responses_so_far
            else 0,
            "engagement_maintained": context.engagement_score,
            "adaptations_needed": len(context.adaptation_history),
        }

    async def extract_medical_insights(self, context: "QuizContext") -> List[Dict]:
        """Extract medical insights from quiz responses."""
        insights = []

        # Analyze mood trends
        mood_responses = [
            r
            for r in context.responses_so_far
            if "humor" in r.get("question_text", "").lower()
        ]
        if mood_responses:
            avg_mood = sum(
                self._safe_float(r.get("processed_value"), default=3.0)
                for r in mood_responses
            ) / len(mood_responses)

            insights.append(
                {
                    "type": "mood_assessment",
                    "value": avg_mood,
                    "interpretation": "concerning"
                    if avg_mood < 2.5
                    else "stable"
                    if avg_mood < 3.5
                    else "positive",
                    "confidence": 0.8,
                }
            )

        return insights

    async def generate_follow_up_recommendations(
        self, context: "QuizContext"
    ) -> List[str]:
        """Generate follow-up recommendations."""
        recommendations = []

        if context.stress_level > self.stress_threshold:
            recommendations.append("consider_stress_management_resources")

        if context.engagement_score < self.engagement_threshold:
            recommendations.append("increase_personalized_communication")

        if len(context.adaptation_history) > 2:
            recommendations.append("review_communication_approach")

        return recommendations

    async def should_complete_early(self, context: "QuizContext") -> bool:
        """Check if quiz should be completed early."""
        # Complete early if high stress detected
        if context.stress_level > 0.9:
            return True

        # Complete early if enough critical information gathered
        critical_responses = sum(
            1
            for r in context.responses_so_far
            if any(
                keyword in r.get("question_text", "").lower()
                for keyword in ["humor", "energia", "sintoma"]
            )
        )

        if critical_responses >= 3 and len(context.responses_so_far) >= 5:
            return True

        return False

    async def should_trigger_intervention(self, context: "QuizContext") -> bool:
        """Check if medical intervention should be triggered."""
        # Check for crisis indicators
        if (
            context.mood_indicators.get("distress", 0)
            > self.intervention_distress_threshold
        ):
            return True

        # Check for concerning response patterns
        concerning_responses = sum(
            1
            for r in context.responses_so_far
            if r.get("processed_value") == "1" and "humor" in r.get("question_text", "")
        )

        if concerning_responses >= 2:
            return True

        return False

    def calculate_adaptation_need_score(self, context: "QuizContext") -> float:
        """Calculate overall score indicating need for adaptation."""
        score = 0.0

        if context.stress_level > self.stress_threshold:
            score += 0.4

        if context.engagement_score < self.engagement_threshold:
            score += 0.3

        if (
            context.mood_indicators.get("distress", 0)
            > self.adaptation_distress_threshold
        ):
            score += 0.3

        return min(1.0, score)

    def should_adapt_quiz(self, context: "QuizContext") -> bool:
        """Determine if quiz adaptation is needed."""
        if context.stress_level > self.stress_threshold:
            return True

        if context.engagement_score < self.engagement_threshold:
            return True

        if (
            context.mood_indicators.get("distress", 0)
            > self.adaptation_distress_threshold
        ):
            return True

        if len(context.responses_so_far) >= 3:
            unclear_responses = sum(
                1
                for response in context.responses_so_far[-3:]
                if response.get("confidence", 1.0) < 0.6
            )
            if unclear_responses >= 2:
                return True

        return False

    def determine_adaptation(self, context: "QuizContext"):
        """Determine adaptation type based on current context."""
        from .notification_manager import QuizAdaptationType

        if context.stress_level > self.stress_threshold:
            return QuizAdaptationType.REDUCE_COMPLEXITY

        if context.engagement_score < self.engagement_threshold:
            return QuizAdaptationType.INCREASE_SUPPORT

        if (
            context.mood_indicators.get("distress", 0)
            > self.adaptation_distress_threshold
        ):
            return QuizAdaptationType.FOCUS_ON_MOOD

        if len(context.responses_so_far) >= 2:
            recent_unclear = [
                response
                for response in context.responses_so_far[-2:]
                if response.get("confidence", 1.0) < 0.6
            ]
            if recent_unclear:
                return QuizAdaptationType.ADD_CLARIFICATION

        return QuizAdaptationType.INCREASE_SUPPORT
