"""
Data Analysis and Quality Assessment Module

This module contains analyzers for variant statistics, healthcare metrics,
data quality assessment, and business impact calculations.
"""

import logging
import statistics
from typing import Dict, List, Any

import numpy as np

logger = logging.getLogger(__name__)


class VariantAnalyzer:
    """Analyzer for variant-specific statistics."""

    @staticmethod
    def calculate_variant_statistics(data: List[Dict], variant_name: str) -> Dict[str, Any]:
        """Calculate comprehensive statistics for a variant."""
        if not data:
            return {"sample_size": 0}

        # Basic counts
        sample_size = len(data)
        responded_count = len([d for d in data if d["event_type"] == "responded"])
        delivered_count = len([d for d in data if d["event_type"] == "delivered"])
        error_count = len([d for d in data if d["event_type"] == "error"])

        # Response metrics
        response_rate = responded_count / sample_size if sample_size > 0 else 0
        delivery_rate = delivered_count / sample_size if sample_size > 0 else 0
        error_rate = error_count / sample_size if sample_size > 0 else 0

        # Response time analysis
        response_times = [d["response_time"] for d in data if d["response_time"] is not None]

        response_time_stats = {}
        if response_times:
            response_time_stats = {
                "mean": statistics.mean(response_times),
                "median": statistics.median(response_times),
                "std": statistics.stdev(response_times) if len(response_times) > 1 else 0,
                "min": min(response_times),
                "max": max(response_times),
                "percentiles": {
                    "p25": np.percentile(response_times, 25),
                    "p75": np.percentile(response_times, 75),
                    "p90": np.percentile(response_times, 90),
                    "p95": np.percentile(response_times, 95)
                }
            }

        # Engagement analysis
        engagement_scores = [d["engagement_score"] for d in data if d["engagement_score"] is not None]

        engagement_stats = {}
        if engagement_scores:
            engagement_stats = {
                "mean": statistics.mean(engagement_scores),
                "median": statistics.median(engagement_scores),
                "std": statistics.stdev(engagement_scores) if len(engagement_scores) > 1 else 0
            }

        return {
            "sample_size": sample_size,
            "response_rate": response_rate,
            "delivery_rate": delivery_rate,
            "error_rate": error_rate,
            "responded_count": responded_count,
            "delivered_count": delivered_count,
            "error_count": error_count,
            "response_time_stats": response_time_stats,
            "engagement_stats": engagement_stats,
            "variant_name": variant_name
        }


