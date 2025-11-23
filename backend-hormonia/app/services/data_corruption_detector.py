"""
Data Corruption Detection Service
Advanced algorithms for detecting data corruption patterns and anomalies.
"""
import logging
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
import re

# from sqlalchemy.orm import
from sqlalchemy import text, func

from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.message import Message
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CorruptionType(Enum):
    """Types of data corruption that can be detected"""
    ENCODING_CORRUPTION = "encoding_corruption"
    FORMAT_CORRUPTION = "format_corruption"
    RELATIONSHIP_CORRUPTION = "relationship_corruption"
    TEMPORAL_CORRUPTION = "temporal_corruption"
    CONTENT_CORRUPTION = "content_corruption"
    METADATA_CORRUPTION = "metadata_corruption"
    REFERENTIAL_CORRUPTION = "referential_corruption"


@dataclass
class CorruptionPattern:
    """Represents a detected corruption pattern"""
    type: CorruptionType
    field: str
    pattern: str
    severity: str  # low, medium, high, critical
    description: str
    detection_method: str
    examples: List[str]
    confidence: float  # 0.0 to 1.0


class DataCorruptionDetector:
    """
    Advanced data corruption detection using pattern recognition,
    statistical analysis, and heuristic algorithms.
    """

    def __init__(self, db: Any):
        self.db = db
        self.corruption_patterns: List[CorruptionPattern] = []
        self.field_statistics: Dict[str, Dict[str, Any]] = {}

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
            detection_results['corruption_score'] = self._calculate_corruption_score()
            detection_results['field_analysis'] = self.field_statistics
            detection_results['recommendations'] = self._generate_corruption_recommendations()

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
                # Analyze name field
                await self._analyze_text_field(patient.name, 'patient.name', patient.id)

                # Analyze email field
                if patient.email:
                    await self._analyze_email_field(patient.email, 'patient.email', patient.id)

                # Analyze phone field
                await self._analyze_phone_field(patient.phone, 'patient.phone', patient.id)

                # Analyze metadata corruption
                if patient.patient_data:
                    await self._analyze_metadata_corruption(patient.patient_data, 'patient.metadata', patient.id)

                # Analyze temporal consistency
                await self._analyze_temporal_consistency_patient(patient)

                # Analyze encoding issues
                await self._analyze_encoding_corruption_patient(patient)

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
                # Analyze flow type consistency
                await self._analyze_flow_type_corruption(flow)

                # Analyze state data corruption
                if flow.state_data:
                    await self._analyze_metadata_corruption(flow.state_data, 'flow.state_data', flow.id)

                # Analyze temporal consistency
                await self._analyze_temporal_consistency_flow(flow)

                # Analyze step progression corruption
                await self._analyze_step_progression_corruption(flow)

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
                # Analyze content corruption
                await self._analyze_message_content_corruption(message)

                # Analyze metadata corruption
                if hasattr(message, 'message_metadata') and message.message_metadata:
                    await self._analyze_metadata_corruption(
                        message.message_metadata, 'message.metadata', message.id
                    )

                # Analyze temporal consistency
                await self._analyze_temporal_consistency_message(message)

                # Analyze encoding issues
                await self._analyze_encoding_corruption_message(message)

            analysis_result['patterns_found'] = len([p for p in self.corruption_patterns
                                                   if 'message' in p.field])

            return analysis_result

        except Exception as e:
            logger.error(f"Message corruption analysis failed: {e}")
            return {'entity_type': 'message', 'error': str(e)}

    async def _analyze_text_field(self, text: str, field_name: str, entity_id: any) -> None:
        """Analyze text field for corruption patterns"""
        try:
            if not text:
                return

            # Check for encoding corruption
            try:
                text.encode('utf-8').decode('utf-8')
            except UnicodeError:
                self._add_corruption_pattern(
                    type=CorruptionType.ENCODING_CORRUPTION,
                    field=field_name,
                    pattern="unicode_error",
                    severity="high",
                    description=f"Unicode encoding error in {field_name}",
                    detection_method="encoding_validation",
                    examples=[f"Entity {entity_id}: {text[:50]}..."],
                    confidence=0.9
                )

            # Check for control characters
            control_chars = [c for c in text if ord(c) < 32 and c not in ['\n', '\r', '\t']]
            if control_chars:
                self._add_corruption_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field=field_name,
                    pattern="control_characters",
                    severity="medium",
                    description=f"Control characters found in {field_name}",
                    detection_method="character_analysis",
                    examples=[f"Entity {entity_id}: Contains {len(control_chars)} control chars"],
                    confidence=0.8
                )

            # Check for unusual character patterns
            if re.search(r'[^\w\s\-.,!?@]', text):
                unusual_chars = re.findall(r'[^\w\s\-.,!?@]', text)
                if len(unusual_chars) > 3:  # Threshold for unusual characters
                    self._add_corruption_pattern(
                        type=CorruptionType.CONTENT_CORRUPTION,
                        field=field_name,
                        pattern="unusual_characters",
                        severity="low",
                        description=f"Unusual character patterns in {field_name}",
                        detection_method="pattern_analysis",
                        examples=[f"Entity {entity_id}: {unusual_chars[:5]}"],
                        confidence=0.6
                    )

            # Check for repeated character patterns (likely corruption)
            if re.search(r'(.)\1{10,}', text):  # Same character repeated 10+ times
                self._add_corruption_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field=field_name,
                    pattern="repeated_characters",
                    severity="high",
                    description=f"Repeated character patterns in {field_name}",
                    detection_method="repetition_analysis",
                    examples=[f"Entity {entity_id}: {text[:100]}..."],
                    confidence=0.9
                )

        except Exception as e:
            logger.error(f"Text field analysis failed for {field_name}: {e}")

    async def _analyze_email_field(self, email: str, field_name: str, entity_id: any) -> None:
        """Analyze email field for corruption patterns"""
        try:
            # Basic email format validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                self._add_corruption_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field=field_name,
                    pattern="invalid_email_format",
                    severity="medium",
                    description=f"Invalid email format in {field_name}",
                    detection_method="regex_validation",
                    examples=[f"Entity {entity_id}: {email}"],
                    confidence=0.8
                )

            # Check for suspicious patterns
            if email.count('@') != 1:
                self._add_corruption_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field=field_name,
                    pattern="multiple_at_symbols",
                    severity="high",
                    description=f"Multiple @ symbols in email",
                    detection_method="character_count",
                    examples=[f"Entity {entity_id}: {email}"],
                    confidence=0.9
                )

        except Exception as e:
            logger.error(f"Email field analysis failed: {e}")

    async def _analyze_phone_field(self, phone: str, field_name: str, entity_id: any) -> None:
        """Analyze phone field for corruption patterns"""
        try:
            # Remove common formatting characters
            clean_phone = re.sub(r'[\s\-\(\)\+]', '', phone)

            # Check for non-digit characters (excluding + for international)
            if not re.match(r'^[\+]?[\d]+$', clean_phone):
                self._add_corruption_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field=field_name,
                    pattern="invalid_phone_characters",
                    severity="medium",
                    description=f"Invalid characters in phone number",
                    detection_method="character_validation",
                    examples=[f"Entity {entity_id}: {phone}"],
                    confidence=0.7
                )

            # Check phone length (Brazilian phones should be 10-11 digits + country code)
            if len(clean_phone) < 10 or len(clean_phone) > 15:
                self._add_corruption_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field=field_name,
                    pattern="invalid_phone_length",
                    severity="medium",
                    description=f"Invalid phone number length",
                    detection_method="length_validation",
                    examples=[f"Entity {entity_id}: {phone} (length: {len(clean_phone)})"],
                    confidence=0.8
                )

        except Exception as e:
            logger.error(f"Phone field analysis failed: {e}")

    async def _analyze_metadata_corruption(self, metadata: Dict, field_name: str, entity_id: any) -> None:
        """Analyze metadata/JSON field for corruption patterns"""
        try:
            # Try to serialize/deserialize to check JSON validity
            try:
                json_str = json.dumps(metadata)
                json.loads(json_str)
            except (TypeError, ValueError) as e:
                self._add_corruption_pattern(
                    type=CorruptionType.METADATA_CORRUPTION,
                    field=field_name,
                    pattern="json_serialization_error",
                    severity="high",
                    description=f"JSON serialization error in {field_name}",
                    detection_method="json_validation",
                    examples=[f"Entity {entity_id}: {str(e)}"],
                    confidence=0.9
                )

            # Check for suspicious nested structures
            def count_nesting_depth(obj, depth=0):
                if isinstance(obj, dict):
                    if not obj:
                        return depth
                    return max(count_nesting_depth(v, depth + 1) for v in obj.values())
                elif isinstance(obj, list):
                    if not obj:
                        return depth
                    return max(count_nesting_depth(item, depth + 1) for item in obj)
                return depth

            nesting_depth = count_nesting_depth(metadata)
            if nesting_depth > 10:  # Suspiciously deep nesting
                self._add_corruption_pattern(
                    type=CorruptionType.METADATA_CORRUPTION,
                    field=field_name,
                    pattern="excessive_nesting",
                    severity="medium",
                    description=f"Excessive nesting depth in metadata",
                    detection_method="structure_analysis",
                    examples=[f"Entity {entity_id}: Depth {nesting_depth}"],
                    confidence=0.7
                )

            # Check for circular references (simplified check)
            try:
                json.dumps(metadata)
            except ValueError as e:
                if "circular" in str(e).lower():
                    self._add_corruption_pattern(
                        type=CorruptionType.METADATA_CORRUPTION,
                        field=field_name,
                        pattern="circular_reference",
                        severity="high",
                        description=f"Circular reference in metadata",
                        detection_method="circular_detection",
                        examples=[f"Entity {entity_id}: {str(e)}"],
                        confidence=0.95
                    )

        except Exception as e:
            logger.error(f"Metadata analysis failed for {field_name}: {e}")

    async def _analyze_temporal_consistency_patient(self, patient: Patient) -> None:
        """Analyze temporal consistency for patient data"""
        try:
            current_time = datetime.utcnow().date()

            # Check birth date consistency
            if patient.birth_date:
                if patient.birth_date > current_time:
                    self._add_corruption_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="patient.birth_date",
                        pattern="future_birth_date",
                        severity="high",
                        description="Birth date is in the future",
                        detection_method="temporal_validation",
                        examples=[f"Patient {patient.id}: {patient.birth_date}"],
                        confidence=0.95
                    )

                # Check if birth date is too far in the past (> 120 years)
                if (current_time - patient.birth_date).days > 120 * 365:
                    self._add_corruption_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="patient.birth_date",
                        pattern="ancient_birth_date",
                        severity="medium",
                        description="Birth date is unrealistically old",
                        detection_method="temporal_validation",
                        examples=[f"Patient {patient.id}: {patient.birth_date}"],
                        confidence=0.8
                    )

            # Check treatment start date consistency
            if patient.treatment_start_date:
                if patient.treatment_start_date > current_time:
                    self._add_corruption_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="patient.treatment_start_date",
                        pattern="future_treatment_date",
                        severity="medium",
                        description="Treatment start date is in the future",
                        detection_method="temporal_validation",
                        examples=[f"Patient {patient.id}: {patient.treatment_start_date}"],
                        confidence=0.9
                    )

                # Check if treatment started before birth
                if patient.birth_date and patient.treatment_start_date < patient.birth_date:
                    self._add_corruption_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="patient.treatment_start_date",
                        pattern="treatment_before_birth",
                        severity="critical",
                        description="Treatment started before birth date",
                        detection_method="temporal_validation",
                        examples=[f"Patient {patient.id}: Treatment {patient.treatment_start_date}, Birth {patient.birth_date}"],
                        confidence=1.0
                    )

        except Exception as e:
            logger.error(f"Temporal consistency analysis failed for patient {patient.id}: {e}")

    async def _analyze_temporal_consistency_flow(self, flow: PatientFlowState) -> None:
        """Analyze temporal consistency for flow data"""
        try:
            current_time = datetime.utcnow()

            # Check if flow started in the future
            if flow.started_at and flow.started_at > current_time:
                self._add_corruption_pattern(
                    type=CorruptionType.TEMPORAL_CORRUPTION,
                    field="flow.started_at",
                    pattern="future_flow_start",
                    severity="high",
                    description="Flow started in the future",
                    detection_method="temporal_validation",
                    examples=[f"Flow {flow.id}: {flow.started_at}"],
                    confidence=0.95
                )

            # Check step progression vs time
            if flow.started_at and flow.current_step > 0:
                days_since_start = (current_time - flow.started_at).days
                if flow.current_step > days_since_start + 10:  # Allow some tolerance
                    self._add_corruption_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="flow.current_step",
                        pattern="impossible_step_progression",
                        severity="medium",
                        description="Flow step progression faster than possible",
                        detection_method="progression_analysis",
                        examples=[f"Flow {flow.id}: Step {flow.current_step} in {days_since_start} days"],
                        confidence=0.8
                    )

        except Exception as e:
            logger.error(f"Flow temporal analysis failed for flow {flow.id}: {e}")

    async def _analyze_temporal_consistency_message(self, message: Message) -> None:
        """Analyze temporal consistency for message data"""
        try:
            current_time = datetime.utcnow()

            # Check if message created in the future
            if message.created_at > current_time:
                self._add_corruption_pattern(
                    type=CorruptionType.TEMPORAL_CORRUPTION,
                    field="message.created_at",
                    pattern="future_message_creation",
                    severity="high",
                    description="Message created in the future",
                    detection_method="temporal_validation",
                    examples=[f"Message {message.id}: {message.created_at}"],
                    confidence=0.95
                )

            # Check if scheduled_for is in the past but status is still pending
            if (message.scheduled_for and
                message.scheduled_for < current_time and
                hasattr(message, 'status') and
                str(message.status) == 'PENDING'):

                time_diff = (current_time - message.scheduled_for).total_seconds()
                if time_diff > 3600:  # More than 1 hour overdue
                    self._add_corruption_pattern(
                        type=CorruptionType.TEMPORAL_CORRUPTION,
                        field="message.scheduled_for",
                        pattern="overdue_pending_message",
                        severity="medium",
                        description="Message scheduled in past but still pending",
                        detection_method="temporal_validation",
                        examples=[f"Message {message.id}: Scheduled {message.scheduled_for}, still pending"],
                        confidence=0.7
                    )

        except Exception as e:
            logger.error(f"Message temporal analysis failed for message {message.id}: {e}")

    async def _analyze_encoding_corruption_patient(self, patient: Patient) -> None:
        """Analyze patient data for encoding corruption"""
        try:
            fields_to_check = [
                ('name', patient.name),
                ('email', patient.email)
            ]

            for field_name, field_value in fields_to_check:
                if field_value:
                    await self._check_encoding_corruption(field_value, f"patient.{field_name}", patient.id)

        except Exception as e:
            logger.error(f"Patient encoding analysis failed for patient {patient.id}: {e}")

    async def _analyze_encoding_corruption_message(self, message: Message) -> None:
        """Analyze message data for encoding corruption"""
        try:
            if message.content:
                await self._check_encoding_corruption(message.content, "message.content", message.id)

        except Exception as e:
            logger.error(f"Message encoding analysis failed for message {message.id}: {e}")

    async def _check_encoding_corruption(self, text: str, field_name: str, entity_id: any) -> None:
        """Check specific text for encoding corruption patterns"""
        try:
            # Check for common encoding corruption patterns
            corruption_patterns = [
                (r'Ã¡', 'latin1_to_utf8', 'á character corruption'),
                (r'Ã©', 'latin1_to_utf8', 'é character corruption'),
                (r'Ã§', 'latin1_to_utf8', 'ç character corruption'),
                (r'â€™', 'windows1252_corruption', 'apostrophe corruption'),
                (r'â€œ', 'windows1252_corruption', 'quote corruption'),
                (r'\\x[0-9a-fA-F]{2}', 'hex_escape_corruption', 'hex escape sequences'),
                (r'\\u[0-9a-fA-F]{4}', 'unicode_escape_corruption', 'unicode escape sequences'),
            ]

            for pattern, corruption_type, description in corruption_patterns:
                if re.search(pattern, text):
                    self._add_corruption_pattern(
                        type=CorruptionType.ENCODING_CORRUPTION,
                        field=field_name,
                        pattern=corruption_type,
                        severity="medium",
                        description=f"Encoding corruption: {description}",
                        detection_method="pattern_matching",
                        examples=[f"Entity {entity_id}: {text[:100]}..."],
                        confidence=0.8
                    )

        except Exception as e:
            logger.error(f"Encoding corruption check failed: {e}")

    async def _analyze_flow_type_corruption(self, flow: PatientFlowState) -> None:
        """Analyze flow type for corruption patterns"""
        try:
            valid_flow_types = ['initial_15_days', 'days_16_45', 'monthly_recurring', 'paused', 'completed']

            if flow.flow_type not in valid_flow_types:
                self._add_corruption_pattern(
                    type=CorruptionType.FORMAT_CORRUPTION,
                    field="flow.flow_type",
                    pattern="invalid_flow_type",
                    severity="medium",
                    description="Invalid flow type value",
                    detection_method="enum_validation",
                    examples=[f"Flow {flow.id}: {flow.flow_type}"],
                    confidence=0.9
                )

        except Exception as e:
            logger.error(f"Flow type analysis failed for flow {flow.id}: {e}")

    async def _analyze_step_progression_corruption(self, flow: PatientFlowState) -> None:
        """Analyze flow step progression for corruption"""
        try:
            # Check for negative steps
            if flow.current_step < 0:
                self._add_corruption_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="flow.current_step",
                    pattern="negative_step",
                    severity="high",
                    description="Negative flow step value",
                    detection_method="value_validation",
                    examples=[f"Flow {flow.id}: Step {flow.current_step}"],
                    confidence=1.0
                )

            # Check for unrealistic step values
            max_steps_by_type = {
                'initial_15_days': 15,
                'days_16_45': 45,
                'monthly_recurring': 365
            }

            max_step = max_steps_by_type.get(flow.flow_type, 365)
            if flow.current_step > max_step * 2:  # Allow double the expected max
                self._add_corruption_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="flow.current_step",
                    pattern="excessive_step_value",
                    severity="medium",
                    description="Flow step value exceeds reasonable limits",
                    detection_method="value_validation",
                    examples=[f"Flow {flow.id}: Step {flow.current_step} for type {flow.flow_type}"],
                    confidence=0.8
                )

        except Exception as e:
            logger.error(f"Step progression analysis failed for flow {flow.id}: {e}")

    async def _analyze_message_content_corruption(self, message: Message) -> None:
        """Analyze message content for corruption patterns"""
        try:
            if not message.content:
                return

            content = message.content

            # Check for binary data in text content
            if re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\xFF]', content):
                self._add_corruption_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="message.content",
                    pattern="binary_data_in_text",
                    severity="high",
                    description="Binary data found in text content",
                    detection_method="binary_detection",
                    examples=[f"Message {message.id}: Contains binary data"],
                    confidence=0.9
                )

            # Check for extremely long messages (potential corruption)
            if len(content) > 10000:  # 10KB seems excessive for a message
                self._add_corruption_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="message.content",
                    pattern="excessive_message_length",
                    severity="medium",
                    description="Message content is excessively long",
                    detection_method="length_validation",
                    examples=[f"Message {message.id}: Length {len(content)} characters"],
                    confidence=0.7
                )

            # Check for message content that's only whitespace
            if content.strip() == "":
                self._add_corruption_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="message.content",
                    pattern="empty_message_content",
                    severity="low",
                    description="Message content is empty or only whitespace",
                    detection_method="content_validation",
                    examples=[f"Message {message.id}: Empty content"],
                    confidence=0.8
                )

        except Exception as e:
            logger.error(f"Message content analysis failed for message {message.id}: {e}")

    def _add_corruption_pattern(self,
                               type: CorruptionType,
                               field: str,
                               pattern: str,
                               severity: str,
                               description: str,
                               detection_method: str,
                               examples: List[str],
                               confidence: float) -> None:
        """Add detected corruption pattern"""
        corruption_pattern = CorruptionPattern(
            type=type,
            field=field,
            pattern=pattern,
            severity=severity,
            description=description,
            detection_method=detection_method,
            examples=examples,
            confidence=confidence
        )
        self.corruption_patterns.append(corruption_pattern)

    def _calculate_corruption_score(self) -> float:
        """Calculate overall corruption score (0-100)"""
        if not self.corruption_patterns:
            return 0.0

        severity_weights = {
            'low': 1,
            'medium': 3,
            'high': 7,
            'critical': 15
        }

        total_score = sum(
            severity_weights.get(pattern.severity, 1) * pattern.confidence
            for pattern in self.corruption_patterns
        )

        # Normalize to 0-100 scale (arbitrary scaling)
        normalized_score = min(100.0, total_score / len(self.corruption_patterns) * 10)
        return round(normalized_score, 2)

    def _generate_corruption_recommendations(self) -> List[str]:
        """Generate recommendations based on detected corruption patterns"""
        recommendations = []

        # Count patterns by type
        type_counts = {}
        for pattern in self.corruption_patterns:
            pattern_type = pattern.type.value
            type_counts[pattern_type] = type_counts.get(pattern_type, 0) + 1

        # Generate specific recommendations
        if type_counts.get('encoding_corruption', 0) > 0:
            recommendations.append("Review data import/export processes for encoding consistency")

        if type_counts.get('format_corruption', 0) > 0:
            recommendations.append("Implement stricter input validation for formatted fields")

        if type_counts.get('temporal_corruption', 0) > 0:
            recommendations.append("Add temporal validation constraints to prevent impossible dates")

        if type_counts.get('content_corruption', 0) > 0:
            recommendations.append("Implement content sanitization and validation")

        if type_counts.get('metadata_corruption', 0) > 0:
            recommendations.append("Add JSON schema validation for metadata fields")

        # General recommendations
        if len(self.corruption_patterns) > 5:
            recommendations.append("Schedule regular corruption detection scans")

        critical_patterns = [p for p in self.corruption_patterns if p.severity == 'critical']
        if critical_patterns:
            recommendations.append("Address critical corruption issues immediately")

        return recommendations[:5]  # Limit to top 5 recommendations

    async def get_corruption_summary(self) -> Dict[str, Any]:
        """Get summary of detected corruption patterns"""
        return {
            'total_patterns': len(self.corruption_patterns),
            'by_type': {
                corruption_type.value: len([p for p in self.corruption_patterns if p.type == corruption_type])
                for corruption_type in CorruptionType
            },
            'by_severity': {
                severity: len([p for p in self.corruption_patterns if p.severity == severity])
                for severity in ['low', 'medium', 'high', 'critical']
            },
            'corruption_score': self._calculate_corruption_score(),
            'top_patterns': [
                {
                    'type': p.type.value,
                    'field': p.field,
                    'description': p.description,
                    'confidence': p.confidence
                }
                for p in sorted(self.corruption_patterns, key=lambda x: x.confidence, reverse=True)[:10]
            ]
        }


def get_corruption_detector(db: Any) -> DataCorruptionDetector:
    """
    Get data corruption detector instance.

    Args:
        db: Database session

    Returns:
        DataCorruptionDetector instance
    """
    return DataCorruptionDetector(db)
