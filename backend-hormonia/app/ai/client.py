"""
Google Gemini 2.5 Flash integration for healthcare messaging and conversation flows.
Provides AI-powered message humanization, personalization, and conversation management.

Uses google-genai SDK directly

Security Fixes:
- Thread-safe singleton with asyncio.Lock
- Async Redis to prevent event loop blocking
- Connection pooling for Redis
"""

# Standard library imports
import asyncio
import math
import hashlib
import logging
import threading
import time
from collections import deque
from typing import Any, Dict, Optional

# Third-party imports
from google import genai
from google.genai import types

# Local application imports
from app.config import settings
from app.core.exceptions import FeatureNotAvailableError
from app.core.redis_manager import get_async_redis_client as get_async_redis
from app.ai.pii_redaction import sanitize_prompt_text_for_external_ai
from app.resilience.circuit_breaker import get_ai_circuit_breaker
from app.services.ai.guardrails import (
    GuardrailViolation,
    OutputKind,
    normalize_ai_output,
    normalize_json_output,
    validate_ai_output,
)
from app.services.ai.output_profiles import resolve_output_profile
from app.utils.rate_limiter import check_ai_rate_limit, AIRateLimitExceeded

# Lazy import for GeminiDomainClient to avoid circular imports
def _create_domain_client(**kwargs):
    from app.ai.client_domain import GeminiDomainClient
    return GeminiDomainClient(**kwargs)

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Custom exception for Gemini API errors."""

    pass


class GeminiClient:
    """
    Google Gemini 3.0 Flash client optimized for healthcare messaging.
    Handles message humanization, personalization, and conversation flows.

    Uses google-genai SDK directly for Gemini calls.

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
        self._genai_client: Optional[genai.Client] = None
        self._genai_config: Optional[types.GenerateContentConfig] = None
        self._fallback_rate_limit_lock = asyncio.Lock()
        self._fallback_rate_limit_events: deque[float] = deque()
        # Circuit breaker for AI service protection
        self._circuit_breaker = get_ai_circuit_breaker()

        if not self.api_key:
            logger.warning(
                "Gemini API key not provided. Client will not be functional."
            )
            self.model = None
            return

        # Initialize google-genai client
        self._initialize_model()

    def _initialize_model(self, *, reason: str = "initial") -> None:
        """Initialize or reinitialize the Gemini model for the current event loop."""
        if not self.api_key:
            self.model = None
            self._genai_client = None
            self._genai_config = None
            return

        try:
            self._genai_client = genai.Client(api_key=self.api_key)
            self._genai_config = types.GenerateContentConfig(
                temperature=settings.AI_GEMINI_TEMPERATURE,
                max_output_tokens=settings.AI_GEMINI_MAX_OUTPUT_TOKENS,
                top_p=settings.AI_GEMINI_TOP_P,
                top_k=settings.AI_GEMINI_TOP_K,
            )
            self.model = self._genai_client
            logger.info(
                "Gemini client initialized with model: %s",
                self.model_name,
                extra={"model": self.model_name, "reason": reason},
            )
        except Exception as e:
            logger.error(
                "Failed to initialize google-genai Client: %s",
                str(e),
                exc_info=True,
                extra={"model": self.model_name, "reason": reason},
            )
            self.model = None
            self._genai_client = None
            self._genai_config = None
            raise GeminiAPIError(f"Failed to initialize Gemini client: {str(e)}")

    def _generate_cache_key(self, prompt: str, *, profile_hint: str = "raw") -> str:
        """Generate a deterministic cache key for the prompt."""
        cache_seed = f"{profile_hint}:{prompt}"
        prompt_hash = hashlib.sha256(cache_seed.encode("utf-8")).hexdigest()
        return f"gemini_cache:{prompt_hash}"

    async def _get_redis_client(self):
        """
        Get async Redis client with lazy initialization.

        FIX: Uses async Redis to prevent blocking the event loop.
        """
        if not self._redis_initialized:
            try:
                timeout = getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", 2.0)
                self._redis_client = await asyncio.wait_for(
                    get_async_redis(),
                    timeout=timeout,
                )
                self._redis_initialized = True
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out initializing async Redis for Gemini cache",
                    extra={"operation": "redis_init_timeout"},
                )
                self._redis_client = None
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

    def _looks_incomplete(self, text: str) -> bool:
        """Heuristic check for truncated or incomplete outputs."""
        if not text:
            return True
        normalized = text.strip()
        if not normalized:
            return True
        if normalized.endswith("..."):
            return False
        if normalized[-1] in ".!?…":
            return False
        lower = normalized.lower()
        for ending in (" a", " o", " os", " as", " de", " da", " do", " em", " para", " por", " e", " que", " com", " sem"):
            if lower.endswith(ending):
                return True
        return True

    def _augment_incomplete_prompt(self, prompt: str) -> str:
        """Add a clear completion instruction without changing the prompt intent."""
        marker = "ATENÇÃO: A RESPOSTA ANTERIOR SAIU INCOMPLETA"
        if marker in prompt:
            return prompt
        return (
            f"{prompt}\n\n{marker}. Gere novamente a mensagem completa, sem cortar a frase, "
            "mantendo o mesmo proposito."
        )

    @staticmethod
    def _repair_ending_punctuation(text: str) -> str:
        """Append terminal punctuation for message outputs when missing."""
        normalized = (text or "").rstrip()
        if not normalized:
            return normalized
        if normalized[-1] in ".!?…":
            return normalized
        return f"{normalized}."

    def _redact_prompt_for_external_ai(self, prompt: str) -> str:
        """
        Redact patient identifiers from free text prompts before external AI calls.

        This is mandatory and intentionally defensive because prompts may be built
        from mixed template/context sources.
        """
        return sanitize_prompt_text_for_external_ai(prompt)

    def _ensure_fallback_rate_limit_state(self) -> None:
        """Ensure fallback limiter state exists for test-created instances."""
        if not hasattr(self, "_fallback_rate_limit_lock") or self._fallback_rate_limit_lock is None:
            self._fallback_rate_limit_lock = asyncio.Lock()
        if not hasattr(self, "_fallback_rate_limit_events") or self._fallback_rate_limit_events is None:
            self._fallback_rate_limit_events = deque()

    async def _check_in_process_rate_limit(
        self,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Local sliding-window limiter used when distributed limiter is unavailable.

        This avoids fail-open behavior while keeping service available during Redis incidents.
        """
        self._ensure_fallback_rate_limit_state()

        if max_requests < 1:
            return False, max(1, window_seconds)

        now = time.monotonic()
        window_start = now - window_seconds

        async with self._fallback_rate_limit_lock:
            while self._fallback_rate_limit_events and self._fallback_rate_limit_events[0] <= window_start:
                self._fallback_rate_limit_events.popleft()

            if len(self._fallback_rate_limit_events) >= max_requests:
                retry_after = max(
                    1,
                    math.ceil(
                        (self._fallback_rate_limit_events[0] + window_seconds) - now
                    ),
                )
                return False, retry_after

            self._fallback_rate_limit_events.append(now)
            # Keep fallback state bounded for this window.
            while len(self._fallback_rate_limit_events) > max_requests:
                self._fallback_rate_limit_events.popleft()

            return True, 0

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
        prompt = self._redact_prompt_for_external_ai(prompt)

        if (
            not self.api_key
            or not self.model
            or self._genai_client is None
            or self._genai_config is None
        ):
            raise GeminiAPIError(
                "Gemini client not properly initialized - missing API key"
            )

        # Rate limiting check (default: 60 RPM)
        rate_limit_rpm = getattr(settings, "AI_GEMINI_RATE_LIMIT_RPM", 60)
        window_seconds = 60
        try:
            rate_limit_timeout = getattr(settings, "REDIS_OPERATION_TIMEOUT", 5)
            allowed, retry_after = await asyncio.wait_for(
                check_ai_rate_limit(
                    service_name="gemini",
                    max_requests=rate_limit_rpm,
                    window_seconds=window_seconds,
                ),
                timeout=rate_limit_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "AI rate limit check timed out; using in-process fallback",
                extra={"service": "gemini"},
            )
            allowed, retry_after = await self._check_in_process_rate_limit(
                max_requests=rate_limit_rpm,
                window_seconds=window_seconds,
            )
        except Exception as e:
            logger.warning(
                "AI rate limit check failed; using in-process fallback",
                extra={"service": "gemini", "error": str(e)},
            )
            allowed, retry_after = await self._check_in_process_rate_limit(
                max_requests=rate_limit_rpm,
                window_seconds=window_seconds,
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
                # Run with timeout
                response = await asyncio.wait_for(
                    self._genai_client.aio.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=self._genai_config,
                    ),
                    timeout=settings.AI_GEMINI_TIMEOUT_SECONDS,
                )

                response_text = (response.text or "").strip()

                if not response_text:
                    raise GeminiAPIError("Empty response from Gemini API")

                finish_reason = None
                if response.candidates:
                    fr = response.candidates[0].finish_reason
                    finish_reason = fr.name if fr is not None else None

                finish_reason_str = (
                    finish_reason.upper() if finish_reason is not None else None
                )
                output_length = len(response_text)

                logger.info(
                    "Gemini generation completed",
                    extra={
                        "attempt": attempt + 1,
                        "prompt_length": len(prompt),
                        "output_length": output_length,
                        "finish_reason": finish_reason_str,
                        "model": self.model_name,
                    },
                )

                incomplete = False
                if finish_reason_str:
                    incomplete = finish_reason_str not in {
                        "STOP",
                        "FINISH_REASON_UNSPECIFIED",
                    }

                if incomplete:
                    logger.warning(
                        "Gemini response incomplete; retrying",
                        extra={
                            "attempt": attempt + 1,
                            "prompt_length": len(prompt),
                            "output_length": output_length,
                            "finish_reason": finish_reason_str,
                            "model": self.model_name,
                        },
                    )
                    if attempt < max_retries - 1:
                        continue
                    logger.error(
                        "Gemini returned incomplete response after retries",
                        extra={
                            "prompt_length": len(prompt),
                            "output_length": output_length,
                            "finish_reason": finish_reason_str,
                            "model": self.model_name,
                        },
                    )

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
                profile: Optional output profile name/object from output_profiles
                output_kind: Optional OutputKind for guardrail validation
                min_length: Optional minimum length for output
                max_length: Optional maximum length for output
                required_keys: Optional iterable of JSON keys to require

        Returns:
            Generated text content

        Raises:
            GeminiAPIError: If generation fails after retries
        """
        _ = kwargs.pop("strict", False)
        profile = resolve_output_profile(kwargs.pop("profile", None))
        output_kind = kwargs.pop(
            "output_kind",
            profile.output_kind if profile else None,
        )
        if output_kind is not None and not isinstance(output_kind, OutputKind):
            try:
                output_kind = OutputKind(str(output_kind))
            except ValueError as exc:
                raise GeminiAPIError(f"Unsupported output kind: {output_kind}") from exc

        min_length = kwargs.pop("min_length", profile.min_length if profile else 3)
        max_length = kwargs.pop("max_length", profile.max_length if profile else 1600)
        required_keys = kwargs.pop(
            "required_keys",
            profile.required_keys_iterable() if profile else None,
        )
        require_ending_punctuation = kwargs.pop(
            "require_ending_punctuation",
            profile.require_ending_punctuation if profile else False,
        )
        allow_placeholders = kwargs.pop(
            "allow_placeholders",
            profile.allow_placeholders if profile else False,
        )
        guardrail_retries = kwargs.pop(
            "guardrail_retries",
            profile.guardrail_retries if profile else 2,
        )

        if output_kind is None and required_keys:
            output_kind = OutputKind.JSON

        prompt = self._redact_prompt_for_external_ai(prompt)

        # Check Cache first
        profile_hint = profile.name if profile else (output_kind.value if output_kind else "raw")
        cache_key = self._generate_cache_key(prompt, profile_hint=profile_hint)
        cached_response = await self._get_cached_response(cache_key)
        if cached_response is not None:
            if output_kind:
                try:
                    if output_kind == OutputKind.JSON:
                        cleaned = normalize_json_output(cached_response)
                    else:
                        cleaned = normalize_ai_output(cached_response)
                    validate_ai_output(
                        cleaned,
                        output_kind,
                        min_length=min_length,
                        max_length=max_length,
                        required_keys=required_keys,
                        require_ending_punctuation=require_ending_punctuation,
                        allow_placeholders=allow_placeholders,
                    )
                    return cleaned
                except GuardrailViolation:
                    logger.warning(
                        "Cached output failed guardrails; regenerating",
                        extra={"cache_key": cache_key, "output_kind": str(output_kind)},
                    )
            else:
                return cached_response

        # Call through circuit breaker with guardrail-aware retries
        prompt_to_use = prompt
        try:
            for attempt in range(guardrail_retries + 1):
                response_text = ""
                try:
                    response_text, used_fallback = await self._circuit_breaker.call_gemini(
                        self._generate_content_internal,
                        prompt_to_use,
                        **kwargs
                    )

                    if used_fallback:
                        raise FeatureNotAvailableError(
                            "Gemini circuit breaker open — feature unavailable",
                            "gemini",
                            "generate_content",
                        )

                    if output_kind:
                        if output_kind == OutputKind.JSON:
                            response_text = normalize_json_output(response_text)
                        else:
                            response_text = normalize_ai_output(response_text)
                        validate_ai_output(
                            response_text,
                            output_kind,
                            min_length=min_length,
                            max_length=max_length,
                            required_keys=required_keys,
                            require_ending_punctuation=require_ending_punctuation,
                            allow_placeholders=allow_placeholders,
                        )

                    if require_ending_punctuation and self._looks_incomplete(response_text):
                        if attempt >= guardrail_retries:
                            raise GeminiAPIError("AI output incomplete after retries")
                        prompt_to_use = self._augment_incomplete_prompt(prompt_to_use)
                        continue

                    await self._cache_response(cache_key, response_text)
                    return response_text
                except GuardrailViolation as guardrail_error:
                    if (
                        output_kind == OutputKind.MESSAGE
                        and require_ending_punctuation
                        and str(guardrail_error) == "missing_ending_punctuation"
                    ):
                        repaired = self._repair_ending_punctuation(response_text)
                        try:
                            validate_ai_output(
                                repaired,
                                output_kind,
                                min_length=min_length,
                                max_length=max_length,
                                required_keys=required_keys,
                                require_ending_punctuation=require_ending_punctuation,
                                allow_placeholders=allow_placeholders,
                            )
                            await self._cache_response(cache_key, repaired)
                            return repaired
                        except GuardrailViolation:
                            pass
                    if attempt >= guardrail_retries:
                        raise GeminiAPIError(
                            f"AI output failed guardrails after retries: {guardrail_error}"
                        ) from guardrail_error
                    continue
        except Exception as e:
            logger.error(
                "Gemini content generation failed: %s",
                str(e),
                exc_info=True,
                extra={"prompt_length": len(prompt), "circuit_breaker": "active"},
            )
            raise

        raise GeminiAPIError("Unexpected error in guarded content generation")

    def compact_patient_context(self, patient_context: Dict[str, Any]) -> Dict[str, Any]:
        """Public wrapper delegating to the standalone context_compactor module."""
        from app.ai.context_compactor import compact_patient_context as _compact

        return _compact(patient_context)

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
_gemini_client_sync_lock = threading.Lock()


def get_gemini_client() -> GeminiClient:
    """
    Get global Gemini client instance (sync version, thread-safe).

    Returns:
        Initialized GeminiClient instance

    Note: For async contexts, prefer get_gemini_client_async() for thread safety.
    """
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    with _gemini_client_sync_lock:
        # Double-check after acquiring lock
        if _gemini_client is None:
            _gemini_client = _create_domain_client()
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
            _gemini_client = _create_domain_client()

    return _gemini_client


async def reset_gemini_client():
    """Reset singleton instance (for testing)."""
    global _gemini_client
    async with _gemini_client_lock:
        _gemini_client = None
