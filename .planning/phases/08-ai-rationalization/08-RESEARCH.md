# Phase 8: AI Rationalization - Research

**Researched:** 2026-02-23
**Domain:** LangGraph single-node graph removal + Gemini circuit breaker integration
**Confidence:** HIGH (all findings from direct codebase inspection, no external sources needed)

## Summary

Phase 8 targets two orthogonal problems: (1) five LangGraph `StateGraph` wrappers around single Gemini calls add overhead and complexity with zero routing benefit, and (2) the existing circuit breaker integration in `GeminiClient.generate_content()` raises a silent `GeminiAPIError("Gemini circuit breaker fallback used")` when the circuit opens, rather than raising `FeatureNotAvailableError` — the canonical signal already defined in `app/core/exceptions.py` and already used in `_invoke.py`.

The solution for AI-03 is to replace each of the five `StateGraph` wrappers with a direct call to the node function logic, inlined into `GeminiDomainClient` methods. The `AIState` schema, all prompt builders, and `generate_content()` remain unchanged; only the LangGraph orchestration layer is removed. The generation graph has additional callers in `MessageComposer` and `ResponseHandler` that invoke `graph.ainvoke()` directly — these must also be migrated.

For AI-04: `GeminiClient.generate_content()` already calls `self._circuit_breaker.call_gemini()`. When the circuit is open and the hardcoded fallback string is returned, `used_fallback=True` triggers `raise GeminiAPIError(...)`. The fix is to map this specific condition to `FeatureNotAvailableError` so callers can catch the canonical exception instead of the generic API error.

**Primary recommendation:** Remove the 5 single-node `StateGraph` objects (graphs.py, `build_*`/`get_*` functions), move their node logic directly into `GeminiDomainClient` methods, migrate `MessageComposer` and `ResponseHandler` direct `.ainvoke()` callers, then fix the circuit-open path to raise `FeatureNotAvailableError`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AI-03 | Simplificar 5 grafos single-node (humanization, sentiment, generation, question_variation, empathetic_follow_up) para chamadas diretas `GeminiClient.generate_content()` | All 5 graphs identified. Exact node functions and their callers mapped. `GeminiClient.generate_content()` already has full circuit breaker + guardrail + cache pipeline — node logic reduces to calling it directly. |
| AI-04 | Adicionar circuit breaker ao redor de chamadas Gemini (FeatureNotAvailableError quando circuit abre) | Circuit breaker already exists (`AIServiceCircuitBreaker.call_gemini()`). It already wraps `generate_content()`. The gap: when circuit opens, `GeminiAPIError` is raised, not `FeatureNotAvailableError`. Fix is a 2-line change in `client.py`. |
</phase_requirements>

---

## The 5 Single-Node Graphs — Complete Map

### Graph 1: `humanization_graph`
**Build function:** `build_humanization_graph()` in `app/ai/langgraph/graphs.py:124`
**Cached getter:** `get_humanization_graph()` — `@lru_cache(maxsize=1)` at line 141
**Node function:** `humanize_node()` in `app/ai/langgraph/nodes_ai.py:174`
**Node logic:** builds humanization prompt via `build_humanization_prompt()`, calls `client.generate_content(prompt, profile=MESSAGE_HUMANIZED)`
**Primary caller:** `GeminiDomainClient.humanize_flow_message()` in `app/ai/client_domain.py:52` — uses `invoke_langgraph_graph()`
**Secondary callers:** `MessageComposer` uses `get_humanization_graph()` via `app/ai/langgraph/graphs.py:11` import (used in `compose_from_flow_template`)

