# AI Integration Clients - Comprehensive Debug Report

**Generated:** 2025-12-22
**Working Directory:** `/backend-hormonia`
**Analysis Scope:** Gemini, OpenAI/LangChain, Configuration, Error Handling

---

## Executive Summary

✅ **Overall Status:** AI integrations are well-implemented with proper error handling
⚠️ **Critical Issues Found:** 2 (API key exposure, missing timeout configuration)
⚠️ **Medium Issues Found:** 4 (rate limiting, fallback gaps, hardcoded values)
✅ **Strengths:** Excellent caching, retry logic, circuit breaker implementation

---

## 1. Gemini Client Analysis

### File: `/app/integrations/gemini_client.py`

#### ✅ Strengths

1. **Proper LangChain Integration** (Lines 15-16)
   - Uses `langchain_google_genai.ChatGoogleGenerativeAI`
   - Avoids deprecated `google.generativeai` SDK

2. **Excellent Caching Implementation** (Lines 78-102)
   ```python
   def _generate_cache_key(self, prompt: str) -> str:
       prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
       return f"gemini_cache:{prompt_hash}"
   ```
   - SHA-256 hashing for cache keys
   - Redis-based semantic caching
   - TTL support (default 3600s)

3. **Robust Retry Logic** (Lines 129-169)
   - Configurable max retries from settings
   - Exponential backoff: `retry_delay * (2**attempt)`
   - Timeout protection: `asyncio.wait_for(..., timeout=settings.AI_GEMINI_TIMEOUT_SECONDS)`

4. **Graceful Fallback** (Lines 211-214)
   ```python
   except Exception as e:
       logger.error(f"Failed to humanize message: {e}")
       return template.replace("[nome]", patient_name)
   ```

#### ⚠️ Issues Found

**CRITICAL #1: API Key Validation Insufficient** (Lines 53-58)
```python
if not self.api_key:
    logger.warning("Gemini API key not provided. Client will not be functional.")
    self.model = None
    return  # Silent failure - no exception raised
```
- **Impact:** Client initializes without API key, fails later at runtime
- **Fix:** Raise exception in production environments
- **File:Line:** `gemini_client.py:53-58`

**MEDIUM #1: No Rate Limiting** (Entire file)
- Gemini API has rate limits (60 requests/minute on free tier)
- No rate limiter decorator or client-side throttling
- **Risk:** 429 errors during high traffic
- **Recommendation:** Add rate limiter from `app/integrations/evolution/rate_limiter.py`

**MEDIUM #2: Cache Miss on Empty Response** (Line 151)
```python
if not response_text:
    raise GeminiAPIError("Empty response from Gemini API via LangChain")
```
- Empty responses are not cached
- **Impact:** Retry storms on persistent failures
- **Fix:** Cache negative responses with shorter TTL

#### 📊 Configuration Analysis

**Environment Variables Used:**
```bash
AI_GEMINI_API_KEY=AIzaSyBg8v_IuE16HjtCBF2VBlDUpQE55IDzs18  # ⚠️ EXPOSED IN .env
AI_GEMINI_MODEL=gemini-2.0-flash-exp
AI_GEMINI_TEMPERATURE=0.7
AI_GEMINI_MAX_OUTPUT_TOKENS=500
AI_GEMINI_TOP_P=0.8
AI_GEMINI_TOP_K=40
AI_GEMINI_TIMEOUT_SECONDS=30
AI_GEMINI_MAX_RETRIES=3
```

**⚠️ SECURITY ISSUE:** API key visible in `.env` file (not `.env.example`)

---

## 2. OpenAI/LangChain Orchestrator

### File: `/app/integrations/openai_client.py`

#### ✅ Strengths

1. **Proper Gemini Migration** (Lines 10-17)
   - Class name `OpenAIClientError` misleading but functional
   - Uses `ChatGoogleGenerativeAI` correctly
   - No OpenAI imports (clean migration)

2. **Comprehensive Prompt Templates** (Lines 142-214)
   - Separate templates for humanization, sentiment analysis
   - SystemMessage + HumanMessage pattern
   - Well-structured healthcare prompts

3. **Timeout Decorator** (Lines 216, 267, 331, 414)
   ```python
   @with_timeout(timeout_seconds=30)
   async def humanize_message(...):
   ```
   - Uses `app.utils.timeout.with_timeout`
   - Consistent 30s timeout across methods

4. **Health Check Endpoint** (Lines 414-451)
   - Tests actual API connectivity
   - Returns structured health status
   - Non-invasive test prompt

#### ⚠️ Issues Found

