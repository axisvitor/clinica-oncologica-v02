"""Decision Engine - Makes intelligent flow decisions based on analysis."""

from __future__ import annotations

# Standard library
import logging
from typing import Any, Callable, Dict, List

# Local
from .models import FlowContext, FlowDecision


class DecisionEngine:
    """
    Makes intelligent flow decisions based on context and analysis.

    Analyzes patient flow situations and makes decisions on
    progression, timing, content personalization, and interventions.

    Attributes:
        agent_id: Unique agent identifier.
        logger: Logger instance.
        consensus_threshold: Threshold for consensus decisions.
        intervention_threshold: Threshold for intervention triggers.
        adaptation_threshold: Threshold for content adaptation.
        transition_day_45: Day for phase transition.
    """

    def __init__(
        self,
        agent_id: str,
        logger: logging.Logger,
        consensus_threshold: float = 0.7,
        intervention_threshold: float = 0.8,
        adaptation_threshold: float = 0.6,
        transition_day_45: int = 45,
    ):
        self.agent_id = agent_id
        self.logger = logger
        self.consensus_threshold = consensus_threshold
        self.intervention_threshold = intervention_threshold
        self.adaptation_threshold = adaptation_threshold
        self.transition_day_45 = transition_day_45

    async def analyze_flow_situation(self, context: FlowContext) -> Dict[str, Any]:
        """Analyze current flow situation and patient state."""
        analysis = {
            "phase": "unknown",
            "progress_score": 0.0,
            "engagement_score": 0.0,
            "risk_level": "low",
            "patterns": [],
            "recommendations": [],
        }

        # Determine current phase
        if context.current_day <= 45:
            analysis["phase"] = "intensive_daily"
        else:
            analysis["phase"] = "monthly_maintenance"

        # Calculate progress score based on various factors
        progress_factors = []

        # Adherence score
        adherence = context.adherence_metrics.get("message_response_rate", 0.0)
        progress_factors.append(adherence * 0.3)

        # Mood improvement score
        mood_trend = context.mood_indicators.get("trend", 0.0)
        progress_factors.append(max(0, mood_trend) * 0.25)

        # Engagement score
        engagement = (
            len(context.recent_interactions) / 7.0
        )  # Expected daily interaction
        engagement = min(1.0, engagement)
        progress_factors.append(engagement * 0.2)
        analysis["engagement_score"] = engagement

        # Quiz completion rate
        quiz_rate = context.adherence_metrics.get("quiz_completion_rate", 1.0)
        progress_factors.append(quiz_rate * 0.25)

        analysis["progress_score"] = sum(progress_factors)

        # Assess risk level
        risk_score = len(context.risk_factors) / 5.0  # Max 5 risk factors

        if risk_score >= 0.6:
            analysis["risk_level"] = "high"
        elif risk_score >= 0.3:
            analysis["risk_level"] = "medium"
        else:
            analysis["risk_level"] = "low"

        # Extract patterns from knowledge graph
        if context.knowledge_context:
            analysis["patterns"] = context.knowledge_context.get("patterns", [])

        # Generate recommendations
        analysis["recommendations"] = await self._generate_recommendations(
            context, analysis
        )

        return analysis

    async def make_flow_decision(
        self,
        context: FlowContext,
        analysis: Dict[str, Any],
        requires_consensus_fn: Callable,
        seek_consensus_fn: Callable,
    ) -> FlowDecision:
        """Make intelligent flow decision based on context and analysis."""
        progress_score = analysis["progress_score"]
        risk_level = analysis["risk_level"]
        engagement_score = analysis["engagement_score"]

        # Decision logic based on multiple factors

        # High risk situations require intervention
        if risk_level == "high":
            if await requires_consensus_fn("escalate_intervention", context):
                consensus_result = await seek_consensus_fn(
                    "intervention_decision",
                    {
                        "patient_id": str(context.patient_id),
                        "risk_factors": context.risk_factors,
                        "analysis": analysis,
                    },
                )

                if consensus_result["consensus_reached"]:
                    return FlowDecision.ESCALATE_INTERVENTION

            return FlowDecision.ESCALATE_INTERVENTION

        # Low engagement requires content personalization
        if engagement_score < 0.4:
            return FlowDecision.PERSONALIZE_CONTENT

        # Phase transition logic
        if context.current_day == self.transition_day_45:
            if await requires_consensus_fn("advance_phase", context):
                consensus_result = await seek_consensus_fn(
                    "phase_transition",
                    {
                        "patient_id": str(context.patient_id),
                        "from_phase": "daily",
                        "to_phase": "monthly",
                        "progress_score": progress_score,
                    },
                )

                if consensus_result["consensus_reached"]:
                    return FlowDecision.ADVANCE_PHASE
            else:
                return FlowDecision.ADVANCE_PHASE

        # Timing optimization for better engagement
        if progress_score > 0.7 and engagement_score < 0.6:
            return FlowDecision.ADJUST_TIMING

        # Content personalization for moderate progress
        if 0.4 <= progress_score < 0.7:
            return FlowDecision.PERSONALIZE_CONTENT

        # Continue current flow if everything is going well
        return FlowDecision.CONTINUE_CURRENT

    async def _generate_recommendations(
        self, context: FlowContext, analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        if analysis["engagement_score"] < 0.5:
            recommendations.append("increase_personalization")
            recommendations.append("optimize_timing")

        if analysis["risk_level"] == "high":
            recommendations.append("escalate_to_medical_team")
            recommendations.append("increase_monitoring_frequency")

        if analysis["progress_score"] > 0.8:
            recommendations.append("consider_reducing_frequency")
            recommendations.append("focus_on_maintenance")

        return recommendations

    def requires_consensus_decision(
        self, decision_type: str, context: FlowContext
    ) -> bool:
        """Check if decision requires consensus from other agents."""
        critical_decisions = ["escalate_intervention", "advance_phase", "pause_flow"]

        return decision_type in critical_decisions
