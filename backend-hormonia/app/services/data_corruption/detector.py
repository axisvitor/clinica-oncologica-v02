"""
Data Corruption Detector - Main Orchestrator
Coordinates all analyzers and generates final reports.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.message import Message

from .types import CorruptionPattern
from .scoring import CorruptionScoring
from .analyzers import PatientAnalyzer, FlowAnalyzer, MessageAnalyzer

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

    async def detect_corruption_patterns(self,
                                       entity_type: str = 'all',
                                       sample_size: Optional[int] = 1000) -> Dict[str, Any]:
        """
        Detect data corruption patterns across different entity types.

        Args:
            entity_type: Type of entity to analyze ('patient', 'flow', 'message', 'all')
            sample_size: Number of records to sample for analysis

        Returns:
            Corruption detection results
        """
        try:
            start_time = datetime.utcnow()
            self.corruption_patterns = []

            detection_results = {
                'analysis_id': f"corruption_detection_{int(start_time.timestamp())}",
                'started_at': start_time.isoformat(),
                'entity_type': entity_type,
                'sample_size': sample_size,
                'patterns_detected': 0,
                'corruption_score': 0.0,
                'field_analysis': {},
                'recommendations': [],
                'details': []
            }

            logger.info(f"Starting corruption detection for {entity_type} (sample: {sample_size})")

            if entity_type in ['patient', 'all']:
                patient_results = await self._analyze_patient_corruption(sample_size)
                detection_results['details'].append(patient_results)

            if entity_type in ['flow', 'all']:
                flow_results = await self._analyze_flow_corruption(sample_size)
                detection_results['details'].append(flow_results)

            if entity_type in ['message', 'all']:
                message_results = await self._analyze_message_corruption(sample_size)
                detection_results['details'].append(message_results)

            # Compile overall results
            detection_results['patterns_detected'] = len(self.corruption_patterns)
            detection_results['corruption_score'] = self.scoring.calculate_corruption_score(
                self.corruption_patterns
            )
            detection_results['field_analysis'] = self.field_statistics
            detection_results['recommendations'] = self.scoring.generate_recommendations(
                self.corruption_patterns
            )

            end_time = datetime.utcnow()
            detection_results['completed_at'] = end_time.isoformat()
            detection_results['duration_seconds'] = (end_time - start_time).total_seconds()

            logger.info(f"Corruption detection completed: {len(self.corruption_patterns)} patterns detected")

            return detection_results

        except Exception as e:
            logger.error(f"Corruption detection failed: {e}")
            return {
                'error': str(e),
                'analysis_id': f"corruption_detection_failed_{int(datetime.utcnow().timestamp())}",
                'patterns_detected': 0,
                'corruption_score': 0.0
            }

    async def _analyze_patient_corruption(self, sample_size: Optional[int]) -> Dict[str, Any]:
        """Analyze patient data for corruption patterns"""
        try:
            query = self.db.query(Patient)
            if sample_size:
                query = query.limit(sample_size)
            patients = query.all()

            analysis_result = {
                'entity_type': 'patient',
                'records_analyzed': len(patients),
                'patterns_found': 0,
                'corruption_indicators': []
            }

            for patient in patients:
                patterns = await self.patient_analyzer.analyze(patient)
                self.corruption_patterns.extend(patterns)

            analysis_result['patterns_found'] = len([p for p in self.corruption_patterns
                                                   if 'patient' in p.field])

            return analysis_result

        except Exception as e:
            logger.error(f"Patient corruption analysis failed: {e}")
            return {'entity_type': 'patient', 'error': str(e)}

    async def _analyze_flow_corruption(self, sample_size: Optional[int]) -> Dict[str, Any]:
        """Analyze flow data for corruption patterns"""
        try:
            query = self.db.query(PatientFlowState)
            if sample_size:
                query = query.limit(sample_size)
            flows = query.all()

            analysis_result = {
                'entity_type': 'flow',
                'records_analyzed': len(flows),
                'patterns_found': 0,
                'corruption_indicators': []
            }

            for flow in flows:
                patterns = await self.flow_analyzer.analyze(flow)
                self.corruption_patterns.extend(patterns)

            analysis_result['patterns_found'] = len([p for p in self.corruption_patterns
                                                   if 'flow' in p.field])

            return analysis_result

        except Exception as e:
            logger.error(f"Flow corruption analysis failed: {e}")
            return {'entity_type': 'flow', 'error': str(e)}

    async def _analyze_message_corruption(self, sample_size: Optional[int]) -> Dict[str, Any]:
        """Analyze message data for corruption patterns"""
        try:
            query = self.db.query(Message)
            if sample_size:
                query = query.limit(sample_size)
            messages = query.all()

            analysis_result = {
                'entity_type': 'message',
                'records_analyzed': len(messages),
                'patterns_found': 0,
                'corruption_indicators': []
            }

            for message in messages:
                patterns = await self.message_analyzer.analyze(message)
                self.corruption_patterns.extend(patterns)

            analysis_result['patterns_found'] = len([p for p in self.corruption_patterns
                                                   if 'message' in p.field])

            return analysis_result

        except Exception as e:
            logger.error(f"Message corruption analysis failed: {e}")
            return {'entity_type': 'message', 'error': str(e)}

    async def get_corruption_summary(self) -> Dict[str, Any]:
        """Get summary of detected corruption patterns"""
        return self.scoring.get_summary(self.corruption_patterns)


def get_corruption_detector(db: Any) -> DataCorruptionDetector:
    """
    Get data corruption detector instance.

    Args:
        db: Database session

    Returns:
        DataCorruptionDetector instance
    """
    return DataCorruptionDetector(db)