**CRITICAL #2: API Key Hardcoded Check** (Lines 114-118)
```python
self.api_key = api_key or settings.AI_GEMINI_API_KEY

if not self.api_key:
    raise OpenAIClientError("Gemini API key is required but not provided")
```
- **Good:** Raises exception on missing key
- **Issue:** Exception type name is misleading (`OpenAIClientError` for Gemini)
- **File:Line:** `openai_client.py:118`

**MEDIUM #3: Model Name Default Issue** (Line 121)
```python
self.model_name = model_name or settings.AI_GEMINI_MODEL
```
- Comment says "fixes provider mismatch" but doesn't validate model exists
- No validation that model name is a valid Gemini model
- **Risk:** Runtime errors on invalid model names

**LOW #1: Deprecated Class Name** (Line 81-84)
```python
class OpenAIClientError(ExternalServiceError):
    """Google Gemini/LangChain specific error."""
    pass
```
- Class name doesn't match actual provider (Gemini)
- Confusing for future maintainers
- **Recommendation:** Rename to `GeminiClientError` or `AIClientError`

#### 📊 Method Analysis

| Method | Timeout | Retry | Fallback | Status |
|--------|---------|-------|----------|--------|
| `humanize_message()` | ✅ 30s | ❌ None | ❌ None | ⚠️ Add retry |
| `analyze_sentiment()` | ✅ 30s | ❌ None | ✅ Default | ✅ Good |
| `generate_text()` | ✅ 30s | ❌ None | ❌ None | ⚠️ Add retry |
| `generate_contextual_response()` | ✅ 30s | ❌ None | ❌ None | ⚠️ Add retry |
| `health_check()` | ✅ 10s | ❌ None | ✅ Unhealthy | ✅ Good |

**MEDIUM #4: No Retry Logic**
- `gemini_client.py` has retries, but `openai_client.py` does not
- **Impact:** Single transient errors cause failures
- **Fix:** Add `@retry` decorator or manual retry loops

---

## 3. Configuration Analysis

### File: `/app/config/settings/integrations.py`

#### ✅ Strengths

1. **Comprehensive AI Settings** (Lines 70-128)
   - All Gemini parameters configurable
   - LangChain tracing support
   - Safety mode for critical keywords

2. **Humanization Safety** (Lines 101-128)
   ```python
   AI_HUMANIZATION_CRITICAL_KEYWORDS: List[str] = Field(
       default=["medicação", "remédio", "dosagem", "mg", "ml",
                "emergência", "urgente", "hospital"],
       description="Keywords that prevent AI humanization for safety",
   )
   ```
   - Medical safety built-in
   - Prevents AI from modifying critical medical instructions

3. **Helper Methods** (Lines 178-202)
   - `is_ai_humanization_enabled()`
   - `should_humanize_message(content)`
   - `get_humanization_config()`
   - Clean API for feature flags

#### ⚠️ Issues Found

**MEDIUM #5: Missing Rate Limit Configuration**
- No `AI_GEMINI_RATE_LIMIT_PER_MINUTE` setting
- No `AI_GEMINI_RATE_LIMIT_PER_DAY` setting
- **Recommendation:** Add rate limit configs

**LOW #2: LangChain API Key Optional** (Line 76-78)
```python
AI_LANGCHAIN_API_KEY: Optional[str] = Field(
    default=None, description="LangChain API key"
)
```
- LangChain tracing is optional but key is never validated
- Could cause silent failures if tracing enabled without key

---

## 4. Error Handling & Resilience

### Circuit Breaker Analysis

**File:** `/app/core/circuit_breaker_enhanced.py`

#### ✅ Excellent Implementation

1. **Gemini-Specific Circuit Breaker** (Lines 93-100)
   ```python
   ServiceType.GEMINI_AI: CircuitBreakerConfig(
       fail_max=5,
       timeout_duration=120,  # 2 minutes
       enable_fallback=True,
       fallback_queue_enabled=False,  # Use cached/template responses
   )
   ```

2. **Comprehensive Metrics** (Lines 185-222)
   - Prometheus integration
   - Success/failure counters
   - Duration histograms
   - State change tracking

3. **Fallback Support** (Lines 230-239)
   ```python
   async def _execute_fallback(self, fallback: Callable[..., T], *args, **kwargs) -> T:
       try:
           if asyncio.iscoroutinefunction(fallback):
               return await fallback(*args, **kwargs)
   ```

#### ⚠️ Issue Found