class HealthcareAnalyzer:
    """Analyzer for healthcare-specific metrics."""

    @staticmethod
    def calculate_healthcare_metrics(
        control_data: List[Dict],
        treatment_data: List[Dict],
        experiment: Any
    ) -> Dict[str, Any]:
        """Calculate healthcare-specific metrics."""
        healthcare_metrics = {}

        try:
            # Patient engagement quality
            control_engagement = [d["engagement_score"] for d in control_data if d["engagement_score"] is not None]
            treatment_engagement = [d["engagement_score"] for d in treatment_data if d["engagement_score"] is not None]

            if control_engagement and treatment_engagement:
                healthcare_metrics["engagement_improvement"] = {
                    "control_avg": statistics.mean(control_engagement),
                    "treatment_avg": statistics.mean(treatment_engagement),
                    "improvement": statistics.mean(treatment_engagement) - statistics.mean(control_engagement)
                }

            # Time to response (healthcare urgency metric)
            control_times = [d["response_time"] for d in control_data if d["response_time"] is not None]
            treatment_times = [d["response_time"] for d in treatment_data if d["response_time"] is not None]

            if control_times and treatment_times:
                healthcare_metrics["response_urgency"] = {
                    "control_median": statistics.median(control_times),
                    "treatment_median": statistics.median(treatment_times),
                    "time_improvement": statistics.median(control_times) - statistics.median(treatment_times)
                }

            # Treatment adherence proxy (completion rate)
            control_completed = len([d for d in control_data if d["event_type"] == "completed"])
            treatment_completed = len([d for d in treatment_data if d["event_type"] == "completed"])

            healthcare_metrics["adherence_proxy"] = {
                "control_completion_rate": control_completed / len(control_data) if control_data else 0,
                "treatment_completion_rate": treatment_completed / len(treatment_data) if treatment_data else 0
            }

            # Safety score calculation
            control_errors = len([d for d in control_data if d["event_type"] == "error"])
            treatment_errors = len([d for d in treatment_data if d["event_type"] == "error"])

            healthcare_metrics["safety_profile"] = {
                "control_error_rate": control_errors / len(control_data) if control_data else 0,
                "treatment_error_rate": treatment_errors / len(treatment_data) if treatment_data else 0,
                "safety_improvement": (control_errors / len(control_data) if control_data else 0) -
                                    (treatment_errors / len(treatment_data) if treatment_data else 0)
            }

            # Clinical significance assessment
            healthcare_metrics["clinical_significance"] = HealthcareAnalyzer.assess_clinical_significance(
                healthcare_metrics, experiment.message_template
            )

            return healthcare_metrics

        except Exception as e:
            logger.error(f"Error calculating healthcare metrics: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def assess_clinical_significance(healthcare_metrics: Dict[str, Any], message_template: str) -> str:
        """Assess clinical significance of results."""
        try:
            # Check engagement improvement
            engagement_improvement = healthcare_metrics.get("engagement_improvement", {}).get("improvement", 0)

            # Check safety improvement
            safety_improvement = healthcare_metrics.get("safety_profile", {}).get("safety_improvement", 0)

            # Check response urgency
            time_improvement = healthcare_metrics.get("response_urgency", {}).get("time_improvement", 0)

            if engagement_improvement > 0.1 and safety_improvement >= 0 and time_improvement > 0:
                return "High clinical significance - improved engagement, safety, and responsiveness"
            elif engagement_improvement > 0.05 or (safety_improvement > 0 and time_improvement > 0):
                return "Moderate clinical significance - notable improvements in key metrics"
            elif safety_improvement < 0:
                return "Clinical concern - safety metrics decreased"
            else:
                return "Low clinical significance - minimal measurable impact"

        except Exception as e:
            logger.error(f"Error assessing clinical significance: {str(e)}")
            return "Unable to assess clinical significance"


class DataQualityAnalyzer:
    """Analyzer for data quality assessment."""

    @staticmethod
    def assess_data_quality(control_data: List[Dict], treatment_data: List[Dict]) -> Dict[str, Any]:
        """Assess data quality for the experiment."""
        try:
            total_records = len(control_data) + len(treatment_data)

            # Completeness check
            complete_records = 0
            for data_set in [control_data, treatment_data]:
                for record in data_set:
                    if all([
                        record.get("event_type"),
                        record.get("timestamp"),
                        record.get("event_data") is not None
                    ]):
                        complete_records += 1

            completeness_score = complete_records / total_records if total_records > 0 else 0

            # Consistency check (temporal ordering)
            timestamps_ordered = True
            for data_set in [control_data, treatment_data]:
                timestamps = [d["timestamp"] for d in data_set if d.get("timestamp")]
                if len(timestamps) > 1:
                    if timestamps != sorted(timestamps):
                        timestamps_ordered = False
                        break

            # Validity check (reasonable values)
            valid_values = True
            for data_set in [control_data, treatment_data]:
                for record in data_set:
                    if record.get("response_time") and record["response_time"] < 0:
                        valid_values = False
                    if record.get("engagement_score") and not (0 <= record["engagement_score"] <= 1):
                        valid_values = False

            return {
                "completeness_score": completeness_score,
                "timestamps_ordered": timestamps_ordered,
                "valid_values": valid_values,
                "total_records": total_records,
                "quality_grade": DataQualityAnalyzer.calculate_quality_grade(
                    completeness_score, timestamps_ordered, valid_values
                )
            }

        except Exception as e:
            logger.error(f"Error assessing data quality: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def calculate_quality_grade(completeness: float, timestamps_ordered: bool, valid_values: bool) -> str:
        """Calculate overall data quality grade."""
        score = 0

        # Completeness scoring
        if completeness >= 0.95:
            score += 40
        elif completeness >= 0.90:
            score += 35
        elif completeness >= 0.80:
            score += 25
        else:
            score += 10

        # Timestamp ordering
        if timestamps_ordered:
            score += 30
        else:
            score += 10

        # Value validity
        if valid_values:
            score += 30
        else:
            score += 5

        # Grade assignment
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"


class BusinessImpactAnalyzer:
    """Analyzer for business impact calculations."""

    @staticmethod
    def calculate_business_impact(
        control_stats: Dict[str, Any],
        treatment_stats: Dict[str, Any],
        experiment: Any
    ) -> Dict[str, Any]:
        """Calculate business impact metrics."""
        try:
            # Response rate improvement
            response_improvement = (
                treatment_stats.get("response_rate", 0) -
                control_stats.get("response_rate", 0)
            )

            # Estimate impact on patient population
            if experiment.total_participants > 0:
                estimated_annual_impact = response_improvement * experiment.total_participants * 12

            # Cost-benefit analysis (simplified)
            ai_processing_cost = 0.01  # Estimated cost per message for AI processing
            improved_engagement_value = 0.50  # Estimated value of improved engagement

            if response_improvement > 0:
                roi = (improved_engagement_value - ai_processing_cost) / ai_processing_cost
            else:
                roi = -1

            return {
                "response_rate_improvement": response_improvement,
                "estimated_annual_impact": estimated_annual_impact if 'estimated_annual_impact' in locals() else 0,
                "roi_estimate": roi,
                "break_even_improvement": ai_processing_cost / improved_engagement_value,
                "recommendation": "implement" if roi > 0 else "do_not_implement"
            }

        except Exception as e:
            logger.error(f"Error calculating business impact: {str(e)}")
            return {"error": str(e)}


class RiskAnalyzer:
    """Analyzer for risk assessment."""

    @staticmethod
    def perform_risk_assessment(
        experiment: Any,
        statistical_results: Dict[str, Any],
        healthcare_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive risk assessment."""
        try:
            risk_factors = []
            risk_level = "low"

            # Check statistical significance
            if not statistical_results.get("overall", {}).get("is_significant", False):
                risk_factors.append("Results not statistically significant")
                risk_level = "medium"

            # Check safety profile
            safety_improvement = healthcare_metrics.get("safety_profile", {}).get("safety_improvement", 0)
            if safety_improvement < 0:
                risk_factors.append("Safety metrics decreased")
                risk_level = "high"

            # Check sample size
            min_sample = statistical_results.get("power_analysis", {}).get("current_sample_size", 0)
            if min_sample < 100:
                risk_factors.append("Small sample size - results may not be reliable")
                risk_level = "medium" if risk_level != "high" else risk_level

            # Check data quality
            # (Would need data quality results passed in)

            return {
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "recommendation": RiskAnalyzer.generate_risk_recommendation(risk_level, risk_factors)
            }

        except Exception as e:
            logger.error(f"Error in risk assessment: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def generate_risk_recommendation(risk_level: str, risk_factors: List[str]) -> str:
        """Generate risk-based recommendation."""
        if risk_level == "high":
            return "High risk identified - do not implement without addressing concerns"
        elif risk_level == "medium":
            return "Moderate risk - proceed with caution and additional monitoring"
        else:
            return "Low risk - safe to proceed with implementation"
