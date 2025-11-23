"""
Structured Data Extraction Service for patient responses.
Implements AI-powered data extraction, response categorization,
sentiment analysis, and medical concern detection.
"""
import logging
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID
# from sqlalchemy.orm import

from app.services.ai import (
    get_sentiment_analyzer,
    get_context_builder,
    PatientContext,
    ConcernLevel,
    NLPUtilities
)
from app.integrations.openai_client import (
    get_langchain_orchestrator,
    LangChainOrchestrator
)
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.message import MessageRepository
from app.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class ResponseCategory(str, Enum):
    """Categories of patient responses."""
    SYMPTOM_REPORT = "symptom_report"
    MEDICATION_INQUIRY = "medication_inquiry"
    SIDE_EFFECT_REPORT = "side_effect_report"
    EMOTIONAL_EXPRESSION = "emotional_expression"
    QUESTION_ANSWER = "question_answer"
    APPOINTMENT_REQUEST = "appointment_request"
    GENERAL_CONVERSATION = "general_conversation"
    EMERGENCY_CONCERN = "emergency_concern"
    TREATMENT_FEEDBACK = "treatment_feedback"
    LIFESTYLE_UPDATE = "lifestyle_update"


class ExtractionConfidence(str, Enum):
    """Confidence levels for data extraction."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class MedicalConcernType(str, Enum):
    """Types of medical concerns."""
    PAIN = "pain"
    SIDE_EFFECT = "side_effect"
    SYMPTOM_WORSENING = "symptom_worsening"
    MEDICATION_ISSUE = "medication_issue"
    EMOTIONAL_DISTRESS = "emotional_distress"
    TREATMENT_ADHERENCE = "treatment_adherence"
    EMERGENCY = "emergency"
    GENERAL_HEALTH = "general_health"


class ExtractedEntity:
    """Extracted entity from patient response."""
    
    def __init__(self,
                 entity_type: str,
                 value: Any,
                 confidence: float,
                 context: str,
                 source_text: str):
        self.entity_type = entity_type
        self.value = value
        self.confidence = confidence
        self.context = context
        self.source_text = source_text
        self.extracted_at = datetime.utcnow()


class MedicalConcern:
    """Medical concern extracted from patient response."""
    
    def __init__(self,
                 concern_type: MedicalConcernType,
                 description: str,
                 severity: ConcernLevel,
                 keywords: List[str],
                 confidence: float,
                 requires_immediate_attention: bool = False):
        self.concern_type = concern_type
        self.description = description
        self.severity = severity
        self.keywords = keywords
        self.confidence = confidence
        self.requires_immediate_attention = requires_immediate_attention
        self.detected_at = datetime.utcnow()


class PatientPreference:
    """Patient preference extracted from response."""
    
    def __init__(self,
                 preference_type: str,
                 value: Any,
                 confidence: float,
                 context: str):
        self.preference_type = preference_type
        self.value = value
        self.confidence = confidence
        self.context = context
        self.extracted_at = datetime.utcnow()


class StructuredExtractionResult:
    """Complete structured extraction result."""
    
    def __init__(self,
                 patient_id: UUID,
                 original_message: str,
                 response_category: ResponseCategory,
                 extracted_entities: List[ExtractedEntity],
                 medical_concerns: List[MedicalConcern],
                 patient_preferences: List[PatientPreference],
                 sentiment_analysis: Dict[str, Any],
                 confidence_score: float,
                 processing_notes: List[str]):
        self.patient_id = patient_id
        self.original_message = original_message
        self.response_category = response_category
        self.extracted_entities = extracted_entities
        self.medical_concerns = medical_concerns
        self.patient_preferences = patient_preferences
        self.sentiment_analysis = sentiment_analysis
        self.confidence_score = confidence_score
        self.processing_notes = processing_notes
        self.extracted_at = datetime.utcnow()


class DataExtractionService:
    """
    AI-powered structured data extraction service for patient responses.
    Handles categorization, entity extraction, medical concern detection,
    and patient preference identification.
    """
    
    def __init__(self, db: Any):
        """
        Initialize data extraction service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.message_repo = MessageRepository(db)
        self.sentiment_analyzer = get_ai_service()
        self.context_builder = get_ai_service()
        self.langchain_orchestrator = get_langchain_orchestrator()
        self.nlp_utils = NLPUtilities()
        
        # Medical terminology patterns
        self._load_medical_patterns()
        
        logger.info("Data Extraction Service initialized")
    
    def _load_medical_patterns(self):
        """Load medical terminology patterns for extraction."""
        self.pain_patterns = {
            'pain_descriptors': [
                r'\b(dor|pain|ache|aching|hurt|hurting|sore|tender)\b',
                r'\b(doloroso|dolorosa|doendo|machucando)\b'
            ],
            'pain_intensity': [
                r'\b(leve|mild|light|fraca|fraco)\b',
                r'\b(moderada|moderate|média|medio)\b',
                r'\b(forte|strong|intensa|intenso|severe)\b',
                r'\b(insuportável|unbearable|terrível|terrible|extrema|extreme)\b'
            ],
            'pain_scale': r'\b([1-9]|10)\s*(?:de\s*10|/10|out\s*of\s*10)\b'
        }
        
        self.medication_patterns = {
            'medication_names': [
                r'\b(comprimido|tablet|cápsula|capsule|medicamento|medication|remédio|medicine)\b',
                r'\b(mg|ml|mcg|g|grama|gram|miligramas?|milligrams?)\b'
            ],
            'dosage': r'\b(\d+(?:\.\d+)?)\s*(mg|ml|mcg|g|comprimidos?|tablets?|cápsulas?|capsules?)\b',
            'frequency': [
                r'\b(uma vez|once|twice|duas vezes|três vezes|three times)\b',
                r'\b(diário|daily|diariamente|por dia|per day)\b',
                r'\b(manhã|morning|tarde|afternoon|noite|night|evening)\b'
            ]
        }
        
        self.symptom_patterns = {
            'common_symptoms': [
                r'\b(náusea|nausea|vômito|vomiting|tontura|dizziness|dizzy)\b',
                r'\b(cansaço|fatigue|tired|weakness|fraqueza)\b',
                r'\b(febre|fever|calafrio|chills|suor|sweating)\b',
                r'\b(dor de cabeça|headache|enxaqueca|migraine)\b'
            ],
            'severity_indicators': [
                r'\b(pior|worse|piorando|worsening|melhor|better|melhorando|improving)\b',
                r'\b(começou|started|parou|stopped|continua|continues|persistent)\b'
            ]
        }
        
        self.emotional_patterns = {
            'positive_emotions': [
                r'\b(feliz|happy|bem|good|ótimo|great|animada|excited|confiante|confident)\b',
                r'\b(melhor|better|aliviada|relieved|grata|grateful|esperançosa|hopeful)\b'
            ],
            'negative_emotions': [
                r'\b(triste|sad|deprimida|depressed|ansiosa|anxious|preocupada|worried)\b',
                r'\b(medo|fear|scared|assustada|nervosa|nervous|estressada|stressed)\b'
            ],
            'emotional_intensity': [
                r'\b(muito|very|extremely|bastante|quite|um pouco|a little|slightly)\b'
            ]
        }
    
    async def extract_structured_data(self,
                                    patient_id: UUID,
                                    message_text: str,
                                    flow_context: Optional[PatientFlowState] = None) -> StructuredExtractionResult:
        """
        Extract structured data from patient message using AI and pattern matching.
        
        Args:
            patient_id: Patient UUID
            message_text: Patient message text
            flow_context: Optional flow context
            
        Returns:
            Structured extraction result
            
        Raises:
            ExternalServiceError: If AI service fails
        """
        try:
            processing_notes = []
            
            # Get patient context
            patient_context = await self._build_patient_context(patient_id, flow_context)
            
            # Categorize response
            response_category = await self._categorize_response(message_text, patient_context)
            processing_notes.append(f"Categorized as: {response_category.value}")
            
            # Extract entities using multiple methods
            extracted_entities = await self._extract_entities(message_text, patient_context)
            processing_notes.append(f"Extracted {len(extracted_entities)} entities")
            
            # Detect medical concerns
            medical_concerns = await self._detect_medical_concerns(message_text, patient_context)
            processing_notes.append(f"Detected {len(medical_concerns)} medical concerns")
            
            # Extract patient preferences
            patient_preferences = await self._extract_patient_preferences(message_text, patient_context)
            processing_notes.append(f"Extracted {len(patient_preferences)} preferences")
            
            # Perform sentiment analysis
            sentiment_response, concern_level = await self.sentiment_analyzer.analyze_response(
                message_text, patient_context
            )
            
            sentiment_analysis = {
                "sentiment": sentiment_response.sentiment.value,
                "confidence": sentiment_response.confidence,
                "concern_level": concern_level.value,
                "key_phrases": sentiment_response.key_phrases,
                "emotional_indicators": sentiment_response.emotional_indicators,
                "medical_concerns": sentiment_response.medical_concerns
            }
            
            # Calculate overall confidence score
            confidence_score = self._calculate_confidence_score(
                extracted_entities, medical_concerns, sentiment_response.confidence
            )
            
            return StructuredExtractionResult(
                patient_id=patient_id,
                original_message=message_text,
                response_category=response_category,
                extracted_entities=extracted_entities,
                medical_concerns=medical_concerns,
                patient_preferences=patient_preferences,
                sentiment_analysis=sentiment_analysis,
                confidence_score=confidence_score,
                processing_notes=processing_notes
            )
            
        except Exception as e:
            logger.error(f"Failed to extract structured data: {e}")
            raise ExternalServiceError(f"Data extraction failed: {str(e)}")
    
    async def _build_patient_context(self,
                                   patient_id: UUID,
                                   flow_context: Optional[PatientFlowState]) -> PatientContext:
        """Build comprehensive patient context for AI processing."""
        try:
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Get recent message history
            recent_messages = self.message_repo.get_conversation_history(patient_id, limit=10)
            recent_message_data = [
                {
                    "content": msg.content,
                    "direction": msg.direction.value,
                    "timestamp": msg.created_at.isoformat()
                }
                for msg in recent_messages
            ]
            
            # Build context
            return await self.context_builder.build_patient_context(
                patient_id=str(patient_id),
                patient_data={
                    "name": patient.name,
                    "treatment_type": getattr(patient, 'treatment_type', 'general'),
                    "current_day": flow_context.current_step if flow_context else 1,
                    "treatment_start_date": flow_context.started_at.isoformat() if flow_context else None,
                    "age": getattr(patient, 'age', None),
                    "preferences": getattr(patient, 'preferences', {})
                },
                recent_messages=recent_message_data,
                medical_data=getattr(patient, 'medical_history', {})
            )
            
        except Exception as e:
            logger.error(f"Failed to build patient context: {e}")
            raise
    
    async def _categorize_response(self,
                                 message_text: str,
                                 patient_context: PatientContext) -> ResponseCategory:
        """Categorize patient response using AI and pattern matching."""
        try:
            # Use AI for categorization
            categorization_prompt = f"""
            Categorize this patient message into one of these categories:
            - symptom_report: Patient reporting symptoms or health changes
            - medication_inquiry: Questions about medications or dosage
            - side_effect_report: Reporting medication side effects
            - emotional_expression: Expressing emotions or mental state
            - question_answer: Answering a specific question
            - appointment_request: Requesting appointment or consultation
            - general_conversation: General conversation or greeting
            - emergency_concern: Urgent medical concern
            - treatment_feedback: Feedback about treatment progress
            - lifestyle_update: Updates about lifestyle, diet, exercise
            
            Patient context: {patient_context.treatment_type} treatment, day {patient_context.treatment_day}
            Message: "{message_text}"
            
            Return only the category name.
            """
            
            try:
                ai_category = await self.langchain_orchestrator.generate_text(categorization_prompt)
                ai_category = ai_category.strip().lower()
                
                # Validate AI response
                for category in ResponseCategory:
                    if category.value in ai_category:
                        return category
            except Exception as e:
                logger.warning(f"AI categorization failed, using pattern matching: {e}")
            
            # Fallback to pattern matching
            return self._categorize_by_patterns(message_text)
            
        except Exception as e:
            logger.error(f"Response categorization failed: {e}")
            return ResponseCategory.GENERAL_CONVERSATION
    
    def _categorize_by_patterns(self, message_text: str) -> ResponseCategory:
        """Categorize response using pattern matching."""
        text_lower = message_text.lower()
        
        # Emergency patterns
        emergency_patterns = [
            r'\b(emergência|emergency|urgent|urgente|help|ajuda|hospital)\b',
            r'\b(não consigo respirar|can\'t breathe|chest pain|dor no peito)\b'
        ]
        if any(re.search(pattern, text_lower) for pattern in emergency_patterns):
            return ResponseCategory.EMERGENCY_CONCERN
        
        # Symptom patterns
        symptom_patterns = [
            r'\b(sintoma|symptom|sinto|feeling|dor|pain|náusea|nausea)\b',
            r'\b(febre|fever|cansaço|tired|tontura|dizzy)\b'
        ]
        if any(re.search(pattern, text_lower) for pattern in symptom_patterns):
            return ResponseCategory.SYMPTOM_REPORT
        
        # Medication patterns
        medication_patterns = [
            r'\b(medicamento|medication|remédio|medicine|comprimido|tablet)\b',
            r'\b(dosagem|dosage|quando tomar|when to take)\b'
        ]
        if any(re.search(pattern, text_lower) for pattern in medication_patterns):
            return ResponseCategory.MEDICATION_INQUIRY
        
        # Emotional patterns
        emotional_patterns = [
            r'\b(sinto|feel|emoção|emotion|triste|sad|feliz|happy|ansiosa|anxious)\b',
            r'\b(preocupada|worried|medo|fear|esperança|hope)\b'
        ]
        if any(re.search(pattern, text_lower) for pattern in emotional_patterns):
            return ResponseCategory.EMOTIONAL_EXPRESSION
        
        # Question patterns
        question_patterns = [r'\?', r'\b(sim|yes|não|no|talvez|maybe)\b']
        if any(re.search(pattern, text_lower) for pattern in question_patterns):
            return ResponseCategory.QUESTION_ANSWER
        
        return ResponseCategory.GENERAL_CONVERSATION
    
    async def _extract_entities(self,
                               message_text: str,
                               patient_context: PatientContext) -> List[ExtractedEntity]:
        """Extract entities from message using AI and pattern matching."""
        entities = []
        
        try:
            # Extract using pattern matching
            pattern_entities = self._extract_entities_by_patterns(message_text)
            entities.extend(pattern_entities)
            
            # Extract using AI
            ai_entities = await self._extract_entities_by_ai(message_text, patient_context)
            entities.extend(ai_entities)
            
            # Remove duplicates and merge similar entities
            entities = self._deduplicate_entities(entities)
            
            return entities
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return entities
    
    def _extract_entities_by_patterns(self, message_text: str) -> List[ExtractedEntity]:
        """Extract entities using regex patterns."""
        entities = []
        text_lower = message_text.lower()
        
        try:
            # Extract pain scale
            pain_scale_match = re.search(self.pain_patterns['pain_scale'], text_lower)
            if pain_scale_match:
                entities.append(ExtractedEntity(
                    entity_type="pain_scale",
                    value=int(pain_scale_match.group(1)),
                    confidence=0.9,
                    context="pain scale rating",
                    source_text=pain_scale_match.group(0)
                ))
            
            # Extract medication dosage
            dosage_matches = re.finditer(self.medication_patterns['dosage'], text_lower)
            for match in dosage_matches:
                entities.append(ExtractedEntity(
                    entity_type="medication_dosage",
                    value={"amount": float(match.group(1)), "unit": match.group(2)},
                    confidence=0.8,
                    context="medication dosage",
                    source_text=match.group(0)
                ))
            
            # Extract numbers
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', message_text)
            for number in numbers:
                entities.append(ExtractedEntity(
                    entity_type="numeric_value",
                    value=float(number),
                    confidence=0.6,
                    context="numeric mention",
                    source_text=number
                ))
            
            # Extract time references
            time_patterns = [
                r'\b(\d{1,2}):(\d{2})\b',
                r'\b(\d{1,2})\s*(am|pm|h|horas?)\b',
                r'\b(manhã|morning|tarde|afternoon|noite|night|evening)\b'
            ]
            
            for pattern in time_patterns:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    entities.append(ExtractedEntity(
                        entity_type="time_reference",
                        value=match.group(0),
                        confidence=0.7,
                        context="time mention",
                        source_text=match.group(0)
                    ))
            
            # Extract yes/no responses
            yes_pattern = r'\b(sim|yes|yeah|ok|okay|claro|certo|positivo)\b'
            no_pattern = r'\b(não|no|nope|never|negativo|jamais)\b'
            
            if re.search(yes_pattern, text_lower):
                entities.append(ExtractedEntity(
                    entity_type="boolean_response",
                    value=True,
                    confidence=0.8,
                    context="affirmative response",
                    source_text=re.search(yes_pattern, text_lower).group(0)
                ))
            elif re.search(no_pattern, text_lower):
                entities.append(ExtractedEntity(
                    entity_type="boolean_response",
                    value=False,
                    confidence=0.8,
                    context="negative response",
                    source_text=re.search(no_pattern, text_lower).group(0)
                ))
            
            return entities
            
        except Exception as e:
            logger.error(f"Pattern-based entity extraction failed: {e}")
            return entities    

    async def _extract_entities_by_ai(self,
                                    message_text: str,
                                    patient_context: PatientContext) -> List[ExtractedEntity]:
        """Extract entities using AI."""
        entities = []
        
        try:
            extraction_prompt = f"""
            Extract structured entities from this patient message. Focus on medical information, measurements, and preferences.
            
            Patient context: {patient_context.treatment_type} treatment, day {patient_context.treatment_day}
            Message: "{message_text}"
            
            Extract and format as JSON:
            {{
                "entities": [
                    {{
                        "type": "entity_type",
                        "value": "extracted_value",
                        "confidence": 0.0-1.0,
                        "context": "description"
                    }}
                ]
            }}
            
            Entity types to look for:
            - symptoms: any health symptoms mentioned
            - medications: medication names or references
            - side_effects: reported side effects
            - pain_level: pain descriptions or ratings
            - mood_state: emotional state indicators
            - preferences: patient preferences or requests
            - measurements: any numeric health measurements
            - time_references: time-related information
            """
            
            ai_response = await self.langchain_orchestrator.generate_text(extraction_prompt)
            
            # Parse AI response (simplified - in production, use proper JSON parsing)
            import json
            try:
                parsed_response = json.loads(ai_response)
                for entity_data in parsed_response.get("entities", []):
                    entities.append(ExtractedEntity(
                        entity_type=entity_data.get("type", "unknown"),
                        value=entity_data.get("value"),
                        confidence=float(entity_data.get("confidence", 0.5)),
                        context=entity_data.get("context", "AI extracted"),
                        source_text=message_text[:50]  # First 50 chars as source
                    ))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to parse AI entity extraction response: {e}")
            
            return entities
            
        except Exception as e:
            logger.error(f"AI entity extraction failed: {e}")
            return entities
    
    def _deduplicate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Remove duplicate entities and merge similar ones."""
        deduplicated = []
        seen_entities = {}
        
        for entity in entities:
            key = f"{entity.entity_type}_{str(entity.value)}"
            
            if key in seen_entities:
                # Keep the one with higher confidence
                existing = seen_entities[key]
                if entity.confidence > existing.confidence:
                    seen_entities[key] = entity
            else:
                seen_entities[key] = entity
        
        return list(seen_entities.values())
    
    async def _detect_medical_concerns(self,
                                     message_text: str,
                                     patient_context: PatientContext) -> List[MedicalConcern]:
        """Detect medical concerns from patient message."""
        concerns = []
        
        try:
            # Pattern-based detection
            pattern_concerns = self._detect_concerns_by_patterns(message_text)
            concerns.extend(pattern_concerns)
            
            # AI-based detection
            ai_concerns = await self._detect_concerns_by_ai(message_text, patient_context)
            concerns.extend(ai_concerns)
            
            # Remove duplicates
            concerns = self._deduplicate_concerns(concerns)
            
            return concerns
            
        except Exception as e:
            logger.error(f"Medical concern detection failed: {e}")
            return concerns
    
    def _detect_concerns_by_patterns(self, message_text: str) -> List[MedicalConcern]:
        """Detect medical concerns using pattern matching."""
        concerns = []
        text_lower = message_text.lower()
        
        try:
            # Emergency concerns
            emergency_patterns = [
                (r'\b(não consigo respirar|can\'t breathe)\b', "breathing difficulty"),
                (r'\b(dor no peito|chest pain)\b', "chest pain"),
                (r'\b(sangramento|bleeding)\b', "bleeding"),
                (r'\b(desmaiei|fainted|unconscious)\b', "loss of consciousness")
            ]
            
            for pattern, description in emergency_patterns:
                if re.search(pattern, text_lower):
                    concerns.append(MedicalConcern(
                        concern_type=MedicalConcernType.EMERGENCY,
                        description=description,
                        severity=ConcernLevel.CRITICAL,
                        keywords=re.findall(pattern, text_lower),
                        confidence=0.9,
                        requires_immediate_attention=True
                    ))
            
            # Pain concerns
            pain_patterns = [
                (r'\b(dor insuportável|unbearable pain)\b', "severe pain"),
                (r'\b(dor forte|severe pain|intense pain)\b', "intense pain"),
                (r'\b(dor de cabeça|headache)\b', "headache"),
                (r'\b(dor nas costas|back pain)\b', "back pain")
            ]
            
            for pattern, description in pain_patterns:
                if re.search(pattern, text_lower):
                    severity = ConcernLevel.HIGH if "insuportável" in pattern or "unbearable" in pattern else ConcernLevel.MEDIUM
                    concerns.append(MedicalConcern(
                        concern_type=MedicalConcernType.PAIN,
                        description=description,
                        severity=severity,
                        keywords=re.findall(pattern, text_lower),
                        confidence=0.8
                    ))
            
            # Side effect concerns
            side_effect_patterns = [
                (r'\b(náusea|nausea|enjoo)\b', "nausea"),
                (r'\b(tontura|dizziness|dizzy)\b', "dizziness"),
                (r'\b(vômito|vomiting)\b', "vomiting"),
                (r'\b(erupção|rash|alergia|allergy)\b', "allergic reaction")
            ]
            
            for pattern, description in side_effect_patterns:
                if re.search(pattern, text_lower):
                    concerns.append(MedicalConcern(
                        concern_type=MedicalConcernType.SIDE_EFFECT,
                        description=description,
                        severity=ConcernLevel.MEDIUM,
                        keywords=re.findall(pattern, text_lower),
                        confidence=0.7
                    ))
            
            # Emotional distress
            emotional_patterns = [
                (r'\b(muito triste|very sad|deprimida|depressed)\b', "depression symptoms"),
                (r'\b(ansiosa|anxious|panic|pânico)\b', "anxiety symptoms"),
                (r'\b(não consigo dormir|can\'t sleep|insomnia|insônia)\b', "sleep issues")
            ]
            
            for pattern, description in emotional_patterns:
                if re.search(pattern, text_lower):
                    concerns.append(MedicalConcern(
                        concern_type=MedicalConcernType.EMOTIONAL_DISTRESS,
                        description=description,
                        severity=ConcernLevel.MEDIUM,
                        keywords=re.findall(pattern, text_lower),
                        confidence=0.6
                    ))
            
            return concerns
            
        except Exception as e:
            logger.error(f"Pattern-based concern detection failed: {e}")
            return concerns
    
    async def _detect_concerns_by_ai(self,
                                   message_text: str,
                                   patient_context: PatientContext) -> List[MedicalConcern]:
        """Detect medical concerns using AI."""
        concerns = []
        
        try:
            concern_detection_prompt = f"""
            Analyze this patient message for medical concerns that require healthcare provider attention.
            
            Patient context: {patient_context.treatment_type} treatment, day {patient_context.treatment_day}
            Message: "{message_text}"
            
            Identify concerns and format as JSON:
            {{
                "concerns": [
                    {{
                        "type": "concern_type",
                        "description": "brief description",
                        "severity": "low|medium|high|critical",
                        "keywords": ["keyword1", "keyword2"],
                        "confidence": 0.0-1.0,
                        "immediate_attention": true/false
                    }}
                ]
            }}
            
            Concern types:
            - pain: pain-related issues
            - side_effect: medication side effects
            - symptom_worsening: worsening symptoms
            - medication_issue: medication problems
            - emotional_distress: mental health concerns
            - treatment_adherence: compliance issues
            - emergency: urgent medical situations
            - general_health: other health concerns
            """
            
            ai_response = await self.langchain_orchestrator.generate_text(concern_detection_prompt)
            
            # Parse AI response
            import json
            try:
                parsed_response = json.loads(ai_response)
                for concern_data in parsed_response.get("concerns", []):
                    concern_type_str = concern_data.get("type", "general_health")
                    concern_type = MedicalConcernType.GENERAL_HEALTH
                    
                    # Map string to enum
                    for ct in MedicalConcernType:
                        if ct.value == concern_type_str:
                            concern_type = ct
                            break
                    
                    severity_str = concern_data.get("severity", "low")
                    severity = ConcernLevel.LOW
                    
                    # Map string to enum
                    for sev in ConcernLevel:
                        if sev.value == severity_str:
                            severity = sev
                            break
                    
                    concerns.append(MedicalConcern(
                        concern_type=concern_type,
                        description=concern_data.get("description", "AI detected concern"),
                        severity=severity,
                        keywords=concern_data.get("keywords", []),
                        confidence=float(concern_data.get("confidence", 0.5)),
                        requires_immediate_attention=concern_data.get("immediate_attention", False)
                    ))
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to parse AI concern detection response: {e}")
            
            return concerns
            
        except Exception as e:
            logger.error(f"AI concern detection failed: {e}")
            return concerns
    
    def _deduplicate_concerns(self, concerns: List[MedicalConcern]) -> List[MedicalConcern]:
        """Remove duplicate medical concerns."""
        deduplicated = []
        seen_concerns = {}
        
        for concern in concerns:
            key = f"{concern.concern_type.value}_{concern.description}"
            
            if key in seen_concerns:
                # Keep the one with higher severity or confidence
                existing = seen_concerns[key]
                if (concern.severity.value > existing.severity.value or 
                    (concern.severity == existing.severity and concern.confidence > existing.confidence)):
                    seen_concerns[key] = concern
            else:
                seen_concerns[key] = concern
        
        return list(seen_concerns.values())
    
    async def _extract_patient_preferences(self,
                                         message_text: str,
                                         patient_context: PatientContext) -> List[PatientPreference]:
        """Extract patient preferences from message."""
        preferences = []
        
        try:
            # Pattern-based preference extraction
            pattern_preferences = self._extract_preferences_by_patterns(message_text)
            preferences.extend(pattern_preferences)
            
            # AI-based preference extraction
            ai_preferences = await self._extract_preferences_by_ai(message_text, patient_context)
            preferences.extend(ai_preferences)
            
            return preferences
            
        except Exception as e:
            logger.error(f"Preference extraction failed: {e}")
            return preferences
    
    def _extract_preferences_by_patterns(self, message_text: str) -> List[PatientPreference]:
        """Extract preferences using pattern matching."""
        preferences = []
        text_lower = message_text.lower()
        
        try:
            # Communication time preferences
            time_preferences = [
                (r'\b(manhã|morning)\b', "morning"),
                (r'\b(tarde|afternoon)\b', "afternoon"),
                (r'\b(noite|evening|night)\b', "evening")
            ]
            
            for pattern, time_period in time_preferences:
                if re.search(pattern, text_lower):
                    preferences.append(PatientPreference(
                        preference_type="communication_time",
                        value=time_period,
                        confidence=0.7,
                        context=f"prefers {time_period} communication"
                    ))
            
            # Communication frequency preferences
            frequency_patterns = [
                (r'\b(diário|daily|todos os dias)\b', "daily"),
                (r'\b(semanal|weekly|uma vez por semana)\b', "weekly"),
                (r'\b(menos mensagens|fewer messages)\b', "less_frequent")
            ]
            
            for pattern, frequency in frequency_patterns:
                if re.search(pattern, text_lower):
                    preferences.append(PatientPreference(
                        preference_type="communication_frequency",
                        value=frequency,
                        confidence=0.6,
                        context=f"prefers {frequency} communication"
                    ))
            
            # Language preferences
            if re.search(r'\b(english|inglês)\b', text_lower):
                preferences.append(PatientPreference(
                    preference_type="language",
                    value="english",
                    confidence=0.8,
                    context="prefers English communication"
                ))
            
            return preferences
            
        except Exception as e:
            logger.error(f"Pattern-based preference extraction failed: {e}")
            return preferences
    
    async def _extract_preferences_by_ai(self,
                                       message_text: str,
                                       patient_context: PatientContext) -> List[PatientPreference]:
        """Extract preferences using AI."""
        preferences = []
        
        try:
            preference_prompt = f"""
            Extract patient preferences and requests from this message.
            
            Patient context: {patient_context.treatment_type} treatment, day {patient_context.treatment_day}
            Message: "{message_text}"
            
            Look for preferences about:
            - Communication timing (morning, afternoon, evening)
            - Communication frequency (daily, weekly, less often)
            - Information detail level (brief, detailed)
            - Language preferences
            - Contact methods
            - Treatment approach preferences
            
            Format as JSON:
            {{
                "preferences": [
                    {{
                        "type": "preference_type",
                        "value": "preference_value",
                        "confidence": 0.0-1.0,
                        "context": "explanation"
                    }}
                ]
            }}
            """
            
            ai_response = await self.langchain_orchestrator.generate_text(preference_prompt)
            
            # Parse AI response
            import json
            try:
                parsed_response = json.loads(ai_response)
                for pref_data in parsed_response.get("preferences", []):
                    preferences.append(PatientPreference(
                        preference_type=pref_data.get("type", "general"),
                        value=pref_data.get("value"),
                        confidence=float(pref_data.get("confidence", 0.5)),
                        context=pref_data.get("context", "AI extracted preference")
                    ))
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to parse AI preference extraction response: {e}")
            
            return preferences
            
        except Exception as e:
            logger.error(f"AI preference extraction failed: {e}")
            return preferences
    
    def _calculate_confidence_score(self,
                                  entities: List[ExtractedEntity],
                                  concerns: List[MedicalConcern],
                                  sentiment_confidence: float) -> float:
        """Calculate overall confidence score for extraction."""
        try:
            if not entities and not concerns:
                return sentiment_confidence
            
            # Calculate average entity confidence
            entity_confidence = 0.0
            if entities:
                entity_confidence = sum(e.confidence for e in entities) / len(entities)
            
            # Calculate average concern confidence
            concern_confidence = 0.0
            if concerns:
                concern_confidence = sum(c.confidence for c in concerns) / len(concerns)
            
            # Weight the scores
            weights = []
            scores = []
            
            if entities:
                weights.append(0.4)
                scores.append(entity_confidence)
            
            if concerns:
                weights.append(0.4)
                scores.append(concern_confidence)
            
            weights.append(0.2)
            scores.append(sentiment_confidence)
            
            # Calculate weighted average
            total_weight = sum(weights)
            weighted_sum = sum(w * s for w, s in zip(weights, scores))
            
            return weighted_sum / total_weight if total_weight > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Confidence calculation failed: {e}")
            return 0.5  # Default medium confidence
    
    async def analyze_response_accuracy(self,
                                      extraction_results: List[StructuredExtractionResult],
                                      ground_truth_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, float]:
        """
        Analyze accuracy of extraction results (for testing and improvement).
        
        Args:
            extraction_results: List of extraction results
            ground_truth_data: Optional ground truth for comparison
            
        Returns:
            Accuracy metrics
        """
        try:
            metrics = {
                "total_extractions": len(extraction_results),
                "avg_confidence": 0.0,
                "entity_extraction_rate": 0.0,
                "concern_detection_rate": 0.0,
                "preference_extraction_rate": 0.0,
                "high_confidence_rate": 0.0
            }
            
            if not extraction_results:
                return metrics
            
            # Calculate average confidence
            total_confidence = sum(result.confidence_score for result in extraction_results)
            metrics["avg_confidence"] = total_confidence / len(extraction_results)
            
            # Calculate extraction rates
            with_entities = sum(1 for result in extraction_results if result.extracted_entities)
            metrics["entity_extraction_rate"] = with_entities / len(extraction_results)
            
            with_concerns = sum(1 for result in extraction_results if result.medical_concerns)
            metrics["concern_detection_rate"] = with_concerns / len(extraction_results)
            
            with_preferences = sum(1 for result in extraction_results if result.patient_preferences)
            metrics["preference_extraction_rate"] = with_preferences / len(extraction_results)
            
            # High confidence rate (>0.7)
            high_confidence = sum(1 for result in extraction_results if result.confidence_score > 0.7)
            metrics["high_confidence_rate"] = high_confidence / len(extraction_results)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Accuracy analysis failed: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on data extraction service."""
        try:
            health_status = {
                "service": "DataExtractionService",
                "timestamp": datetime.utcnow().isoformat(),
                "healthy": True,
                "components": {}
            }
            
            # Check AI services
            try:
                test_response = await self.langchain_orchestrator.generate_text("Test message")
                health_status["components"]["ai_service"] = {
                    "healthy": True,
                    "response_received": bool(test_response)
                }
            except Exception as e:
                health_status["components"]["ai_service"] = {
                    "healthy": False,
                    "error": str(e)
                }
                health_status["healthy"] = False
            
            # Check sentiment analyzer
            try:
                # Create dummy context for test
                test_context = PatientContext(
                    patient_id="test",
                    name="Test",
                    treatment_type="test",
                    treatment_day=1
                )
                sentiment_result, _ = await self.sentiment_analyzer.analyze_response(
                    "Test message", test_context
                )
                health_status["components"]["sentiment_analyzer"] = {
                    "healthy": True,
                    "sentiment_detected": bool(sentiment_result.sentiment)
                }
            except Exception as e:
                health_status["components"]["sentiment_analyzer"] = {
                    "healthy": False,
                    "error": str(e)
                }
                health_status["healthy"] = False
            
            # Check database connectivity
            try:
                self.db.execute("SELECT 1")
                health_status["components"]["database"] = {"healthy": True}
            except Exception as e:
                health_status["components"]["database"] = {
                    "healthy": False,
                    "error": str(e)
                }
                health_status["healthy"] = False
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service": "DataExtractionService",
                "timestamp": datetime.utcnow().isoformat(),
                "healthy": False,
                "error": str(e)
            }


# Global service instance
_data_extraction_service: Optional[DataExtractionService] = None


def get_data_extraction_service(db: Any) -> DataExtractionService:
    """
    Get data extraction service instance.
    
    Args:
        db: Database session
        
    Returns:
        DataExtractionService instance
    """
    return DataExtractionService(db)