### Graph 2: `sentiment_graph`
**Build function:** `build_sentiment_graph()` in `graphs.py:147`
**Cached getter:** `get_sentiment_graph()` at line 164
**Node function:** `sentiment_node()` in `nodes_ai.py:203`
**Node logic:** calls `compact_patient_context(context)`, builds sentiment prompt via `build_sentiment_prompt()`, calls `client.generate_content(prompt, profile=JSON_SENTIMENT)`, then parses JSON via `_parse_sentiment_analysis()`
**Primary caller:** `GeminiDomainClient.analyze_response_sentiment()` in `client_domain.py:142` — uses `invoke_langgraph_graph(graph, ..., expect_dict=True)`

### Graph 3: `generation_graph`
**Build function:** `build_generation_graph()` in `graphs.py:170`
**Cached getter:** `get_generation_graph()` at line 188
**Node function:** `generate_node()` in `nodes_ai.py:289`
**Node logic:** extracts `prompt=state["input_text"]`, `output_kind`, `profile`, calls `client.generate_content(prompt, profile=profile, output_kind=output_kind, **metadata)`
**Callers (all use direct `.ainvoke()` — NOT `invoke_langgraph_graph`):**
- `app/agents/communication/message_composer/composer.py` — 5 direct `graph.ainvoke()` calls (lines 86, 151, 207, 265, 329)
- `app/domain/agents/quiz/response_handler.py` — `_invoke_interpretation_graph()` at line 373, direct `graph.ainvoke()` call at line 380
**Note:** No `GeminiDomainClient` wrapper exists for the generation graph. These callers invoke the graph directly and read `result.get("output", "")`.

### Graph 4: `question_variation_graph`
**Build function:** `build_question_variation_graph()` in `graphs.py:193`
**Cached getter:** `get_question_variation_graph()` at line 210
**Node function:** `question_variation_node()` in `nodes_ai.py:227`
**Node logic:** builds question variation prompt via `build_question_variation_prompt()`, calls `client.generate_content(prompt, profile=MESSAGE_STANDARD)`, then runs de-duplication logic `_is_too_similar_to_recent()` / `_build_non_repetitive_question()`
**Primary caller:** `GeminiDomainClient.generate_varied_question()` in `client_domain.py:88` — uses `invoke_langgraph_graph()`

### Graph 5: `empathetic_follow_up_graph`
**Build function:** `build_empathetic_follow_up_graph()` in `graphs.py:216`
**Cached getter:** `get_empathetic_follow_up_graph()` at line 233
**Node function:** `empathetic_follow_up_node()` in `nodes_ai.py:261`
**Node logic:** calls `compact_patient_context(context)`, builds empathetic prompt via `build_empathetic_prompt()`, calls `client.generate_content(prompt, profile=MESSAGE_HUMANIZED)`
**Primary caller:** `GeminiDomainClient.create_empathetic_follow_up()` in `client_domain.py:180` — uses `invoke_langgraph_graph()`

---

## Multi-Node Graphs That Must NOT Be Touched

Inspecting all `StateGraph` usages confirms exactly **two multi-node graphs** that must be preserved:

1. **`flow_message_graph`** (`build_flow_message_graph()` in `graphs.py:49`): 2 nodes — `load_flow_context` + `dispatch_send_mode` with conditional routing
2. **`flow_response_graph`** (`build_flow_response_graph()` in `graphs.py:89`): 2 nodes — `load_response_context` + `dispatch_response_continuation` with conditional routing
3. **`consensus_graph`** (`build_consensus_graph()` in `consensus.py:215`): 4 nodes — `prepare_consensus`, `dispatch_consensus_requests`, `collect_votes`, `evaluate_consensus` with conditional loops

These are legitimate multi-step orchestrations. Phase 8 must not touch them.

---

## GeminiClient Interface (What the Nodes Actually Call)

**File:** `app/ai/client.py` — class `GeminiClient`

**Primary method:**
```python
async def generate_content(self, prompt: str, **kwargs) -> str
```

**kwargs accepted:**
- `profile`: `OutputProfile | str | None` — resolved via `resolve_output_profile()`
- `output_kind`: `OutputKind | str | None`
- `min_length`: int
- `max_length`: int
- `required_keys`: iterable of str (for JSON validation)
- `require_ending_punctuation`: bool
- `allow_placeholders`: bool
- `guardrail_retries`: int

