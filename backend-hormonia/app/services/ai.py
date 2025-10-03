"""
AI-powered services for message personalization and sentiment analysis.
Provides high-level interfaces for AI operations in the Hormonia system.
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum

from app.integrations.openai_client import (
    LangChainOrchestrator,
    MessagePersonalizationRequest,
    SentimentAnalysisRequest,
    PersonalizationResponse,
    SentimentAnalysisResponse,
    SentimentType,
    get_langchain_orchestrator
)
from app.exceptions import ExternalServiceError
from app.utils.token_limiter import TokenLimiter, get_token_limiter


logger = logging.getLogger(__name__)


class ConcernLevel(str, Enum):
    """Medical concern severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PatientContext:
    """Patient context data structure for AI operations."""
    
    def __init__(
        self,
        patient_id: str,
        name: str,
        treatment_type: str,
        treatment_day: int,
        age: Optional[int] = None,
        recent_responses: Optional[List[str]] = None,
        medical_history: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None
    ):
        self.patient_id = patient_id
        self.name = name
        self.treatment_type = treatment_type
        self.treatment_day = treatment_day
        self.age = age
        self.recent_responses = recent_responses or []
        self.medical_history = medical_history or {}
        self.preferences = preferences or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for AI processing."""
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "treatment_type": self.treatment_type,
            "treatment_day": self.treatment_day,
            "age": self.age,
            "recent_responses": self.recent_responses,
            "medical_history": self.medical_history,
            "preferences": self.preferences
        }


class AIHumanizer:
    """
    AI-powered message humanization service.
    
    Transforms template messages into personalized, empathetic communications
    tailored to individual patients and their treatment context.
    """
    
    def __init__(self, orchestrator: Optional[LangChainOrchestrator] = None):
        """
        Initialize AI humanizer.

        Args:
            orchestrator: LangChain orchestrator instance
        """
        self.orchestrator = orchestrator or get_langchain_orchestrator()
        self.token_limiter = get_token_limiter()
        logger.info("AI Humanizer initialized with token limiting")
    
    async def humanize_message(
        self,
        template_message: str,
        patient_context: PatientContext,
        message_type: str = "general"
    ) -> PersonalizationResponse:
        """
        Humanize a template message for a specific patient.
        
        Args:
            template_message: Template message to personalize
            patient_context: Patient context information
            message_type: Type of message (welcome, check_in, reminder, etc.)
            
        Returns:
            Personalized message response
            
        Raises:
            ExternalServiceError: If AI service fails
        """
        try:
            # Apply token limiting to patient context (500 token budget)
            limited_context = self.token_limiter.limit_patient_context(
                patient_context.to_dict(),
                max_tokens=TokenLimiter.DEFAULT_MAX_TOKENS  # 500 tokens
            )

            # Limit recent responses separately for previous_responses field
            limited_responses = self.token_limiter.limit_messages_history(
                [{"content": resp} for resp in patient_context.recent_responses],
                max_tokens=TokenLimiter.MESSAGE_MAX_TOKENS  # 100 tokens
            )
            limited_response_texts = [msg["content"] for msg in limited_responses]

            # Create personalization request with limited context
            request = MessagePersonalizationRequest(
                template_message=template_message,
                patient_name=patient_context.name,
                patient_context=limited_context,
                treatment_day=patient_context.treatment_day,
                previous_responses=limited_response_texts
            )

            logger.debug(f"Context limited to ~{self.token_limiter.estimate_tokens(str(limited_context))} tokens")
            
            # Get AI-generated personalized message
            response = await self.orchestrator.humanize_message(request)
            
            # Enhance with additional personalization based on message type
            enhanced_message = self._enhance_by_message_type(
                response.humanized_message,
                message_type,
                patient_context
            )
            
            # Update response with enhanced message
            response.humanized_message = enhanced_message
            response.personalization_notes.append(f"Enhanced for {message_type} message type")
            
            logger.info(f"Message humanized for patient {patient_context.patient_id}")
            return response
            
        except Exception as e:
            logger.error(f"Message humanization failed for patient {patient_context.patient_id}: {e}")
            raise ExternalServiceError(f"Failed to humanize message: {str(e)}")
    
    def _enhance_by_message_type(
        self,
        message: str,
        message_type: str,
        patient_context: PatientContext
    ) -> str:
        """
        Enhance message based on specific message type.
        
        Args:
            message: Base humanized message
            message_type: Type of message
            patient_context: Patient context
            
        Returns:
            Enhanced message
        """
        enhancements = {
            "welcome": self._enhance_welcome_message,
            "check_in": self._enhance_check_in_message,
            "reminder": self._enhance_reminder_message,
            "support": self._enhance_support_message
        }
        
        enhancer = enhancements.get(message_type)
        if enhancer:
            return enhancer(message, patient_context)
        
        return message
    
    def _enhance_welcome_message(self, message: str, context: PatientContext) -> str:
        """Enhance welcome messages with treatment-specific information."""
        if context.treatment_day == 1:
            message += f"\n\nWelcome to your {context.treatment_type} journey! I'll be here to support you every step of the way. 🌟"
        return message
    
    def _enhance_check_in_message(self, message: str, context: PatientContext) -> str:
        """Enhance check-in messages with progress acknowledgment."""
        if context.treatment_day > 7:
            message += f"\n\nYou've been doing great for {context.treatment_day} days now! Keep up the excellent work. 💪"
        return message
    
    def _enhance_reminder_message(self, message: str, context: PatientContext) -> str:
        """Enhance reminder messages with gentle encouragement."""
        message += "\n\nRemember, consistency is key to your treatment success. You've got this! 🎯"
        return message
    
    def _enhance_support_message(self, message: str, context: PatientContext) -> str:
        """Enhance support messages with empathy and resources."""
        message += "\n\nIf you need immediate assistance, don't hesitate to contact your healthcare provider. We're here for you. 🤝"
        return message


class SentimentAnalyzer:
    """
    AI-powered sentiment analysis service.
    
    Analyzes patient messages for emotional state, medical concerns,
    and treatment adherence indicators.
    """
    
    def __init__(self, orchestrator: Optional[LangChainOrchestrator] = None):
        """
        Initialize sentiment analyzer.

        Args:
            orchestrator: LangChain orchestrator instance
        """
        self.orchestrator = orchestrator or get_langchain_orchestrator()
        self.token_limiter = get_token_limiter()
        logger.info("Sentiment Analyzer initialized with token limiting")
    
    async def analyze_response(
        self,
        patient_message: str,
        patient_context: PatientContext
    ) -> Tuple[SentimentAnalysisResponse, ConcernLevel]:
        """
        Analyze patient message for sentiment and medical concerns.
        
        Args:
            patient_message: Patient's message to analyze
            patient_context: Patient context information
            
        Returns:
            Tuple of (sentiment analysis response, concern level)
            
        Raises:
            ExternalServiceError: If AI service fails
        """
        try:
            # Limit message to prevent exceeding token budget
            limited_message = self.token_limiter.truncate_to_tokens(
                patient_message,
                max_tokens=TokenLimiter.MESSAGE_MAX_TOKENS  # 100 tokens
            )

            # Limit patient context to fit within budget
            limited_context = self.token_limiter.limit_patient_context(
                patient_context.to_dict(),
                max_tokens=TokenLimiter.CONTEXT_MAX_TOKENS  # 300 tokens
            )

            # Create sentiment analysis request with limited data
            request = SentimentAnalysisRequest(
                message=limited_message,
                patient_context=limited_context
            )

            logger.debug(f"Sentiment analysis context limited to ~{self.token_limiter.estimate_tokens(str(limited_context))} tokens")
            
            # Get AI sentiment analysis
            response = await self.orchestrator.analyze_sentiment(request)
            
            # Determine concern level based on analysis
            concern_level = self._determine_concern_level(response, patient_context)
            
            # Enhance analysis with domain-specific insights
            enhanced_response = self._enhance_medical_analysis(response, patient_context)
            
            logger.info(f"Sentiment analyzed for patient {patient_context.patient_id}: {response.sentiment}")
            return enhanced_response, concern_level
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed for patient {patient_context.patient_id}: {e}")
            raise ExternalServiceError(f"Failed to analyze sentiment: {str(e)}")
    
    def _determine_concern_level(
        self,
        analysis: SentimentAnalysisResponse,
        context: PatientContext
    ) -> ConcernLevel:
        """
        Determine medical concern level based on sentiment analysis.
        
        Args:
            analysis: Sentiment analysis response
            context: Patient context
            
        Returns:
            Concern level
        """
        # Critical concerns
        critical_indicators = [
            "severe pain", "can't breathe", "chest pain", "suicidal",
            "emergency", "hospital", "severe bleeding"
        ]
        
        # High concern indicators
        high_concern_indicators = [
            "severe", "unbearable", "getting worse", "can't sleep",
            "vomiting", "fever", "dizzy", "confused"
        ]
        
        # Medium concern indicators
        medium_concern_indicators = [
            "headache", "nausea", "tired", "worried", "anxious",
            "side effect", "uncomfortable"
        ]
        
        message_lower = " ".join(analysis.key_phrases + analysis.medical_concerns).lower()
        
        # Check for critical concerns
        if any(indicator in message_lower for indicator in critical_indicators):
            return ConcernLevel.CRITICAL
        
        # Check sentiment and medical concerns
        if analysis.sentiment == SentimentType.CONCERNING:
            if analysis.medical_concerns:
                if any(indicator in message_lower for indicator in high_concern_indicators):
                    return ConcernLevel.HIGH
                elif any(indicator in message_lower for indicator in medium_concern_indicators):
                    return ConcernLevel.MEDIUM
                else:
                    return ConcernLevel.MEDIUM
        
        # Check for negative sentiment with medical concerns
        if analysis.sentiment == SentimentType.NEGATIVE and analysis.medical_concerns:
            return ConcernLevel.MEDIUM
        
        return ConcernLevel.LOW
    
    def _enhance_medical_analysis(
        self,
        analysis: SentimentAnalysisResponse,
        context: PatientContext
    ) -> SentimentAnalysisResponse:
        """
        Enhance analysis with medical domain knowledge.
        
        Args:
            analysis: Base sentiment analysis
            context: Patient context
            
        Returns:
            Enhanced analysis
        """
        # Add treatment-specific concern detection
        treatment_concerns = self._get_treatment_specific_concerns(
            context.treatment_type,
            analysis.key_phrases
        )
        
        if treatment_concerns:
            analysis.medical_concerns.extend(treatment_concerns)
        
        # Add timeline-based insights
        timeline_insights = self._get_timeline_insights(
            context.treatment_day,
            analysis.sentiment
        )
        
        if timeline_insights:
            analysis.key_phrases.extend(timeline_insights)
        
        return analysis
    
    def _get_treatment_specific_concerns(
        self,
        treatment_type: str,
        key_phrases: List[str]
    ) -> List[str]:
        """Get treatment-specific medical concerns."""
        concerns = []
        phrases_text = " ".join(key_phrases).lower()
        
        if "hormone" in treatment_type.lower():
            hormone_concerns = {
                "mood swings": "hormonal mood changes",
                "weight gain": "hormone-related weight changes",
                "hot flashes": "menopausal symptoms",
                "irregular periods": "menstrual irregularities"
            }
            
            for phrase, concern in hormone_concerns.items():
                if phrase in phrases_text:
                    concerns.append(concern)
        
        return concerns
    
    def _get_timeline_insights(
        self,
        treatment_day: int,
        sentiment: SentimentType
    ) -> List[str]:
        """Get timeline-based insights."""
        insights = []
        
        if treatment_day <= 7 and sentiment == SentimentType.NEGATIVE:
            insights.append("early treatment adjustment period")
        elif treatment_day > 30 and sentiment == SentimentType.CONCERNING:
            insights.append("long-term treatment concern")
        
        return insights


class ContextBuilder:
    """
    Patient context compilation service.
    
    Builds comprehensive patient context from various data sources
    for AI processing and personalization.
    """
    
    def __init__(self):
        """Initialize context builder."""
        self.token_limiter = get_token_limiter()
        logger.info("Context Builder initialized with token limiting")
    
    async def build_patient_context(
        self,
        patient_id: str,
        patient_data: Dict[str, Any],
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        medical_data: Optional[Dict[str, Any]] = None
    ) -> PatientContext:
        """
        Build comprehensive patient context for AI operations.
        
        Args:
            patient_id: Patient identifier
            patient_data: Basic patient information
            recent_messages: Recent message history
            medical_data: Medical history and data
            
        Returns:
            Compiled patient context
        """
        try:
            # Extract and limit recent responses to fit token budget
            recent_responses = []
            if recent_messages:
                # Filter inbound messages
                inbound_messages = [
                    msg for msg in recent_messages
                    if msg.get("direction") == "inbound"
                ]

                # Apply token limiting to messages (max 200 tokens for history)
                limited_messages = self.token_limiter.limit_messages_history(
                    inbound_messages,
                    max_tokens=200
                )

                # Extract content from limited messages
                recent_responses = [
                    msg.get("content", "")
                    for msg in limited_messages
                ]

                logger.debug(f"Limited message history from {len(inbound_messages)} to {len(recent_responses)} messages")
            
            # Calculate treatment day
            treatment_day = self._calculate_treatment_day(
                patient_data.get("treatment_start_date"),
                patient_data.get("current_day", 1)
            )
            
            # Build context
            context = PatientContext(
                patient_id=patient_id,
                name=patient_data.get("name", "Patient"),
                treatment_type=patient_data.get("treatment_type", "general"),
                treatment_day=treatment_day,
                age=patient_data.get("age"),
                recent_responses=recent_responses,
                medical_history=medical_data or {},
                preferences=patient_data.get("preferences", {})
            )
            
            logger.info(f"Patient context built for {patient_id}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to build context for patient {patient_id}: {e}")
            raise ExternalServiceError(f"Failed to build patient context: {str(e)}")
    
    def _calculate_treatment_day(
        self,
        start_date: Optional[str],
        current_day: int
    ) -> int:
        """
        Calculate current treatment day.
        
        Args:
            start_date: Treatment start date (ISO format)
            current_day: Current day from patient record
            
        Returns:
            Treatment day number
        """
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                now = datetime.now(start.tzinfo)
                days_diff = (now - start).days + 1
                return max(days_diff, 1)
            except (ValueError, AttributeError):
                pass
        
        return max(current_day, 1)


class NLPUtilities:
    """
    Natural language processing utilities.
    
    Provides helper functions for text processing, keyword extraction,
    and linguistic analysis.
    """
    
    @staticmethod
    def extract_keywords(text: str, min_length: int = 3) -> List[str]:
        """
        Extract keywords from text.
        
        Args:
            text: Input text
            min_length: Minimum keyword length
            
        Returns:
            List of extracted keywords
        """
        # Simple keyword extraction (could be enhanced with NLP libraries)
        import re
        
        # Remove punctuation and convert to lowercase
        clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Split into words and filter
        words = [
            word.strip() for word in clean_text.split()
            if len(word.strip()) >= min_length
        ]
        
        # Remove common stop words
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through',
            'during', 'before', 'after', 'above', 'below', 'between',
            'among', 'this', 'that', 'these', 'those', 'i', 'me', 'my',
            'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your',
            'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
            'himself', 'she', 'her', 'hers', 'herself', 'it', 'its',
            'itself', 'they', 'them', 'their', 'theirs', 'themselves',
            'some', 'any', 'all', 'each', 'every', 'many', 'much',
            'more', 'most', 'other', 'such', 'no', 'nor', 'not',
            'only', 'own', 'same', 'so', 'than', 'too', 'very',
            'can', 'will', 'just', 'should', 'now', 'am', 'is', 'are',
            'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'would', 'could', 'should'
        }
        
        keywords = [word for word in words if word not in stop_words]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for keyword in keywords:
            if keyword not in seen:
                seen.add(keyword)
                unique_keywords.append(keyword)
        
        return unique_keywords
    
    @staticmethod
    def detect_urgency_indicators(text: str) -> List[str]:
        """
        Detect urgency indicators in text.
        
        Args:
            text: Input text
            
        Returns:
            List of detected urgency indicators
        """
        urgency_patterns = [
            r'\b(urgent|emergency|help|asap|immediately|now|critical)\b',
            r'\b(severe|intense|unbearable|extreme)\b',
            r'\b(can\'t|cannot|unable to)\b',
            r'\b(worse|worsening|deteriorating)\b',
            r'\b(pain|hurt|ache|aching)\b.*\b(severe|bad|terrible|awful)\b'
        ]
        
        import re
        indicators = []
        text_lower = text.lower()
        
        for pattern in urgency_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                indicators.extend(matches if isinstance(matches[0], str) else [m[0] for m in matches])
        
        return list(set(indicators))  # Remove duplicates
    
    @staticmethod
    def calculate_readability_score(text: str) -> float:
        """
        Calculate simple readability score.
        
        Args:
            text: Input text
            
        Returns:
            Readability score (0-100, higher is more readable)
        """
        import re
        
        # Count sentences, words, and syllables (simplified)
        sentences = len(re.findall(r'[.!?]+', text))
        words = len(text.split())
        
        if sentences == 0 or words == 0:
            return 0.0
        
        # Simplified syllable counting
        syllables = sum(max(1, len(re.findall(r'[aeiouAEIOU]', word))) for word in text.split())
        
        # Simplified Flesch Reading Ease formula
        if sentences > 0 and words > 0:
            score = 206.835 - (1.015 * (words / sentences)) - (84.6 * (syllables / words))
            return max(0, min(100, score))
        
        return 50.0  # Default middle score


# Global service instances
_ai_humanizer: Optional[AIHumanizer] = None
_sentiment_analyzer: Optional[SentimentAnalyzer] = None
_context_builder: Optional[ContextBuilder] = None


def get_ai_humanizer() -> AIHumanizer:
    """Get global AI humanizer instance."""
    global _ai_humanizer
    
    if _ai_humanizer is None:
        _ai_humanizer = AIHumanizer()
    
    return _ai_humanizer


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get global sentiment analyzer instance."""
    global _sentiment_analyzer
    
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    
    return _sentiment_analyzer


def get_context_builder() -> ContextBuilder:
    """Get global context builder instance."""
    global _context_builder
    
    if _context_builder is None:
        _context_builder = ContextBuilder()
    
    return _context_builder