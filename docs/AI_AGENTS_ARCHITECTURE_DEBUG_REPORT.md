# AI Agents Architecture - Debug Report

**Generated:** 2025-12-22
**System:** Backend Hormonia - Oncology Clinic Management System
**Scope:** AI Integration & Agent Architecture Analysis

---

## Executive Summary

The backend system implements a sophisticated AI-powered agent architecture using:
- **Google Gemini 2.5 Flash** (via LangChain) for AI operations
- **LangChain orchestration** for message personalization and sentiment analysis
- **Base agent framework** for multi-agent coordination (Hive-Mind system)
- **Caching layer** with Redis for 70% cost reduction
- **Token limiting** for budget control

### Critical Findings
- ✅ **No circular imports detected** in AI architecture
- ⚠️ **Multiple initialization paths** for AI clients (potential confusion)
- ⚠️ **Missing error handling** in some initialization flows
- ⚠️ **Inconsistent naming** ("OpenAI" classes used for Gemini API)
- ✅ **Good separation of concerns** between services and integrations

---

## Architecture Overview

### 1. Core Components

```
app/
├── agents/
│   ├── base.py                          # BaseAgent class (Hive-Mind)
│   ├── communication/
│   │   └── message_composer/
│   │       └── agent.py                 # MessageComposerAgent
│   └── monitoring/
│       └── agent_health_monitor.py      # Health monitoring
├── integrations/
│   ├── gemini_client.py                 # GeminiClient (LangChain-based)
│   └── openai_client.py                 # LangChainOrchestrator (Gemini backend!)
├── services/ai/
│   ├── ai_service.py                    # Unified AIService
│   ├── batch_processor.py               # Batch processing
│   └── cache_layer/                     # Caching infrastructure
├── schemas/
│   ├── ai.py                            # API v1 schemas
│   └── v2/ai.py                         # API v2 schemas (enhanced)
└── services/audit/
    └── ai_audit.py                      # HIPAA-compliant audit logging
```

### 2. AI Service Layers

#### Layer 1: AI Clients (Integration Layer)
- **GeminiClient** (`app/integrations/gemini_client.py`)
  - Purpose: Google Gemini 2.5 Flash integration
  - Uses: `langchain-google-genai` → `ChatGoogleGenerativeAI`
  - Features: Semantic caching, message humanization, sentiment analysis
  - Caching: Redis-based with TTL (3600s default)

- **LangChainOrchestrator** (`app/integrations/openai_client.py`)
  - ⚠️ **Naming Issue**: File named "openai_client" but uses Gemini!
  - Purpose: LangChain-based orchestration for message operations
  - Uses: `ChatGoogleGenerativeAI` (not OpenAI!)
  - Features: Message personalization, sentiment analysis, prompt templates

#### Layer 2: Service Layer
- **AIService** (`app/services/ai/ai_service.py`)
  - Purpose: Unified interface for all AI operations
  - Features:
    - Message humanization with context
    - Sentiment analysis with medical concern detection
    - Intent classification
    - Patient context building
    - Integrated caching (70% cost reduction)
    - Token limiting for budget control
  - Dependencies:
    - `LangChainOrchestrator` (for AI calls)
    - `CacheLayer` (for caching)
    - `TokenLimiter` (for cost control)

#### Layer 3: Agent Layer
- **BaseAgent** (`app/agents/base.py`)
  - Purpose: Base class for all Hive-Mind agents
  - Features:
    - Inter-agent communication
    - Task orchestration
    - Performance metrics
    - Message queue management
    - Claude-Flow hook integration
  - Abstract methods: `process_task()`, `get_capabilities()`, `validate_task()`

- **MessageComposerAgent** (`app/agents/communication/message_composer/agent.py`)
  - Extends: `BaseAgent`
  - Purpose: Intelligent message composition and personalization
  - Dependencies:
    - `GeminiClient` (via `get_gemini_client()`)
    - `ConversationMemory`
    - `TemplateLoader`
  - Features:
    - Message composition from templates
    - Personalization based on patient history
    - Tone adaptation
    - Quiz message generation

- **AgentHealthMonitor** (`app/monitoring/agent_health_monitor.py`)
  - Purpose: Monitor agent health and performance
  - Features:
    - Real-time metrics tracking
    - Alert generation
    - Auto-recovery mechanisms
    - System-wide health overview