**Full pipeline inside `generate_content()`:**
1. PII redaction (`_redact_prompt_for_external_ai`)
2. Semantic cache check (Redis, keyed by prompt hash + profile)
3. Circuit breaker call (`self._circuit_breaker.call_gemini(self._generate_content_internal, ...)`)
4. Guardrail normalization + validation (`normalize_ai_output`, `validate_ai_output`)
5. Cache write

**The circuit breaker is already active on all `generate_content()` calls.** The gap for AI-04 is only in the exception type raised when the circuit opens.

---

## Circuit Breaker — Current State and Gap

**File:** `app/resilience/circuit_breaker/service_breaker.py`
**Primary class:** `CircuitBreaker` (NOT `ProductionCircuitBreaker` from `breaker.py`)
**AI-specific wrapper:** `AIServiceCircuitBreaker` — singleton accessed via `get_ai_circuit_breaker()`

**`AIServiceCircuitBreaker.call_gemini()` signature:**
```python
async def call_gemini(
    self,
    func: Callable,
    prompt: str,
    fallback_response: Optional[str] = None,
    **kwargs,
) -> tuple[str, bool]  # (response, used_fallback)
```

**What happens when circuit is OPEN:**
- `CircuitBreaker.call()` at line 160-172 in `service_breaker.py`: if circuit is open and no reset timeout, calls `_execute_fallback(fallback, ...)` with the hardcoded lambda that returns static strings
- `used_fallback = True` is set in the lambda
- `GeminiClient.generate_content()` receives `(fallback_text, True)` and raises `GeminiAPIError("Gemini circuit breaker fallback used")` (line 602 in `client.py`)

**The gap for AI-04:** Callers of `generate_content()` (including the new direct node logic) receive a generic `GeminiAPIError` when the circuit opens. The canonical exception for this condition is `FeatureNotAvailableError` from `app/core/exceptions.py`. The fix: in `client.py` line 601-602, replace the `GeminiAPIError` raise with `FeatureNotAvailableError`.

**`FeatureNotAvailableError` definition** (`app/core/exceptions.py:730`):
```python
class FeatureNotAvailableError(AIServiceError):
    def __init__(self, message: str, graph_name: str, operation: Optional[str] = None):
        ...
        self.graph_name = graph_name
        self.operation = operation
```
**Note:** This class was designed for LangGraph graphs (`ai_service=f"langgraph:{graph_name}"`). After removing the graphs, the `graph_name` parameter still makes sense as a feature identifier. The class needs no changes.

**Current uses of `FeatureNotAvailableError`:**
- `app/ai/langgraph/_invoke.py` — raises it when graph returns None/empty output
- `app/services/enhanced_flow_engine.py` — catches it (confirmed by grep)

---

## The `invoke_langgraph_graph` Wrapper (AI-02 artifact)

**File:** `app/ai/langgraph/_invoke.py`
**Purpose:** Centralized invocation with None-fallback elimination (implemented in Phase 4 as AI-02)
**Behavior:**
1. Calls `await graph.ainvoke(state, config=config)`
2. Extracts `result.get(output_key)` (default `"output"`)
3. If `expect_dict=True`: validates output is non-empty dict, else validates truthy
4. Raises `FeatureNotAvailableError` on empty/None output

**Post-Phase-8 fate:** After removing the 5 single-node graphs, `invoke_langgraph_graph` becomes unused for AI graph calls. It may still be referenced from `client_domain.py` (which will be rewritten). The wrapper itself can be kept for `flow_message_graph` / `flow_response_graph` / `consensus_graph` if they ever need the pattern, or removed entirely if no callers remain.

---

## AIState Schema (What the Nodes Consumed)

**File:** `app/ai/langgraph/ai_state.py`

