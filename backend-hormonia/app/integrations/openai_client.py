"""
Google Gemini and LangChain integration for AI-powered message personalization.
Handles message humanization, sentiment analysis, and AI orchestration.
"""
import logging
from typing import Dict, List, Optional, Any
from enum import Enum

# Removed OpenAI import - using Google Gemini instead
from langchain_google_genai import ChatGoogleGenerativeAI
# Updated imports for langchain-core (NumPy 2.x compatible)
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.config import settings
from app.exceptions import ExternalServiceError
from app.utils.timeout import with_timeout


logger = logging.getLogger(__name__)


class SentimentType(str, Enum):
    """Sentiment analysis results."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    CONCERNING = "concerning"  # Medical concern detected


class MessagePersonalizationRequest(BaseModel):
    """Request for message personalization."""
    template_message: str = Field(..., description="Template message to humanize")
    patient_name: str = Field(..., description="Patient's name")
    patient_context: Dict[str, Any] = Field(default_factory=dict, description="Patient context data")
    treatment_day: int = Field(..., description="Current treatment day")
    previous_responses: List[str] = Field(default_factory=list, description="Recent patient responses")


class SentimentAnalysisRequest(BaseModel):
    """Request for sentiment analysis."""
    message: str = Field(..., description="Message to analyze")
    patient_context: Dict[str, Any] = Field(default_factory=dict, description="Patient context")


class PersonalizationResponse(BaseModel):
    """Response from message personalization."""
    humanized_message: str = Field(..., description="Personalized message")
    confidence_score: float = Field(..., description="AI confidence score (0-1)")
    personalization_notes: List[str] = Field(default_factory=list, description="Applied personalizations")


class SentimentAnalysisResponse(BaseModel):
    """Response from sentiment analysis."""
    sentiment: SentimentType = Field(..., description="Detected sentiment")
    confidence_score: float = Field(..., description="Confidence score (0-1)")
    key_phrases: List[str] = Field(default_factory=list, description="Important phrases detected")
    medical_concerns: List[str] = Field(default_factory=list, description="Medical concerns if any")


class OpenAIClientError(ExternalServiceError):
    """Google Gemini/LangChain specific error."""
    pass


class LangChainOrchestrator:
    """
    LangChain orchestrator for AI operations.
    
    Manages Google Gemini integration, prompt templates, and AI-powered features
    for message personalization and sentiment analysis.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ):
        """
        Initialize LangChain orchestrator.

        Args:
            api_key: Google Gemini API key (defaults to settings.GEMINI_API_KEY)
            model_name: Google Gemini model to use (defaults to settings.GEMINI_MODEL)
            temperature: Creativity level (0-1)
            max_tokens: Maximum response tokens

        Raises:
            OpenAIClientError: If API key is missing or invalid
        """
        self.api_key = api_key or settings.GEMINI_API_KEY

        # Validate API key
        if not self.api_key:
            raise OpenAIClientError("Gemini API key is required but not provided")

        # Use settings.GEMINI_MODEL as default instead of gpt-3.5-turbo (fixes provider mismatch)
        self.model_name = model_name or settings.GEMINI_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        try:
            # Initialize Google Gemini chat model
            self.chat_model = ChatGoogleGenerativeAI(
                model=self.model_name,  # FIX: Use self.model_name instead of model_name parameter
                google_api_key=self.api_key,
                temperature=temperature,
                max_output_tokens=max_tokens
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatGoogleGenerativeAI: {e}")
            raise OpenAIClientError(f"Failed to initialize Gemini client: {str(e)}")
        
        # Initialize prompt templates
        self._setup_prompt_templates()
        
        logger.info(f"LangChain orchestrator initialized with model: {model_name}")
    
    def _setup_prompt_templates(self):
        """Setup prompt templates for different AI operations."""
        
        # Message humanization template
        self.humanization_template = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
            You are a compassionate healthcare assistant helping hormone therapy patients.
            Your role is to personalize template messages to make them more human, empathetic, and engaging.
            
            Guidelines:
            - Maintain medical accuracy and professionalism
            - Use warm, supportive language
            - Personalize based on patient context and treatment progress
            - Keep the core message intent intact
            - Adapt tone based on treatment day and patient responses
            - Use the patient's name naturally in the message
            """),
            HumanMessage(content="""
            Please humanize this template message for a hormone therapy patient:
            
            Template: {template_message}
            Patient Name: {patient_name}
            Treatment Day: {treatment_day}
            Patient Context: {patient_context}
            Recent Responses: {previous_responses}
            
            Return a personalized, empathetic message that maintains the original intent.
            """)
        ])
        
        # Sentiment analysis template
        self.sentiment_template = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
            You are a medical AI assistant analyzing patient messages for sentiment and medical concerns.
            
            Analyze the message for:
            1. Overall sentiment (positive, negative, neutral, concerning)
            2. Medical concerns or symptoms that need attention
            3. Key phrases that indicate patient state
            4. Confidence in your analysis
            
            Focus on identifying:
            - Side effects or adverse reactions
            - Emotional distress or mental health concerns
            - Treatment compliance issues
            - Questions or confusion about treatment
            - Positive progress indicators
            """),
            HumanMessage(content="""
            Analyze this patient message:
            
            Message: {message}
            Patient Context: {patient_context}
            
            Provide analysis in this format:
            Sentiment: [positive/negative/neutral/concerning]
            Confidence: [0.0-1.0]
            Key Phrases: [list of important phrases]
            Medical Concerns: [list any medical concerns or empty list]
            """)
        ])
    
    @with_timeout(timeout_seconds=30)
    async def humanize_message(self, request: MessagePersonalizationRequest) -> PersonalizationResponse:
        """
        Humanize a template message for a specific patient.
        
        Args:
            request: Personalization request with template and context
            
        Returns:
            Personalized message response
            
        Raises:
            OpenAIClientError: On AI service failures
        """
        try:
            # Format the prompt
            messages = self.humanization_template.format_messages(
                template_message=request.template_message,
                patient_name=request.patient_name,
                treatment_day=request.treatment_day,
                patient_context=str(request.patient_context),
                previous_responses=", ".join(request.previous_responses[-3:])  # Last 3 responses
            )
            
            # Get AI response
            response = await self.chat_model.agenerate([messages])
            humanized_message = response.generations[0][0].text.strip()
            
            # Extract personalization notes (simplified for now)
            personalization_notes = [
                f"Personalized for {request.patient_name}",
                f"Adapted for treatment day {request.treatment_day}"
            ]
            
            if request.previous_responses:
                personalization_notes.append("Considered recent patient responses")
            
            return PersonalizationResponse(
                humanized_message=humanized_message,
                confidence_score=0.85,  # Would be calculated based on model confidence
                personalization_notes=personalization_notes
            )
            
        except Exception as e:
            logger.error(f"Message humanization failed: {e}")
            raise OpenAIClientError(f"Failed to humanize message: {str(e)}")
    
    @with_timeout(timeout_seconds=30)
    async def analyze_sentiment(self, request: SentimentAnalysisRequest) -> SentimentAnalysisResponse:
        """
        Analyze sentiment and medical concerns in patient message.
        
        Args:
            request: Sentiment analysis request
            
        Returns:
            Sentiment analysis response
            
        Raises:
            OpenAIClientError: On AI service failures
        """
        try:
            # Format the prompt
            messages = self.sentiment_template.format_messages(
                message=request.message,
                patient_context=str(request.patient_context)
            )
            
            # Get AI response
            response = await self.chat_model.agenerate([messages])
            analysis_text = response.generations[0][0].text.strip()
            
            # Parse the structured response (simplified parsing)
            lines = analysis_text.split('\n')
            sentiment = SentimentType.NEUTRAL
            confidence = 0.5
            key_phrases = []
            medical_concerns = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('Sentiment:'):
                    sentiment_str = line.split(':', 1)[1].strip().lower()
                    if sentiment_str in [s.value for s in SentimentType]:
                        sentiment = SentimentType(sentiment_str)
                elif line.startswith('Confidence:'):
                    try:
                        confidence = float(line.split(':', 1)[1].strip())
                    except ValueError:
                        pass
                elif line.startswith('Key Phrases:'):
                    phrases_str = line.split(':', 1)[1].strip()
                    if phrases_str and phrases_str != '[]':
                        key_phrases = [p.strip() for p in phrases_str.split(',')]
                elif line.startswith('Medical Concerns:'):
                    concerns_str = line.split(':', 1)[1].strip()
                    if concerns_str and concerns_str != '[]':
                        medical_concerns = [c.strip() for c in concerns_str.split(',')]
            
            return SentimentAnalysisResponse(
                sentiment=sentiment,
                confidence_score=confidence,
                key_phrases=key_phrases,
                medical_concerns=medical_concerns
            )
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            raise OpenAIClientError(f"Failed to analyze sentiment: {str(e)}")
    
    @with_timeout(timeout_seconds=30)
    async def generate_text(self, prompt: str) -> str:
        """
        Generate text from a simple prompt (compatibility method for DataExtractionService).

        This method provides a simple text generation interface compatible with
        the DataExtractionService which expects a generate_text(prompt) method.

        Args:
            prompt: The text prompt to generate from

        Returns:
            Generated text response

        Raises:
            OpenAIClientError: If generation fails
        """
        try:
            messages = [HumanMessage(content=prompt)]
            response = await self.chat_model.agenerate([messages])
            return response.generations[0][0].text.strip()
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            raise OpenAIClientError(f"Failed to generate text: {str(e)}")

    @with_timeout(timeout_seconds=30)
    async def generate_contextual_response(
        self,
        patient_message: str,
        patient_context: Dict[str, Any],
        conversation_history: List[str]
    ) -> str:
        """
        Generate contextual response to patient message.

        Args:
            patient_message: Patient's message
            patient_context: Patient context data
            conversation_history: Recent conversation history

        Returns:
            Generated response message
        """
        try:
            context_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""
                You are a healthcare assistant responding to a hormone therapy patient.
                Provide helpful, empathetic responses while maintaining professional boundaries.

                Guidelines:
                - Be supportive and understanding
                - Provide general guidance but avoid specific medical advice
                - Encourage patients to contact their healthcare provider for medical concerns
                - Keep responses concise and actionable
                """),
                HumanMessage(content="""
                Patient Message: {patient_message}
                Patient Context: {patient_context}
                Recent Conversation: {conversation_history}

                Provide an appropriate response.
                """)
            ])

            messages = context_prompt.format_messages(
                patient_message=patient_message,
                patient_context=str(patient_context),
                conversation_history=", ".join(conversation_history[-5:])
            )

            response = await self.chat_model.agenerate([messages])
            return response.generations[0][0].text.strip()

        except Exception as e:
            logger.error(f"Contextual response generation failed: {e}")
            raise OpenAIClientError(f"Failed to generate response: {str(e)}")
    
    @with_timeout(timeout_seconds=10)
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on AI services.
        
        Returns:
            Health status information
            
        Raises:
            OpenAIClientError: If health check fails
        """
        try:
            # Simple test prompt
            test_messages = [
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(content="Say 'OK' if you can respond.")
            ]
            
            response = await self.chat_model.agenerate([test_messages])
            response_text = response.generations[0][0].text.strip()
            
            return {
                "status": "healthy",
                "model": self.model_name,
                "api_key_configured": bool(self.api_key),
                "test_response": response_text,
                "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp
            }
            
        except Exception as e:
            logger.error(f"AI service health check failed: {e}")
            return {
                "status": "unhealthy",
                "model": self.model_name,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp
            }