---

## Detailed Component Analysis

### 1. GeminiClient (`app/integrations/gemini_client.py`)

**Purpose:** Google Gemini 2.5 Flash integration with healthcare-specific optimizations

**Initialization:**
```python
def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
    self.api_key = api_key or settings.AI_GEMINI_API_KEY
    self.model_name = model or settings.AI_GEMINI_MODEL
    self.redis_client = get_sync_redis()  # ✅ Sync Redis client

    # Initialize LangChain model
    self.model = ChatGoogleGenerativeAI(
        model=self.model_name,
        google_api_key=self.api_key,
        temperature=settings.AI_GEMINI_TEMPERATURE,
        max_output_tokens=settings.AI_GEMINI_MAX_OUTPUT_TOKENS,
        top_p=settings.AI_GEMINI_TOP_P,
        top_k=settings.AI_GEMINI_TOP_K,
    )
```

**Key Methods:**
- `generate_content(prompt, **kwargs)` - Main generation method with retry logic
- `humanize_flow_message()` - Convert templates to natural conversation
- `generate_varied_question()` - Generate question variations
- `analyze_response_sentiment()` - Sentiment analysis with medical focus
- `create_empathetic_follow_up()` - Generate empathetic responses

**Features:**
- ✅ Semantic caching with Redis (SHA-256 hash keys)
- ✅ Retry logic with exponential backoff
- ✅ Timeout handling (configurable via settings)
- ✅ Few-shot learning support
- ✅ Health check endpoint

**Issues:**
- ⚠️ Synchronous Redis client in async context (uses `get_sync_redis()`)
- ⚠️ Cache methods are async but Redis client is sync (potential bottleneck)

**Risk Level:** 🟡 MEDIUM

---

### 2. LangChainOrchestrator (`app/integrations/openai_client.py`)

**⚠️ CRITICAL NAMING ISSUE:**
- File: `openai_client.py`
- Class: `LangChainOrchestrator`
- Exception: `OpenAIClientError`
- **Actual Backend:** Google Gemini (NOT OpenAI!)

**Purpose:** LangChain-based orchestration for message personalization

**Initialization:**
```python
def __init__(
    self,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 500,
):
    self.api_key = api_key or settings.AI_GEMINI_API_KEY  # ✅ Gemini API key
    self.model_name = model_name or settings.AI_GEMINI_MODEL  # ✅ Gemini model

    # Initialize Google Gemini (NOT OpenAI!)
    self.chat_model = ChatGoogleGenerativeAI(
        model=self.model_name,
        google_api_key=self.api_key,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
```

**Key Methods:**
- `humanize_message(request)` - Personalize template messages
- `analyze_sentiment(request)` - Sentiment analysis with medical concerns
- `generate_text(prompt)` - Simple text generation
- `generate_contextual_response()` - Context-aware responses
- `health_check()` - Service health verification

**Features:**
- ✅ ChatPromptTemplate for structured prompts
- ✅ Healthcare-specific prompt engineering
- ✅ Timeout decorator (`@with_timeout(30)`)
- ✅ Medical concern detection
- ✅ Pydantic models for validation

**Issues:**
- ⚠️ **Confusing naming** (file/class names suggest OpenAI but use Gemini)
- ⚠️ Model name parameter shadowing in `__init__` (line 128: uses parameter instead of `self.model_name`)
- ℹ️ Backward compatibility shim exists (`get_openai_client()` → `get_langchain_orchestrator()`)

**Risk Level:** 🟡 MEDIUM (confusion risk, not functionality)

---

### 3. AIService (`app/services/ai/ai_service.py`)

**Purpose:** Unified AI service with integrated caching and batch processing

**Architecture:**
```
AIService
├── LangChainOrchestrator (AI calls)
├── CacheLayer (Redis caching)
└── TokenLimiter (cost control)
```

**Initialization:**
```python
async def initialize(self):
    if not self.orchestrator:
        self.orchestrator = get_langchain_orchestrator()
    if not self.cache:
        self.cache = await get_cache_layer()
    self._initialized = True
```

**Key Methods:**

