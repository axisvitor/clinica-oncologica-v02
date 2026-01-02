# AI Response Flow - Issues Quick Reference

**Quick navigation to identified issues with file:line references**

---

## 🚨 CRITICAL ISSUES (P0 - Fix Immediately)

### 1. Async Cleanup Issues

**Issue:** Orphaned tasks and improper async cleanup
**Impact:** Memory leaks, connection pool exhaustion

```
File: /app/services/ai/cache_layer/__init__.py
Lines: 416-421

def reset_cache_layer() -> None:
    # ❌ Creates orphaned task
    loop.create_task(instance.close())  # Never awaited
```

**Fix:**
```python
async def reset_cache_layer() -> None:
    global _cache_layer_instance
    async with _cache_layer_lock:
        instance = _cache_layer_instance
        _cache_layer_instance = None
        if instance:
            await instance.close()  # ✅ Properly awaited
```

---

### 2. Missing Cleanup in Cache Close

**Issue:** Cache manager not closed during shutdown
**Impact:** Redis connections not released

```
File: /app/services/ai/cache_layer/__init__.py
Line: 185-190

async def close(self) -> None:
    async with self._lock:
        # ❌ Missing: await self._cache_manager.close()
        self._entries.clear()
        self._tag_index.clear()
```

**Fix:**
```python
async def close(self) -> None:
    async with self._lock:
        if self._cache_manager:
            await self._cache_manager.close()  # ✅ Add this
        self._entries.clear()
        self._tag_index.clear()
        self._initialized = False
```

---

### 3. Sync Redis in Async Code

**Issue:** Blocking Redis calls in async methods
**Impact:** Event loop blocking, poor performance

```
File: /app/integrations/gemini_client.py
Lines: 86-89

async def _get_cached_response(self, cache_key: str) -> Optional[str]:
    try:
        cached_value = self.redis_client.get(cache_key)  # ❌ Sync call
```

**Fix:**
```python
# Use async Redis client
self.redis_client = await get_async_redis()
cached_value = await self.redis_client.get(cache_key)  # ✅ Async
```

---

## ⚠️ HIGH PRIORITY (P1 - Fix This Week)

### 4. No Timeout on Initialization

**Issue:** Service can hang indefinitely on startup
**Impact:** Service unavailability

```
File: /app/services/ai/ai_service.py
Lines: 136-151

async def initialize(self):
    if not self.cache:
        self.cache = await get_cache_layer()  # ❌ No timeout
```

**Fix:**
```python
async def initialize(self, timeout: float = 30.0):
    try:
        async with asyncio.timeout(timeout):
            if not self.cache:
                self.cache = await get_cache_layer()
    except asyncio.TimeoutError:
        raise ExternalServiceError("AI service init timeout")
```

---

### 5. Missing Cache Timeouts in Batch Processor

**Issue:** Batch processing can hang on cache operations
**Impact:** Entire batch stalls

```
File: /app/services/ai/batch_processor.py
Lines: 323-326

if self.cache:
    cached = await self.cache.get(cache_key, ...)  # ❌ No timeout
```

**Fix:**
```python
CACHE_TIMEOUT = 2.0

if self.cache:
    try:
        cached = await asyncio.wait_for(
            self.cache.get(cache_key, operation.operation_type),
            timeout=CACHE_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning(f"Cache timeout for {operation.operation_type}")
        cached = None
```

---

### 6. No Retry Logic in Patient Summary

**Issue:** Single failure causes fallback even for transient errors
**Impact:** Poor UX on network glitches

```
File: /app/services/ai/patient_summary_service.py
Lines: 199-202

except Exception as e:
    logger.error(f"AI summary generation failed: {e}")
    return self._build_fallback_summary(data), 0  # ❌ No retry
```

**Fix:**
```python
max_retries = 3
for attempt in range(max_retries):
    try:
        response = await self.model.ainvoke(messages)
        break
    except asyncio.TimeoutError:
        if attempt == max_retries - 1:
            return self._build_fallback_summary(data), -1
        await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

### 7. Silent Exception Swallowing

**Issue:** Errors not reported to monitoring
**Impact:** Hidden failures, no visibility

```
File: /app/api/v2/routers/ai/humanize.py
Lines: 199-211

except Exception as e:
    logger.error(f"Humanize error: {e}", exc_info=True)
    return HumanizeResponse(...)  # ❌ Silent fallback