```python
class AIState(TypedDict, total=False):
    input_text: str          # Used by: sentiment, question_variation, empathetic, generation
    template: Optional[str]  # Used by: humanize
    context: Dict[str, Any]  # Used by: all nodes
    history: List[str]       # Used by: humanize, question_variation, empathetic, generation
    hints: List[str]         # Used by: humanize
    message_type: Optional[str]
    output_kind: str         # Used by: generation
    output: Any              # RESULT field — extracted by callers
    confidence: float        # RESULT field — set by nodes but not used by callers
    metadata: Dict[str, Any] # Used by: humanize, question_variation, empathetic, generation
    error: Optional[str]
```

After removing graphs, the `AIState` TypedDict becomes unused (no more graph state flowing). The `validate_ai_state()` function can be removed too. Node function signatures change: they no longer receive `AIState`, they receive direct parameters from `GeminiDomainClient` methods.

---

## Prompt Builders (Preserved, Unchanged)

**File:** `app/ai/langgraph/prompts.py`

All 4 builders remain:
- `build_humanization_prompt(template, ai_instructions, recent_interactions=None) -> str`
- `build_question_variation_prompt(base_question, ai_instructions, recent_interactions=None) -> str`
- `build_sentiment_prompt(response, context_snapshot) -> str`
- `build_empathetic_prompt(patient_response, conversation_history, context_snapshot, examples, *, allow_questions, day_complete) -> str`

These are pure functions. After removing graphs, they are called directly from `GeminiDomainClient` methods (same as before, but without the AIState intermediary).

**Generation node** does not use a prompt builder — it uses `state["input_text"]` directly as the prompt.

---

## Output Profiles (Preserved, Unchanged)

**File:** `app/services/ai/output_profiles.py`

Used profiles:
- `MESSAGE_HUMANIZED` — used by humanize and empathetic follow-up
- `MESSAGE_STANDARD` — used by question variation
- `JSON_SENTIMENT` — used by sentiment

These are imported and passed to `generate_content(profile=...)`. No changes needed.

---

## Architecture Patterns

### Pattern 1: Migrating `GeminiDomainClient` Methods (humanize, sentiment, question_variation, empathetic_follow_up)

Current pattern (via graph):
```python
async def humanize_flow_message(self, template, patient_name, patient_context, ...) -> str:
    graph = get_humanization_graph()
    state = {"template": template, "context": {...}, "history": [...], ...}
    output = await invoke_langgraph_graph(graph=graph, state=state, config={...}, graph_name="humanization_graph", ...)
    return output
```

Post-Phase-8 pattern (direct):
```python
async def humanize_flow_message(self, template, patient_name, patient_context, ...) -> str:
    from app.core.exceptions import FeatureNotAvailableError
    context = {**(patient_context or {}), "patient_name": patient_name}
    template = _replace_patient_name(template, patient_name)
    recent_interactions = _coerce_recent_interactions(context.get("recent_interactions"), ...)
    prompt = build_humanization_prompt(template=template, ai_instructions=ai_instructions, recent_interactions=recent_interactions)
    output = await self.generate_content(prompt, profile=MESSAGE_HUMANIZED)
    if not output:
        raise FeatureNotAvailableError("humanization returned no output", graph_name="humanization", operation="humanize_flow_message")
    return output
```

Key insight: All helper functions (`_coerce_recent_interactions`, `_replace_patient_name`, `_is_too_similar_to_recent`, `_build_non_repetitive_question`, `_parse_sentiment_analysis`) currently live in `nodes_ai.py`. They must be accessible from wherever the logic is moved. Options:
- Move them to `client_domain.py` (preferred — locality)
- Move them to a shared `app/ai/helpers.py` module
- Keep `nodes_ai.py` as a helper module (simplest — no renames, just remove the `async def *_node()` wrappers)

### Pattern 2: Migrating `MessageComposer` and `ResponseHandler` (generation graph)