1. **Message Humanization:**
   ```python
   async def humanize_message(
       template_message: str,
       patient_context: PatientContext,
       message_type: str = "general",
       force_refresh: bool = False,
   ) -> PersonalizationResponse
   ```
   - ✅ Cache-first approach (70% hit rate target)
   - ✅ Token limiting (500 tokens max for context)
   - ✅ Message type-specific enhancements
   - ✅ Patient context sanitization

2. **Sentiment Analysis:**
   ```python
   async def analyze_sentiment(
       patient_message: str,
       patient_context: PatientContext,
       force_refresh: bool = False,
   ) -> Tuple[SentimentAnalysisResponse, ConcernLevel]
   ```
   - ✅ Medical concern detection
   - ✅ Concern level classification (LOW/MEDIUM/HIGH/CRITICAL)
   - ✅ Treatment-specific insights
   - ✅ Timeline-based analysis

**Features:**
- ✅ Singleton pattern with async lock (thread-safe)
- ✅ Comprehensive caching strategy
- ✅ Token limiting for cost control
- ✅ Medical domain knowledge integration
- ✅ Cache invalidation by patient ID

**Issues:**
- ℹ️ None detected - well-designed service layer

**Risk Level:** 🟢 LOW

---

### 4. BaseAgent (`app/agents/base.py`)

**Purpose:** Base class for Hive-Mind multi-agent system

**Architecture:**
```
BaseAgent (Abstract)
├── MessageComposerAgent
├── AnalyticsAgent
└── PatientAgent (implied)
```

**Key Features:**

1. **Agent Lifecycle:**
   ```python
   async def start()  # Initialize and start agent
   async def stop()   # Graceful shutdown
   ```

2. **Message System:**
   ```python
   async def send_message(to_agent, message_type, payload, priority)
   async def receive_message(message: AgentMessage)
   ```

3. **Task Execution:**
   ```python
   @abstractmethod
   async def process_task(task_data) -> Dict[str, Any]

   @abstractmethod
   async def get_capabilities() -> List[str]

   @abstractmethod
   async def validate_task(task_data) -> bool
   ```

4. **Background Tasks:**
   - Message processing loop
   - Heartbeat to swarm manager
   - Metrics collection

**Integration Points:**
- ✅ Claude-Flow hooks (pre/post task)
- ✅ Swarm manager integration
- ✅ Performance metrics tracking
- ✅ Inter-agent communication via message queue

**Issues:**
- ℹ️ Swarm manager import is dynamic (line 301, 487) - could cause issues if not initialized
- ℹ️ Claude-Flow hooks are stubbed (lines 509, 522) - need implementation

**Risk Level:** 🟡 MEDIUM (runtime dependencies)

---

### 5. MessageComposerAgent (`app/agents/communication/message_composer/agent.py`)

**Purpose:** Specialized agent for intelligent message composition

**Initialization:**
```python
def __init__(self, db_session: Session, template_loader: Optional[...] = None):
    super().__init__(
        agent_id="message_composer",
        agent_type="communication",
        specialization="message_composer",
        db_session=db_session,
        capabilities=[
            AgentCapabilities.MESSAGE_COMPOSITION,
            AgentCapabilities.PERSONALIZATION,
            AgentCapabilities.EMOTIONAL_INTELLIGENCE,
            AgentCapabilities.PATIENT_ADAPTATION,
        ],
    )

    # Initialize components
    self.gemini_client = get_gemini_client()  # ✅ Direct Gemini integration
    self.conversation_memory = get_conversation_memory()
    self.template_manager = MessageTemplateManager(...)
    self.context_builder = MessageContextBuilder(...)
    self.tone_adapter = MessageToneAdapter(...)
    self.composer = MessageComposer(...)
```

**Task Processing:**
```python
async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
    task_type = task.get("task_type")

    if task_type == "compose_message":
        return await self._compose_message(payload)
    elif task_type == "personalize_template":
        return await self._personalize_template(payload)
    elif task_type == "adapt_tone":
        return await self._adapt_message_tone(payload)
    elif task_type == "compose_follow_up":
        return await self._compose_follow_up(payload)
    elif task_type == "generate_quiz_message":
        return await self._generate_quiz_message(payload)
```

**Features:**
- ✅ Multiple composition methods
- ✅ Fallback message handling
- ✅ Template-based and AI-generated options
- ✅ Conversation pattern learning
- ✅ Knowledge graph updates

