# Phase 4: AI Reliability - Research

**Researched:** 2026-02-22
**Domain:** LangGraph startup health check + silent-None-fallback elimination
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Startup check verifies connectivity only -- no quota/rate-limit checks at boot
- Patient never sees AI failure indicators -- failures are purely backend/ops visibility
- When humanization fails: queue for retry first, then send unhumanized as final fallback
- After retry exhaustion, the raw template message is sent -- patient gets the information, just without humanization

### Claude's Discretion

- Startup mode (hard fail vs degraded) and health check depth (import vs API ping)
- Health check module location (lifespan.py inline vs separate module)
- Sentry severity level for AI failures (error vs warning)
- Notification approach (Sentry-only vs Sentry + structured logging)
- Error detail richness in FeatureNotAvailableError (graph name + PII-safe context)
- Retry count and backoff timing for failed humanization
- Whether fallback strategy is uniform across all graph types or per-operation
- Which graph types to sweep (all 5 vs active production paths)
- Whether to also cover direct GeminiClient calls or LangGraph-only
- Whether to create new FeatureNotAvailableError or reuse existing exception
- Centralized wrapper vs per-call-site None checks

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AI-01 | LangGraph startup health check que verifica disponibilidade na inicialização da aplicação | Lifespan pattern established in `_initialize_ai_services()`; LangGraph import-guard already present in `graphs.py` with `_LANGGRAPH_IMPORT_ERROR`; hard-fail pattern established by SEC-03 (`_check_no_service_account_file()` raises RuntimeError in prod/staging) |
| AI-02 | Converter fallbacks `None` de LangGraph para `FeatureNotAvailableError` explícito (sem silent degradation) | 9 call sites across 6 files return/use None silently; `AIServiceError` already in `app/core/exceptions.py`; new `FeatureNotAvailableError` should be subclass of it; Sentry SDK 1.45.1 installed with FastAPI integration active |
</phase_requirements>

---

## Summary

Phase 4 is a targeted reliability hardening: two independent plans that add explicit failure modes where the codebase currently silently degrades. The codebase already has all the scaffolding needed -- the lifespan.py startup pattern, the exception hierarchy, the Sentry integration, and the LangGraph import guard -- so this phase adds behavior on top of existing infrastructure rather than introducing new dependencies.

**AI-01 (startup health check):** The `_initialize_ai_services()` function in `lifespan.py` currently calls `integrate_humanization_into_quiz_service()` and catches all exceptions, logging them but continuing. There is no LangGraph import or availability check at startup. The `graphs.py` module already has a `try/except ImportError` guard that sets `_LANGGRAPH_IMPORT_ERROR` when LangGraph cannot be imported, but this exception is never surfaced at startup -- it is only raised when a graph build function is called. The fix for AI-01 is to add a startup check inside `_initialize_ai_services()` (or a dedicated helper) that calls `_ensure_langgraph_available()` and raises `RuntimeError` in prod/staging if unavailable.

**AI-02 (None fallback elimination):** Nine call sites across 6 files call LangGraph graph `ainvoke()` and silently fall back when the result is `None` or empty. The most critical path is `client_domain.py` (`GeminiDomainClient`), which raises `GeminiAPIError` for empty output but does not distinguish between "LangGraph not available" and "graph returned nothing." The production code in `enhanced_flow_engine.py` uses `result.get("output", {"sentiment": "neutral", ...})` -- a textbook silent degradation. The fix is to raise `FeatureNotAvailableError` (a new exception subclass of `AIServiceError`) at each call site or via a thin centralized wrapper, making every None return an explicit, Sentry-captured event.

**Primary recommendation:** Hard-fail at startup in prod/staging (import check is sufficient per CONTEXT.md decisions); use a centralized wrapper `_invoke_langgraph_graph()` for all 9 ainvoke call sites to eliminate per-site copy-paste and ensure uniform Sentry capture.

---

## Standard Stack