These callers use direct `.ainvoke()`:
```python
graph = get_generation_graph()
result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": ...}})
message = result.get("output", "")
if not message:
    raise ValueError("AI returned empty ...")
```

Post-Phase-8 pattern:
```python
# MessageComposer has self.gemini_client — use it directly
message = await self.gemini_client.generate_content(prompt, profile=profile, output_kind=OutputKind.MESSAGE)
if not message:
    raise ValueError("AI returned empty ...")
```

For `ResponseHandler`, it needs access to a `GeminiClient`. It already uses `get_generation_graph()` implicitly — it needs a client injected or retrieved via `get_gemini_client()`.

### Pattern 3: Fix `FeatureNotAvailableError` in Circuit Breaker Path

Current code in `client.py` (line 601-602):
```python
if used_fallback:
    raise GeminiAPIError("Gemini circuit breaker fallback used")
```

Post-Phase-8:
```python
if used_fallback:
    from app.core.exceptions import FeatureNotAvailableError
    raise FeatureNotAvailableError(
        "Gemini circuit breaker open — feature unavailable",
        graph_name="gemini",
        operation="generate_content",
    )
```

This is a 3-line change that makes the circuit-open signal canonical across all Gemini callers.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Circuit breaking for Gemini | Custom retry/timeout logic | `AIServiceCircuitBreaker.call_gemini()` (already in `generate_content()`) | Already implemented and active |
| Prompt building | Inline prompt strings | `app/ai/langgraph/prompts.py` builders | Already tested, PII-safe |
| Output guardrails | Custom validation | `generate_content(profile=..., output_kind=...)` | Already has full guardrail pipeline |
| Sentiment JSON parsing | Custom JSON parser | `_parse_sentiment_analysis()` in `nodes_ai.py` | Already validated with `AIResponseValidation` |
| De-duplication for question variation | New similarity logic | `_is_too_similar_to_recent()` + `_build_non_repetitive_question()` in `nodes_ai.py` | Already implemented |

---

## Common Pitfalls

### Pitfall 1: Forgetting `MessageComposer` and `ResponseHandler` Direct Callers
**What goes wrong:** Only migrating `GeminiDomainClient` methods while leaving `message_composer/composer.py` and `quiz/response_handler.py` calling `get_generation_graph().ainvoke()` — graphs deleted but callers not updated
**Why it happens:** `generate_node` is not called via `GeminiDomainClient` — it's a direct `.ainvoke()` on the compiled graph
**How to avoid:** Migrate all 6 `graph.ainvoke()` call sites in `MessageComposer` (5) and `ResponseHandler` (1) as part of AI-03

### Pitfall 2: Removing `nodes_ai.py` Helper Functions
**What goes wrong:** Deleting `nodes_ai.py` entirely removes `_coerce_recent_interactions`, `_is_too_similar_to_recent`, `_parse_sentiment_analysis`, etc.
**Why it happens:** `nodes_ai.py` looks like it's only node definitions
**How to avoid:** Keep the helper functions. Either keep `nodes_ai.py` as a helpers module (remove the `async def *_node()` functions but keep the helpers), or move helpers to `client_domain.py` or a shared module. Tests reference `nodes_ai` helpers directly (`test_nodes_question_variation.py` imports `nodes_ai` module).

### Pitfall 3: FeatureNotAvailableError Signature Mismatch
**What goes wrong:** Raising `FeatureNotAvailableError("msg", graph_name="gemini", ...)` but the class requires positional args
**Why it happens:** `FeatureNotAvailableError.__init__(self, message: str, graph_name: str, operation: Optional[str] = None)` — `graph_name` is positional, not keyword-only
**How to avoid:** `raise FeatureNotAvailableError("message", "gemini", "generate_content")` — positional args