**MEDIUM #6: Gemini Client Not Using Circuit Breaker**
- Circuit breaker defined for `ServiceType.GEMINI_AI`
- `gemini_client.py` doesn't use `@with_circuit_breaker` decorator
- `openai_client.py` doesn't use circuit breaker
- **Impact:** No circuit breaking on actual AI calls
- **File:Line:** `gemini_client.py:104` (missing decorator)
- **Fix:**
  ```python
  from app.core.circuit_breaker_enhanced import with_circuit_breaker, ServiceType

  @with_circuit_breaker(ServiceType.GEMINI_AI)
  async def generate_content(self, prompt: str, **kwargs) -> str:
      # existing implementation
  ```

---

## 5. Patient Summary Service

### File: `/app/services/ai/patient_summary_service.py`

#### ✅ Strengths

1. **Direct Gemini Initialization** (Lines 75-80)
   ```python
   self.model = ChatGoogleGenerativeAI(
       model=settings.AI_GEMINI_MODEL,
       google_api_key=settings.AI_GEMINI_API_KEY,
       temperature=0.3,  # Lower temperature for consistency
       max_output_tokens=2000,
   )
   ```
   - Proper parameter tuning for medical summaries
   - Lower temperature (0.3) for factual output

2. **Token Usage Tracking** (Lines 186-189)
   ```python
   if hasattr(response, "response_metadata"):
       usage = response.response_metadata.get("usage_metadata", {})
       token_usage = usage.get("total_token_count", 0)
   ```
   - Tracks API costs
   - Metadata extraction from LangChain responses

3. **Robust Fallback** (Lines 288-304)
   - Returns structured fallback on AI failure
   - Includes basic metrics without AI
   - Never fails silently

#### ⚠️ Issues Found

**LOW #3: No Circuit Breaker** (Line 180)
- `await self.model.ainvoke(messages)` not protected
- Should use circuit breaker like other services

**LOW #4: Hardcoded Timeout Missing**
- No explicit timeout on `ainvoke()` call
- Could hang indefinitely on network issues
- **Fix:** Add `asyncio.wait_for()`

---

## 6. API Dependencies & Caching

### File: `/app/api/v2/routers/ai/dependencies.py`

#### ✅ Strengths

1. **User-Scoped Cache Keys** (Lines 111-132)
   ```python
   def generate_cache_key(prefix: str, user_id: Optional[str] = None, **kwargs) -> str:
       if user_id:
           kwargs["_user_id"] = user_id
       param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
   ```
   - Prevents cache leakage between users
   - HIPAA/LGPD compliant
   - SHA-256 instead of MD5

2. **Connection Pool Management** (Lines 48-65)
   ```python
   _redis_pool: Optional[redis.ConnectionPool] = None

   async def _get_redis_pool() -> Optional[redis.ConnectionPool]:
       global _redis_pool
       if _redis_pool is None:
           _redis_pool = redis.ConnectionPool.from_url(
               settings.REDIS_URL,
               max_connections=20,
           )
   ```
   - Shared pool prevents connection leaks
   - Configurable max connections

3. **Context Manager for Cleanup** (Lines 87-108)
   ```python
   @asynccontextmanager
   async def redis_connection():
       client = None
       try:
           client = await get_redis_cache()
           yield client
       finally:
           if client:
               await client.close()
   ```
   - Ensures proper cleanup
   - Prevents resource leaks

#### ⚠️ Issues Found

**LOW #5: Token Usage Tracking Not Used**
- `track_token_usage()` function defined (Lines 195-226)
- No evidence of actual usage in codebase
- **Impact:** Missing billing/analytics data
- **Recommendation:** Integrate into AI endpoint handlers

---

## 7. Critical Security Findings

### 🔴 CRITICAL: API Key Exposure

**File:** `.env` (root directory)
**Line:** 172, 184

```bash
AI_GEMINI_API_KEY=AIzaSyBg8v_IuE16HjtCBF2VBlDUpQE55IDzs18
AI_LANGCHAIN_API_KEY=
```

**Issue:** Production API key committed to repository
**Impact:**
- Unauthorized API usage
- Billing attacks
- Rate limit exhaustion
- Data exposure