```

**Fix:**
```python
except Exception as e:
    logger.error(f"Humanize error: {e}", exc_info=True)

    # ✅ Alert monitoring
    sentry_sdk.capture_exception(e)
    increment_ai_failure_metric("humanize")

    # Check circuit breaker
    if check_circuit_breaker_state("ai_humanize"):
        raise HTTPException(503, "AI service unavailable")

    return HumanizeResponse(...)  # Fallback with warning
```

---

## 🔧 MEDIUM PRIORITY (P2 - Next Sprint)

### 8. Singleton Cleanup Missing

**Issue:** Resources not released on service reset
**Impact:** Memory leaks in tests, long-running processes

```
File: /app/services/ai/ai_service.py
Lines: 791-796

async def reset_ai_service():
    global _ai_service
    async with _ai_service_lock:
        _ai_service = None  # ❌ No cleanup
```

**Fix:**
```python
async def reset_ai_service():
    global _ai_service
    async with _ai_service_lock:
        if _ai_service:
            # ✅ Clean up resources
            if _ai_service.cache:
                await _ai_service.cache.close()
            _ai_service.orchestrator = None
        _ai_service = None
```

---

### 9. Cache Entry References Not Released

**Issue:** Large objects kept in memory during eviction
**Impact:** Higher memory footprint

```
File: /app/services/ai/cache_layer/__init__.py
Lines: 350-361

while len(self._entries) >= self.max_local_entries:
    oldest_key, oldest_entry = self._entries.popitem(last=False)
    # ❌ oldest_entry.value not explicitly cleared
```

**Fix:**
```python
oldest_key, oldest_entry = self._entries.popitem(last=False)
oldest_entry.value = None  # ✅ Release reference
del oldest_entry  # Help GC
```

---

### 10. Cache Poisoning Risk

**Issue:** No user isolation in cache keys
**Impact:** Potential PII leakage

```
File: /app/integrations/gemini_client.py
Lines: 78-81

def _generate_cache_key(self, prompt: str) -> str:
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    return f"gemini_cache:{prompt_hash}"  # ❌ No user context
```

**Fix:**
```python
def _generate_cache_key(self, prompt: str, user_id: str = None) -> str:
    key_components = [prompt]
    if user_id:
        key_components.append(user_id)  # ✅ User isolation

    key_string = ":".join(key_components)
    prompt_hash = hashlib.sha256(key_string.encode()).hexdigest()
    return f"gemini_cache:{user_id or 'anon'}:{prompt_hash}"
```

---

## 📊 CODE SMELLS (P3 - Technical Debt)

### 11. God Object - AIService

**Issue:** Too many responsibilities in one class
**Impact:** Hard to test, maintain

```
File: /app/services/ai/ai_service.py
Lines: 1-796 (entire file)
Methods: 30+ (humanize, sentiment, intent, concerns, cache, context)
```

**Recommendation:**
```
Split into:
- HumanizationService (ai_service.py:156-304)
- SentimentAnalysisService (ai_service.py:309-531)
- IntentClassificationService (ai_service.py:536-581)
- ConcernDetectionService (ai_service.py:586-624)
- PatientContextBuilder (ai_service.py:651-697)
```

---

### 12. Feature Envy - Cache Key Building

**Issue:** Multiple services know how to build cache keys
**Impact:** Duplication, maintenance burden

```
Files:
- /app/services/ai/ai_service.py:702-715
- /app/services/ai/batch_processor.py:421-441

Both implement similar _build_cache_key() methods
```

**Fix:**
```python
# Move to CacheLayer
class CacheLayer:
    async def get_for_operation(
        self, operation: CacheOperation, **kwargs
    ) -> Any:
        key = self._build_key_from_args(operation, kwargs)
        return await self.get(key, operation)
```

---

### 13. Magic Numbers

**Issue:** Constants hardcoded throughout code
**Impact:** Hard to maintain, configure

```
File: /app/services/ai/ai_service.py
Lines: 227-228, 233-234, 380-381

max_tokens=TokenLimiter.DEFAULT_MAX_TOKENS,  # 500 tokens
max_tokens=TokenLimiter.MESSAGE_MAX_TOKENS,  # 100 tokens
max_tokens=TokenLimiter.CONTEXT_MAX_TOKENS,  # 300 tokens
```

**Fix:**
```python
# At module level
MAX_CONTEXT_TOKENS = 500
MAX_MESSAGE_TOKENS = 100
MAX_RESPONSE_HISTORY_TOKENS = 100

# Usage
limited_context = self.token_limiter.limit_patient_context(
    patient_context.to_dict(),
    max_tokens=MAX_CONTEXT_TOKENS,
)
```

---

## 🧪 TESTING GAPS

### Critical Test Cases Missing

```python
# tests/services/ai/test_ai_service_async.py