### Pitfall 4: `@lru_cache` Graph Functions Still Cached After Deletion
**What goes wrong:** Some test or import path caches a graph reference before deletion; test suite breaks due to stale imports
**Why it happens:** `get_humanization_graph()` etc. are `@lru_cache(maxsize=1)` — cached at module level
**How to avoid:** After removing graph functions, search all imports and remove them. `graphs.py` will still exist for `flow_message_graph` and `flow_response_graph`.

### Pitfall 5: `generate_content` Called Without `profile` in `MessageComposer`
**What goes wrong:** `MessageComposer` currently does `graph.ainvoke({"input_text": prompt, "output_kind": ...})` — the `generate_node` extracts `profile` from metadata. Post-migration, calling `generate_content(prompt)` without a profile means no guardrail profile applied.
**Why it happens:** `MessageComposer` never specifies a profile — relies on `generate_node`'s `metadata.pop("profile", None)` defaulting to None
**How to avoid:** Use `profile=MESSAGE_STANDARD` for message generation calls. Verify guardrail behavior is equivalent.

### Pitfall 6: `instrument_node` / Checkpointer Overhead Removed — Need Log Equivalents
**What goes wrong:** Removing graphs also removes `instrument_node` wrapping which provides `node_start`/`node_end` structured logs. Operations lose traceability.
**Why it happens:** `instrument_node` is a decorator applied in `_add_node()` in `graphs.py`
**How to avoid:** AI-03 does not require maintaining observability parity. The requirement only says "graphs do not exist as StateGraph compiled". Add function-level logging if desired but it's not a blocker.

---

## Code Examples

### Example: Direct `humanize_flow_message` After Graph Removal
```python
# In app/ai/client_domain.py
from app.ai.langgraph.prompts import build_humanization_prompt, _replace_patient_name
from app.ai.langgraph.nodes_ai import _coerce_recent_interactions
from app.services.ai.output_profiles import MESSAGE_HUMANIZED
from app.core.exceptions import FeatureNotAvailableError

async def humanize_flow_message(self, template, patient_name, patient_context,
                                  conversation_history, personalization_hints,
                                  few_shot_examples=None, ai_instructions=None,
                                  strict=False) -> str:
    context = {**(patient_context or {}), "patient_name": patient_name}
    recent_interactions = _coerce_recent_interactions(
        context.get("recent_interactions"),
        fallback_history=conversation_history,
    )
    template = _replace_patient_name(template, patient_name)
    metadata = {"few_shot_examples": few_shot_examples or [], "ai_instructions": ai_instructions}
    prompt = build_humanization_prompt(
        template=template,
        ai_instructions=metadata.get("ai_instructions"),
        recent_interactions=recent_interactions,
    )
    output = await self.generate_content(prompt, profile=MESSAGE_HUMANIZED)
    if not output:
        raise FeatureNotAvailableError(
            "humanization returned no output",
            "humanization",
            "humanize_flow_message",
        )
    logger.info("Message humanized successfully", extra={"operation": "humanize", "patient": patient_name, "template_length": len(template)})
    return output
```

### Example: Direct `analyze_response_sentiment` After Graph Removal
```python
# In app/ai/client_domain.py
from app.ai.langgraph.prompts import build_sentiment_prompt
from app.ai.langgraph.nodes_ai import _parse_sentiment_analysis
from app.ai.context_compactor import compact_patient_context
from app.services.ai.output_profiles import JSON_SENTIMENT
from app.core.exceptions import FeatureNotAvailableError

async def analyze_response_sentiment(self, response, patient_context, strict=False) -> dict:
    context_snapshot = compact_patient_context(patient_context or {})
    prompt = build_sentiment_prompt(response=response, context_snapshot=context_snapshot)
    analysis_text = await self.generate_content(prompt, profile=JSON_SENTIMENT)
    if not analysis_text:
        raise FeatureNotAvailableError(
            "sentiment returned no output",
            "sentiment",
            "analyze_response_sentiment",
        )
    analysis = _parse_sentiment_analysis(analysis_text)
    logger.info("Sentiment analysis completed", extra={"operation": "sentiment"})
    return analysis
```

