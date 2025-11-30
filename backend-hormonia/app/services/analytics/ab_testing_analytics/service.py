"""
Main A/B Testing Analytics Service

This module contains the main service class that orchestrates all analytics
operations including comprehensive results calculation, reporting, and real-time metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import and_

from app.models.ab_experiment import (
    ABExperiment, ABExperimentResult, ABExperimentMetric, ABVariantAssignment,
    ExperimentStatus, VariantType
)
from app.services.encryption import UnifiedEncryptionService as EncryptionService

from .statistics import StatisticalAnalyzer
from .analyzers import (
    VariantAnalyzer,
    HealthcareAnalyzer,
    DataQualityAnalyzer,
    BusinessImpactAnalyzer,
    RiskAnalyzer
)
from .reporters import ReportGenerator
from .helpers import (
    MetricsHelper,
    TrendAnalyzer,
    AlertChecker,
    DataExtractor,
    ResultsStore
)

logger = logging.getLogger(__name__)


class ABTestingAnalyticsService:
    """
    Advanced analytics service for A/B testing in healthcare environments.

    Provides comprehensive statistical analysis, effect size calculations,
    healthcare-specific metrics, and detailed reporting capabilities.
    """

    def __init__(self, db: Any, encryption_service: Optional[EncryptionService] = None):
        """Initialize analytics service."""
        self.db = db
        self.encryption_service = encryption_service or EncryptionService()

        # Initialize component services
        self.statistical_analyzer = StatisticalAnalyzer()
        self.variant_analyzer = VariantAnalyzer()
        self.healthcare_analyzer = HealthcareAnalyzer()
        self.data_quality_analyzer = DataQualityAnalyzer()
        self.business_impact_analyzer = BusinessImpactAnalyzer()
        self.risk_analyzer = RiskAnalyzer()
        self.report_generator = ReportGenerator()
        self.trend_analyzer = TrendAnalyzer(db)
        self.data_extractor = DataExtractor(db)
        self.results_store = ResultsStore(db)

        # Statistical configuration
        self.alpha_levels = [0.001, 0.01, 0.05, 0.1]
        self.confidence_levels = [0.90, 0.95, 0.99]

    def calculate_comprehensive_results(self, experiment_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive A/B test results with advanced analytics.

        Args:
            experiment_id: Experiment UUID

        Returns:
            Comprehensive results with statistical analysis
        """
        try:
            # Get experiment and validate
            experiment = self.db.query(ABExperiment).filter(
                ABExperiment.id == experiment_id
            ).first()

            if not experiment:
                raise ValueError(f"Experiment {experiment_id} not found")

            # Get raw data
            control_data, treatment_data = self.data_extractor.get_experiment_data(experiment_id)

            if not control_data or not treatment_data:
                return {"error": "Insufficient data for analysis"}

            # Calculate basic statistics
            control_stats = self.variant_analyzer.calculate_variant_statistics(control_data, "control")
            treatment_stats = self.variant_analyzer.calculate_variant_statistics(treatment_data, "treatment")

            # Perform statistical tests
            statistical_results = self.statistical_analyzer.perform_comprehensive_statistical_tests(
                control_data, treatment_data, experiment.primary_metric
            )

            # Calculate effect sizes
            effect_sizes = self.statistical_analyzer.calculate_comprehensive_effect_sizes(
                control_stats, treatment_stats
            )

            # Calculate healthcare-specific metrics
            healthcare_metrics = self.healthcare_analyzer.calculate_healthcare_metrics(
                control_data, treatment_data, experiment
            )

            # Perform power analysis
            power_analysis = self.statistical_analyzer.perform_power_analysis(
                control_stats, treatment_stats, statistical_results
            )

            # Generate confidence intervals
            confidence_intervals = self.statistical_analyzer.calculate_confidence_intervals(
                control_stats, treatment_stats, self.confidence_levels
            )

            # Assess data quality
            data_quality = self.data_quality_analyzer.assess_data_quality(control_data, treatment_data)

            # Generate business impact analysis
            business_impact = self.business_impact_analyzer.calculate_business_impact(
                control_stats, treatment_stats, experiment
            )

            # Create comprehensive results
            results = {
                "experiment_id": experiment_id,
                "experiment_name": experiment.name,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "analysis_version": "2.0",

                # Sample information
                "sample_sizes": {
                    "control": len(control_data),
                    "treatment": len(treatment_data),
                    "total": len(control_data) + len(treatment_data)
                },

                # Basic statistics
                "variant_statistics": {
                    "control": control_stats,
                    "treatment": treatment_stats
                },

                # Statistical tests
                "statistical_tests": statistical_results,

                # Effect sizes
                "effect_sizes": effect_sizes,

                # Healthcare metrics
                "healthcare_metrics": healthcare_metrics,

                # Power analysis
                "power_analysis": power_analysis,

                # Confidence intervals
                "confidence_intervals": confidence_intervals,

                # Data quality
                "data_quality": data_quality,

                # Business impact
                "business_impact": business_impact,

                # Recommendations
                "recommendations": self.report_generator.generate_advanced_recommendations(
                    statistical_results, effect_sizes, healthcare_metrics, data_quality
                ),

                # Risk assessment
                "risk_assessment": self.risk_analyzer.perform_risk_assessment(
                    experiment, statistical_results, healthcare_metrics
                )
            }

            # Store results in database
            self.results_store.store_experiment_results(experiment_id, results)

            return results

        except Exception as e:
            logger.error(f"Error calculating comprehensive results: {str(e)}")
            return {"error": str(e)}

    def generate_detailed_report(self, experiment_id: str, report_format: str = "comprehensive") -> Dict[str, Any]:
        """
        Generate detailed analytical report.

        Args:
            experiment_id: Experiment UUID
            report_format: Format type (comprehensive, executive, clinical)

        Returns:
            Detailed analytical report
        """
        try:
            # Get comprehensive results
            results = self.calculate_comprehensive_results(experiment_id)

            if results.get("error"):
                return results

            # Generate report based on format
            if report_format == "executive":
                return self.report_generator.generate_executive_report(results)
            elif report_format == "clinical":
                return self.report_generator.generate_clinical_report(results)
            else:
                return self.report_generator.generate_comprehensive_report(results)

        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return {"error": str(e)}

    def calculate_real_time_metrics(self, experiment_id: str) -> Dict[str, Any]:
        """
        Calculate real-time metrics for ongoing experiments.

        Args:
            experiment_id: Experiment UUID

        Returns:
            Real-time metrics dashboard data
        """
        try:
            # Get recent data (last 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            recent_metrics = self.db.query(ABExperimentMetric).filter(
                and_(
                    ABExperimentMetric.experiment_id == experiment_id,
                    ABExperimentMetric.event_timestamp >= cutoff_time
                )
            ).all()

            if not recent_metrics:
                return {"message": "No recent data available"}

            # Separate by variant
            control_metrics = [m for m in recent_metrics if m.variant == VariantType.CONTROL]
            treatment_metrics = [m for m in recent_metrics if m.variant == VariantType.TREATMENT]

            # Calculate real-time KPIs
            real_time_kpis = {
                "timestamp": datetime.utcnow().isoformat(),
                "period": "last_24_hours",

                "message_volume": {
                    "control": len(control_metrics),
                    "treatment": len(treatment_metrics),
                    "total": len(recent_metrics)
                },

                "response_rates": {
                    "control": MetricsHelper.calculate_response_rate(control_metrics),
                    "treatment": MetricsHelper.calculate_response_rate(treatment_metrics)
                },

                "average_response_time": {
                    "control": MetricsHelper.calculate_avg_response_time(control_metrics),
                    "treatment": MetricsHelper.calculate_avg_response_time(treatment_metrics)
                },

                "error_rates": {
                    "control": MetricsHelper.calculate_error_rate(control_metrics),
                    "treatment": MetricsHelper.calculate_error_rate(treatment_metrics)
                },

                "engagement_scores": {
                    "control": MetricsHelper.calculate_avg_engagement(control_metrics),
                    "treatment": MetricsHelper.calculate_avg_engagement(treatment_metrics)
                }
            }

            # Calculate trend indicators
            trend_analysis = self.trend_analyzer.calculate_trend_indicators(experiment_id)
            real_time_kpis["trends"] = trend_analysis

            # Performance alerts
            alerts = AlertChecker.check_performance_alerts(real_time_kpis)
            real_time_kpis["alerts"] = alerts

            return real_time_kpis

        except Exception as e:
            logger.error(f"Error calculating real-time metrics: {str(e)}")
            return {"error": str(e)}

    def perform_sequential_analysis(self, experiment_id: str) -> Dict[str, Any]:
        """
        Perform sequential analysis to determine if experiment can be stopped early.

        Args:
            experiment_id: Experiment UUID

        Returns:
            Sequential analysis results with stopping recommendations
        """
        try:
            experiment = self.db.query(ABExperiment).filter(
                ABExperiment.id == experiment_id
            ).first()

            if not experiment or experiment.status != ExperimentStatus.ACTIVE:
                return {"error": "Experiment not found or not active"}

            # Get current data
            control_data, treatment_data = self.data_extractor.get_experiment_data(experiment_id)

            # Perform sequential probability ratio test (SPRT)
            sprt_result = self.statistical_analyzer.perform_sprt(control_data, treatment_data)

            # Calculate Bayesian analysis
            bayesian_analysis = self.statistical_analyzer.perform_bayesian_analysis(control_data, treatment_data)

            # Assess futility
            futility_analysis = self.statistical_analyzer.assess_futility(control_data, treatment_data)

            # Generate stopping recommendation
            stopping_recommendation = self.report_generator.generate_stopping_recommendation(
                sprt_result, bayesian_analysis, futility_analysis, experiment
            )

            return {
                "experiment_id": experiment_id,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "sprt_analysis": sprt_result,
                "bayesian_analysis": bayesian_analysis,
                "futility_analysis": futility_analysis,
                "stopping_recommendation": stopping_recommendation,
                "current_sample_sizes": {
                    "control": len(control_data),
                    "treatment": len(treatment_data)
                }
            }

        except Exception as e:
            logger.error(f"Error performing sequential analysis: {str(e)}")
            return {"error": str(e)}

    def generate_statistical_summary(self, experiment_id: str) -> Dict[str, Any]:
        """
        Generate statistical summary for regulatory reporting.

        Args:
            experiment_id: Experiment UUID

        Returns:
            Statistical summary for compliance reporting
        """
        try:
            results = self.calculate_comprehensive_results(experiment_id)

            if results.get("error"):
                return results

            # Extract key statistical measures
            statistical_summary = {
                "experiment_id": experiment_id,
                "analysis_date": datetime.utcnow().isoformat(),

                # Hypothesis testing
                "primary_hypothesis": {
                    "null_hypothesis": "No difference between control and treatment",
                    "alternative_hypothesis": "Treatment differs from control",
                    "alpha_level": 0.05,
                    "test_statistic": results["statistical_tests"].get("test_statistic"),
                    "p_value": results["statistical_tests"].get("p_value"),
                    "conclusion": results["statistical_tests"].get("conclusion")
                },

                # Effect size
                "effect_size": {
                    "cohens_d": results["effect_sizes"].get("cohens_d"),
                    "magnitude": results["effect_sizes"].get("magnitude"),
                    "practical_significance": results["effect_sizes"].get("practical_significance")
                },

                # Confidence intervals
                "confidence_intervals": results["confidence_intervals"],

                # Sample characteristics
                "sample_characteristics": {
                    "total_participants": results["sample_sizes"]["total"],
                    "randomization_ratio": 1.0,  # Assuming 50:50 split
                    "attrition_rate": results["data_quality"].get("attrition_rate", 0)
                },

                # Data quality indicators
                "data_quality": {
                    "completeness": results["data_quality"].get("completeness_score"),
                    "consistency": results["data_quality"].get("consistency_score"),
                    "validity": results["data_quality"].get("validity_score")
                },

                # Clinical significance
                "clinical_significance": results["healthcare_metrics"].get("clinical_significance"),

                # Risk assessment
                "risk_assessment": results["risk_assessment"]
            }

            return statistical_summary

        except Exception as e:
            logger.error(f"Error generating statistical summary: {str(e)}")
            return {"error": str(e)}


def get_ab_testing_analytics_service(db: Any) -> ABTestingAnalyticsService:
    """Get A/B testing analytics service instance."""
    return ABTestingAnalyticsService(db)
