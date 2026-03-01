"""
Flow Analyzer
Analyzes flow-specific corruption patterns.
"""

import logging
from .base import BaseAnalyzer
from .field_analyzer import FieldAnalyzer
from .temporal_analyzer import TemporalAnalyzer
from ..types import CorruptionType

logger = logging.getLogger(__name__)


class FlowAnalyzer(BaseAnalyzer):
    """Analyzes flow data for corruption"""

    def __init__(self):
        super().__init__()
        self.field_analyzer = FieldAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer()

    async def analyze(self, flow) -> list:
        """Analyze flow for corruption patterns"""
        try:
            # Analyze flow type consistency
            await self._analyze_flow_type(flow)

            # Analyze state data corruption
            if flow.state_data:
                await self.field_analyzer.analyze_metadata(
                    flow.state_data, "flow.state_data", flow.id
                )

            # Analyze temporal consistency
            await self.temporal_analyzer.analyze_flow_temporal(flow)

            # Analyze step progression corruption
            await self._analyze_step_progression(flow)

            # Collect all patterns
            all_patterns = (
                self.corruption_patterns
                + self.field_analyzer.corruption_patterns
                + self.temporal_analyzer.corruption_patterns
            )

            return all_patterns

        except Exception as e:
            logger.error(f"Flow analysis failed for flow {flow.id}: {e}")
            return []

    async def _analyze_flow_type(self, flow) -> None:
        """Analyze flow type for corruption patterns"""
        try:
            valid_flow_types = [
                "onboarding",
                "daily_follow_up",
                "quiz_mensal",
                "paused",
                "completed",
            ]

            if flow.flow_type not in valid_flow_types:
                self._add_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field="flow.flow_type",
                    pattern="invalid_flow_type",
                    severity="medium",
                    description="Invalid flow type value",
                    detection_method="enum_validation",
                    examples=[f"Flow {flow.id}: {flow.flow_type}"],
                    confidence=0.9,
                )

        except Exception as e:
            logger.error(f"Flow type analysis failed for flow {flow.id}: {e}")

    async def _analyze_step_progression(self, flow) -> None:
        """Analyze flow step progression for corruption"""
        try:
            # Check for negative steps
            if flow.current_step < 0:
                self._add_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="flow.current_step",
                    pattern="negative_step",
                    severity="high",
                    description="Negative flow step value",
                    detection_method="value_validation",
                    examples=[f"Flow {flow.id}: Step {flow.current_step}"],
                    confidence=1.0,
                )

            # Check for unrealistic step values
            max_steps_by_type = {
                "onboarding": 15,
                "daily_follow_up": 45,
                "quiz_mensal": 365,
            }

            max_step = max_steps_by_type.get(flow.flow_type, 365)
            if flow.current_step > max_step * 2:
                self._add_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="flow.current_step",
                    pattern="excessive_step_value",
                    severity="medium",
                    description="Flow step value exceeds reasonable limits",
                    detection_method="value_validation",
                    examples=[
                        f"Flow {flow.id}: Step {flow.current_step} for type {flow.flow_type}"
                    ],
                    confidence=0.8,
                )

        except Exception as e:
            logger.error(f"Step progression analysis failed for flow {flow.id}: {e}")