### Example: Circuit Breaker Fix in `generate_content`
```python
# In app/ai/client.py — change lines 600-602
from app.core.exceptions import FeatureNotAvailableError

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
```

### Example: `MessageComposer` Migration (generation graph → direct call)
```python
# In app/agents/communication/message_composer/composer.py
# Before:
graph = get_generation_graph()
result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": ...}})
message_content = result.get("output", "")

# After:
message_content = await self.gemini_client.generate_content(
    prompt,
    output_kind=OutputKind.MESSAGE,
)
```

---

## Files to Change — Complete List

### AI-03: Remove Single-Node Graphs

| File | Change |
|------|--------|
| `app/ai/langgraph/graphs.py` | Remove 5 `build_*` and 5 `get_*` functions (lines 122-236). Keep `build_flow_message_graph`, `get_flow_message_graph`, `build_flow_response_graph`, `get_flow_response_graph` and their routing helpers. |
| `app/ai/client_domain.py` | Rewrite all 4 methods (`humanize_flow_message`, `generate_varied_question`, `analyze_response_sentiment`, `create_empathetic_follow_up`) to call `generate_content()` directly. Remove `invoke_langgraph_graph` import. |
| `app/agents/communication/message_composer/composer.py` | Replace 5 `graph.ainvoke()` calls with `self.gemini_client.generate_content()`. Remove `get_generation_graph` import. |
| `app/domain/agents/quiz/response_handler.py` | Replace `_invoke_interpretation_graph()` with direct `client.generate_content()`. Inject/obtain GeminiClient. Remove `get_generation_graph` import. |
| `app/ai/langgraph/__init__.py` | Keep `invoke_langgraph_graph` export (still used by flow graphs if needed); or remove if no longer needed. |
| `app/ai/langgraph/nodes_ai.py` | Remove `async def *_node()` functions (5 node wrappers). Keep all helper functions (`_coerce_recent_interactions`, `_is_too_similar_to_recent`, `_parse_sentiment_analysis`, etc.). |
| `app/ai/langgraph/ai_state.py` | Keep `AIState` and `validate_ai_state` — only delete if confirmed no remaining callers after removing node functions. |

### AI-04: Fix Circuit Breaker Exception Type

| File | Change |
|------|--------|
| `app/ai/client.py` | Lines 601-602: replace `raise GeminiAPIError("Gemini circuit breaker fallback used")` with `raise FeatureNotAvailableError(...)`. |

---

## Tests to Add/Update

### For AI-03 (Graph Removal)
- Unit tests in `tests/unit/ai/` for each migrated method in `GeminiDomainClient` — test that `generate_content()` is called with correct prompt and profile (monkeypatch `generate_content`)
- Update `tests/unit/ai/test_nodes_question_variation.py` — currently tests `nodes_ai.question_variation_node()` directly. After removing the node function, these tests either migrate to testing the `GeminiDomainClient.generate_varied_question()` method, or the test module is removed.
- Verify `tests/langgraph/test_state_validation.py` — currently imports `generate_node` from `nodes_ai`. Must update after removing the node function.
- Add integration test: confirm that none of `get_humanization_graph`, `get_sentiment_graph`, `get_generation_graph`, `get_question_variation_graph`, `get_empathetic_follow_up_graph` exist or are importable

### For AI-04 (Circuit Breaker Exception)
- Unit test: when `call_gemini` returns `(text, True)` (used_fallback=True), `generate_content()` raises `FeatureNotAvailableError` not `GeminiAPIError`
- Verify `enhanced_flow_engine.py` catches `FeatureNotAvailableError` correctly (already catches it per grep result — no change needed)

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Direct Gemini SDK calls | LangChain `ChatGoogleGenerativeAI.ainvoke()` | Abstraction already in place |
| Per-graph checkpointer (Redis/Memory) | Per-graph `compile_graph()` with checkpointer | Single-node graphs had checkpointers for no routing benefit — eliminating saves Redis reads/writes |
| `graph.ainvoke(state, config)` → node function → `generate_content()` | Direct `generate_content()` call | One fewer async hop, no state serialization, no checkpoint I/O |
| `GeminiAPIError` on circuit open | `FeatureNotAvailableError` on circuit open | Canonical exception enables structured error handling and Sentry tagging |