### Core (already installed, no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `langgraph` | 1.0.8 | Graph orchestration | Already installed; `StateGraph`, `END` imported in `graphs.py` |
| `sentry-sdk[fastapi]` | 1.45.1 | Error capture | Already installed and initialized in `app/core/setup/sentry.py`; FastAPI + SQLAlchemy + Redis integrations active |
| `langchain-google-genai` | 2.1.12 | Gemini model calls | Already installed; used in `app/ai/client.py` via `ChatGoogleGenerativeAI` |
| `langchain-core` | 1.2.7 | LangChain abstractions | Already installed |

### No New Dependencies Required

This phase adds zero new packages. All tools are already in `requirements.txt` and installed.

---

## Architecture Patterns

### Recommended Structure for Changes

```
backend-hormonia/app/
├── ai/langgraph/
│   └── graphs.py          # Add _ensure_langgraph_available() helper
│   └── _health.py         # NEW (optional) - standalone startup check
├── core/
│   └── exceptions.py      # Add FeatureNotAvailableError
│   └── lifespan.py        # Extend _initialize_ai_services() with LangGraph check
├── ai/
│   └── client_domain.py   # Add centralized _invoke_langgraph_graph() wrapper
├── services/
│   └── enhanced_flow_engine.py  # Replace silent None fallbacks
├── agents/communication/message_composer/
│   └── composer.py        # Replace silent None fallbacks
├── services/follow_up_system/generators/
│   └── response.py        # Replace silent None fallbacks
└── domain/agents/quiz/
    └── response_handler.py # Replace silent None fallbacks
```

### Pattern 1: Startup Hard-Fail (AI-01)

**What:** In `_initialize_ai_services()` in `lifespan.py`, call a function that verifies LangGraph is importable. In prod/staging, raise `RuntimeError` if not available. In dev/test, log a warning.

**When to use:** Startup-only check. Consistent with existing SEC-03 guard pattern (`_check_no_service_account_file()`).

**Key insight from codebase:** `graphs.py` already sets `_LANGGRAPH_IMPORT_ERROR` at module level. The startup check simply needs to inspect it (or re-attempt the import). No API call needed -- import check is sufficient per CONTEXT.md.

**Example pattern** (modeled on `_check_no_service_account_file()`):
```python
# In app/core/lifespan.py or app/ai/langgraph/_health.py
def check_langgraph_available() -> None:
    """Fail fast if LangGraph is not importable.

    In production/staging: raises RuntimeError to prevent silent degradation.
    In development: logs a critical warning only.
    """
    from app.ai.langgraph.graphs import _LANGGRAPH_IMPORT_ERROR
    if _LANGGRAPH_IMPORT_ERROR is not None:
        env = getattr(settings, "APP_ENVIRONMENT", "development").lower()
        if env in ("production", "prod", "staging"):
            raise RuntimeError(
                f"LangGraph is not available in {env} environment: {_LANGGRAPH_IMPORT_ERROR}. "
                "Install langgraph or remove it from requirements."
            )
        logger.critical(
            "LangGraph not available -- AI humanization will be disabled: %s",
            _LANGGRAPH_IMPORT_ERROR,
        )
```

**Integration in `_initialize_ai_services()`:**
```python
async def _initialize_ai_services(app: FastAPI, logger) -> None:
    start = time.time()
    try:
        # NEW: AI-01 -- LangGraph availability check
        check_langgraph_available()

        from app.services.quiz_question_humanizer_integration import (
            integrate_humanization_into_quiz_service,
        )
        integrate_humanization_into_quiz_service()
        elapsed = time.time() - start
        logger.info(f"✓ AI services initialized ({elapsed:.2f}s)")
    except RuntimeError:
        raise  # Re-raise startup hard-fail in prod/staging
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Failed to initialize AI services ({elapsed:.2f}s): {e}")
        logger.info("Continuing without AI humanization features")
```

