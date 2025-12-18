"""
Data Models and Constants for A/B Testing Analytics

This module contains all constant definitions, enums, and data model classes
used throughout the A/B testing analytics system.
"""


class HealthcareMetrics:
    """Healthcare-specific metrics for A/B testing evaluation."""

    RESPONSE_RATE = "response_rate"
    ENGAGEMENT_QUALITY = "engagement_quality"
    TREATMENT_ADHERENCE = "treatment_adherence"
    PATIENT_SATISFACTION = "patient_satisfaction"
    CLINICAL_OUTCOME_IMPROVEMENT = "clinical_outcome_improvement"
    MEDICATION_COMPLIANCE = "medication_compliance"
    APPOINTMENT_ADHERENCE = "appointment_adherence"
    SYMPTOM_REPORTING_ACCURACY = "symptom_reporting_accuracy"
    TIME_TO_RESPONSE = "time_to_response"
    COMPLETION_RATE = "completion_rate"
    ERROR_RATE = "error_rate"
    SAFETY_SCORE = "safety_score"


class StatisticalSignificance:
    """Statistical significance levels and interpretations."""

    HIGHLY_SIGNIFICANT = "highly_significant"  # p < 0.001
    VERY_SIGNIFICANT = "very_significant"  # p < 0.01
    SIGNIFICANT = "significant"  # p < 0.05
    MARGINALLY_SIGNIFICANT = "marginally_significant"  # p < 0.1
    NOT_SIGNIFICANT = "not_significant"  # p >= 0.1


class EffectSizeMagnitude:
    """Effect size magnitude classifications."""

    NEGLIGIBLE = "negligible"  # d < 0.2
    SMALL = "small"  # 0.2 <= d < 0.5
    MEDIUM = "medium"  # 0.5 <= d < 0.8
    LARGE = "large"  # 0.8 <= d < 1.2
    VERY_LARGE = "very_large"  # d >= 1.2