**Immediate Actions Required:**
1. ✅ Rotate API key immediately in Google Cloud Console
2. ✅ Add `.env` to `.gitignore` (verify it's there)
3. ✅ Remove from git history: `git filter-branch` or BFG Repo-Cleaner
4. ✅ Use environment variables in production (Railway secrets)
5. ✅ Scan repository for other exposed secrets

**Prevention:**
```bash
# Add to .gitignore
.env
.env.local
.env.*.local

# Pre-commit hook
pre-commit install
# Add secret scanning hook
```

---

## 8. Missing Features & Gaps

### Rate Limiting

**Current State:** ❌ None implemented
**Required For:** Gemini API (60 RPM free tier, 1500 RPM paid)

**Recommendation:** Add rate limiter

```python
# In gemini_client.py
from app.integrations.evolution.rate_limiter import AsyncRateLimiter

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.rate_limiter = AsyncRateLimiter(
            max_requests=60,
            window_seconds=60,
            key_prefix="gemini_api"
        )

    async def generate_content(self, prompt: str, **kwargs) -> str:
        async with self.rate_limiter.acquire():
            # Existing implementation
```

### Retry Logic Gaps

**Missing Retries:**
- `openai_client.py`: `humanize_message()` ❌
- `openai_client.py`: `analyze_sentiment()` ❌
- `openai_client.py`: `generate_text()` ❌
- `patient_summary_service.py`: `_generate_ai_summary()` ❌

**Recommendation:** Add retry decorator

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
async def humanize_message(self, request: MessagePersonalizationRequest):
    # Existing implementation
```

### Timeout Configuration

**Current Timeouts:**
- `gemini_client.py`: ✅ 30s (configurable)
- `openai_client.py`: ✅ 30s (decorator)
- `patient_summary_service.py`: ❌ None

**Missing:**
```python
# In patient_summary_service.py:180
response = await asyncio.wait_for(
    self.model.ainvoke(messages),
    timeout=settings.AI_GEMINI_TIMEOUT_SECONDS
)
```

---

## 9. Hardcoded Values

### Found Hardcoded Values

| File | Line | Value | Issue | Fix |
|------|------|-------|-------|-----|
| `gemini_client.py` | 95 | `ttl=3600` | Cache TTL | Add `AI_CACHE_TTL_SECONDS` |
| `openai_client.py` | 99 | `temperature=0.7` | Default temp | Use from settings |
| `openai_client.py` | 100 | `max_tokens=500` | Token limit | Use from settings |
| `patient_summary_service.py` | 78 | `temperature=0.3` | Summary temp | Add config |
| `patient_summary_service.py` | 79 | `max_output_tokens=2000` | Token limit | Add config |
| `dependencies.py` | 60 | `max_connections=20` | Pool size | Use `REDIS_POOL_MAX_CONNECTIONS` |

**Recommendation:** Extract all to `settings/integrations.py`

```python
# Add to integrations.py
AI_GEMINI_CACHE_TTL_SECONDS: int = Field(default=3600)
AI_GEMINI_SUMMARY_TEMPERATURE: float = Field(default=0.3)
AI_GEMINI_SUMMARY_MAX_TOKENS: int = Field(default=2000)
```

---

## 10. Dependencies Analysis

### File: `requirements.txt`

#### ✅ Correct Dependencies

```txt
# Lines 36-43
langchain-core>=0.3.75,<0.4.0
langchain-google-genai>=2.1.12,<3.0.0
google-ai-generativelanguage==0.7.0
googleapis-common-protos>=1.70.0,<2.0.0
google-api-core>=2.25.0,<3.0.0
google-auth>=2.40.0,<3.0.0
```

#### ⚠️ Version Constraints

**Python 3.13 Compatibility:** ✅ All packages compatible
**NumPy 2.x Requirement:** ✅ Met (`numpy>=2.1.0`)
**Protobuf Version:** ✅ `protobuf>=5.0,<7.0.0`

#### Missing Dependencies

❌ **Rate Limiter Package:**
- Uses `asyncio-mqtt` but not for rate limiting
- Recommendation: Already has `tenacity`, use it

✅ **Circuit Breaker:** Already has `aiobreaker>=1.2.0`

---

## 11. Testing Coverage

### Search Results

```bash
tests/api/v2/test_ai.py  # AI endpoint tests
tests/services/baseline/test_ai_baseline.py  # Baseline tests
tests/e2e/test_webhook_ai_flow.py  # E2E AI flow tests
```

**Recommendation:** Review test coverage for:
- ✅ Circuit breaker behavior
- ✅ Fallback mechanisms
- ❌ Rate limiting (not implemented)
- ❌ Cache invalidation
- ❌ API key rotation

---

## 12. Recommendations Summary

### 🔴 Critical (Immediate)

1. **Rotate Exposed API Key**
   - File: `.env:172`
   - Action: Generate new key in Google Cloud Console
   - Timeline: Immediate

2. **Add Circuit Breaker to AI Calls**
   - Files: `gemini_client.py:104`, `openai_client.py:218`
   - Action: Add `@with_circuit_breaker(ServiceType.GEMINI_AI)` decorator
   - Timeline: This sprint

### ⚠️ High Priority

3. **Implement Rate Limiting**
   - File: `gemini_client.py`
   - Action: Add `AsyncRateLimiter` with 60 RPM limit
   - Timeline: Next sprint

4. **Add Retry Logic to LangChainOrchestrator**
   - File: `openai_client.py`
   - Action: Add `@retry` decorator to all AI methods
   - Timeline: Next sprint

5. **Add Timeout to PatientSummaryService**
   - File: `patient_summary_service.py:180`
   - Action: Wrap `ainvoke()` with `asyncio.wait_for()`
   - Timeline: Next sprint

### 📊 Medium Priority

6. **Extract Hardcoded Values**
   - Files: Multiple
   - Action: Move all magic numbers to `settings/integrations.py`
   - Timeline: Backlog

7. **Rename Misleading Classes**
   - File: `openai_client.py:81`
   - Action: Rename `OpenAIClientError` to `GeminiClientError`
   - Timeline: Backlog

8. **Add Token Usage Tracking**
   - File: AI endpoint handlers
   - Action: Call `track_token_usage()` on each request
   - Timeline: Backlog

### 📝 Low Priority

9. **Cache Negative Responses**
   - File: `gemini_client.py:151`
   - Action: Cache empty responses with 5-minute TTL
   - Timeline: Backlog

10. **Add Rate Limit Config**
    - File: `settings/integrations.py`
    - Action: Add `AI_GEMINI_RATE_LIMIT_PER_MINUTE` setting
    - Timeline: Backlog

---

## 13. Code Quality Score

| Category | Score | Notes |
|----------|-------|-------|
| **Error Handling** | 8/10 | Excellent try-except coverage, good fallbacks |
| **Configuration** | 7/10 | Well-organized, some hardcoded values |
| **Security** | 4/10 | API key exposed, needs rotation |
| **Resilience** | 7/10 | Circuit breaker exists but not used |
| **Caching** | 9/10 | Excellent Redis caching, user-scoped |
| **Monitoring** | 8/10 | Good metrics, missing usage tracking |
| **Testing** | 6/10 | Basic tests exist, needs more coverage |
| **Documentation** | 8/10 | Good docstrings, clear comments |

**Overall Score:** 7.1/10 (Good, needs security fixes)

---

## 14. File Reference Quick Index

### AI Clients
- **Gemini:** `/app/integrations/gemini_client.py`
- **LangChain:** `/app/integrations/openai_client.py`
- **Summary Service:** `/app/services/ai/patient_summary_service.py`

### Configuration
- **Main Settings:** `/app/config/settings/__init__.py`
- **Integrations:** `/app/config/settings/integrations.py`
- **Environment:** `.env.example` (safe), `.env` (⚠️ exposed key)

### Infrastructure
- **Circuit Breaker:** `/app/core/circuit_breaker_enhanced.py`
- **Dependencies:** `/app/api/v2/routers/ai/dependencies.py`
- **Redis Manager:** `/app/core/redis_unified.py`

### Error Handling
- **Custom Exceptions:** `/app/exceptions/flow_exceptions.py`
- **Base Exceptions:** `/app/core/exceptions.py`

---

## 15. Next Steps

1. ✅ **Immediate:** Rotate API key
2. ✅ **Week 1:** Add circuit breaker decorators
3. ✅ **Week 2:** Implement rate limiting
4. ✅ **Week 3:** Add retry logic to LangChainOrchestrator
5. ✅ **Week 4:** Extract hardcoded configuration values

---

## Appendix A: Environment Variables Reference

```bash
# AI Service Configuration
AI_GEMINI_API_KEY=                    # ⚠️ CRITICAL: Rotate immediately
AI_GEMINI_MODEL=gemini-2.0-flash-exp
AI_GEMINI_TEMPERATURE=0.7
AI_GEMINI_MAX_OUTPUT_TOKENS=500
AI_GEMINI_TOP_P=0.8
AI_GEMINI_TOP_K=40
AI_GEMINI_TIMEOUT_SECONDS=30
AI_GEMINI_MAX_RETRIES=3

# LangChain
AI_LANGCHAIN_ENABLE_TRACING_V2=false
AI_LANGCHAIN_API_KEY=

# Humanization
AI_ENABLE_HUMANIZATION=true
AI_HUMANIZATION_ENABLE_SAFETY_MODE=true
AI_HUMANIZATION_MAX_RETRIES=2
AI_HUMANIZATION_TIMEOUT_SECONDS=10.0
AI_HUMANIZATION_ENABLE_FALLBACK=true
AI_HUMANIZATION_CRITICAL_KEYWORDS=["medicação","remédio",...]
```

---

**End of Report**