**Dependencies:**
- `GeminiClient` (direct dependency)
- `PatientRepository`
- `ConversationMemory`
- `EnhancedTemplateLoader`
- Custom components: `MessageTemplateManager`, `MessageContextBuilder`, `MessageToneAdapter`, `MessageComposer`

**Issues:**
- ℹ️ Direct dependency on `GeminiClient` instead of `AIService` (bypasses caching)
- ⚠️ Potential for duplicate AI calls if not coordinated with `AIService`

**Risk Level:** 🟡 MEDIUM (potential inefficiency)

---

## Initialization Flow Analysis

### Current Initialization Paths

```
Path 1: Direct GeminiClient
└── app.integrations.gemini_client.get_gemini_client()
    └── GeminiClient (singleton)
        └── ChatGoogleGenerativeAI (LangChain)

Path 2: LangChainOrchestrator
└── app.integrations.openai_client.get_langchain_orchestrator()
    └── LangChainOrchestrator (singleton)
        └── ChatGoogleGenerativeAI (LangChain)

Path 3: AIService (Recommended)
└── app.services.ai.ai_service.get_ai_service()
    └── AIService
        ├── LangChainOrchestrator
        ├── CacheLayer
        └── TokenLimiter
```

### Potential Issues

1. **Multiple Clients for Same API:**
   - `GeminiClient` creates its own `ChatGoogleGenerativeAI` instance
   - `LangChainOrchestrator` creates another `ChatGoogleGenerativeAI` instance
   - Both use same API key and settings
   - ⚠️ No connection pooling or rate limiting coordination

2. **Bypassing Cache:**
   - `MessageComposerAgent` uses `GeminiClient` directly
   - `AIService` has integrated caching
   - **Result:** Agent bypasses cache layer, missing 70% cost savings

3. **Inconsistent Initialization:**
   - Some components get orchestrator, some get raw client
   - Different timeout configurations
   - Different error handling strategies

---

## Error Handling Assessment

### ✅ Good Practices

1. **Retry Logic:**
   ```python
   # In GeminiClient.generate_content()
   for attempt in range(max_retries):
       try:
           response = await asyncio.wait_for(
               self.model.ainvoke(messages),
               timeout=settings.AI_GEMINI_TIMEOUT_SECONDS,
           )
           # ... success handling
       except Exception as e:
           # ... exponential backoff
           await asyncio.sleep(retry_delay * (2**attempt))
   ```

2. **Timeout Handling:**
   ```python
   @with_timeout(timeout_seconds=30)
   async def humanize_message(...)
   ```

3. **Fallback Responses:**
   ```python
   # In MessageComposerAgent
   if not message_content:
       message_content = self.template_manager.get_fallback_message(
           message_type, patient.name
       )
   ```

### ⚠️ Issues Found

1. **Missing Validation:**
   ```python
   # In LangChainOrchestrator.__init__
   if not self.api_key:
       raise OpenAIClientError("Gemini API key is required")

   # ⚠️ But GeminiClient allows None:
   if not self.api_key or not self.model:
       logger.warning("Gemini API key not provided.")
       self.model = None
       return  # Silently returns, may cause issues later
   ```

2. **Sync Redis in Async Context:**
   ```python
   # In GeminiClient
   self.redis_client = get_sync_redis()  # ⚠️ Sync client

   async def _get_cached_response(self, cache_key: str):
       cached_value = self.redis_client.get(cache_key)  # ⚠️ Blocking call
   ```

3. **Swarm Manager Dependency:**
   ```python
   # In BaseAgent
   from app.orchestration.swarm_manager import get_swarm_manager
   swarm_manager = await get_swarm_manager()  # ⚠️ May not exist
   ```

---

## Circular Import Analysis

### ✅ No Circular Imports Detected

**Import Flow:**
```
app/integrations/gemini_client.py
└── langchain_google_genai
└── app.config.settings
└── app.core.redis_unified

app/integrations/openai_client.py
└── langchain_google_genai
└── langchain_core
└── app.config.settings
└── app.exceptions

app/services/ai/ai_service.py
└── app.integrations.openai_client
└── app.services.ai.cache_layer
└── app.utils.token_limiter

app/agents/base.py
└── sqlalchemy.orm
└── app.utils.logging

app/agents/communication/message_composer/agent.py
└── app.agents.base
└── app.integrations.gemini_client
└── app.models.patient
└── app.repositories.patient
```