async def test_concurrent_initialization_no_race():
    """Issue: Race condition in singleton pattern"""
    # File: /app/services/ai/ai_service.py:765-789
    tasks = [get_ai_service() for _ in range(10)]
    services = await asyncio.gather(*tasks)
    assert all(s is services[0] for s in services)

async def test_memory_cleanup_on_reset():
    """Issue: Memory leaks in reset"""
    # File: /app/services/ai/ai_service.py:791-796
    import tracemalloc
    tracemalloc.start()

    service = await get_ai_service()
    snapshot1 = tracemalloc.take_snapshot()

    await reset_ai_service()
    gc.collect()

    snapshot2 = tracemalloc.take_snapshot()
    # Verify memory released
    assert sum(s.size_diff for s in snapshot2.compare_to(snapshot1, 'lineno')) < 1024

async def test_timeout_handling_redis_down():
    """Issue: No timeout on initialization"""
    # File: /app/services/ai/ai_service.py:136-151
    with patch('app.core.redis_unified.get_sync_redis', side_effect=ConnectionError):
        with pytest.raises(ExternalServiceError, match="timeout"):
            await get_ai_service()

async def test_batch_processing_partial_failure():
    """Issue: Batch error handling"""
    # File: /app/services/ai/batch_processor.py:277-303
    # Test partial failures in batch don't break entire batch
```

---

## 📁 File Index

### Core AI Services
```
/app/services/ai/
├── ai_service.py              # 796 lines - Main AI service
│   ├── Lines 136-151         # ⚠️ Issue #4: No timeout on init
│   ├── Lines 156-304         # Humanization logic
│   ├── Lines 309-531         # Sentiment analysis
│   ├── Lines 702-715         # 📊 Issue #12: Cache key duplication
│   └── Lines 791-796         # 🔧 Issue #8: Missing cleanup
│
├── batch_processor.py         # 621 lines - Parallel processing
│   ├── Lines 305-360         # ⚠️ Issue #5: Missing cache timeout
│   ├── Lines 421-441         # 📊 Issue #12: Cache key duplication
│   └── Lines 277-303         # Batch execution logic
│
├── patient_summary_service.py # 497 lines - Summary generation
│   ├── Lines 156-202         # ⚠️ Issue #6: No retry logic
│   └── Lines 318-346         # Cache check logic
│
└── cache_layer/__init__.py    # 433 lines - Unified cache
    ├── Lines 185-190         # 🚨 Issue #2: Missing cache cleanup
    ├── Lines 349-365         # 🔧 Issue #9: Memory references
    └── Lines 416-421         # 🚨 Issue #1: Orphaned tasks
```

### API Routes
```
/app/api/v2/routers/ai/
├── humanize.py               # Message humanization endpoint
│   └── Lines 199-211        # ⚠️ Issue #7: Silent exceptions
├── summary.py                # Patient summary endpoint
├── analysis.py               # Analysis endpoints
└── dependencies.py           # Shared dependencies
```

### Integrations
```
/app/integrations/
├── openai_client.py          # LangChain orchestrator
│   └── Lines 125-136        # Model initialization
├── gemini_client.py          # Gemini client
    ├── Lines 78-81          # 🔧 Issue #10: Cache poisoning risk
    └── Lines 86-89          # 🚨 Issue #3: Sync Redis in async
```

---

## 🎯 Priority Matrix

| Priority | Issues | Est. Hours | Risk |
|----------|--------|------------|------|
| **P0** | #1, #2, #3 | 16h | High |
| **P1** | #4, #5, #6, #7 | 30h | Medium |
| **P2** | #8, #9, #10 | 16h | Low |
| **P3** | #11, #12, #13 | 12h | Low |

**Total Technical Debt:** ~74 hours

---

## 🔍 Search Patterns

Use these patterns to find related issues:

```bash
# Find all orphaned tasks
grep -r "create_task" --include="*.py" | grep -v "await"

# Find sync Redis calls in async code
grep -r "self.redis_client\." --include="*.py" | grep -v "await"

# Find missing timeouts on asyncio operations
grep -r "await.*\(get\|set\|call\)" --include="*.py" | grep -v "timeout"

# Find broad exception handlers
grep -r "except Exception" --include="*.py"

# Find magic numbers
grep -r "max_tokens=[0-9]" --include="*.py"
```

---

**Quick Reference Generated:** 2025-12-22
**Total Issues:** 13 documented
**Files Analyzed:** 8
**Lines Reviewed:** ~3000