---

## Open Questions

1. **Should `nodes_ai.py` be kept as a helper module or merged into `client_domain.py`?**
   - What we know: helper functions are tested indirectly via `test_nodes_question_variation.py`
   - What's unclear: whether keeping the file (renamed to `helpers.py` or as-is) is cleaner than inlining
   - Recommendation: Keep `nodes_ai.py` as a helpers module — rename the file or just remove the node `async def` functions. This minimizes churn and avoids breaking the test file's imports.

2. **Does `ResponseHandler` (`quiz/response_handler.py`) have a `GeminiClient` available?**
   - What we know: it calls `get_generation_graph()` from a module-level import, not a class attribute
   - What's unclear: whether the class has a DI mechanism for the Gemini client or needs `get_gemini_client()` called at call time
   - Recommendation: Use `from app.ai.client import get_gemini_client; client = get_gemini_client()` inside `_invoke_interpretation_graph()` — same singleton pattern used elsewhere.

3. **Does removing `@lru_cache` graph functions break any test fixtures?**
   - What we know: `tests/langgraph/test_langgraph_real_flows.py` and `tests/unit/ai/test_nodes_question_variation.py` import from `nodes_ai`
   - What's unclear: whether any test imports the graph getters directly
   - Recommendation: Grep for all `get_*_graph` imports in tests before deleting.

---

## Sources

### Primary (HIGH confidence)
All findings from direct codebase inspection — no external sources required for this phase.

- `backend-hormonia/app/ai/langgraph/graphs.py` — all 5 single-node graph definitions confirmed
- `backend-hormonia/app/ai/langgraph/nodes_ai.py` — all 5 node functions and their helpers
- `backend-hormonia/app/ai/langgraph/ai_state.py` — AIState TypedDict
- `backend-hormonia/app/ai/langgraph/prompts.py` — all 4 prompt builders
- `backend-hormonia/app/ai/langgraph/_invoke.py` — `invoke_langgraph_graph` wrapper
- `backend-hormonia/app/ai/client.py` — `GeminiClient`, full `generate_content()` pipeline, circuit breaker integration
- `backend-hormonia/app/ai/client_domain.py` — `GeminiDomainClient`, all 4 domain methods
- `backend-hormonia/app/resilience/circuit_breaker/service_breaker.py` — `CircuitBreaker`, `AIServiceCircuitBreaker`, `call_gemini()`
- `backend-hormonia/app/resilience/circuit_breaker/__init__.py` — module exports
- `backend-hormonia/app/core/exceptions.py:730` — `FeatureNotAvailableError` definition
- `backend-hormonia/app/agents/communication/message_composer/composer.py` — 5 direct `graph.ainvoke()` callers
- `backend-hormonia/app/domain/agents/quiz/response_handler.py:373` — `_invoke_interpretation_graph()` caller
- `backend-hormonia/app/ai/langgraph/consensus.py` — 4-node multi-node graph (preserved)
- `backend-hormonia/requirements.txt` — LangGraph version `>=1.0.7,<2.0.0`

---

## Metadata

**Confidence breakdown:**
- Graph locations and callers: HIGH — all found via direct code inspection
- Circuit breaker gap: HIGH — traced the exact code path from `call_gemini()` through `used_fallback` flag to `GeminiAPIError`
- Migration approach: HIGH — all helper functions identified, no hidden dependencies
- Test impact: MEDIUM — identified affected test files; exact test changes depend on final file organization decision

**Research date:** 2026-02-23
**Valid until:** indefinite (codebase research, not external library docs)