**Conclusion:** Clean import hierarchy with proper separation of concerns.

---

## Issues by Severity

### 🔴 CRITICAL (Immediate Action Required)
*None detected*

### 🟡 MEDIUM (Should Be Addressed)

1. **Naming Confusion - `openai_client.py`**
   - **File:** `app/integrations/openai_client.py`
   - **Issue:** File/class names reference OpenAI but implementation uses Gemini
   - **Impact:** Developer confusion, maintenance difficulty
   - **Recommendation:** Rename to `langchain_client.py` or `gemini_orchestrator.py`

2. **Sync Redis in Async Context**
   - **File:** `app/integrations/gemini_client.py:51`
   - **Issue:** Using sync Redis client (`get_sync_redis()`) in async methods
   - **Impact:** Blocking calls, reduced performance
   - **Recommendation:** Use async Redis client or ensure proper async wrapping

3. **Cache Bypass in MessageComposerAgent**
   - **File:** `app/agents/communication/message_composer/agent.py:61`
   - **Issue:** Direct `GeminiClient` usage bypasses `AIService` cache
   - **Impact:** Missing 70% cost savings from caching
   - **Recommendation:** Refactor to use `AIService` instead of `GeminiClient`

4. **Missing Swarm Manager Validation**
   - **File:** `app/agents/base.py:301, 487`
   - **Issue:** Dynamic import without existence check
   - **Impact:** Runtime errors if swarm manager not initialized
   - **Recommendation:** Add existence validation or lazy initialization

5. **Model Name Parameter Shadowing**
   - **File:** `app/integrations/openai_client.py:128`
   - **Issue:** Using parameter `model_name` instead of `self.model_name`
   - **Impact:** May use wrong model if default changes
   - **Recommendation:** Use `self.model_name` consistently

### 🟢 LOW (Nice to Have)

1. **Claude-Flow Hooks Not Implemented**
   - **File:** `app/agents/base.py:509, 522`
   - **Issue:** Hooks are stubbed, not implemented
   - **Impact:** Missing integration features
   - **Recommendation:** Implement hooks or remove stubs

2. **Inconsistent Error Messages**
   - **File:** Multiple locations
   - **Issue:** Some errors reference "OpenAI" when using Gemini
   - **Impact:** Debugging confusion
   - **Recommendation:** Update error messages to reflect actual service

---

## Recommendations

### Short-Term (High Priority)

1. **Fix Naming Confusion:**
   ```python
   # Rename: openai_client.py → gemini_orchestrator.py
   # Rename: OpenAIClientError → GeminiClientError
   # Update: All references in codebase
   ```

2. **Implement Async Redis:**
   ```python
   # In GeminiClient
   from app.core.redis_unified import get_async_redis

   async def __init__(self):
       self.redis_client = await get_async_redis()
   ```

3. **Refactor MessageComposerAgent:**
   ```python
   # Replace direct GeminiClient usage with AIService
   from app.services.ai.ai_service import get_ai_service

   async def initialize(self):
       self.ai_service = await get_ai_service()
       # Use self.ai_service instead of self.gemini_client
   ```

### Medium-Term (Performance)

1. **Centralize AI Client Management:**
   - Create single entry point for all AI operations
   - Implement connection pooling
   - Add rate limiting coordination
   - Centralize error handling

2. **Enhance Caching Strategy:**
   - Implement semantic similarity caching
   - Add cache warming for common queries
   - Implement cache analytics
   - Add cache invalidation strategies

3. **Improve Observability:**
   - Add distributed tracing
   - Implement AI call metrics
   - Add cost tracking per endpoint
   - Create AI usage dashboards

### Long-Term (Architecture)

1. **Agent Orchestration Enhancement:**
   - Implement full swarm manager
   - Add agent discovery mechanism
   - Implement health checks for all agents
   - Add auto-scaling based on load

2. **AI Service Abstraction:**
   - Create provider-agnostic interface
   - Support multiple AI providers
   - Implement provider fallback
   - Add A/B testing framework