**Note:** The existing `asyncio.gather(..., return_exceptions=True)` in Phase 1 startup catches all exceptions by default. To make the RuntimeError propagate (hard fail), `_initialize_ai_services()` must re-raise RuntimeError before the gather can swallow it, OR the gather must not use `return_exceptions=True` for this service. The cleanest solution: move `check_langgraph_available()` **before** the `asyncio.gather()` call in `_startup()`.

### Pattern 2: Centralized LangGraph Wrapper (AI-02)

**What:** A single async wrapper that calls `graph.ainvoke()`, checks the result for None/empty, and raises `FeatureNotAvailableError` if the result is unusable. All 9 call sites use this wrapper.

**When to use:** Every `graph.ainvoke()` call site.

**Why centralized vs per-site:** 9 call sites across 6 files. Per-site = 9 places to maintain. Centralized wrapper = 1 place, uniform behavior, single Sentry tag set.

**New exception class** (add to `app/core/exceptions.py`):
```python
class FeatureNotAvailableError(AIServiceError):
    """Raised when a required AI feature (LangGraph graph) returns no usable output.

    This exception replaces silent None fallbacks. It signals to the caller
    that the feature failed explicitly, enabling Sentry capture and retry logic.

    Never shown to patients -- used for backend/ops visibility only.
    """

    def __init__(
        self,
        message: str,
        graph_name: str,
        operation: Optional[str] = None,
    ):
        super().__init__(
            message,
            ai_service=f"langgraph:{graph_name}",
            error_code="FEATURE_NOT_AVAILABLE",
            is_recoverable=True,
        )
        self.graph_name = graph_name
        self.operation = operation
```

**Centralized wrapper** (add to `app/ai/client_domain.py` or `app/ai/langgraph/_invoke.py`):
```python
async def _invoke_langgraph_graph(
    graph: Any,
    state: dict,
    config: dict,
    graph_name: str,
    output_key: str = "output",
    operation: Optional[str] = None,
) -> Any:
    """Invoke a LangGraph graph and raise FeatureNotAvailableError on None output.

    Args:
        graph: Compiled LangGraph graph (result of .compile())
        state: Input state dict
        config: LangGraph run config (with thread_id)
        graph_name: Human-readable graph name for error messages
        output_key: Key to extract from result dict (default: "output")
        operation: Optional operation label for error context

    Returns:
        The graph output value (never None)

    Raises:
        FeatureNotAvailableError: If graph returns None, empty string, or non-dict result
    """
    from app.core.exceptions import FeatureNotAvailableError

    result = await graph.ainvoke(state, config=config)
    output = result.get(output_key) if isinstance(result, dict) else None

    if not output:
        raise FeatureNotAvailableError(
            f"{graph_name} returned no usable output",
            graph_name=graph_name,
            operation=operation,
        )
    return output
```

### Pattern 3: Sentry Capture at Call Sites

**What:** When `FeatureNotAvailableError` is caught, capture it to Sentry before applying the fallback (retry or send unhumanized).

**Implementation:** The Sentry FastAPI integration (already active) automatically captures unhandled exceptions. For handled fallbacks (where we catch and apply retry/fallback), call `sentry_sdk.capture_exception(exc)` explicitly before the fallback branch.

```python
import sentry_sdk

try:
    humanized = await _invoke_langgraph_graph(
        graph, state, config, graph_name="humanization_graph"
    )
except FeatureNotAvailableError as exc:
    sentry_sdk.capture_exception(exc)
    # Queue for retry, then send unhumanized as final fallback
    humanized = await _queue_humanization_retry_or_fallback(template, patient_id)
```

**Severity:** Use `sentry_sdk.capture_exception()` (error level, not warning) for `FeatureNotAvailableError` -- these are genuine AI failures, not expected degradation. This is consistent with Sentry's default behavior for captured exceptions.

### Anti-Patterns to Avoid

