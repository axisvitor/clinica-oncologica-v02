# AI Integration Guide - Hormonia Oncology System

## Overview

The Hormonia oncology system leverages **Google Gemini 2.5 Flash** for intelligent healthcare messaging, patient communication, and clinical decision support. This document covers the complete AI architecture including integration patterns, caching strategies, resilience mechanisms, and cost optimization.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Google Gemini 2.5 Flash Integration](#google-gemini-25-flash-integration)
3. [Hybrid Cache System](#hybrid-cache-system)
4. [Circuit Breaker Pattern](#circuit-breaker-pattern)
5. [Humanization Service](#humanization-service)
6. [Batch Processing](#batch-processing)
7. [Configuration Reference](#configuration-reference)
8. [Usage Examples](#usage-examples)
9. [Cost Optimization](#cost-optimization)
10. [Monitoring and Metrics](#monitoring-and-metrics)

---

## Architecture Overview

```
+------------------+     +-------------------+     +------------------+
|                  |     |                   |     |                  |
|   Application    |---->|   AI Service      |---->|  Gemini Client   |
|   Layer          |     |   Layer           |     |  (LangChain)     |
|                  |     |                   |     |                  |
+------------------+     +-------------------+     +------------------+
                               |       |
                               |       |
              +----------------+       +----------------+
              |                                         |
              v                                         v
     +------------------+                    +--------------------+
     |                  |                    |                    |
     |  Hybrid Cache    |                    |  Circuit Breaker   |
     |  (Redis+Memory)  |                    |  (AI Protection)   |
     |                  |                    |                    |
     +------------------+                    +--------------------+
              |
              +----> Redis (Primary)
              +----> Memory LRU (Fallback)
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `GeminiClient` | `app/integrations/gemini_client.py` | Google Gemini API wrapper with LangChain |
| `AIService` | `app/services/ai/ai_service.py` | Unified AI operations orchestrator |
| `CacheLayer` | `app/services/ai/cache_layer/__init__.py` | Hybrid caching for AI responses |
| `CircuitBreaker` | `app/services/circuit_breaker.py` | Resilience and fallback mechanisms |
| `BatchProcessor` | `app/services/ai/batch_processor.py` | Parallel AI operation execution |
| `MessageComposerAgent` | `app/agents/communication/message_composer/agent.py` | Intelligent message composition |
| `PatientSummaryService` | `app/services/ai/patient_summary_service.py` | AI-powered patient summaries |

---

## Google Gemini 2.5 Flash Integration

### Model Configuration

The system uses **LangChain's ChatGoogleGenerativeAI** for Gemini integration, providing:

- Async-first design for non-blocking operations
- Automatic retry with exponential backoff
- Thread-safe singleton initialization
- Semantic caching for repeated prompts

**File:** `app/integrations/gemini_client.py`

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

class GeminiClient:
    def __init__(self, api_key=None, model=None):
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=api_key,
            temperature=0.7,
            max_output_tokens=500,
            top_p=0.8,
            top_k=40,
        )
```

### Default Model Parameters

| Parameter | Default Value | Description |
|-----------|---------------|-------------|
| `AI_GEMINI_MODEL` | `gemini-2.0-flash-exp` | Gemini model identifier |
| `AI_GEMINI_TEMPERATURE` | `0.7` | Generation randomness (0-1) |
| `AI_GEMINI_MAX_OUTPUT_TOKENS` | `500` | Maximum response length |
| `AI_GEMINI_TOP_P` | `0.8` | Nucleus sampling parameter |
| `AI_GEMINI_TOP_K` | `40` | Top-k sampling parameter |
| `AI_GEMINI_TIMEOUT_SECONDS` | `30` | API request timeout |
| `AI_GEMINI_MAX_RETRIES` | `3` | Maximum retry attempts |

### Core API Methods

```python
# Generate content with circuit breaker protection
response = await gemini_client.generate_content(prompt)

# Humanize healthcare messages
humanized = await gemini_client.humanize_flow_message(
    template="Lembrete de consulta",
    patient_name="Maria",
    patient_context={"treatment_day": 5},
    conversation_history=["Oi!", "Como voce esta?"],
    personalization_hints=["supportive", "casual"],
)

# Analyze patient sentiment
analysis = await gemini_client.analyze_response_sentiment(
    response="Estou me sentindo melhor hoje",
    patient_context={"treatment_type": "hormone_therapy"}
)

# Generate empathetic follow-up
follow_up = await gemini_client.create_empathetic_follow_up(
    patient_response="Tenho sentido muita dor de cabeca",
    conversation_history=[...],
    patient_context={...}
)

# Health check
is_healthy = await gemini_client.health_check()
```

---

## Hybrid Cache System

The AI cache layer implements a **two-tier hybrid caching strategy** with Redis as primary storage and in-memory LRU as fallback.

**File:** `app/services/ai/cache_layer/__init__.py`

### Cache Architecture

```
+-------------------+
|  Cache Request    |
+-------------------+
         |
         v
+-------------------+     Hit
|  Memory LRU       |-----------> Return Cached
|  (L1 - Fast)      |
+-------------------+
         | Miss
         v
+-------------------+     Hit
|  Redis            |-----------> Return + Update L1
|  (L2 - Persistent)|
+-------------------+
         | Miss
         v
+-------------------+
|  Generate with    |
|  Gemini API       |
+-------------------+
         |
         v
+-------------------+
|  Store in L1 + L2 |
+-------------------+
```

### Cache Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `MEMORY` | Memory-only caching | Development, single instance |
| `REDIS` | Redis-only caching | Distributed, shared cache |
| `HYBRID` | Redis + Memory fallback | Production (default) |

### TTL Configuration by Operation

| Operation | TTL (seconds) | Description |
|-----------|---------------|-------------|
| `TEMPLATE_HUMANIZATION` | 3600 (1 hour) | Humanized message templates |
| `RESPONSE_GENERATION` | 3600 (1 hour) | AI-generated responses |
| `SENTIMENT_ANALYSIS` | 900 (15 min) | Sentiment analysis results |
| `CONCERN_DETECTION` | 900 (15 min) | Medical concern detection |
| `INTENT_CLASSIFICATION` | 900 (15 min) | Intent classification |
| `QUIZ_INTERPRETATION` | 600 (10 min) | Quiz response interpretation |

### Memory Protection

The cache implements **bounded LRU eviction** to prevent memory exhaustion:

```python
MAX_LOCAL_CACHE_SIZE = 10000  # Maximum entries in local cache

# LRU eviction when at capacity
while len(self._entries) >= self.max_local_entries:
    oldest_key, oldest_entry = self._entries.popitem(last=False)
    self._eviction_count += 1
```

### Cache Usage Example

```python
from app.services.ai.cache_layer import get_cache_layer, CacheOperation

cache = await get_cache_layer()

# Get from cache
cached_value = await cache.get(
    key="sentiment_analysis:patient123",
    operation=CacheOperation.SENTIMENT_ANALYSIS
)

# Set in cache with tags for invalidation
await cache.set(
    key="humanize:template_welcome",
    value=humanized_message,
    operation=CacheOperation.TEMPLATE_HUMANIZATION,
    tags=["patient:123", "template:welcome"]
)

# Invalidate by tag
deleted_count = await cache.invalidate_by_tag("patient:123")

# Get cache statistics
stats = await cache.get_stats()
# {
#     "strategy": "hybrid",
#     "local_cache_entries": 1500,
#     "max_local_entries": 10000,
#     "eviction_count": 50,
#     "cache_utilization": 0.15,
#     "metrics": {"hits": 8500, "misses": 1500, "hit_rate_percent": 85.0}
# }
```

---

## Circuit Breaker Pattern

The circuit breaker protects the system from cascading failures when AI services are degraded or unavailable.

**File:** `app/services/circuit_breaker.py`

### Circuit States

```
     Success >= threshold
          +--------+
          |        |
          v        |
+------+      +-----------+      +------+
|CLOSED|----->| HALF_OPEN |----->| OPEN |
+------+      +-----------+      +------+
    ^              |                  |
    |              | Failure          | Timeout
    |              v                  | Elapsed
    |         +------+                |
    +---------| OPEN |<---------------+
              +------+
```

| State | Behavior |
|-------|----------|
| `CLOSED` | Normal operation, requests pass through |
| `OPEN` | Failing, all requests rejected with fallback |
| `HALF_OPEN` | Testing recovery, limited requests allowed |

### Circuit Breaker Configuration

| Circuit | Failure Threshold | Recovery Timeout | Success Threshold |
|---------|-------------------|------------------|-------------------|
| `gemini` | 3 failures | 30 seconds | 2 successes |
| `sentiment` | 5 failures | 60 seconds | 2 successes |
| `quiz` | 5 failures | 45 seconds | 2 successes |

### Fallback Mechanisms

```python
class AIServiceCircuitBreaker:
    async def call_gemini(self, func, prompt, fallback_response=None):
        async def fallback():
            if fallback_response:
                return fallback_response
            # Context-aware fallback
            if "sentiment" in prompt.lower():
                return '{"sentiment": "neutral", "confidence": 0.5}'
            return "Desculpe, estou temporariamente indisponivel."

        return await self.breakers["gemini"].call(func, prompt, fallback=fallback)

    async def call_sentiment_analysis(self, func, message, context):
        async def fallback():
            # Rule-based sentiment fallback
            positive = ["bem", "melhor", "otimo", "bom"]
            negative = ["mal", "pior", "ruim", "dor"]

            sentiment = "neutral"
            if any(w in message.lower() for w in positive):
                sentiment = "positive"
            elif any(w in message.lower() for w in negative):
                sentiment = "negative"

            return {"sentiment": sentiment, "confidence": 0.6, "fallback": True}

        return await self.breakers["sentiment"].call(func, message, context, fallback=fallback)
```

### Usage

```python
from app.services.circuit_breaker import get_ai_circuit_breaker

cb = get_ai_circuit_breaker()

# Protected Gemini call
response = await cb.call_gemini(
    gemini_client.generate_content,
    prompt,
    fallback_response="Fallback message"
)

# Get circuit statistics
stats = cb.get_all_stats()
# {
#     "gemini": {"state": "closed", "success_rate": "99.5%", ...},
#     "sentiment": {"state": "closed", ...},
#     "quiz": {"state": "closed", ...}
# }
```

---

## Humanization Service

The humanization service transforms clinical templates into natural, empathetic conversations.

### Features

- **Contextual Personalization**: Adapts messages based on patient history
- **Tone Adaptation**: Matches communication style to patient preferences
- **Conversation Continuity**: References previous interactions
- **Few-Shot Prompting**: Uses examples for consistent output quality
- **Safety Mode**: Preserves critical medical information

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `AI_ENABLE_HUMANIZATION` | `true` | Enable/disable AI humanization |
| `AI_HUMANIZATION_ENABLE_SAFETY_MODE` | `true` | Protect critical content |
| `AI_HUMANIZATION_MAX_RETRIES` | `2` | Retry attempts |
| `AI_HUMANIZATION_TIMEOUT_SECONDS` | `10.0` | Request timeout |
| `AI_HUMANIZATION_ENABLE_FALLBACK` | `true` | Use original on failure |

### Safety Keywords

Messages containing these keywords bypass AI humanization:

```python
AI_HUMANIZATION_CRITICAL_KEYWORDS = [
    "medicacao", "remedio", "dosagem", "mg", "ml",
    "emergencia", "urgente", "hospital"
]
```

### Humanization Example

**Input Template:**
```
Ola [nome], lembrete da sua consulta amanha as 14h.
```

**Humanized Output:**
```
Oi Maria! Tudo bem por ai?

Passando so pra te lembrar que amanha a gente se ve as 14h!
Fico muito feliz em acompanhar sua jornada de tratamento.

Se precisar de qualquer coisa antes da consulta, e so me chamar!
```

---

## Batch Processing

The batch processor executes multiple AI operations in parallel, reducing latency by 60-70%.

**File:** `app/services/ai/batch_processor.py`

### Batch Architecture

```
+-----------------------+
|  Patient Interaction  |
+-----------------------+
           |
           v
+----------+----------+----------+----------+
|          |          |          |          |
v          v          v          v          v
Sentiment  Response   Concern    Intent
Analysis   Generation Detection  Classify
(P=8)      (P=9)      (P=10)     (P=7)
|          |          |          |          |
+----------+----------+----------+----------+
           |
           v
    +------------+
    | Aggregate  |
    | Results    |
    +------------+
```

### Priority Levels

| Priority | Value | Operations |
|----------|-------|------------|
| Critical | 10 | Concern Detection |
| High | 9 | Response Generation |
| Medium | 8 | Sentiment Analysis |
| Normal | 7 | Intent Classification |

### Batch Processing Example

```python
from app.services.ai.batch_processor import get_batch_processor

processor = await get_batch_processor()

# Process patient interaction
result = await processor.process_patient_interaction(
    patient_id=patient_uuid,
    message="Estou sentindo muita dor de cabeca e nausea",
    patient_context=PatientContext(
        patient_id="123",
        name="Maria",
        treatment_type="hormone_therapy",
        treatment_day=15
    )
)

# Result contains all parallel AI outputs
print(result.results)
# {
#     "sentiment_analysis": {"sentiment": "negative", "confidence": 0.85},
#     "response_generation": {"result": "Sinto muito..."},
#     "concern_detection": {"severity": "medium", "concerns": ["headache", "nausea"]},
#     "intent_classification": {"intent": "concern", "confidence": 0.9}
# }

print(f"Latency: {result.latency_ms}ms")  # ~150ms vs ~600ms sequential
print(f"Cache hits: {result.cache_hits}")
print(f"Success rate: {result.success_rate}%")
```

### Performance Statistics

```python
stats = processor.get_stats()
# {
#     "batches_processed": 1500,
#     "total_operations": 6000,
#     "avg_latency_ms": 145.5,
#     "cache_hit_rate": 72.3
# }
```

---

## Configuration Reference

### Environment Variables

```bash
# Google Gemini AI
AI_GEMINI_API_KEY=your-api-key-here
AI_GEMINI_MODEL=gemini-2.0-flash-exp
AI_GEMINI_TEMPERATURE=0.7
AI_GEMINI_MAX_OUTPUT_TOKENS=500
AI_GEMINI_TOP_P=0.8
AI_GEMINI_TOP_K=40
AI_GEMINI_TIMEOUT_SECONDS=30
AI_GEMINI_MAX_RETRIES=3

# Humanization
AI_ENABLE_HUMANIZATION=true
AI_HUMANIZATION_ENABLE_SAFETY_MODE=true
AI_HUMANIZATION_MAX_RETRIES=2
AI_HUMANIZATION_TIMEOUT_SECONDS=10.0
AI_HUMANIZATION_ENABLE_FALLBACK=true

# LangChain (optional)
AI_LANGCHAIN_ENABLE_TRACING_V2=false
AI_LANGCHAIN_API_KEY=your-langchain-key

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0
```

### Configuration File Reference

**File:** `app/config/settings/integrations.py`

```python
class IntegrationsSettings(BaseAppSettings):
    # Gemini Configuration
    AI_GEMINI_API_KEY: Optional[str] = Field(default=None)
    AI_GEMINI_MODEL: str = Field(default="gemini-2.0-flash-exp")
    AI_GEMINI_TEMPERATURE: float = Field(default=0.7)
    AI_GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=500)
    AI_GEMINI_TOP_P: float = Field(default=0.8)
    AI_GEMINI_TOP_K: int = Field(default=40)
    AI_GEMINI_TIMEOUT_SECONDS: int = Field(default=30)
    AI_GEMINI_MAX_RETRIES: int = Field(default=3)

    # Humanization
    AI_ENABLE_HUMANIZATION: bool = Field(default=True)
    AI_HUMANIZATION_ENABLE_SAFETY_MODE: bool = Field(default=True)
    AI_HUMANIZATION_MAX_RETRIES: int = Field(default=2)
    AI_HUMANIZATION_TIMEOUT_SECONDS: float = Field(default=10.0)
```

---

## Usage Examples

### Basic Message Humanization

```python
from app.integrations.gemini_client import get_gemini_client

client = get_gemini_client()

humanized = await client.humanize_flow_message(
    template="Bom dia [nome]! Hoje e dia de check-in.",
    patient_name="Joao",
    patient_context={
        "treatment_day": 10,
        "treatment_type": "quimioterapia",
        "mood_trend": "improving"
    },
    conversation_history=[
        "Oi Joao, como voce esta?",
        "Estou bem, obrigado!"
    ],
    personalization_hints=["supportive", "encouraging"]
)
```

### AI Service with Caching

```python
from app.services.ai.ai_service import get_ai_service, PatientContext

ai_service = await get_ai_service()

# Build patient context
context = await ai_service.build_patient_context(
    patient_id="123",
    patient_data={
        "name": "Maria",
        "treatment_type": "hormone_therapy",
        "treatment_day": 15,
        "preferences": {"communication_style": "casual"}
    },
    recent_messages=[...],
    medical_data={...}
)

# Humanize with automatic caching
response = await ai_service.humanize_message(
    template_message="Lembrete semanal",
    patient_context=context,
    message_type="reminder",
    force_refresh=False  # Use cache if available
)

# Analyze sentiment with medical concern detection
sentiment, concern_level = await ai_service.analyze_sentiment(
    patient_message="Nao estou me sentindo bem hoje",
    patient_context=context
)
```

### Patient Summary Generation

```python
from app.services.ai.patient_summary_service import PatientSummaryService
from app.schemas.v2.patient_summary import GenerateSummaryRequest

service = PatientSummaryService(db_session)

summary = await service.generate_summary(
    GenerateSummaryRequest(
        patient_id=patient_uuid,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        force_refresh=False,
        save_summary=True
    ),
    generated_by=doctor_uuid
)

# Export to PDF
pdf_bytes = await service.export_to_pdf(summary.summary_id)
```

---

## Cost Optimization

### 1. Intelligent Caching (70% Cost Reduction)

The hybrid cache system significantly reduces API calls:

| Cache Layer | Hit Rate Target | TTL Strategy |
|-------------|-----------------|--------------|
| Memory (L1) | >90% | Short TTL (15-60 min) |
| Redis (L2) | >80% | Medium TTL (1-2 hours) |

### 2. Token Limiting

```python
from app.utils.token_limiter import TokenLimiter

limiter = TokenLimiter()

# Limit patient context to 500 tokens
limited_context = limiter.limit_patient_context(
    patient_context,
    max_tokens=TokenLimiter.DEFAULT_MAX_TOKENS
)

# Limit message history to 100 tokens
limited_history = limiter.limit_messages_history(
    messages,
    max_tokens=TokenLimiter.MESSAGE_MAX_TOKENS
)
```

### 3. Batch Processing

Parallel execution reduces total API time:

| Processing Mode | Latency | API Calls |
|-----------------|---------|-----------|
| Sequential | ~600ms | 4 |
| Parallel (Batch) | ~150ms | 4 |

### 4. Model Selection

| Use Case | Recommended Model | Tokens/Request |
|----------|-------------------|----------------|
| Message humanization | `gemini-2.0-flash-exp` | ~500 |
| Sentiment analysis | `gemini-2.0-flash-exp` | ~300 |
| Patient summaries | `gemini-2.0-flash-exp` | ~2000 |

### 5. Fallback Strategy

Circuit breaker fallbacks use zero API calls:

```python
# Rule-based sentiment fallback (no API call)
positive_words = ["bem", "melhor", "otimo"]
if any(word in message.lower() for word in positive_words):
    return {"sentiment": "positive", "confidence": 0.6}
```

### Cost Estimation Formula

```
Monthly Cost = (Total Requests - Cached Requests) * Avg Tokens * Token Price

Example:
- 100,000 monthly requests
- 70% cache hit rate = 30,000 API calls
- 400 avg tokens per call = 12M tokens
- $0.00001 per token = $120/month
```

---

## Monitoring and Metrics

### Health Check Endpoint

```python
# GET /api/v2/ai/health
{
    "gemini": {
        "status": "healthy",
        "model": "gemini-2.0-flash-exp",
        "latency_ms": 245
    },
    "cache": {
        "status": "healthy",
        "strategy": "hybrid",
        "hit_rate": 85.2
    },
    "circuit_breakers": {
        "gemini": {"state": "closed", "failures": 0},
        "sentiment": {"state": "closed", "failures": 0},
        "quiz": {"state": "closed", "failures": 0}
    }
}
```

### Key Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Cache hit rate | >80% | <60% |
| API latency (p95) | <500ms | >1000ms |
| Circuit breaker state | CLOSED | OPEN |
| Error rate | <1% | >5% |
| Token usage | Budget-based | 120% of budget |

### Logging

```python
import logging
logger = logging.getLogger(__name__)

# Structured logging for AI operations
logger.info(
    "Message humanized successfully",
    extra={
        "operation": "humanize",
        "patient": patient_name,
        "template_length": len(template),
        "cache_hit": False,
        "latency_ms": 245
    }
)
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `GeminiAPIError` | API key invalid | Verify `AI_GEMINI_API_KEY` |
| High latency | Cache miss | Check Redis connection |
| Circuit open | Multiple failures | Wait for recovery timeout |
| Empty responses | Token limit exceeded | Reduce `MAX_OUTPUT_TOKENS` |

### Debug Mode

```python
import logging
logging.getLogger("app.integrations.gemini_client").setLevel(logging.DEBUG)
logging.getLogger("app.services.ai").setLevel(logging.DEBUG)
```

---

## Related Documentation

- [Redis Configuration Guide](/docs/infrastructure/REDIS_GUIDE.md)
- [Circuit Breaker Patterns](/docs/patterns/CIRCUIT_BREAKER.md)
- [Patient Flow Engine](/docs/flows/PATIENT_FLOW.md)
- [API Reference](/docs/api/AI_ENDPOINTS.md)

---

*Last Updated: December 2025*
*Version: 2.0.0*
