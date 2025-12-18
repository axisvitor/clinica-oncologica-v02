"""
Statistical Testing and Analysis Module

This module contains all statistical test implementations including t-tests,
chi-square tests, effect size calculations, power analysis, and confidence intervals.
"""

import logging
from typing import Dict, List, Any

import numpy as np
from scipy import stats

from .models import StatisticalSignificance, EffectSizeMagnitude

logger = logging.getLogger(__name__)


class StatisticalAnalyzer:
    """Statistical testing and analysis for A/B experiments."""

    def __init__(self):
        """Initialize statistical analyzer."""
        self.alpha_levels = [0.001, 0.01, 0.05, 0.1]
        self.confidence_levels = [0.90, 0.95, 0.99]
        self.effect_size_thresholds = {
            EffectSizeMagnitude.SMALL: 0.2,
            EffectSizeMagnitude.MEDIUM: 0.5,
            EffectSizeMagnitude.LARGE: 0.8,
            EffectSizeMagnitude.VERY_LARGE: 1.2,
        }

    def perform_comprehensive_statistical_tests(
        self, control_data: List[Dict], treatment_data: List[Dict], primary_metric: str
    ) -> Dict[str, Any]:
        """Perform comprehensive statistical testing."""
        results = {}

        try:
            # Extract primary metric values
            if primary_metric == "response_rate":
                control_responses = len(
                    [d for d in control_data if d["event_type"] == "responded"]
                )
                treatment_responses = len(
                    [d for d in treatment_data if d["event_type"] == "responded"]
                )

                # Chi-square test for proportions
                contingency_table = np.array(
                    [
                        [control_responses, len(control_data) - control_responses],
                        [
                            treatment_responses,
                            len(treatment_data) - treatment_responses,
                        ],
                    ]
                )

                if contingency_table.sum() > 0:
                    chi2, p_value, dof, expected = stats.chi2_contingency(
                        contingency_table
                    )
                    results["chi_square"] = {
                        "statistic": chi2,
                        "p_value": p_value,
                        "degrees_of_freedom": dof,
                    }

                # Fisher's exact test
                if all(contingency_table.flatten() < 1000):  # Use for small samples
                    odds_ratio, fisher_p = stats.fisher_exact(contingency_table)
                    results["fisher_exact"] = {
                        "odds_ratio": odds_ratio,
                        "p_value": fisher_p,
                    }

            # T-test for continuous metrics
            control_times = [
                d["response_time"]
                for d in control_data
                if d["response_time"] is not None
            ]
            treatment_times = [
                d["response_time"]
                for d in treatment_data
                if d["response_time"] is not None
            ]

            if len(control_times) > 1 and len(treatment_times) > 1:
                # Welch's t-test (unequal variances)
                t_stat, t_p_value = stats.ttest_ind(
                    control_times, treatment_times, equal_var=False
                )
                results["t_test"] = {"statistic": t_stat, "p_value": t_p_value}

                # Mann-Whitney U test (non-parametric)
                u_stat, u_p_value = stats.mannwhitneyu(
                    control_times, treatment_times, alternative="two-sided"
                )
                results["mann_whitney"] = {"statistic": u_stat, "p_value": u_p_value}

            # Determine significance level
            min_p_value = min([test.get("p_value", 1.0) for test in results.values()])
            significance_level = self.determine_significance_level(min_p_value)

            results["overall"] = {
                "min_p_value": min_p_value,
                "significance_level": significance_level,
                "is_significant": min_p_value < 0.05,
                "conclusion": self.generate_statistical_conclusion(
                    min_p_value, primary_metric
                ),
            }

            return results

        except Exception as e:
            logger.error(f"Error in statistical testing: {str(e)}")
            return {"error": str(e)}

    def calculate_comprehensive_effect_sizes(
        self, control_stats: Dict[str, Any], treatment_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate comprehensive effect size measures."""
        effect_sizes = {}

        try:
            # Cohen's d for response rate
            control_rate = control_stats.get("response_rate", 0)
            treatment_rate = treatment_stats.get("response_rate", 0)
            control_n = control_stats.get("sample_size", 1)
            treatment_n = treatment_stats.get("sample_size", 1)

            # Pooled standard deviation for proportions
            pooled_p = ((control_rate * control_n) + (treatment_rate * treatment_n)) / (
                control_n + treatment_n
            )
            pooled_std = np.sqrt(pooled_p * (1 - pooled_p))

            if pooled_std > 0:
                cohens_d = (treatment_rate - control_rate) / pooled_std
                effect_sizes["cohens_d"] = cohens_d
                effect_sizes["magnitude"] = self.classify_effect_size(abs(cohens_d))
            else:
                effect_sizes["cohens_d"] = 0
                effect_sizes["magnitude"] = EffectSizeMagnitude.NEGLIGIBLE

            # Absolute and relative differences
            effect_sizes["absolute_difference"] = treatment_rate - control_rate
            effect_sizes["relative_change"] = (
                (treatment_rate - control_rate) / control_rate
                if control_rate > 0
                else 0
            )

            # Glass's delta (for unequal variances)
            control_std = control_stats.get("response_time_stats", {}).get("std", 0)
            if control_std > 0:
                control_mean = control_stats.get("response_time_stats", {}).get(
                    "mean", 0
                )
                treatment_mean = treatment_stats.get("response_time_stats", {}).get(
                    "mean", 0
                )
                glass_delta = (treatment_mean - control_mean) / control_std
                effect_sizes["glass_delta"] = glass_delta

            # Cliff's delta (non-parametric effect size)
            effect_sizes["cliffs_delta"] = self.calculate_cliffs_delta(
                control_stats, treatment_stats
            )

            # Practical significance assessment
            effect_sizes["practical_significance"] = self.assess_practical_significance(
                effect_sizes
            )

            return effect_sizes

        except Exception as e:
            logger.error(f"Error calculating effect sizes: {str(e)}")
            return {"error": str(e)}

    def perform_power_analysis(
        self,
        control_stats: Dict[str, Any],
        treatment_stats: Dict[str, Any],
        statistical_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Perform power analysis for the experiment."""
        try:
            observed_effect_size = statistical_results.get("overall", {}).get(
                "min_p_value", 1.0
            )
            sample_sizes = {
                "control": control_stats.get("sample_size", 0),
                "treatment": treatment_stats.get("sample_size", 0),
            }

            # Calculate achieved power
            achieved_power = self.calculate_achieved_power(
                sample_sizes["control"], sample_sizes["treatment"], observed_effect_size
            )

            # Calculate required sample size for different effect sizes
            required_sample_sizes = {}
            for effect_size in [0.1, 0.2, 0.5]:
                required_n = self.calculate_required_sample_size(effect_size, 0.05, 0.8)
                required_sample_sizes[f"effect_size_{effect_size}"] = required_n

            return {
                "achieved_power": achieved_power,
                "required_sample_sizes": required_sample_sizes,
                "current_sample_size": sum(sample_sizes.values()),
                "power_adequate": achieved_power >= 0.8,
            }

        except Exception as e:
            logger.error(f"Error in power analysis: {str(e)}")
            return {"error": str(e)}

    def calculate_confidence_intervals(
        self,
        control_stats: Dict[str, Any],
        treatment_stats: Dict[str, Any],
        confidence_levels: List[float],
    ) -> Dict[str, Any]:
        """Calculate confidence intervals for different confidence levels."""
        intervals = {}

        try:
            control_rate = control_stats.get("response_rate", 0)
            treatment_rate = treatment_stats.get("response_rate", 0)
            control_n = control_stats.get("sample_size", 1)
            treatment_n = treatment_stats.get("sample_size", 1)

            difference = treatment_rate - control_rate

            for conf_level in confidence_levels:
                z_score = stats.norm.ppf(1 - (1 - conf_level) / 2)

                # Standard error for difference in proportions
                se = np.sqrt(
                    (control_rate * (1 - control_rate) / control_n)
                    + (treatment_rate * (1 - treatment_rate) / treatment_n)
                )

                margin_of_error = z_score * se

                intervals[f"{int(conf_level * 100)}%"] = {
                    "lower_bound": difference - margin_of_error,
                    "upper_bound": difference + margin_of_error,
                    "margin_of_error": margin_of_error,
                    "point_estimate": difference,
                }

            return intervals

        except Exception as e:
            logger.error(f"Error calculating confidence intervals: {str(e)}")
            return {"error": str(e)}

    def perform_sprt(
        self, control_data: List[Dict], treatment_data: List[Dict]
    ) -> Dict[str, Any]:
        """Perform sequential probability ratio test (SPRT)."""
        try:
            # Simplified SPRT implementation
            control_successes = len(
                [d for d in control_data if d["event_type"] == "responded"]
            )
            treatment_successes = len(
                [d for d in treatment_data if d["event_type"] == "responded"]
            )

            control_total = len(control_data)
            treatment_total = len(treatment_data)

            if control_total == 0 or treatment_total == 0:
                return {"error": "Insufficient data for SPRT"}

            control_rate = control_successes / control_total
            treatment_rate = treatment_successes / treatment_total

            # Calculate log-likelihood ratio
            if control_rate > 0 and treatment_rate > 0:
                llr = treatment_successes * np.log(treatment_rate / control_rate) + (
                    treatment_total - treatment_successes
                ) * np.log((1 - treatment_rate) / (1 - control_rate))
            else:
                llr = 0

            # Thresholds for SPRT (Type I and II error rates of 0.05)
            threshold_upper = np.log(19)  # log(1-beta/alpha)
            threshold_lower = np.log(1 / 19)  # log(beta/1-alpha)

            if llr >= threshold_upper:
                decision = "stop_treatment_wins"
            elif llr <= threshold_lower:
                decision = "stop_control_wins"
            else:
                decision = "continue"

            return {
                "log_likelihood_ratio": llr,
                "threshold_upper": threshold_upper,
                "threshold_lower": threshold_lower,
                "decision": decision,
                "control_rate": control_rate,
                "treatment_rate": treatment_rate,
            }

        except Exception as e:
            logger.error(f"Error in SPRT: {str(e)}")
            return {"error": str(e)}

    def perform_bayesian_analysis(
        self, control_data: List[Dict], treatment_data: List[Dict]
    ) -> Dict[str, Any]:
        """Perform Bayesian analysis of experiment results."""
        try:
            control_successes = len(
                [d for d in control_data if d["event_type"] == "responded"]
            )
            treatment_successes = len(
                [d for d in treatment_data if d["event_type"] == "responded"]
            )

            control_total = len(control_data)
            treatment_total = len(treatment_data)

            # Beta distribution parameters (using uniform prior: alpha=1, beta=1)
            control_alpha = 1 + control_successes
            control_beta = 1 + (control_total - control_successes)

            treatment_alpha = 1 + treatment_successes
            treatment_beta = 1 + (treatment_total - treatment_successes)

            # Calculate posterior means
            control_mean = control_alpha / (control_alpha + control_beta)
            treatment_mean = treatment_alpha / (treatment_alpha + treatment_beta)

            # Monte Carlo simulation for probability that treatment is better
            n_samples = 10000
            control_samples = np.random.beta(control_alpha, control_beta, n_samples)
            treatment_samples = np.random.beta(
                treatment_alpha, treatment_beta, n_samples
            )

            prob_treatment_better = np.mean(treatment_samples > control_samples)

            return {
                "control_posterior_mean": control_mean,
                "treatment_posterior_mean": treatment_mean,
                "probability_treatment_better": prob_treatment_better,
                "probability_control_better": 1 - prob_treatment_better,
                "credible_difference": treatment_mean - control_mean,
            }

        except Exception as e:
            logger.error(f"Error in Bayesian analysis: {str(e)}")
            return {"error": str(e)}

    def assess_futility(
        self, control_data: List[Dict], treatment_data: List[Dict]
    ) -> Dict[str, Any]:
        """Assess futility of continuing the experiment."""
        try:
            control_rate = (
                len([d for d in control_data if d["event_type"] == "responded"])
                / len(control_data)
                if control_data
                else 0
            )
            treatment_rate = (
                len([d for d in treatment_data if d["event_type"] == "responded"])
                / len(treatment_data)
                if treatment_data
                else 0
            )

            # Conditional power calculation (simplified)
            current_difference = abs(treatment_rate - control_rate)
            minimal_detectable_effect = 0.05  # 5% improvement

            if current_difference < minimal_detectable_effect / 2:
                futility_score = 0.8  # High futility
                recommendation = "Consider stopping due to futility"
            elif current_difference < minimal_detectable_effect:
                futility_score = 0.5  # Moderate futility
                recommendation = "Monitor closely"
            else:
                futility_score = 0.2  # Low futility
                recommendation = "Continue experiment"

            return {
                "futility_score": futility_score,
                "current_difference": current_difference,
                "minimal_detectable_effect": minimal_detectable_effect,
                "recommendation": recommendation,
            }

        except Exception as e:
            logger.error(f"Error in futility assessment: {str(e)}")
            return {"error": str(e)}

    # Helper methods

    def determine_significance_level(self, p_value: float) -> str:
        """Determine significance level based on p-value."""
        if p_value < 0.001:
            return StatisticalSignificance.HIGHLY_SIGNIFICANT
        elif p_value < 0.01:
            return StatisticalSignificance.VERY_SIGNIFICANT
        elif p_value < 0.05:
            return StatisticalSignificance.SIGNIFICANT
        elif p_value < 0.1:
            return StatisticalSignificance.MARGINALLY_SIGNIFICANT
        else:
            return StatisticalSignificance.NOT_SIGNIFICANT

    def classify_effect_size(self, effect_size: float) -> str:
        """Classify effect size magnitude."""
        if effect_size < 0.2:
            return EffectSizeMagnitude.NEGLIGIBLE
        elif effect_size < 0.5:
            return EffectSizeMagnitude.SMALL
        elif effect_size < 0.8:
            return EffectSizeMagnitude.MEDIUM
        elif effect_size < 1.2:
            return EffectSizeMagnitude.LARGE
        else:
            return EffectSizeMagnitude.VERY_LARGE

    def generate_statistical_conclusion(
        self, p_value: float, primary_metric: str
    ) -> str:
        """Generate human-readable statistical conclusion."""
        significance = self.determine_significance_level(p_value)

        if significance == StatisticalSignificance.NOT_SIGNIFICANT:
            return f"No statistically significant difference found in {primary_metric}"
        elif significance == StatisticalSignificance.MARGINALLY_SIGNIFICANT:
            return (
                f"Marginally significant difference found in {primary_metric} (p < 0.1)"
            )
        elif significance == StatisticalSignificance.SIGNIFICANT:
            return f"Statistically significant difference found in {primary_metric} (p < 0.05)"
        elif significance == StatisticalSignificance.VERY_SIGNIFICANT:
            return f"Highly significant difference found in {primary_metric} (p < 0.01)"
        else:
            return f"Very highly significant difference found in {primary_metric} (p < 0.001)"

    def calculate_cliffs_delta(
        self, control_stats: Dict[str, Any], treatment_stats: Dict[str, Any]
    ) -> float:
        """Calculate Cliff's delta (non-parametric effect size)."""
        # Simplified implementation - would need actual data points for true calculation
        control_rate = control_stats.get("response_rate", 0)
        treatment_rate = treatment_stats.get("response_rate", 0)

        # Approximation based on rates
        return (treatment_rate - control_rate) / max(control_rate, treatment_rate, 0.01)

    def assess_practical_significance(self, effect_sizes: Dict[str, Any]) -> str:
        """Assess practical significance of effect size."""
        cohens_d = abs(effect_sizes.get("cohens_d", 0))
        relative_change = abs(effect_sizes.get("relative_change", 0))

        if cohens_d >= 0.5 and relative_change >= 0.1:
            return "High practical significance"
        elif cohens_d >= 0.2 or relative_change >= 0.05:
            return "Moderate practical significance"
        else:
            return "Low practical significance"

    def calculate_achieved_power(self, n1: int, n2: int, effect_size: float) -> float:
        """Calculate achieved statistical power."""
        # Simplified power calculation
        total_n = n1 + n2
        if total_n < 30:
            return 0.3  # Low power for small samples
        elif total_n < 100:
            return 0.5  # Moderate power
        elif total_n < 500:
            return 0.7  # Good power
        else:
            return 0.9  # Excellent power

    def calculate_required_sample_size(
        self, effect_size: float, alpha: float, power: float
    ) -> int:
        """Calculate required sample size for desired power."""
        # Simplified sample size calculation
        # Based on Cohen's formula for two-sample t-test
        z_alpha = stats.norm.ppf(1 - alpha / 2)
        z_beta = stats.norm.ppf(power)

        n = ((z_alpha + z_beta) ** 2 * 2) / (effect_size**2)
        return int(np.ceil(n))
