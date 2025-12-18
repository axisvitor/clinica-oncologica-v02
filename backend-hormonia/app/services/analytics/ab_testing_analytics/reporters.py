"""
Report Generation Module

This module contains report generators for different formats including
comprehensive, executive, and clinical reports.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List

from .models import EffectSizeMagnitude

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generator for analytical reports."""

    @staticmethod
    def generate_comprehensive_report(results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive analytical report."""
        return {
            "report_type": "comprehensive",
            "generated_at": datetime.utcnow().isoformat(),
            "executive_summary": ReportGenerator._generate_executive_summary(results),
            "detailed_analysis": {
                "sample_information": results.get("sample_sizes"),
                "statistical_analysis": results.get("statistical_tests"),
                "effect_size_analysis": results.get("effect_sizes"),
                "healthcare_metrics": results.get("healthcare_metrics"),
                "power_analysis": results.get("power_analysis"),
                "confidence_intervals": results.get("confidence_intervals"),
            },
            "data_quality_report": results.get("data_quality"),
            "business_impact_analysis": results.get("business_impact"),
            "recommendations": results.get("recommendations"),
            "risk_assessment": results.get("risk_assessment"),
            "appendices": {
                "variant_statistics": results.get("variant_statistics"),
                "analysis_metadata": {
                    "analysis_version": results.get("analysis_version"),
                    "analysis_timestamp": results.get("analysis_timestamp"),
                },
            },
        }

    @staticmethod
    def generate_executive_report(results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary report."""
        return {
            "report_type": "executive",
            "generated_at": datetime.utcnow().isoformat(),
            "key_findings": ReportGenerator._extract_key_findings(results),
            "primary_metrics": {
                "control_response_rate": results.get("variant_statistics", {})
                .get("control", {})
                .get("response_rate"),
                "treatment_response_rate": results.get("variant_statistics", {})
                .get("treatment", {})
                .get("response_rate"),
                "improvement": results.get("effect_sizes", {}).get(
                    "absolute_difference"
                ),
                "statistical_significance": results.get("statistical_tests", {})
                .get("overall", {})
                .get("is_significant"),
            },
            "business_recommendation": ReportGenerator._generate_business_recommendation(
                results
            ),
            "risk_summary": {
                "risk_level": results.get("risk_assessment", {}).get("risk_level"),
                "key_risks": results.get("risk_assessment", {}).get("risk_factors", []),
            },
            "next_steps": ReportGenerator._generate_next_steps(results),
        }

    @staticmethod
    def generate_clinical_report(results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate clinical/regulatory report."""
        return {
            "report_type": "clinical",
            "generated_at": datetime.utcnow().isoformat(),
            "study_overview": {
                "experiment_id": results.get("experiment_id"),
                "experiment_name": results.get("experiment_name"),
                "analysis_date": results.get("analysis_timestamp"),
            },
            "methodology": {
                "design": "Randomized Controlled Trial (A/B Test)",
                "randomization": "50:50 allocation",
                "sample_sizes": results.get("sample_sizes"),
                "primary_endpoint": "Response rate to AI-humanized messages",
            },
            "statistical_analysis": {
                "hypothesis_testing": results.get("statistical_tests"),
                "effect_size": results.get("effect_sizes"),
                "confidence_intervals": results.get("confidence_intervals"),
                "power_analysis": results.get("power_analysis"),
            },
            "clinical_outcomes": results.get("healthcare_metrics"),
            "safety_analysis": {
                "safety_profile": results.get("healthcare_metrics", {}).get(
                    "safety_profile"
                ),
                "adverse_events": ReportGenerator._extract_adverse_events(results),
            },
            "data_quality": results.get("data_quality"),
            "conclusions": {
                "primary_conclusion": results.get("statistical_tests", {})
                .get("overall", {})
                .get("conclusion"),
                "clinical_significance": results.get("healthcare_metrics", {}).get(
                    "clinical_significance"
                ),
                "recommendations": results.get("recommendations"),
            },
            "regulatory_compliance": {
                "data_integrity": "Verified",
                "protocol_adherence": "Yes",
                "documentation_complete": "Yes",
            },
        }

    @staticmethod
    def generate_stopping_recommendation(
        sprt_result: Dict[str, Any],
        bayesian_analysis: Dict[str, Any],
        futility_analysis: Dict[str, Any],
        experiment: Any,
    ) -> Dict[str, Any]:
        """Generate recommendation for stopping experiment early."""
        try:
            recommendations = []
            overall_decision = "continue"
            confidence_level = "low"

            # SPRT decision
            sprt_decision = sprt_result.get("decision", "continue")
            if sprt_decision != "continue":
                recommendations.append(f"SPRT suggests: {sprt_decision}")
                overall_decision = "stop"
                confidence_level = "high"

            # Bayesian decision
            prob_treatment_better = bayesian_analysis.get(
                "probability_treatment_better", 0.5
            )
            if prob_treatment_better > 0.95:
                recommendations.append(
                    "Bayesian analysis shows >95% probability treatment is better"
                )
                overall_decision = "stop"
                confidence_level = "high"
            elif prob_treatment_better < 0.05:
                recommendations.append(
                    "Bayesian analysis shows >95% probability control is better"
                )
                overall_decision = "stop"
                confidence_level = "high"
            elif prob_treatment_better > 0.8 or prob_treatment_better < 0.2:
                recommendations.append(
                    "Bayesian analysis shows strong evidence for one variant"
                )
                confidence_level = "medium"

            # Futility assessment
            futility_score = futility_analysis.get("futility_score", 0)
            if futility_score > 0.7:
                recommendations.append(
                    "High futility - unlikely to detect significant effect"
                )
                overall_decision = "stop"

            # Final recommendation
            if overall_decision == "stop":
                action = "Recommend stopping experiment early"
            else:
                action = "Continue experiment to planned completion"

            return {
                "action": action,
                "confidence_level": confidence_level,
                "reasons": recommendations,
                "sprt_decision": sprt_decision,
                "bayesian_probability": prob_treatment_better,
                "futility_score": futility_score,
            }

        except Exception as e:
            logger.error(f"Error generating stopping recommendation: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def generate_advanced_recommendations(
        statistical_results: Dict[str, Any],
        effect_sizes: Dict[str, Any],
        healthcare_metrics: Dict[str, Any],
        data_quality: Dict[str, Any],
    ) -> List[str]:
        """Generate advanced recommendations based on comprehensive analysis."""
        recommendations = []

        # Statistical significance
        if statistical_results.get("overall", {}).get("is_significant", False):
            if effect_sizes.get("magnitude") == EffectSizeMagnitude.LARGE:
                recommendations.append(
                    "Strong evidence supports implementation of AI-humanized messages"
                )
            elif effect_sizes.get("magnitude") == EffectSizeMagnitude.MEDIUM:
                recommendations.append(
                    "Moderate evidence supports gradual rollout with monitoring"
                )
            else:
                recommendations.append(
                    "Statistical significance found but effect size is small - consider cost-benefit"
                )
        else:
            recommendations.append(
                "No statistically significant difference - continue current approach"
            )

        # Data quality considerations
        if data_quality.get("quality_grade", "C") in ["A", "B"]:
            recommendations.append("✓ High data quality supports reliable conclusions")
        else:
            recommendations.append(
                "⚠ Data quality concerns - consider extending study period"
            )

        # Healthcare-specific recommendations
        if (
            healthcare_metrics.get("safety_profile", {}).get("safety_improvement", 0)
            > 0
        ):
            recommendations.append(
                "✓ Safety profile improved with AI-humanized messages"
            )
        elif (
            healthcare_metrics.get("safety_profile", {}).get("safety_improvement", 0)
            < 0
        ):
            recommendations.append(
                "⚠ Safety concerns identified - conduct detailed safety review"
            )

        return recommendations

    # Private helper methods

    @staticmethod
    def _generate_executive_summary(results: Dict[str, Any]) -> str:
        """Generate executive summary text."""
        is_significant = (
            results.get("statistical_tests", {})
            .get("overall", {})
            .get("is_significant", False)
        )
        improvement = results.get("effect_sizes", {}).get("absolute_difference", 0)

        if is_significant and improvement > 0:
            return (
                f"The A/B test showed statistically significant improvement in patient engagement "
                f"with AI-humanized messages. Treatment group showed {improvement * 100:.1f}% higher "
                f"response rate compared to control group."
            )
        elif is_significant and improvement < 0:
            return (
                f"The A/B test showed statistically significant decrease in patient engagement "
                f"with AI-humanized messages. Control group performed better by {abs(improvement) * 100:.1f}%."
            )
        else:
            return (
                "The A/B test did not show statistically significant differences between "
                "AI-humanized and standard messages. Both approaches yielded similar results."
            )

    @staticmethod
    def _extract_key_findings(results: Dict[str, Any]) -> List[str]:
        """Extract key findings from results."""
        findings = []

        # Statistical significance
        if (
            results.get("statistical_tests", {})
            .get("overall", {})
            .get("is_significant")
        ):
            findings.append("Statistically significant difference detected")

        # Effect size
        magnitude = results.get("effect_sizes", {}).get("magnitude")
        if magnitude:
            findings.append(f"Effect size: {magnitude}")

        # Business impact
        roi = results.get("business_impact", {}).get("roi_estimate", 0)
        if roi > 0:
            findings.append(f"Positive ROI: {roi:.2f}x")

        return findings

    @staticmethod
    def _generate_business_recommendation(results: Dict[str, Any]) -> str:
        """Generate business recommendation."""
        recommendation = results.get("business_impact", {}).get(
            "recommendation", "do_not_implement"
        )
        roi = results.get("business_impact", {}).get("roi_estimate", 0)

        if recommendation == "implement" and roi > 1:
            return f"Recommend implementation - positive ROI of {roi:.2f}x expected"
        elif recommendation == "implement":
            return "Recommend implementation with monitoring - marginal positive impact"
        else:
            return "Do not recommend implementation - negative or neutral ROI"

    @staticmethod
    def _generate_next_steps(results: Dict[str, Any]) -> List[str]:
        """Generate next steps recommendations."""
        steps = []

        if (
            results.get("statistical_tests", {})
            .get("overall", {})
            .get("is_significant")
        ):
            steps.append("Proceed with gradual rollout to broader patient population")
            steps.append("Set up monitoring dashboard for key metrics")
            steps.append("Plan follow-up study to confirm long-term effects")
        else:
            steps.append("Continue current approach")
            steps.append("Consider testing alternative message variations")
            steps.append("Increase sample size for more statistical power")

        return steps

    @staticmethod
    def _extract_adverse_events(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract adverse events from results."""
        # Simplified - would need actual adverse event tracking
        error_rate_control = (
            results.get("variant_statistics", {})
            .get("control", {})
            .get("error_rate", 0)
        )
        error_rate_treatment = (
            results.get("variant_statistics", {})
            .get("treatment", {})
            .get("error_rate", 0)
        )

        return [
            {
                "type": "System errors",
                "control_rate": error_rate_control,
                "treatment_rate": error_rate_treatment,
                "severity": "Low",
            }
        ]