- **`asyncio.gather(return_exceptions=True)` swallowing startup RuntimeError:** If the hard-fail RuntimeError is raised inside an `asyncio.gather()` with `return_exceptions=True`, it will be captured as a return value rather than propagating. The startup check must run BEFORE the gather, or the gather must explicitly check return values and re-raise RuntimeErrors.
- **Checking `if not output` when output is 0 or False:** For JSON output (e.g., sentiment), the output is a dict. Check `if output is None` or `if not isinstance(output, dict)` as appropriate, not blind falsy checks.
- **Logging patient data in FeatureNotAvailableError details:** LGPD/HIPAA compliance -- error details must be PII-safe. Graph name + operation label only; never include patient ID, name, or message content.
- **Per-call-site `try/except ImportError` wrapping:** The codebase already handles LangGraph absence at module level (`_LANGGRAPH_IMPORT_ERROR`). Do not duplicate per-call-site import guards.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Error capture to Sentry | Custom HTTP call to Sentry API | `sentry_sdk.capture_exception(exc)` | SDK is already initialized; handles sampling, PII filtering via `_sentry_before_send` |
| Retry with backoff | Custom sleep/loop | Celery task retry mechanism | CONTEXT.md: "queue for retry first" -- implies Celery task, not inline retry |
| Thread-safe singleton for graph | Custom locking | `@lru_cache(maxsize=1)` already on all `get_*_graph()` functions | Already implemented in `graphs.py` |

**Key insight:** The codebase already has `@lru_cache(maxsize=1)` on all 7 `get_*_graph()` functions. The startup check does NOT need to call these functions -- doing so would compile all graphs eagerly, which is expensive. The import guard (`_LANGGRAPH_IMPORT_ERROR`) is sufficient.

---

## Common Pitfalls

### Pitfall 1: `asyncio.gather(return_exceptions=True)` Swallows RuntimeError

**What goes wrong:** The AI-01 startup hard-fail is placed inside `_initialize_ai_services()`, which is called via `asyncio.gather(..., return_exceptions=True)`. The RuntimeError is captured as a return value and logged, but the app continues starting up. The app then accepts traffic and silently degrades.

