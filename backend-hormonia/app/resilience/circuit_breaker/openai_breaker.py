"""
OpenAI-specific Circuit Breaker

Specialized circuit breaker for OpenAI API with intelligent fallbacks.
"""

import openai
from typing import Any, Dict, List, Optional
from ..circuit_breaker.breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerStates
from ..circuit_breaker.cache_fallback import CacheFallback, CachedCircuitBreakerMixin
import logging

logger = logging.getLogger(__name__)


class OpenAICircuitBreakerConfig(CircuitBreakerConfig):
    """OpenAI-specific circuit breaker configuration"""

    def __init__(self):
        super().__init__(
            failure_threshold=3,           # Trip after 3 failures
            recovery_timeout=120.0,        # Wait 2 minutes before retry
            success_threshold=2,           # Need 2 successes to close
            timeout=30.0,                  # 30 second timeout
            expected_exception=(
                openai.APIError,
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.APIConnectionError,
                ConnectionError,
                TimeoutError
            ),
            monitor_window=300,            # 5 minute window
            min_requests=5                 # Minimum requests for evaluation
        )


class OpenAICircuitBreaker(CachedCircuitBreakerMixin, CircuitBreaker):
    """
    Circuit breaker specifically designed for OpenAI API

    Features:
    - Intelligent caching of AI responses
    - Rate limit aware recovery
    - Model-specific fallbacks
    - Token usage tracking
    """

    def __init__(self, cache_ttl: float = 1800.0):  # 30 minutes cache
        config = OpenAICircuitBreakerConfig()
        cache_fallback = CacheFallback(default_ttl=cache_ttl, max_size=500)

        super().__init__(
            config=config,
            name="openai_api",
            cache_fallback=cache_fallback
        )

        # OpenAI specific metrics
        self._token_usage = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0
        }
        self._model_usage = {}

        logger.info("OpenAI circuit breaker initialized with cache fallback")

    def create_chat_completion(self,
                             messages: List[Dict],
                             model: str = "gpt-3.5-turbo",
                             **kwargs) -> Dict[str, Any]:
        """
        Create chat completion with circuit breaker protection
        """
        def _create_completion():
            response = openai.ChatCompletion.create(
                messages=messages,
                model=model,
                **kwargs
            )

            # Track token usage
            if hasattr(response, 'usage'):
                usage = response.usage
                self._token_usage['prompt_tokens'] += usage.prompt_tokens
                self._token_usage['completion_tokens'] += usage.completion_tokens
                self._token_usage['total_tokens'] += usage.total_tokens

            # Track model usage
            self._model_usage[model] = self._model_usage.get(model, 0) + 1

            return response

        try:
            return self.call_with_cache(_create_completion)
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")

            # Try fallback strategies
            fallback_response = self._try_fallback_strategies(
                messages, model, **kwargs
            )
            if fallback_response:
                return fallback_response

            raise

    async def acreate_chat_completion(self,
                                    messages: List[Dict],
                                    model: str = "gpt-3.5-turbo",
                                    **kwargs) -> Dict[str, Any]:
        """
        Async create chat completion with circuit breaker protection
        """
        async def _create_completion():
            response = await openai.ChatCompletion.acreate(
                messages=messages,
                model=model,
                **kwargs
            )

            # Track token usage
            if hasattr(response, 'usage'):
                usage = response.usage
                self._token_usage['prompt_tokens'] += usage.prompt_tokens
                self._token_usage['completion_tokens'] += usage.completion_tokens
                self._token_usage['total_tokens'] += usage.total_tokens

            # Track model usage
            self._model_usage[model] = self._model_usage.get(model, 0) + 1

            return response

        try:
            return await self.acall_with_cache(_create_completion)
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")

            # Try fallback strategies
            fallback_response = self._try_fallback_strategies(
                messages, model, **kwargs
            )
            if fallback_response:
                return fallback_response

            raise

    def _try_fallback_strategies(self,
                               messages: List[Dict],
                               model: str,
                               **kwargs) -> Optional[Dict[str, Any]]:
        """
        Try various fallback strategies when primary call fails
        """
        # Strategy 1: Check cache for similar requests
        cached_response = self._find_similar_cached_response(messages, model)
        if cached_response:
            logger.info("Using similar cached response as fallback")
            return cached_response

        # Strategy 2: Use simpler model if available
        fallback_model = self._get_fallback_model(model)
        if fallback_model and self.state != CircuitBreakerStates.OPEN:
            try:
                logger.info(f"Trying fallback model: {fallback_model}")

                def _fallback_completion():
                    return openai.ChatCompletion.create(
                        messages=messages,
                        model=fallback_model,
                        **kwargs
                    )

                return self.call(_fallback_completion)
            except Exception as e:
                logger.warning(f"Fallback model {fallback_model} also failed: {str(e)}")

        # Strategy 3: Return generic error response
        return self._create_error_response(messages)

    def _find_similar_cached_response(self,
                                    messages: List[Dict],
                                    model: str) -> Optional[Dict[str, Any]]:
        """
        Find cached response for similar message patterns
        """
        # This could be enhanced with semantic similarity
        # For now, check for exact prompt matches with different models

        for cached_model in self._model_usage.keys():
            if cached_model != model:
                cached_result = self.cache_fallback.get_cached_result(
                    lambda: None,  # Dummy function
                    messages, cached_model
                )
                if cached_result:
                    return cached_result

        return None

    def _get_fallback_model(self, model: str) -> Optional[str]:
        """
        Get fallback model for the given model
        """
        fallback_map = {
            "gpt-4": "gpt-3.5-turbo",
            "gpt-4-turbo": "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k": "gpt-3.5-turbo",
        }
        return fallback_map.get(model)

    def _create_error_response(self, messages: List[Dict]) -> Dict[str, Any]:
        """
        Create a generic error response when all fallbacks fail
        """
        return {
            "id": "fallback_response",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "fallback",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I apologize, but I'm currently experiencing technical difficulties. Please try again in a few moments."
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }

    def get_openai_metrics(self) -> Dict:
        """Get OpenAI-specific metrics"""
        base_metrics = self.get_metrics()

        return {
            **base_metrics,
            'token_usage': self._token_usage.copy(),
            'model_usage': self._model_usage.copy(),
            'cache_metrics': self.cache_fallback.get_metrics(),
            'avg_tokens_per_request': (
                self._token_usage['total_tokens'] / max(1, self.metrics.successful_requests)
            )
        }

    def reset_token_usage(self):
        """Reset token usage counters"""
        self._token_usage = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0
        }
        self._model_usage.clear()
        logger.info("OpenAI token usage metrics reset")


# Global instance for easy access
openai_circuit_breaker = OpenAICircuitBreaker()


def with_openai_circuit_breaker(func):
    """
    Decorator to wrap OpenAI API calls with circuit breaker
    """
    def wrapper(*args, **kwargs):
        return openai_circuit_breaker.call_with_cache(func, *args, **kwargs)

    async def async_wrapper(*args, **kwargs):
        return await openai_circuit_breaker.acall_with_cache(func, *args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper