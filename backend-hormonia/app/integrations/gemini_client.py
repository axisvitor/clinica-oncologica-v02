"""
Google Gemini 2.5 Flash integration for healthcare messaging and conversation flows.
Provides AI-powered message humanization, personalization, and conversation management.

REFACTORED TO USE LANGCHAIN-GOOGLE-GENAI (Option A - LangChain-only)

Security Fixes:
- Thread-safe singleton with asyncio.Lock
- Async Redis to prevent event loop blocking
- Connection pooling for Redis
"""

# Standard library imports
import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

# Third-party imports
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Local application imports
from app.config import settings
from app.core.redis_unified import get_async_redis
from app.services.circuit_breaker import get_ai_circuit_breaker
from app.utils.rate_limiter import check_ai_rate_limit, AIRateLimitExceeded

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Custom exception for Gemini API errors."""

    pass


class GeminiClient:
    """
    Google Gemini 2.5 Flash client optimized for healthcare messaging.
    Handles message humanization, personalization, and conversation flows.

    REFACTORED: Now uses ChatGoogleGenerativeAI from langchain-google-genai
    instead of google.generativeai SDK to avoid dependency conflicts.

    ADDED: Semantic Caching with Redis.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Gemini client with healthcare-optimized configuration.

        Args:
            api_key: Google AI API key (defaults to settings)
            model: Gemini model name (defaults to settings)
        """
        self.api_key = api_key or settings.AI_GEMINI_API_KEY
        self.model_name = model or settings.AI_GEMINI_MODEL
        # FIX: Use lazy async Redis initialization to prevent event loop blocking
        self._redis_client = None
        self._redis_initialized = False
        self._model_loop_id: Optional[int] = None
        # Circuit breaker for AI service protection
        self._circuit_breaker = get_ai_circuit_breaker()

        if not self.api_key:
            logger.warning(
                "Gemini API key not provided. Client will not be functional."
            )
            self.model = None
            return

        # Initialize LangChain ChatGoogleGenerativeAI model
        self._initialize_model()

    @staticmethod
    def _current_loop_id() -> Optional[int]:
        try:
            return id(asyncio.get_running_loop())
        except RuntimeError:
            return None

    def _initialize_model(self, *, reason: str = "initial") -> None:
        """Initialize or reinitialize the Gemini model for the current event loop."""
        if not self.api_key:
            self.model = None
            self._model_loop_id = None
            return

        try:
            self.model = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=settings.AI_GEMINI_TEMPERATURE,
                max_output_tokens=settings.AI_GEMINI_MAX_OUTPUT_TOKENS,
                top_p=settings.AI_GEMINI_TOP_P,
                top_k=settings.AI_GEMINI_TOP_K,
            )
            self._model_loop_id = self._current_loop_id()
            logger.info(
                "Gemini client initialized with model: %s",
                self.model_name,
                extra={"model": self.model_name, "reason": reason},
            )
        except Exception as e:
            logger.error(
                "Failed to initialize ChatGoogleGenerativeAI: %s",
                str(e),
                exc_info=True,
                extra={"model": self.model_name, "reason": reason},
            )
            self.model = None
            raise GeminiAPIError(f"Failed to initialize Gemini client: {str(e)}")

    def _ensure_model_for_loop(self) -> None:
        """Ensure model is bound to the current event loop."""
        current_loop_id = self._current_loop_id()
        if self.model is None:
            self._initialize_model(reason="missing_model")
            return

        if current_loop_id is not None and current_loop_id != self._model_loop_id:
            logger.info(
                "Reinitializing Gemini model for new event loop",
                extra={
                    "previous_loop_id": self._model_loop_id,
                    "current_loop_id": current_loop_id,
                },
            )
            self._initialize_model(reason="loop_changed")

    def _generate_cache_key(self, prompt: str) -> str:
        """Generate a deterministic cache key for the prompt."""
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return f"gemini_cache:{prompt_hash}"

    async def _get_redis_client(self):
        """
        Get async Redis client with lazy initialization.

        FIX: Uses async Redis to prevent blocking the event loop.
        """
        if not self._redis_initialized:
            try:
                self._redis_client = await get_async_redis()
                self._redis_initialized = True
            except Exception as e:
                logger.warning(
                    "Failed to initialize async Redis: %s",
                    str(e),
                    extra={"operation": "redis_init"}
                )
                self._redis_client = None
                self._redis_initialized = True
        return self._redis_client

    async def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """Retrieve cached response if available (async)."""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return None

            # FIX: Use async Redis get
            cached_value = await redis_client.get(cache_key)
            if cached_value:
                logger.debug("Gemini cache hit for key: %s", cache_key)
                # Handle both string and bytes responses
                if isinstance(cached_value, bytes):
                    return cached_value.decode("utf-8")
                return cached_value
        except Exception as e:
            logger.warning(
                "Cache retrieval failed: %s",
                str(e),
                extra={"cache_key": cache_key}
            )
        return None

    async def _cache_response(
        self, cache_key: str, response: str, ttl: int = 3600
    ) -> None:
        """Cache the response in Redis (async)."""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return

            # FIX: Use async Redis setex
            await redis_client.setex(cache_key, ttl, response)
            logger.debug("Cached Gemini response for key: %s", cache_key)
        except Exception as e:
            logger.warning(
                "Failed to cache response: %s",
                str(e),
                extra={"cache_key": cache_key, "ttl": ttl}
            )

    async def _generate_content_internal(self, prompt: str, **kwargs) -> str:
        """
        Internal method to generate content using Gemini.

        This method is wrapped by generate_content with circuit breaker protection.

        Args:
            prompt: The input prompt for generation
            **kwargs: Additional generation parameters

        Returns:
            Generated text content

        Raises:
            GeminiAPIError: If generation fails after retries
        """
        self._ensure_model_for_loop()

        if not self.api_key or not self.model:
            raise GeminiAPIError(
                "Gemini client not properly initialized - missing API key"
            )

        # Rate limiting check (default: 60 RPM)
        rate_limit_rpm = getattr(settings, "AI_GEMINI_RATE_LIMIT_RPM", 60)
        allowed, retry_after = await check_ai_rate_limit(
            service_name="gemini",
            max_requests=rate_limit_rpm,
            window_seconds=60,
        )
        if not allowed:
            logger.warning(
                "Gemini rate limit exceeded",
                extra={"retry_after": retry_after, "rate_limit_rpm": rate_limit_rpm},
            )
            raise AIRateLimitExceeded(retry_after=retry_after, service="gemini")

        max_retries = kwargs.get("max_retries", settings.AI_GEMINI_MAX_RETRIES)
        retry_delay = kwargs.get("retry_delay", 1)

        for attempt in range(max_retries):
            try:
                # Use LangChain's ainvoke method for async generation
                messages = [HumanMessage(content=prompt)]

                # Run with timeout
                response = await asyncio.wait_for(
                    self.model.ainvoke(messages),
                    timeout=settings.AI_GEMINI_TIMEOUT_SECONDS,
                )

                # Extract text from LangChain response
                response_text = (
                    response.content.strip()
                    if hasattr(response, "content")
                    else str(response).strip()
                )

                if not response_text:
                    raise GeminiAPIError("Empty response from Gemini API via LangChain")

                logger.debug("Gemini generation successful on attempt %d", attempt + 1)

                return response_text

            except Exception as e:
                logger.warning(
                    "Gemini API attempt %d failed: %s",
                    attempt + 1,
                    str(e),
                    extra={"attempt": attempt + 1, "max_retries": max_retries}
                )

                if attempt == max_retries - 1:
                    raise GeminiAPIError(
                        f"Failed to generate content after {max_retries} attempts: {e}"
                    )

                # Exponential backoff
                await asyncio.sleep(retry_delay * (2**attempt))

        raise GeminiAPIError("Unexpected error in content generation")

    async def generate_content(self, prompt: str, **kwargs) -> str:
        """
        Generate content using Gemini with circuit breaker protection, error handling, retries, and caching.

        Args:
            prompt: The input prompt for generation
            **kwargs: Additional generation parameters

        Returns:
            Generated text content

        Raises:
            GeminiAPIError: If generation fails after retries
        """
        # Check Cache first
        cache_key = self._generate_cache_key(prompt)
        cached_response = await self._get_cached_response(cache_key)
        if cached_response:
            return cached_response

        # Fallback response for when circuit is open
        fallback_response = kwargs.pop(
            "fallback_response",
            "Desculpe, estou temporariamente indisponível. Por favor, tente novamente em alguns instantes."
        )

        # Call through circuit breaker
        try:
            response_text, used_fallback = await self._circuit_breaker.call_gemini(
                self._generate_content_internal,
                prompt,
                fallback_response=fallback_response,
                **kwargs
            )

            # Cache only successful (non-fallback) responses
            if not used_fallback:
                await self._cache_response(cache_key, response_text)

            return response_text

        except Exception as e:
            logger.error(
                "Gemini content generation failed: %s",
                str(e),
                exc_info=True,
                extra={"prompt_length": len(prompt), "circuit_breaker": "active"},
            )
            # If circuit breaker fallback fails, return fallback response
            return fallback_response

    async def humanize_flow_message(
        self,
        template: str,
        patient_name: str,
        patient_context: Dict[str, Any],
        conversation_history: List[str],
        personalization_hints: List[str],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Transform template message into natural, human-like conversation.

        Args:
            template: Base message template
            patient_name: Patient's name for personalization
            patient_context: Patient context and preferences
            conversation_history: Recent conversation messages
            personalization_hints: Hints for personalization approach
            few_shot_examples: Optional list of example inputs and outputs for few-shot prompting.

        Returns:
            Humanized message text
        """
        prompt = self._build_humanization_prompt(
            template,
            patient_name,
            patient_context,
            conversation_history,
            personalization_hints,
            few_shot_examples,
        )

        try:
            humanized = await self.generate_content(prompt)
            logger.info(
                "Message humanized successfully",
                extra={
                    "operation": "humanize",
                    "patient": patient_name,
                    "template_length": len(template)
                }
            )
            return humanized
        except Exception as e:
            logger.error(
                "Failed to humanize message: %s",
                str(e),
                exc_info=True,
                extra={"patient": patient_name}
            )
            # Fallback to template with basic personalization
            return template.replace("[nome]", patient_name).replace(
                "[NOME]", patient_name
            )

    async def generate_varied_question(
        self,
        base_question: str,
        previous_questions: List[str],
        patient_context: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Generate question variation to avoid repetition.

        Args:
            base_question: Original question template
            previous_questions: Recently asked questions
            patient_context: Patient context for personalization
            few_shot_examples: Optional list of example inputs and outputs for few-shot prompting.

        Returns:
            Varied question text
        """
        prompt = self._build_question_variation_prompt(
            base_question, previous_questions, patient_context, few_shot_examples
        )

        try:
            varied_question = await self.generate_content(prompt)
            logger.info(
                "Question variation generated",
                extra={"operation": "question_variation"}
            )
            return varied_question
        except Exception as e:
            logger.error(
                "Failed to generate question variation: %s",
                str(e),
                exc_info=True
            )
            return base_question

    async def analyze_response_sentiment(
        self, response: str, patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze patient response sentiment and extract insights.

        Args:
            response: Patient's response text
            patient_context: Patient context for analysis

        Returns:
            Sentiment analysis results
        """
        prompt = self._build_sentiment_analysis_prompt(response, patient_context)

        try:
            analysis_text = await self.generate_content(prompt)
            # Parse structured response
            analysis = self._parse_sentiment_analysis(analysis_text)
            logger.info(
                "Sentiment analysis completed",
                extra={"operation": "sentiment"}
            )
            return analysis
        except Exception as e:
            logger.error(
                "Failed to analyze sentiment: %s",
                str(e),
                exc_info=True
            )
            return {
                "sentiment": "neutral",
                "confidence": 0.5,
                "emotional_indicators": [],
                "medical_concerns": False,
                "requires_attention": False,
            }

    async def create_empathetic_follow_up(
        self,
        patient_response: str,
        conversation_history: List[str],
        patient_context: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Create empathetic follow-up message based on patient response.

        Args:
            patient_response: Patient's latest response
            conversation_history: Recent conversation messages
            patient_context: Patient context and preferences
            few_shot_examples: Optional list of example inputs and outputs for few-shot prompting.

        Returns:
            Empathetic follow-up message
        """
        prompt = self._build_empathetic_response_prompt(
            patient_response, conversation_history, patient_context, few_shot_examples
        )

        try:
            follow_up = await self.generate_content(prompt)
            logger.info(
                "Empathetic follow-up generated",
                extra={"operation": "follow_up"}
            )
            return follow_up
        except Exception as e:
            logger.error(
                "Failed to generate empathetic follow-up: %s",
                str(e),
                exc_info=True
            )
            return "Obrigada por compartilhar isso comigo. Como posso te ajudar melhor?"

    def _format_few_shot_examples(
        self, examples: Optional[List[Dict[str, str]]]
    ) -> str:
        """Format few-shot examples for inclusion in prompt."""
        if not examples:
            return ""

        formatted = "\nEXEMPLOS DE REFERÊNCIA:\n"
        for ex in examples:
            formatted += (
                f"Entrada: {ex.get('input', '')}\nSaída: {ex.get('output', '')}\n---\n"
            )
        return formatted

    def _build_humanization_prompt(
        self,
        template: str,
        patient_name: str,
        patient_context: Dict[str, Any],
        conversation_history: List[str],
        personalization_hints: List[str],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Build prompt for message humanization."""
        examples_section = self._format_few_shot_examples(few_shot_examples)
        return f"""
Você é uma assistente de saúde especializada em comunicação empática e humanizada.
Sua missão é transformar mensagens médicas em conversas naturais e acolhedoras.

CONTEXTO DO PACIENTE:
- Nome: {patient_name}
- Contexto: {json.dumps(patient_context, ensure_ascii=False)}
- Dicas de personalização: {", ".join(personalization_hints)}

CONVERSAS RECENTES:
{chr(10).join(conversation_history[-5:]) if conversation_history else "Nenhuma conversa anterior"}

MENSAGEM ORIGINAL: {template}

{examples_section}

DIRETRIZES:
1. Use linguagem natural e acolhedora, como uma conversa entre amigos
2. Evite repetir frases ou estruturas já usadas nas conversas recentes
3. Adapte o tom baseado no contexto do paciente
4. Inclua elementos que demonstrem que você "lembra" das conversas anteriores
5. Mantenha a precisão médica, mas torne a linguagem mais acessível
6. Use emojis moderadamente para criar proximidade (se apropriado)
7. Mantenha o foco na saúde hormonal e bem-estar

MENSAGEM HUMANIZADA:
"""

    def _build_question_variation_prompt(
        self,
        base_question: str,
        previous_questions: List[str],
        patient_context: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Build prompt for question variation."""
        examples_section = self._format_few_shot_examples(few_shot_examples)
        return f"""
Você precisa fazer uma pergunta sobre saúde, mas de forma que não pareça repetitiva.

PERGUNTA BASE: {base_question}
PERGUNTAS JÁ FEITAS: {chr(10).join(previous_questions[-5:]) if previous_questions else "Nenhuma pergunta anterior"}
CONTEXTO DO PACIENTE: {json.dumps(patient_context, ensure_ascii=False)}

{examples_section}

Crie uma versão completamente diferente da pergunta que:
1. Tenha o mesmo objetivo médico
2. Use palavras e estrutura totalmente diferentes
3. Seja mais conversacional e natural
4. Demonstre interesse genuíno no bem-estar do paciente
5. Evite soar como questionário médico
6. Mantenha o foco na saúde hormonal

NOVA PERGUNTA:
"""

    def _build_sentiment_analysis_prompt(
        self, response: str, patient_context: Dict[str, Any]
    ) -> str:
        """Build prompt for sentiment analysis."""
        return f"""
Analise a resposta de um paciente de terapia hormonal e forneça insights estruturados.

RESPOSTA DO PACIENTE: {response}
CONTEXTO: {json.dumps(patient_context, ensure_ascii=False)}

Forneça uma análise no seguinte formato JSON:
{{
    "sentiment": "positive|neutral|negative",
    "confidence": 0.0-1.0,
    "emotional_indicators": ["lista", "de", "indicadores"],
    "medical_concerns": true|false,
    "requires_attention": true|false,
    "key_themes": ["temas", "identificados"],
    "suggested_follow_up": "tipo de seguimento recomendado"
}}

ANÁLISE:
"""

    def _build_empathetic_response_prompt(
        self,
        patient_response: str,
        conversation_history: List[str],
        patient_context: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Build prompt for empathetic response."""
        examples_section = self._format_few_shot_examples(few_shot_examples)
        return f"""
Um paciente de terapia hormonal acabou de responder algo. Você precisa criar uma resposta empática e de apoio.

RESPOSTA DO PACIENTE: {patient_response}
HISTÓRICO DA CONVERSA: {chr(10).join(conversation_history[-3:]) if conversation_history else "Primeira interação"}
CONTEXTO: {json.dumps(patient_context, ensure_ascii=False)}

{examples_section}

Crie uma resposta que:
1. Reconheça e valide os sentimentos do paciente
2. Demonstre que você realmente "ouviu" o que foi dito
3. Ofereça apoio sem minimizar preocupações
4. Seja genuinamente humana, não robótica
5. Mantenha o foco no bem-estar do paciente
6. Use linguagem que transmita cuidado e compreensão
7. Seja específica para terapia hormonal quando relevante

RESPOSTA EMPÁTICA:
"""

    def _parse_sentiment_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse sentiment analysis response into structured data with Pydantic validation."""
        import re
        from json import JSONDecodeError
        from app.schemas.ai_schemas import AIResponseValidation

        parsed_data: Dict[str, Any] = {}

        # Try to extract JSON from the response
        json_match = re.search(r"\{.*\}", analysis_text, re.DOTALL)
        if json_match:
            try:
                parsed_data = json.loads(json_match.group())
            except JSONDecodeError as e:
                logger.warning(
                    "JSON decode error in sentiment analysis: %s at position %d",
                    str(e),
                    e.pos,
                    extra={"operation": "parse_sentiment", "raw_length": len(analysis_text)},
                )
            except ValueError as e:
                logger.warning(
                    "Value error parsing sentiment JSON: %s",
                    str(e),
                    extra={"operation": "parse_sentiment"},
                )

        # Validate with Pydantic (handles missing fields and type coercion)
        if parsed_data:
            validated = AIResponseValidation.validate_sentiment(parsed_data)
            return validated.model_dump()

        # Fallback to basic keyword analysis
        sentiment = "neutral"
        if any(
            word in analysis_text.lower()
            for word in ["positiv", "bem", "melhor", "ótim"]
        ):
            sentiment = "positive"
        elif any(
            word in analysis_text.lower()
            for word in ["negativ", "preocup", "problem", "dor", "mal"]
        ):
            sentiment = "negative"

        return {
            "sentiment": sentiment,
            "confidence": 0.6,
            "emotional_indicators": [],
            "medical_concerns": "preocup" in analysis_text.lower()
            or "dor" in analysis_text.lower(),
            "requires_attention": "atenção" in analysis_text.lower()
            or "urgente" in analysis_text.lower(),
            "key_themes": [],
            "suggested_follow_up": "standard",
        }

    async def health_check(self) -> bool:
        """
        Check if Gemini API is accessible and working.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key or not self.model:
            logger.warning("Gemini client not initialized - no API key")
            return False

        try:
            test_prompt = "Responda apenas 'OK' se você está funcionando corretamente."
            response = await self.generate_content(test_prompt, max_retries=1)
            if "OK" not in response.upper():
                logger.warning(
                    "Gemini health check returned unexpected response",
                    extra={"operation": "health_check"},
                )
                return False
            return True
        except Exception as e:
            logger.error(
                "Gemini health check failed: %s",
                str(e),
                exc_info=True,
                extra={"operation": "health_check"},
            )
            return False


# Global Gemini client instance with thread-safe initialization
_gemini_client: Optional[GeminiClient] = None
_gemini_client_lock = asyncio.Lock()


def get_gemini_client() -> GeminiClient:
    """
    Get global Gemini client instance (sync version for backward compatibility).

    Returns:
        Initialized GeminiClient instance

    Note: For async contexts, prefer get_gemini_client_async() for thread safety.
    """
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


async def get_gemini_client_async() -> GeminiClient:
    """
    Get global Gemini client instance (thread-safe async version).

    FIX: Uses asyncio.Lock to prevent race conditions during concurrent initialization.

    Returns:
        Initialized GeminiClient instance
    """
    global _gemini_client

    # Fast path - already initialized
    if _gemini_client is not None:
        return _gemini_client

    # Thread-safe initialization
    async with _gemini_client_lock:
        # Double-check after acquiring lock
        if _gemini_client is None:
            _gemini_client = GeminiClient()

    return _gemini_client


async def reset_gemini_client():
    """Reset singleton instance (for testing)."""
    global _gemini_client
    async with _gemini_client_lock:
        _gemini_client = None


async def test_gemini_integration():
    """Test Gemini integration with a simple healthcare message."""
    try:
        client = get_gemini_client()

        # Test basic functionality
        test_template = "Olá [nome], como você está se sentindo hoje?"
        humanized = await client.humanize_flow_message(
            template=test_template,
            patient_name="Maria",
            patient_context={"treatment_day": 5, "mood": "positive"},
            conversation_history=["Oi Maria!", "Tudo bem por aí?"],
            personalization_hints=["casual", "supportive"],
        )

        logger.info(
            "Gemini test successful",
            extra={"operation": "integration_test", "result": "success"}
        )
        return True

    except Exception as e:
        logger.error(
            "Gemini integration test failed: %s",
            str(e),
            exc_info=True,
            extra={"operation": "integration_test"}
        )
        return False