class PromptManager:
    """
    Manages prompt templates and AI prompt engineering.
    
    Centralizes prompt templates for different AI operations and provides
    utilities for prompt optimization and management.
    """
    
    def __init__(self):
        """Initialize prompt manager."""
        self.templates = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Load default prompt templates."""
        
        # Message humanization prompts
        self.templates["humanize_welcome"] = PromptTemplate(
            input_variables=["patient_name", "treatment_type"],
            template="""
            Create a warm welcome message for {patient_name} starting {treatment_type} therapy.
            Make it personal, encouraging, and informative about what to expect.
            """
        )
        
        self.templates["humanize_check_in"] = PromptTemplate(
            input_variables=["patient_name", "treatment_day", "last_response"],
            template="""
            Create a check-in message for {patient_name} on day {treatment_day} of treatment.
            Reference their last response: "{last_response}"
            Be supportive and ask about their current experience.
            """
        )
        
        # Sentiment analysis prompts
        self.templates["analyze_side_effects"] = PromptTemplate(
            input_variables=["message", "known_side_effects"],
            template="""
            Analyze this patient message for potential side effects: "{message}"
            Known side effects for this treatment: {known_side_effects}
            Identify any mentioned symptoms and their severity.
            """
        )
    
    def get_template(self, template_name: str) -> Optional[PromptTemplate]:
        """Get prompt template by name."""
        return self.templates.get(template_name)
    
    def add_template(self, name: str, template: PromptTemplate):
        """Add new prompt template."""
        self.templates[name] = template
    
    def list_templates(self) -> List[str]:
        """List available template names."""
        return list(self.templates.keys())


# Global instances
_langchain_orchestrator: Optional[LangChainOrchestrator] = None
_prompt_manager: Optional[PromptManager] = None


def get_langchain_orchestrator() -> LangChainOrchestrator:
    """Get global LangChain orchestrator instance."""
    global _langchain_orchestrator
    
    if _langchain_orchestrator is None:
        _langchain_orchestrator = LangChainOrchestrator()
    
    return _langchain_orchestrator


def get_prompt_manager() -> PromptManager:
    """Get global prompt manager instance."""
    global _prompt_manager
    
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    
    return _prompt_manager


# Backward compatibility shim for tests that patch get_openai_client
def get_openai_client() -> LangChainOrchestrator:  # pragma: no cover
    """Alias to return the Gemini-based orchestrator for backward compatibility."""
    return get_langchain_orchestrator()
