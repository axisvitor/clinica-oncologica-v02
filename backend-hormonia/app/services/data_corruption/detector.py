"""
Data Corruption Detector - Main Orchestrator
Coordinates all analyzers and generates final reports.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from uuid import UUID

from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.message import Message
from app.services.flow.types import FlowType

from .types import CorruptionPattern
from .scoring import CorruptionScoring
from .analyzers import PatientAnalyzer, FlowAnalyzer, MessageAnalyzer
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class DataCorruptionDetector:
    """
    Advanced data corruption detection using pattern recognition,
    statistical analysis, and heuristic algorithms.
    """

    def __init__(self, db: Any):
        self.db = db
        self.corruption_patterns: List[CorruptionPattern] = []
        self.field_statistics: Dict[str, Dict[str, Any]] = {}

        # Initialize analyzers
        self.patient_analyzer = PatientAnalyzer()
        self.flow_analyzer = FlowAnalyzer()
        self.message_analyzer = MessageAnalyzer()
        self.scoring = CorruptionScoring()

    async def detect_corruption_patterns(
        self, entity_type: str = "all", sample_size: Optional[int] = 1000
    ) -> Dict[str, Any]:
        """
        Detect data corruption patterns across different entity types.

        Args:
            entity_type: Type of entity to analyze ('patient', 'flow', 'message', 'all')
            sample_size: Number of records to sample for analysis

        Returns:
            Corruption detection results
        """
        try:
            start_time = now_sao_paulo()
            self.corruption_patterns = []

            detection_results = {
                "analysis_id": f"corruption_detection_{int(start_time.timestamp())}",
                "started_at": start_time.isoformat(),
                "entity_type": entity_type,
                "sample_size": sample_size,
                "patterns_detected": 0,
                "corruption_score": 0.0,
                "field_analysis": {},
                "recommendations": [],
                "details": [],
            }

            logger.info(
                f"Starting corruption detection for {entity_type} (sample: {sample_size})"
            )

            if entity_type in ["patient", "all"]:
                patient_results = await self._analyze_patient_corruption(sample_size)
                detection_results["details"].append(patient_results)

            if entity_type in ["flow", "all"]:
                flow_results = await self._analyze_flow_corruption(sample_size)
                detection_results["details"].append(flow_results)

            if entity_type in ["message", "all"]:
                message_results = await self._analyze_message_corruption(sample_size)
                detection_results["details"].append(message_results)

            # Compile overall results
            detection_results["patterns_detected"] = len(self.corruption_patterns)
            detection_results["corruption_score"] = (
                self.scoring.calculate_corruption_score(self.corruption_patterns)
            )
            detection_results["field_analysis"] = self.field_statistics
            detection_results["recommendations"] = (
                self.scoring.generate_recommendations(self.corruption_patterns)
            )

            end_time = now_sao_paulo()
            detection_results["completed_at"] = end_time.isoformat()
            detection_results["duration_seconds"] = (
                end_time - start_time
            ).total_seconds()

            logger.info(
                f"Corruption detection completed: {len(self.corruption_patterns)} patterns detected"
            )

            return detection_results

        except Exception as e:
            logger.error(f"Corruption detection failed: {e}")
            return {
                "error": str(e),
                "analysis_id": f"corruption_detection_failed_{int(now_sao_paulo().timestamp())}",
                "patterns_detected": 0,
                "corruption_score": 0.0,
            }

    async def _analyze_patient_corruption(
        self, sample_size: Optional[int]
    ) -> Dict[str, Any]:
        """Analyze patient data for corruption patterns"""
        try:
            query = self.db.query(Patient)
            if sample_size:
                query = query.limit(sample_size)
            patients = query.all()

            analysis_result = {
                "entity_type": "patient",
                "records_analyzed": len(patients),
                "patterns_found": 0,
                "corruption_indicators": [],
            }

            for patient in patients:
                patterns = await self.patient_analyzer.analyze(patient)
                self.corruption_patterns.extend(patterns)

            analysis_result["patterns_found"] = len(
                [p for p in self.corruption_patterns if "patient" in p.field]
            )

            return analysis_result

        except Exception as e:
            logger.error(f"Patient corruption analysis failed: {e}")
            return {"entity_type": "patient", "error": str(e)}

    async def _analyze_flow_corruption(
        self, sample_size: Optional[int]
    ) -> Dict[str, Any]:
        """Analyze flow data for corruption patterns"""
        try:
            query = self.db.query(PatientFlowState)
            if sample_size:
                query = query.limit(sample_size)
            flows = query.all()

            analysis_result = {
                "entity_type": "flow",
                "records_analyzed": len(flows),
                "patterns_found": 0,
                "corruption_indicators": [],
            }

            for flow in flows:
                patterns = await self.flow_analyzer.analyze(flow)
                self.corruption_patterns.extend(patterns)

            analysis_result["patterns_found"] = len(
                [p for p in self.corruption_patterns if "flow" in p.field]
            )

            return analysis_result

        except Exception as e:
            logger.error(f"Flow corruption analysis failed: {e}")
            return {"entity_type": "flow", "error": str(e)}

    async def _analyze_message_corruption(
        self, sample_size: Optional[int]
    ) -> Dict[str, Any]:
        """Analyze message data for corruption patterns"""
        try:
            query = self.db.query(Message)
            if sample_size:
                query = query.limit(sample_size)
            messages = query.all()

            analysis_result = {
                "entity_type": "message",
                "records_analyzed": len(messages),
                "patterns_found": 0,
                "corruption_indicators": [],
            }

            for message in messages:
                patterns = await self.message_analyzer.analyze(message)
                self.corruption_patterns.extend(patterns)

            analysis_result["patterns_found"] = len(
                [p for p in self.corruption_patterns if "message" in p.field]
            )

            return analysis_result

        except Exception as e:
            logger.error(f"Message corruption analysis failed: {e}")
            return {"entity_type": "message", "error": str(e)}

    async def get_corruption_summary(self) -> Dict[str, Any]:
        """Get summary of detected corruption patterns"""
        return self.scoring.get_summary(self.corruption_patterns)

    async def detect_flow_state_corruption(
        self, patient_id: UUID, flow_state: Optional[PatientFlowState] = None
    ) -> List[Dict[str, Any]]:
        """Detect flow state issues that can be corrected automatically."""
        issues: List[Dict[str, Any]] = []
        try:
            if flow_state is None:
                flow_state = (
                    self.db.query(PatientFlowState)
                    .filter(
                        PatientFlowState.patient_id == patient_id,
                        PatientFlowState.completed_at.is_(None),
                    )
                    .order_by(PatientFlowState.started_at.desc())
                    .first()
                )

            if not flow_state:
                return issues

            step_data = flow_state.step_data or {}
            now = now_sao_paulo()

            # Enrollment date (stored in step_data)
            enrollment_raw = step_data.get("enrollment_date") or flow_state.started_at
            enrollment_dt = self._parse_datetime(enrollment_raw)
            if enrollment_dt and enrollment_dt > now + timedelta(minutes=5):
                issues.append(
                    {
                        "type": "future_enrollment_date",
                        "severity": "high",
                        "enrollment_date": enrollment_dt.isoformat(),
                    }
                )

            # Current day calculation
            current_day = step_data.get("current_flow_day")
            if current_day is None and flow_state.current_step is not None:
                current_day = flow_state.current_step
            try:
                current_day_int = int(current_day) if current_day is not None else 0
            except (TypeError, ValueError):
                current_day_int = 0

            if enrollment_dt:
                days_since_enrollment = (
                    now.date() - enrollment_dt.date()
                ).days + 1
            else:
                days_since_enrollment = max(1, current_day_int or 1)

            if current_day_int < 1 or current_day_int > max(days_since_enrollment + 7, 365):
                issues.append(
                    {
                        "type": "invalid_day_range",
                        "severity": "medium",
                        "current_day": current_day_int,
                        "expected_day": days_since_enrollment,
                    }
                )

            # Flow type mismatch
            expected_flow_type = self._expected_flow_type(days_since_enrollment)
            flow_type_value = (
                flow_state.flow_type.value
                if hasattr(flow_state.flow_type, "value")
                else str(flow_state.flow_type)
            )
            canonical_flow_types = {
                FlowType.ONBOARDING.value,
                FlowType.DAILY_FOLLOW_UP.value,
                FlowType.QUIZ_MENSAL.value,
            }
            if (
                expected_flow_type
                and flow_type_value in canonical_flow_types
                and flow_type_value != expected_flow_type
            ):
                issues.append(
                    {
                        "type": "flow_type_mismatch",
                        "severity": "medium",
                        "current_flow_type": flow_type_value,
                        "expected_flow_type": expected_flow_type,
                    }
                )

            # Required fields in step_data
            for required_field in ("current_flow_day", "flow_kind"):
                if required_field not in step_data:
                    issues.append(
                        {
                            "type": "missing_required_field",
                            "severity": "medium",
                            "missing_field": required_field,
                        }
                    )

            # Temporal anomalies
            last_message_sent = self._parse_datetime(
                step_data.get("last_message_sent")
                or step_data.get("last_message_sent_at")
            )
            if last_message_sent and last_message_sent > now + timedelta(minutes=5):
                issues.append(
                    {
                        "type": "future_last_message",
                        "severity": "low",
                        "last_message_sent": last_message_sent.isoformat(),
                    }
                )

            next_message_due = self._parse_datetime(step_data.get("next_message_due"))
            if next_message_due and next_message_due < now - timedelta(days=2):
                issues.append(
                    {
                        "type": "overdue_next_message",
                        "severity": "low",
                        "next_message_due": next_message_due.isoformat(),
                    }
                )

            return issues
        except Exception as e:
            logger.error(f"Flow state corruption detection failed: {e}")
            return issues

    async def detect_bulk_corruption(self, sample_size: int = 100) -> List[Dict[str, Any]]:
        """Detect corruption across a sample of active flows."""
        report: List[Dict[str, Any]] = []
        try:
            flows = (
                self.db.query(PatientFlowState)
                .filter(PatientFlowState.completed_at.is_(None))
                .order_by(PatientFlowState.started_at.desc())
                .limit(sample_size)
                .all()
            )
            for flow_state in flows:
                issues = await self.detect_flow_state_corruption(
                    flow_state.patient_id, flow_state=flow_state
                )
                if issues:
                    report.append(
                        {
                            "flow_id": str(flow_state.id),
                            "patient_id": str(flow_state.patient_id),
                            "issues": issues,
                        }
                    )
            return report
        except Exception as e:
            logger.error(f"Bulk corruption detection failed: {e}")
            return report

    @staticmethod
    def _expected_flow_type(days_since_enrollment: int) -> Optional[str]:
        """Return expected flow type based on days since enrollment."""
        if days_since_enrollment <= 15:
            return FlowType.ONBOARDING.value
        if days_since_enrollment <= 45:
            return FlowType.DAILY_FOLLOW_UP.value
        return FlowType.QUIZ_MENSAL.value

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse ISO datetime strings or passthrough datetime values."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, dict):
            for key in ("sent_at", "timestamp", "created_at"):
                if key in value:
                    return DataCorruptionDetector._parse_datetime(value[key])
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None


def get_corruption_detector(db: Any) -> DataCorruptionDetector:
    """
    Get data corruption detector instance.

    Args:
        db: Database session

    Returns:
        DataCorruptionDetector instance
    """
    return DataCorruptionDetector(db)
