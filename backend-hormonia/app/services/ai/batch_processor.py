"""
AI Batch Processor - Refactored
================================

Consolidates:
- ai_batch_processor.py (parallel processing logic)
- Integration with unified cache_layer.py
- Integration with ai_service.py

Features:
- Parallel processing of AI operations (60-70% latency reduction)
- Priority-based operation ordering
- Integrated caching through CacheLayer
- Performance metrics and statistics
- Timeout handling and error recovery

Author: AI Architect
Date: 20 Jan 2025
Version: 2.0.0 (Refactored)
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from uuid import UUID
from dataclasses import dataclass, field

from app.integrations.gemini_client import get_gemini_client

from .cache_layer import CacheLayer, CacheOperation, get_cache_layer
from .ai_service import PatientContext

logger = logging.getLogger(__name__)


@dataclass
class AIOperation:
    """Single AI operation request."""

    operation_type: CacheOperation
    prompt: str
    context: Optional[Dict[str, Any]] = None
    priority: int = 5  # 1-10, higher is more important
    timeout: float = 10.0  # seconds


@dataclass
class BatchResult:
    """Result of batch AI processing."""

    patient_id: UUID
    timestamp: datetime = field(default_factory=datetime.utcnow)
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    cache_hits: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate of batch operations."""
        total = len(self.results) + len(self.errors)
        return (len(self.results) / total * 100) if total > 0 else 0.0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = len(self.results)
        return (self.cache_hits / total * 100) if total > 0 else 0.0