3. **Testing Infrastructure:**
   - Add AI integration tests
   - Implement mock AI responses
   - Add performance benchmarks
   - Create regression test suite

---

## Code Quality Metrics

### ✅ Strengths

1. **Well-Structured Code:**
   - Clear separation of concerns
   - Proper use of abstract base classes
   - Good error handling patterns
   - Comprehensive documentation

2. **Modern Python Patterns:**
   - Async/await throughout
   - Type hints (though not complete)
   - Pydantic models for validation
   - Dataclasses for data structures

3. **Healthcare-Specific Features:**
   - Medical concern detection
   - HIPAA-compliant audit logging
   - Patient context management
   - Treatment-specific insights

4. **Performance Optimizations:**
   - Semantic caching (70% cost reduction)
   - Token limiting
   - Retry logic with backoff
   - Batch processing support

### ⚠️ Areas for Improvement

1. **Type Annotations:**
   - Incomplete in some areas
   - Mixed Optional/None patterns
   - Missing return types in some methods

2. **Documentation:**
   - Some docstrings missing
   - Limited inline comments in complex logic
   - Missing architecture diagrams

3. **Testing:**
   - No test files found in analysis
   - Missing integration tests
   - No mock fixtures observed

---

## Security Assessment

### ✅ Good Practices

1. **API Key Management:**
   - Keys from settings, not hardcoded
   - No keys in logs (hashed in audit)
   - Proper environment variable usage

2. **HIPAA Compliance:**
   - Patient data hashing in logs
   - Audit trail implementation
   - Data retention policies
   - Legal basis tracking

3. **Input Sanitization:**
   - Token limiting prevents oversized inputs
   - Message length validation
   - Context sanitization

### ⚠️ Considerations

1. **AI Output Validation:**
   - Limited validation of AI-generated content
   - No content filtering observed
   - Medical advice disclaimers needed

2. **Rate Limiting:**
   - No global rate limiting visible
   - API key shared across services
   - Potential for API abuse

---

## Performance Analysis

### Estimated Latency (per operation)

| Operation | Without Cache | With Cache (70% hit) | Savings |
|-----------|---------------|---------------------|---------|
| Message Humanization | ~1500ms | ~450ms | 70% |
| Sentiment Analysis | ~1200ms | ~360ms | 70% |
| Context Building | ~800ms | ~240ms | 70% |
| **Total API Call** | ~3500ms | ~1050ms | **70%** |

### Token Usage (estimated)

| Operation | Avg Tokens | Cost (Gemini Pro) | Monthly (10k calls) |
|-----------|-----------|-------------------|---------------------|
| Humanization | 400 | $0.0006 | $6.00 |
| Sentiment Analysis | 300 | $0.00045 | $4.50 |
| Full Analysis | 800 | $0.0012 | $12.00 |

**With 70% cache hit rate:** Monthly cost reduced to ~$3.60

---

## Conclusion

The AI agents architecture is **well-designed and functional** with modern patterns and good separation of concerns. The main issues are:

1. **Naming confusion** (OpenAI references for Gemini implementation)
2. **Cache bypass** in MessageComposerAgent
3. **Sync Redis** in async context
4. **Missing validations** in some initialization paths

### Overall Assessment: 🟢 **HEALTHY** with minor improvements needed

### Immediate Actions:
1. ✅ Rename `openai_client.py` → `gemini_orchestrator.py`
2. ✅ Implement async Redis in `GeminiClient`
3. ✅ Refactor `MessageComposerAgent` to use `AIService`
4. ✅ Add swarm manager validation

### Priority: 🟡 MEDIUM
These are architectural improvements, not critical bugs. System is functional but can be optimized.

---

## Appendix: File Locations

### AI Integration Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/integrations/gemini_client.py` (540 lines)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/integrations/openai_client.py` (540 lines)

### AI Service Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/ai/ai_service.py` (796 lines)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/ai/batch_processor.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/ai/cache_layer/`

### Agent Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/agents/base.py` (554 lines)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/agents/communication/message_composer/agent.py` (395 lines)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/monitoring/agent_health_monitor.py` (678 lines)

### Schema Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/ai.py` (604 lines)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/ai.py` (607 lines)

### Audit Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/audit/ai_audit.py` (345 lines)

---

**Report End**