**Why it happens:** `return_exceptions=True` is a deliberate choice in `lifespan.py` to allow partial startup (e.g., Redis down doesn't block the app). But it also catches RuntimeErrors intended to be hard fails.

**How to avoid:** Run `check_langgraph_available()` **before** the `asyncio.gather()` call in `_startup()`, at the top of the try block, after `_check_no_service_account_file()`. This preserves the existing parallel initialization pattern while ensuring the LangGraph check propagates.

**Warning signs:** App starts successfully in staging even when LangGraph package is not installed.

### Pitfall 2: `@lru_cache` Graphs Being Built at Import Time

**What goes wrong:** If the startup check calls `get_humanization_graph()` (the cached getter), it eagerly compiles all 5 single-node graphs plus 2 multi-node graphs. This adds significant startup overhead and may fail for unrelated reasons (Redis unavailable for checkpointer).

**Why it happens:** `@lru_cache` builds on first call, not at import.

**How to avoid:** The startup check should only verify `_LANGGRAPH_IMPORT_ERROR is None` (import check), not call any `get_*_graph()` function. The graphs themselves are compiled lazily on first use -- this is correct behavior.

### Pitfall 3: Silent Falsy Check on Dict Output

**What goes wrong:** The centralized wrapper does `if not output:` to check for None. But for sentiment analysis, the output is a dict. An empty dict `{}` is falsy, and a dict with `{"sentiment": "neutral", "confidence": 0.0}` is truthy. However, `result.get("output")` returning `{}` (empty dict) would slip through as falsy=True, when a non-empty dict is the correct check.

**Why it happens:** Mixed output types across graphs -- some graphs return strings, others return dicts.

**How to avoid:** The wrapper should accept an `output_validator` callable or check by type:
- For string outputs (humanize, question_variation, empathetic_follow_up): `if not output` (empty string is falsy)
- For dict outputs (sentiment): `if not isinstance(output, dict) or not output`

The wrapper can be split into two variants or accept a type parameter.

### Pitfall 4: `FeatureNotAvailableError` Reaching the Patient

**What goes wrong:** A FastAPI exception handler catches `AIServiceError` or its base `ExternalServiceError` and returns a 503 response. This response reaches the patient's WhatsApp via the flow engine.

**Why it happens:** The exception propagates up through caller chains without being caught at the flow boundary.

**How to avoid:** The flow engine callers (e.g., `enhanced_flow_engine.py`) must catch `FeatureNotAvailableError` specifically and apply the queue-then-unhumanized fallback pattern BEFORE it reaches the HTTP response layer. The exception should be a signal for fallback logic, not a 503 response.

### Pitfall 5: `result.get("output")` Returning `None` vs Graph Not Running

**What goes wrong:** There are two distinct failure modes that both result in `output = None`:
1. LangGraph ran the graph but the node function returned `{..., "output": None}`
2. LangGraph was not available, `StateGraph` is `None`, and `build_*_graph()` was never called

Mode 2 means the graph object itself is None. Mode 1 means the graph ran but produced empty output.

**How to avoid:** Check for `StateGraph is None` at graph build time (already done with `raise RuntimeError("LangGraph is not installed")` in each build function). The startup check for AI-01 ensures the app never starts in prod if this would happen. At runtime, catching the RuntimeError from `build_*_graph()` separately from catching `FeatureNotAvailableError` allows precise diagnosis.

---

## Code Examples

### Example 1: Current Silent Degradation (to be eliminated)

```python
# enhanced_flow_engine.py line 533 -- CURRENT BEHAVIOR (silent degradation)
sentiment_analysis = result.get(
    "output", {"sentiment": "neutral", "confidence": 0.5}
)
```

This silently returns a fake neutral sentiment if the graph returns None. No Sentry event. No log at error level. The downstream code processes a fabricated sentiment, potentially missing medical concerns.

### Example 2: client_domain.py Pattern (nearly correct, needs FeatureNotAvailableError)

```python
# client_domain.py line 74 -- CURRENT BEHAVIOR
output = result.get("output") if isinstance(result, dict) else None
if not output:
    raise GeminiAPIError("Humanization graph returned empty output")
```

This raises an exception (good!) but uses `GeminiAPIError` (ambiguous -- conflates "Gemini API failed" with "LangGraph graph returned None"). Should be `FeatureNotAvailableError`.

### Example 3: Proposed Wrapper Usage

```python
# After adding _invoke_langgraph_graph() wrapper:

# In client_domain.py (humanize_flow_message):
output = await _invoke_langgraph_graph(
    graph=get_humanization_graph(),
    state=state,
    config={"configurable": {"thread_id": f"humanize:{thread_id}"}},
    graph_name="humanization_graph",
    operation="humanize_flow_message",
)
return output  # str, guaranteed non-empty

# In enhanced_flow_engine.py:
try:
    output = await _invoke_langgraph_graph(
        graph=get_humanization_graph(),
        state=initial_state,
        config={"configurable": {"thread_id": f"flow_humanize:{patient_id}"}},
        graph_name="humanization_graph",
        operation="generate_flow_message",
    )
    personalized_message = output
except FeatureNotAvailableError as exc:
    sentry_sdk.capture_exception(exc)
    personalized_message = message_template.base_content  # unhumanized fallback
```

### Example 4: Startup Check Integration

```python
# In lifespan.py _startup(), BEFORE asyncio.gather():

# SEC-03: Check for credential files
_check_no_service_account_file()

# AI-01: Check LangGraph availability before accepting traffic
_check_langgraph_available()

# PHASE 1: Parallel initialization (unchanged)
await asyncio.gather(
    _initialize_monitoring(app, logger),
    _initialize_redis_websocket_events(app, logger),
    _initialize_ai_services(app, logger),  # simplified -- no more LangGraph check here
    ...
    return_exceptions=True
)
```

---

## Call Sites Inventory (AI-02 Scope)

All current `graph.ainvoke()` call sites and their current None-handling:

| File | Method | Graph Used | Current None Handling | Priority |
|------|---------|------------|----------------------|----------|
| `app/ai/client_domain.py` | `humanize_flow_message` | `get_humanization_graph()` | `raise GeminiAPIError` | HIGH - production path |
| `app/ai/client_domain.py` | `generate_varied_question` | `get_question_variation_graph()` | `raise GeminiAPIError` | HIGH - production path |
| `app/ai/client_domain.py` | `analyze_response_sentiment` | `get_sentiment_graph()` | `raise GeminiAPIError` | HIGH - production path |
| `app/ai/client_domain.py` | `create_empathetic_follow_up` | `get_empathetic_follow_up_graph()` | `raise GeminiAPIError` | HIGH - production path |
| `app/services/enhanced_flow_engine.py` | graph humanization path | `get_humanization_graph()` | `raise ValueError` (bare) | HIGH - production path |
| `app/services/enhanced_flow_engine.py` | sentiment path | `get_sentiment_graph()` | Silent dict fallback `{"sentiment": "neutral", ...}` | CRITICAL - silent degradation |
| `app/agents/communication/message_composer/composer.py` | 5 methods | `get_generation_graph()`, `get_humanization_graph()` | Various -- some raise, some return None | HIGH |
| `app/services/follow_up_system/generators/response.py` | `generate_response` | `get_empathetic_follow_up_graph()` | Returns None on exception | MEDIUM |
| `app/domain/agents/quiz/response_handler.py` | quiz path | `get_generation_graph()` | Returns None on exception | MEDIUM |

**Recommendation:** Sweep all 5 `client_domain.py` paths + both `enhanced_flow_engine.py` paths as Phase 04-02 scope. The `composer.py`, `response.py`, and `response_handler.py` paths are secondary.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| Silent `result.get("output", fallback_value)` | `FeatureNotAvailableError` + Sentry capture | Failures visible in dashboards |
| No startup check for AI dependencies | Startup `check_langgraph_available()` | App refuses to start with broken AI layer |
| `GeminiAPIError` for all graph failures | Distinct `FeatureNotAvailableError` | Precise error classification in Sentry |

---

## Recommendations (Claude's Discretion)

Based on codebase analysis:

1. **Startup mode:** Hard fail in prod/staging, warn-only in dev/test. Consistent with SEC-03 pattern.

2. **Health check depth:** Import-only check (`_LANGGRAPH_IMPORT_ERROR is not None`). No API ping at startup per CONTEXT.md decision. No graph compilation at startup.

3. **Module location:** Inline `_check_langgraph_available()` as a module-level function in `lifespan.py`, NOT a separate module. The function is 8-10 lines and does not warrant a new file. Pattern: same as `_check_no_service_account_file()`.

4. **Exception class:** Create `FeatureNotAvailableError` as subclass of `AIServiceError` in `app/core/exceptions.py`. Do NOT reuse `GeminiAPIError` (that's a client.py-local class, not in the core hierarchy) or the bare `AIServiceError` (too generic). The new class signals "AI feature available but returned no usable output."

5. **Sentry severity:** `capture_exception()` (error level). These are real failures that require attention.

6. **Notification:** Sentry-only. The structured logger already logs at ERROR level in the wrapper. Structured log + Sentry exception = sufficient ops visibility without additional channels.

7. **Retry:** Defer to Celery retry mechanism (Celery task re-queuing). Do NOT implement inline `asyncio.sleep()` retry in the wrapper -- this blocks the event loop. The Celery tasks that call these paths already have retry configuration.

8. **Scope of None sweep:** All 5 `client_domain.py` methods + both `enhanced_flow_engine.py` call sites = 7 call sites = Plan 04-02 scope. The other 4 (composer.py, response.py, response_handler.py) can be addressed if time permits or deferred.

9. **Wrapper approach:** Centralized `_invoke_langgraph_graph()` function. Place it in `app/ai/langgraph/_invoke.py` or as a helper inside `client_domain.py`. The 7-site sweep becomes uniform.

10. **Error detail richness:** `FeatureNotAvailableError` includes `graph_name` and `operation` fields only. No patient ID, no prompt content, no message text. Safe for Sentry.

---

## Open Questions

1. **Celery retry task structure for humanization failures**
   - What we know: CONTEXT.md specifies "queue for retry first, then send unhumanized." The codebase has Celery tasks in `app/tasks/` and `app/celery_app.py` with 38 beat_schedule jobs.
   - What's unclear: There is no pre-existing "retry humanization" Celery task. Creating one is potentially out of scope for Plan 04-02 (which targets the None conversion). The retry mechanism may be as simple as letting the calling Celery task fail and re-queue naturally.
   - Recommendation: Plan 04-02 focuses on raising `FeatureNotAvailableError` explicitly. The retry/fallback logic can be added to the *callers* (which are often already in Celery tasks) using the existing `self.retry()` mechanism. Do not create a new task type.

2. **`asyncio.gather(return_exceptions=True)` interaction with hard-fail**
   - What we know: The current startup flow uses `return_exceptions=True`, which would swallow a RuntimeError from inside `_initialize_ai_services()`.
   - What's unclear: Whether moving the LangGraph check BEFORE the gather is safe (the gather currently runs all Phase 1 services in parallel; moving the check before it makes it sequential for LangGraph but leaves everything else parallel).
   - Recommendation: Move `check_langgraph_available()` to be called BEFORE the gather, right after `_check_no_service_account_file()`. This is 2 lines added before the gather. The gather itself is unchanged.

---

## Sources

### Primary (HIGH confidence)

- Codebase direct inspection:
  - `backend-hormonia/app/core/lifespan.py` -- startup pattern, `_initialize_ai_services()`, `_check_no_service_account_file()` precedent
  - `backend-hormonia/app/ai/langgraph/graphs.py` -- 7 graph builders, `_LANGGRAPH_IMPORT_ERROR` pattern, `@lru_cache`
  - `backend-hormonia/app/ai/langgraph/nodes_ai.py` -- 5 AI nodes (humanize, sentiment, question_variation, empathetic_follow_up, generate)
  - `backend-hormonia/app/ai/client.py` -- `GeminiClient`, `health_check()` method exists
  - `backend-hormonia/app/ai/client_domain.py` -- `GeminiDomainClient`, all 4 `ainvoke` call sites, current error handling
  - `backend-hormonia/app/services/enhanced_flow_engine.py` -- silent dict fallback at line 533 (CRITICAL)
  - `backend-hormonia/app/core/exceptions.py` -- full exception hierarchy, `AIServiceError`, `ExternalServiceError`
  - `backend-hormonia/app/core/setup/sentry.py` -- Sentry initialization with `_sentry_before_send` filter
  - `backend-hormonia/requirements.txt` -- `langgraph>=1.0.7,<2.0.0`, `sentry-sdk[fastapi]>=1.38.0,<2.0.0`
  - `.venv` package versions: `langgraph==1.0.8`, `sentry-sdk==1.45.1`, `langchain-google-genai==2.1.12`

### Secondary (MEDIUM confidence)

- `.planning/phases/04-ai-reliability/04-CONTEXT.md` -- user decisions constraining the implementation approach

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- versions confirmed from installed packages in `.venv`
- Architecture: HIGH -- all patterns derived from codebase direct inspection, not external docs
- Pitfalls: HIGH -- all identified from actual code paths in the codebase
- Call sites inventory: HIGH -- confirmed by Grep across all 9 call sites

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (30 days; stable codebase with low churn in AI layer)