class BatchProcessor:
    """
    Batch processor for AI operations.

    Processes multiple AI operations in parallel to reduce latency
    by 60-70%. Integrates with unified CacheLayer for intelligent caching.

    Features:
    - Parallel execution with asyncio
    - Priority-based ordering
    - Automatic caching through CacheLayer
    - Timeout handling
    - Performance metrics

    Example:
        >>> processor = BatchProcessor()
        >>> await processor.initialize()
        >>> result = await processor.process_patient_interaction(
        ...     patient_id=uuid4(),
        ...     message="Estou com dor",
        ...     patient_context=context
        ... )
    """

    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        """
        Initialize batch processor.

        Args:
            cache_layer: Cache layer instance (optional, uses singleton)
        """
        self.gemini_client = None
        self.cache: Optional[CacheLayer] = cache_layer
        self.stats = {
            "batches_processed": 0,
            "total_operations": 0,
            "avg_latency_ms": 0.0,
            "cache_hit_rate": 0.0,
        }
        self._initialized = False

        logger.info("BatchProcessor initialized")

    async def initialize(self):
        """Initialize connections and services."""
        if self._initialized:
            return

        # Initialize Gemini client
        self.gemini_client = get_gemini_client()

        # Initialize cache
        if not self.cache:
            self.cache = await get_cache_layer()

        self._initialized = True
        logger.info("BatchProcessor initialized successfully")

    async def process_patient_interaction(
        self, patient_id: UUID, message: str, patient_context: PatientContext
    ) -> BatchResult:
        """
        Process all AI operations for a patient interaction in parallel.

        Performs sentiment analysis, response generation, concern detection,
        and intent classification in parallel to reduce latency.

        Args:
            patient_id: Patient UUID
            message: Patient message
            patient_context: Patient context data

        Returns:
            BatchResult with all AI operation results

        Example:
            >>> result = await processor.process_patient_interaction(
            ...     patient_id=uuid4(),
            ...     message="Estou com muita dor de cabeça",
            ...     patient_context=context
            ... )
            >>> print(result.results['sentiment_analysis'])
            >>> print(result.latency_ms)
        """
        start_time = datetime.utcnow()

        # Define all operations for patient interaction
        operations = [
            AIOperation(
                operation_type=CacheOperation.SENTIMENT_ANALYSIS,
                prompt=self._create_sentiment_prompt(message, patient_context),
                context={"patient_id": str(patient_id)},
                priority=8,
            ),
            AIOperation(
                operation_type=CacheOperation.RESPONSE_GENERATION,
                prompt=self._create_response_prompt(message, patient_context),
                context={"patient_id": str(patient_id)},
                priority=9,
            ),
            AIOperation(
                operation_type=CacheOperation.CONCERN_DETECTION,
                prompt=self._create_concern_prompt(message, patient_context),
                context={"patient_id": str(patient_id)},
                priority=10,
            ),
            AIOperation(
                operation_type=CacheOperation.INTENT_CLASSIFICATION,
                prompt=self._create_intent_prompt(message),
                context={"patient_id": str(patient_id)},
                priority=7,
            ),
        ]

        # Process in parallel
        results = await self._process_batch(operations)

        # Calculate latency
        end_time = datetime.utcnow()
        latency_ms = (end_time - start_time).total_seconds() * 1000

        # Create batch result
        batch_result = BatchResult(patient_id=patient_id, latency_ms=latency_ms)

        # Process results
        for operation, result in zip(operations, results):
            if isinstance(result, Exception):
                batch_result.errors.append(
                    f"{operation.operation_type.value}: {str(result)}"
                )
            else:
                key = operation.operation_type.value
                batch_result.results[key] = result

                # Check if it was a cache hit (result will have _cache_hit marker)
                if isinstance(result, dict) and result.get("_cache_hit", False):
                    batch_result.cache_hits += 1

        # Update stats
        self._update_stats(batch_result)

        logger.info(
            f"Batch processed for patient {patient_id}: "
            f"{len(batch_result.results)} successes, "
            f"{len(batch_result.errors)} errors, "
            f"{batch_result.latency_ms:.2f}ms latency, "
            f"{batch_result.cache_hit_rate:.1f}% cache hit rate"
        )

        return batch_result

    async def process_quiz_interpretation(
        self, patient_id: UUID, question: Dict[str, Any], response: str
    ) -> BatchResult:
        """
        Process quiz response interpretation with multiple AI operations.

        Args:
            patient_id: Patient UUID
            question: Quiz question data
            response: Patient's response

        Returns:
            BatchResult with interpretation results
        """
        start_time = datetime.utcnow()

        operations = [
            AIOperation(
                operation_type=CacheOperation.QUIZ_INTERPRETATION,
                prompt=self._create_quiz_interpretation_prompt(question, response),
                context={
                    "patient_id": str(patient_id),
                    "question_id": question.get("id"),
                },
                priority=9,
            ),
            AIOperation(
                operation_type=CacheOperation.SENTIMENT_ANALYSIS,
                prompt=self._create_sentiment_prompt(response, None),
                context={"patient_id": str(patient_id), "quiz": True},
                priority=7,
            ),
        ]

        results = await self._process_batch(operations)

        # Calculate latency
        end_time = datetime.utcnow()
        latency_ms = (end_time - start_time).total_seconds() * 1000

        batch_result = BatchResult(patient_id=patient_id, latency_ms=latency_ms)

        for operation, result in zip(operations, results):
            if not isinstance(result, Exception):
                batch_result.results[operation.operation_type.value] = result
                if isinstance(result, dict) and result.get("_cache_hit", False):
                    batch_result.cache_hits += 1
            else:
                batch_result.errors.append(str(result))

        self._update_stats(batch_result)

        return batch_result

    async def _process_batch(
        self, operations: List[AIOperation]
    ) -> List[Union[Any, Exception]]:
        """
        Process a batch of AI operations in parallel.

        Args:
            operations: List of AI operations

        Returns:
            List of results or exceptions
        """
        # Sort by priority (higher priority first)
        sorted_ops = sorted(operations, key=lambda x: x.priority, reverse=True)

        # Create tasks for parallel execution
        tasks = []
        for operation in sorted_ops:
            task = self._process_single_operation(operation)
            tasks.append(task)

        # Execute all tasks in parallel with timeout handling
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Reorder results to match original operation order
        result_map = dict(zip(sorted_ops, results))
        return [result_map[op] for op in operations]

    async def _process_single_operation(self, operation: AIOperation) -> Any:
        """
        Process a single AI operation with caching.

        Uses CacheLayer for automatic caching. If cache miss, executes
        the AI operation and caches the result.

        Args:
            operation: AI operation to process

        Returns:
            Operation result
        """
        try:
            # Build cache key
            cache_key = self._build_cache_key(operation)

            # Try to get from cache
            if self.cache:
                cached = await self.cache.get(cache_key, operation.operation_type)

                if cached is not None:
                    # Mark as cache hit
                    if isinstance(cached, dict):
                        cached["_cache_hit"] = True
                    return cached

            # Cache miss - execute operation
            result = await asyncio.wait_for(
                self._execute_ai_operation(operation.operation_type, operation.prompt),
                timeout=operation.timeout,
            )

            # Cache the result
            if self.cache:
                # Mark as cache miss
                if isinstance(result, dict):
                    result["_cache_hit"] = False

                await self.cache.set(
                    cache_key,
                    result,
                    operation.operation_type,
                    tags=[operation.context.get("patient_id")]
                    if operation.context and operation.context.get("patient_id")
                    else None,
                )

            return result

        except asyncio.TimeoutError:
            logger.error(f"Timeout for {operation.operation_type.value}")
            raise TimeoutError(f"Operation {operation.operation_type.value} timed out")
        except Exception as e:
            logger.error(f"Error in {operation.operation_type.value}: {e}")
            raise

    async def _execute_ai_operation(
        self, operation_type: CacheOperation, prompt: str
    ) -> Any:
        """
        Execute actual AI operation using Gemini.

        Args:
            operation_type: Type of operation
            prompt: Prompt for AI

        Returns:
            AI response
        """
        if not self.gemini_client:
            raise RuntimeError("Gemini client not initialized")

        # Add operation-specific system prompts
        system_prompts = {
            CacheOperation.SENTIMENT_ANALYSIS: "Analyze sentiment and return JSON with sentiment, confidence, and concerns.",
            CacheOperation.RESPONSE_GENERATION: "Generate empathetic response in Portuguese.",
            CacheOperation.CONCERN_DETECTION: "Identify medical concerns and return severity level.",
            CacheOperation.INTENT_CLASSIFICATION: "Classify user intent from predefined categories.",
            CacheOperation.QUIZ_INTERPRETATION: "Interpret quiz response and validate against options.",
            CacheOperation.TEMPLATE_HUMANIZATION: "Humanize template message maintaining key information.",
        }

        system_prompt = system_prompts.get(operation_type, "")
        full_prompt = f"{system_prompt}\n\n{prompt}"

        # Execute with Gemini
        response = await self.gemini_client.generate_content(full_prompt)

        # Parse response based on operation type
        return self._parse_response(operation_type, response)

    def _parse_response(self, operation_type: CacheOperation, response: Any) -> Any:
        """Parse AI response based on operation type."""
        # Simple text response
        if hasattr(response, "text"):
            text = response.text

            # Try to parse as JSON for structured operations
            if operation_type in (
                CacheOperation.SENTIMENT_ANALYSIS,
                CacheOperation.CONCERN_DETECTION,
                CacheOperation.QUIZ_INTERPRETATION,
            ):
                try:
                    import json

                    return json.loads(text)
                except json.JSONDecodeError:
                    # Return as text if not valid JSON
                    return {"result": text}

            return {"result": text}

        return {"result": str(response)}

    def _build_cache_key(self, operation: AIOperation) -> str:
        """Build cache key for operation."""
        import hashlib

        # Include operation type, prompt, and context in key
        key_parts = [
            operation.operation_type.value,
            operation.prompt[:100],  # Truncate prompt
        ]

        if operation.context:
            key_parts.append(str(operation.context))

        key_string = ":".join(key_parts)

        # Hash if too long
        if len(key_string) > 100:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{operation.operation_type.value}:{key_hash}"

        return key_string

    # Prompt creation methods

    def _create_sentiment_prompt(
        self, message: str, patient_context: Optional[PatientContext]
    ) -> str:
        """Create sentiment analysis prompt."""
        context_str = ""
        if patient_context:
            context_str = f"\nPatient: {patient_context.name}, Treatment: {patient_context.treatment_type}, Day {patient_context.treatment_day}"

        return f"""Analyze the sentiment of this patient message:{context_str}

Message: "{message}"

Return JSON with:
- sentiment: "positive", "neutral", "negative", or "concerning"
- confidence: 0.0-1.0
- key_phrases: list of important phrases
- medical_concerns: list of any medical concerns detected
"""

    def _create_response_prompt(
        self, message: str, patient_context: PatientContext
    ) -> str:
        """Create response generation prompt."""
        return f"""Generate an empathetic response to this patient message:

Patient: {patient_context.name}
Treatment: {patient_context.treatment_type}
Treatment Day: {patient_context.treatment_day}

Message: "{message}"

Generate a caring, professional response in Portuguese that:
1. Acknowledges their message
2. Shows empathy
3. Provides relevant guidance if needed
4. Encourages them

Response:"""

    def _create_concern_prompt(
        self, message: str, patient_context: PatientContext
    ) -> str:
        """Create concern detection prompt."""
        return f"""Identify medical concerns in this patient message:

Patient: {patient_context.name}
Treatment: {patient_context.treatment_type}
Treatment Day: {patient_context.treatment_day}

Message: "{message}"

Return JSON with:
- concerns: list of medical concerns
- severity: "low", "medium", "high", or "critical"
- requires_immediate_attention: true/false
- recommended_actions: list of actions
"""

    def _create_intent_prompt(self, message: str) -> str:
        """Create intent classification prompt."""
        return f"""Classify the intent of this message:

Message: "{message}"

Categories:
- question: User is asking a question
- concern: User is expressing a health concern
- feedback: User is providing feedback
- request: User is requesting something
- general: General conversation

Return JSON with:
- intent: category name
- confidence: 0.0-1.0
- subcategory: optional subcategory
"""

    def _create_quiz_interpretation_prompt(
        self, question: Dict[str, Any], response: str
    ) -> str:
        """Create quiz interpretation prompt."""
        question_text = question.get("text", "")
        options = question.get("options", [])
        options_str = "\n".join([f"- {opt}" for opt in options])

        return f"""Interpret this quiz response:

Question: {question_text}

Options:
{options_str}

Patient Response: "{response}"

Return JSON with:
- matched_option: the option that best matches the response
- confidence: 0.0-1.0
- interpretation: interpretation of the response
- concerns: any concerns identified
"""

    def _update_stats(self, batch_result: BatchResult):
        """Update processing statistics."""
        self.stats["batches_processed"] += 1
        self.stats["total_operations"] += len(batch_result.results) + len(
            batch_result.errors
        )

        # Update average latency (running average)
        old_avg = self.stats["avg_latency_ms"]
        n = self.stats["batches_processed"]
        new_avg = ((n - 1) * old_avg + batch_result.latency_ms) / n
        self.stats["avg_latency_ms"] = new_avg

        # Update cache hit rate (running average)
        if len(batch_result.results) > 0:
            old_hit_rate = self.stats["cache_hit_rate"]
            new_hit_rate = ((n - 1) * old_hit_rate + batch_result.cache_hit_rate) / n
            self.stats["cache_hit_rate"] = new_hit_rate

    def get_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics."""
        return {
            "batches_processed": self.stats["batches_processed"],
            "total_operations": self.stats["total_operations"],
            "avg_latency_ms": round(self.stats["avg_latency_ms"], 2),
            "cache_hit_rate": round(self.stats["cache_hit_rate"], 2),
        }

    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = {
            "batches_processed": 0,
            "total_operations": 0,
            "avg_latency_ms": 0.0,
            "cache_hit_rate": 0.0,
        }
        logger.info("Batch processor stats reset")


# Singleton instance
_batch_processor: Optional[BatchProcessor] = None


async def get_batch_processor() -> BatchProcessor:
    """
    Get or create singleton BatchProcessor instance.

    Returns:
        Initialized BatchProcessor instance
    """
    global _batch_processor

    if _batch_processor is None:
        _batch_processor = BatchProcessor()
        await _batch_processor.initialize()

    return _batch_processor


async def reset_batch_processor():
    """Reset singleton instance (for testing)."""
    global _batch_processor
    _batch_processor = None
