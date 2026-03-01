"""
Capacity Planning and Forecasting
Predictive resource planning and scaling recommendations.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import statistics
from collections import deque
import numpy as np
from scipy import stats as scipy_stats
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    """Resource trend direction"""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


class ScalingRecommendation(str, Enum):
    """Scaling action recommendations"""

    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"
    INVESTIGATE = "investigate"


@dataclass
class ResourceForecast:
    """Resource usage forecast"""

    resource_type: str
    current_value: float
    forecast_1h: float
    forecast_6h: float
    forecast_24h: float
    forecast_7d: float
    trend: TrendDirection
    confidence_score: float
    forecast_timestamp: datetime


@dataclass
class CapacityAnalysis:
    """Capacity planning analysis"""

    resource_type: str
    current_usage: float
    current_capacity: float
    utilization_percent: float
    projected_exhaustion: Optional[datetime]
    days_until_exhaustion: Optional[int]
    growth_rate_per_day: float
    recommendation: ScalingRecommendation
    details: Dict[str, Any]


@dataclass
class CostProjection:
    """Cost projection for resource usage"""

    current_monthly_cost: float
    projected_1m_cost: float
    projected_3m_cost: float
    projected_6m_cost: float
    cost_trend: TrendDirection
    optimization_potential: float
    recommendations: List[str]


class TimeSeriesForecaster:
    """Time series forecasting using multiple methods"""

    def __init__(self, history_size: int = 1000):
        self.history_size = history_size

    def forecast(
        self, data: List[float], periods: int = 24
    ) -> Tuple[List[float], float]:
        """
        Forecast future values using ensemble of methods
        Returns: (forecasts, confidence_score)
        """
        if len(data) < 10:
            return [data[-1]] * periods if data else [0] * periods, 0.0

        # Use multiple forecasting methods
        linear_forecast = self._linear_regression_forecast(data, periods)
        moving_avg_forecast = self._moving_average_forecast(data, periods)
        exponential_forecast = self._exponential_smoothing_forecast(data, periods)

        # Ensemble forecast (weighted average)
        forecasts = []
        for i in range(periods):
            ensemble_value = (
                linear_forecast[i] * 0.4
                + moving_avg_forecast[i] * 0.3
                + exponential_forecast[i] * 0.3
            )
            forecasts.append(max(0, ensemble_value))  # No negative values

        # Calculate confidence based on historical variance
        confidence = self._calculate_confidence(data)

        return forecasts, confidence

    def _linear_regression_forecast(
        self, data: List[float], periods: int
    ) -> List[float]:
        """Simple linear regression forecast"""
        n = len(data)
        x = np.arange(n)
        y = np.array(data)

        # Calculate slope and intercept
        slope, intercept, _, _, _ = scipy_stats.linregress(x, y)

        # Forecast
        forecasts = []
        for i in range(1, periods + 1):
            forecast_value = slope * (n + i) + intercept
            forecasts.append(forecast_value)

        return forecasts

    def _moving_average_forecast(
        self, data: List[float], periods: int, window: int = 10
    ) -> List[float]:
        """Moving average forecast"""
        window = min(window, len(data))
        ma = sum(data[-window:]) / window

        # Simple forecast: extend moving average
        return [ma] * periods

    def _exponential_smoothing_forecast(
        self, data: List[float], periods: int, alpha: float = 0.3
    ) -> List[float]:
        """Exponential smoothing forecast"""
        # Calculate smoothed values
        smoothed = [data[0]]
        for i in range(1, len(data)):
            smoothed_value = alpha * data[i] + (1 - alpha) * smoothed[-1]
            smoothed.append(smoothed_value)

        # Forecast
        last_smoothed = smoothed[-1]
        return [last_smoothed] * periods

    def _calculate_confidence(self, data: List[float]) -> float:
        """Calculate forecast confidence score"""
        if len(data) < 2:
            return 0.0

        # Use coefficient of variation (lower is better)
        mean = statistics.mean(data)
        if mean == 0:
            return 0.0

        std_dev = statistics.stdev(data)
        cv = std_dev / mean

        # Convert to confidence score (0-1)
        confidence = max(0, min(1, 1 - cv))

        return confidence


class CapacityPlanner:
    """Main capacity planning system"""

    def __init__(self):
        self.forecaster = TimeSeriesForecaster()
        self.resource_history: Dict[str, deque] = {}

        # Resource limits and thresholds
        self.resource_limits = {
            "cpu": 100.0,
            "memory": 100.0,
            "disk": 100.0,
            "connections": 1000,
        }

        self.warning_threshold = 80.0
        self.critical_threshold = 95.0

    def update_resource_data(
        self, resource_type: str, value: float, timestamp: Optional[datetime] = None
    ):
        """Update resource usage data"""
        if resource_type not in self.resource_history:
            self.resource_history[resource_type] = deque(maxlen=1000)

        self.resource_history[resource_type].append(
            {"value": value, "timestamp": timestamp or now_sao_paulo()}
        )

    async def generate_forecast(self, resource_type: str) -> Optional[ResourceForecast]:
        """Generate resource usage forecast"""
        if resource_type not in self.resource_history:
            return None

        history = list(self.resource_history[resource_type])
        if len(history) < 10:
            return None

        # Extract values
        values = [h["value"] for h in history]

        # Generate forecasts for different time horizons
        forecast_1h, confidence = self.forecaster.forecast(values, periods=1)
        forecast_6h, _ = self.forecaster.forecast(values, periods=6)
        forecast_24h, _ = self.forecaster.forecast(values, periods=24)
        forecast_7d, _ = self.forecaster.forecast(
            values, periods=168
        )  # 7 days * 24 hours

        # Determine trend
        trend = self._determine_trend(values)

        return ResourceForecast(
            resource_type=resource_type,
            current_value=values[-1],
            forecast_1h=forecast_1h[0] if forecast_1h else values[-1],
            forecast_6h=forecast_6h[5] if len(forecast_6h) > 5 else values[-1],
            forecast_24h=forecast_24h[23] if len(forecast_24h) > 23 else values[-1],
            forecast_7d=forecast_7d[167] if len(forecast_7d) > 167 else values[-1],
            trend=trend,
            confidence_score=confidence,
            forecast_timestamp=now_sao_paulo(),
        )

    def _determine_trend(self, data: List[float]) -> TrendDirection:
        """Determine resource trend direction"""
        if len(data) < 3:
            return TrendDirection.STABLE

        # Calculate moving average slopes
        recent = data[-10:]
        x = np.arange(len(recent))
        y = np.array(recent)

        slope, _, _, _, _ = scipy_stats.linregress(x, y)

        # Calculate volatility
        volatility = (
            statistics.stdev(recent) / statistics.mean(recent)
            if statistics.mean(recent) > 0
            else 0
        )

        if volatility > 0.5:
            return TrendDirection.VOLATILE
        elif slope > 0.1:
            return TrendDirection.INCREASING
        elif slope < -0.1:
            return TrendDirection.DECREASING
        else:
            return TrendDirection.STABLE

    async def analyze_capacity(self, resource_type: str) -> Optional[CapacityAnalysis]:
        """Analyze resource capacity and provide recommendations"""
        forecast = await self.generate_forecast(resource_type)
        if not forecast:
            return None

        capacity = self.resource_limits.get(resource_type, 100.0)
        utilization = (forecast.current_value / capacity) * 100

        # Calculate growth rate
        history = list(self.resource_history[resource_type])
        if len(history) >= 24:  # Need at least 24 hours of data
            growth_rate = self._calculate_growth_rate(
                [h["value"] for h in history[-24:]]
            )
        else:
            growth_rate = 0.0

        # Project when resource will be exhausted
        projected_exhaustion = None
        days_until_exhaustion = None

        if growth_rate > 0:
            remaining_capacity = capacity - forecast.current_value
            days_to_exhaustion = remaining_capacity / growth_rate
            if days_to_exhaustion > 0:
                projected_exhaustion = now_sao_paulo() + timedelta(
                    days=days_to_exhaustion
                )
                days_until_exhaustion = int(days_to_exhaustion)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            utilization, forecast.trend, days_until_exhaustion
        )

        return CapacityAnalysis(
            resource_type=resource_type,
            current_usage=forecast.current_value,
            current_capacity=capacity,
            utilization_percent=utilization,
            projected_exhaustion=projected_exhaustion,
            days_until_exhaustion=days_until_exhaustion,
            growth_rate_per_day=growth_rate,
            recommendation=recommendation,
            details={
                "forecast": asdict(forecast),
                "warning_threshold": self.warning_threshold,
                "critical_threshold": self.critical_threshold,
            },
        )

    def _calculate_growth_rate(self, data: List[float]) -> float:
        """Calculate daily growth rate"""
        if len(data) < 2:
            return 0.0

        # Linear regression to get growth rate
        x = np.arange(len(data))
        y = np.array(data)

        slope, _, _, _, _ = scipy_stats.linregress(x, y)

        # Convert hourly slope to daily
        daily_growth = slope * 24

        return daily_growth

    def _generate_recommendation(
        self,
        utilization: float,
        trend: TrendDirection,
        days_until_exhaustion: Optional[int],
    ) -> ScalingRecommendation:
        """Generate scaling recommendation"""
        # Critical threshold exceeded
        if utilization >= self.critical_threshold:
            return ScalingRecommendation.SCALE_UP

        # Warning threshold exceeded with increasing trend
        if utilization >= self.warning_threshold:
            if trend == TrendDirection.INCREASING:
                return ScalingRecommendation.SCALE_UP
            elif trend == TrendDirection.VOLATILE:
                return ScalingRecommendation.INVESTIGATE
            else:
                return ScalingRecommendation.MAINTAIN

        # Low utilization with decreasing trend
        if utilization < 30 and trend == TrendDirection.DECREASING:
            return ScalingRecommendation.SCALE_DOWN

        # Exhaustion imminent
        if days_until_exhaustion and days_until_exhaustion < 7:
            return ScalingRecommendation.SCALE_UP

        return ScalingRecommendation.MAINTAIN

    async def generate_cost_projection(
        self, resource_type: str, cost_per_unit: float
    ) -> Optional[CostProjection]:
        """Generate cost projections"""
        forecast = await self.generate_forecast(resource_type)
        if not forecast:
            return None

        # Calculate costs
        current_monthly = forecast.current_value * cost_per_unit * 24 * 30
        projected_1m = forecast.forecast_24h * cost_per_unit * 24 * 30
        projected_3m = forecast.forecast_7d * cost_per_unit * 24 * 90
        projected_6m = forecast.forecast_7d * cost_per_unit * 24 * 180

        # Calculate optimization potential
        history = list(self.resource_history[resource_type])
        values = [h["value"] for h in history]

        avg_usage = statistics.mean(values)
        max_usage = max(values)
        optimization_potential = (
            ((max_usage - avg_usage) / max_usage * 100) if max_usage > 0 else 0
        )

        # Generate recommendations
        recommendations = []
        if optimization_potential > 20:
            recommendations.append(
                f"High variance detected. Consider right-sizing resources "
                f"(potential savings: {optimization_potential:.1f}%)"
            )

        if forecast.trend == TrendDirection.INCREASING:
            recommendations.append(
                "Upward trend detected. Plan for capacity increase to avoid service degradation"
            )

        if forecast.trend == TrendDirection.DECREASING:
            recommendations.append(
                "Downward trend detected. Consider scaling down to optimize costs"
            )

        return CostProjection(
            current_monthly_cost=current_monthly,
            projected_1m_cost=projected_1m,
            projected_3m_cost=projected_3m,
            projected_6m_cost=projected_6m,
            cost_trend=forecast.trend,
            optimization_potential=optimization_potential,
            recommendations=recommendations,
        )

    async def generate_capacity_report(self) -> Dict[str, Any]:
        """Generate comprehensive capacity planning report"""
        report = {
            "generated_at": now_sao_paulo().isoformat(),
            "resources": {},
            "summary": {
                "total_resources": len(self.resource_history),
                "critical_resources": 0,
                "warning_resources": 0,
                "scaling_recommendations": [],
            },
        }

        for resource_type in self.resource_history.keys():
            analysis = await self.analyze_capacity(resource_type)
            if analysis:
                report["resources"][resource_type] = asdict(analysis)

                # Update summary
                if analysis.utilization_percent >= self.critical_threshold:
                    report["summary"]["critical_resources"] += 1
                elif analysis.utilization_percent >= self.warning_threshold:
                    report["summary"]["warning_resources"] += 1

                if analysis.recommendation != ScalingRecommendation.MAINTAIN:
                    report["summary"]["scaling_recommendations"].append(
                        {
                            "resource": resource_type,
                            "action": analysis.recommendation,
                            "urgency": "high"
                            if analysis.utilization_percent >= self.critical_threshold
                            else "medium",
                        }
                    )

        return report


# Global planner instance
capacity_planner = CapacityPlanner()
