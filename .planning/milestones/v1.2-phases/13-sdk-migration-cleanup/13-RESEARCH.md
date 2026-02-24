# Phase 13: SDK Migration & Cleanup - Research

**Researched:** 2026-02-24
**Domain:** google-genai SDK migration from langchain-google-genai; pydantic-ai run_sync in Celery workers
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Migration cutover strategy:** Hard-switch to google-genai SDK — no gradual toggle, legacy code path removed entirely
- **Remove the GeminiDomainClient shim layer:** Direct google-genai calls in GeminiClient, no abstraction
- **Remove AI_FRAMEWORK setting** and its env var entry completely (not tombstoned, not deprecated — deleted)
- **Adapt the full 50-scenario regression suite** to target google-genai SDK directly (no trimming)
- **Celery async bridge:** Use run_sync() everywhere — every Celery task calling an AI agent wraps with run_sync(), no event loop management in workers
- **Scope:** Limited to Celery-to-agent bridge only — the broader sync-in-async migration (42 methods, 8 files) is a separate future effort
- **Keep existing Celery retry configuration unchanged** (autoretry_for, max_retries, backoff) — run_sync() is just the execution wrapper
- **Validate both FastAPI (async native) and Celery (run_sync) paths** after SDK swap
- **Remove ALL langchain-* packages** from production, dev, and test requirements — clean dependency tree
- **Full config cleanup:** .env.example, docker-compose, deployment configs, documentation — nothing left behind
- **Permanent test assertion** that greps codebase for langchain/langgraph imports and fails if any found
- **Staging smoke test checklist** before production deploy (deploy staging, trigger each AI agent type, verify output quality)
- **Milestone complete** after Phase 13 validated — no additional monitoring phase

### Claude's Discretion

- Tombstone files from earlier phases: keep or delete based on whether any imports still reference tombstoned paths
- Rollback strategy: Claude determines best approach (likely git revert to pre-Phase 13 given the hard-switch decision)
- Production confidence bar: Claude defines based on system error monitoring and staging smoke test results

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SDK-01 | GeminiClient._initialize_model() migrated from ChatGoogleGenerativeAI (langchain-google-genai) to google-genai SDK directly | google-genai 1.64.0 is already installed; `google.genai.Client(api_key=...)` replaces ChatGoogleGenerativeAI init; `client.aio.models.generate_content()` replaces `model.ainvoke()` |
| SDK-02 | langchain-google-genai package removed from requirements.txt (last LangChain dependency) | Currently NOT in requirements.txt — it is an undeclared transitive dependency; langchain_core IS imported directly in client.py and patient_summary_service.py; removal requires eliminating all import sites |
| SDK-03 | All Celery tasks calling AI agents use agent.run_sync() to avoid RuntimeError: Event loop is closed | pydantic-ai 1.63.0 Agent.run_sync() uses `_utils.get_event_loop()` which may return a closed loop; a Celery-safe pattern must ensure a fresh open loop before calling run_sync() |

</phase_requirements>

---

## Summary

Phase 13 eliminates the last LangChain dependency from the backend by migrating `GeminiClient` from `ChatGoogleGenerativeAI` (langchain-google-genai) to the `google.genai.Client` SDK directly. The google-genai SDK (version 1.64.0) is already installed as a transitive dependency of pydantic-ai-slim[google], so no new package installation is needed. The migration is a well-defined swap: replace `_initialize_model()`, replace `_generate_content_internal()`, and update the test stub.

A second, equally important task is the Celery async bridge. The codebase's Celery tasks all use `asgiref.async_to_sync()` or custom `run_async_in_celery()` helpers. The decision is to migrate Celery-to-AI calls to `agent.run_sync()` (pydantic-ai's built-in synchronous runner). However, pydantic-ai's `run_sync()` uses `asyncio.get_event_loop()` internally, which can return a **closed** loop in Celery workers — the root cause of `RuntimeError: Event loop is closed`. The fix requires a thin wrapper that ensures a fresh open loop before calling `run_sync()`.

**Primary recommendation:** Migrate GeminiClient to google-genai SDK using `client.aio.models.generate_content()` for async path; add `run_sync_safe()` to PIISafeAgent that ensures a fresh event loop before calling pydantic-ai's `run_sync()`. Eliminate all `langchain_*` import sites (6 files) and remove the packages from requirements.

---

## Standard Stack

### Core (already installed, no new packages needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | 1.64.0 | Direct Gemini SDK — replaces langchain-google-genai | Installed transitively via pydantic-ai-slim[google]; official Google SDK |
| pydantic-ai-slim | 1.63.0 | Agent runner including run_sync() | Already installed and used in Phase 11 |
| asgiref | >=3.11.0 | Existing Celery async bridge (kept for non-AI tasks) | Already in requirements.txt |

### Packages to Remove

| Package | Current Status | Action |
|---------|---------------|--------|
| langchain-google-genai | Undeclared transitive dep (not in requirements.txt) | Remove import sites; it becomes unreachable |
| langchain-core | Undeclared transitive dep (not in requirements.txt) | Remove import sites; it becomes unreachable |

**Key finding:** `langchain-google-genai` and `langchain-core` are NOT in `requirements.txt`. They are installed as transitive dependencies of other packages. The cleanup is eliminating import sites, not removing a declared package. After removing import sites, `pip check` should be run to verify no remaining explicit dependency brings them in.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| google-genai SDK | google-generativeai (old SDK) | google-generativeai is deprecated; google-genai is the replacement |
| agent.run_sync() | asgiref.async_to_sync() | run_sync() is pydantic-ai native; async_to_sync works but obscures the agent call intent |
| agent.run_sync() | asyncio.run() | asyncio.run() creates/destroys a new loop per call; run_sync() reuses if loop is available |

---

## Architecture Patterns

### Pattern 1: GeminiClient SDK Migration

**What:** Replace `ChatGoogleGenerativeAI` model instance with `google.genai.Client` instance. Replace `HumanMessage`-based `model.ainvoke()` calls with `client.aio.models.generate_content()`.

**When to use:** This is the only pattern — hard cutover, no toggle.

**Before (LangChain):**
```python
# _initialize_model()
from langchain_google_genai import ChatGoogleGenerativeAI
self.model = ChatGoogleGenerativeAI(
    model=self.model_name,
    google_api_key=self.api_key,
    temperature=settings.AI_GEMINI_TEMPERATURE,
    max_output_tokens=settings.AI_GEMINI_MAX_OUTPUT_TOKENS,
    top_p=settings.AI_GEMINI_TOP_P,
    top_k=settings.AI_GEMINI_TOP_K,
)

# _generate_content_internal()
from langchain_core.messages import HumanMessage
messages = [HumanMessage(content=prompt)]
response = await asyncio.wait_for(
    self.model.ainvoke(messages),
    timeout=settings.AI_GEMINI_TIMEOUT_SECONDS,
)
response_text = str(response.content).strip()
finish_reason = response.response_metadata.get("finish_reason")
```

**After (google-genai SDK):**
```python
# Source: google-genai 1.64.0 SDK, verified via inspect

# _initialize_model()
from google import genai
from google.genai import types
self._genai_client = genai.Client(api_key=self.api_key)
self._genai_config = types.GenerateContentConfig(
    temperature=settings.AI_GEMINI_TEMPERATURE,
    max_output_tokens=settings.AI_GEMINI_MAX_OUTPUT_TOKENS,
    top_p=settings.AI_GEMINI_TOP_P,
    top_k=settings.AI_GEMINI_TOP_K,
)
self.model = self._genai_client  # kept as sentinel for health check

# _generate_content_internal()
response = await asyncio.wait_for(
    self._genai_client.aio.models.generate_content(
        model=self.model_name,
        contents=prompt,
        config=self._genai_config,
    ),
    timeout=settings.AI_GEMINI_TIMEOUT_SECONDS,
)
response_text = (response.text or "").strip()
# finish_reason lives on response.candidates[0].finish_reason (FinishReason enum)
finish_reason = None
if response.candidates:
    finish_reason = response.candidates[0].finish_reason
finish_reason_str = finish_reason.name if finish_reason else None
```

**Response text:** `response.text` is a `@property` that concatenates all text parts from the first candidate. Returns `Optional[str]`.

**FinishReason enum values (from google.genai.types.FinishReason):**
`FINISH_REASON_UNSPECIFIED`, `STOP`, `MAX_TOKENS`, `SAFETY`, `RECITATION`, `LANGUAGE`, `OTHER`, `BLOCKLIST`, `PROHIBITED_CONTENT`, `SPII`, `MALFORMED_FUNCTION_CALL`, `IMAGE_SAFETY`, `UNEXPECTED_TOOL_CALL`, `IMAGE_PROHIBITED_CONTENT`, `NO_IMAGE`, `IMAGE_RECITATION`, `IMAGE_OTHER`

**Mapping to existing logic:** Current code treats `STOP`, `FINISH_REASON_UNSPECIFIED`, `STOPPED`, `COMPLETE`, `COMPLETED`, `SUCCESS` as complete. New SDK only has `STOP` and `FINISH_REASON_UNSPECIFIED` as non-error — update the set to `{"STOP", "FINISH_REASON_UNSPECIFIED"}`.

### Pattern 2: PatientSummaryService Migration

**What:** `PatientSummaryService.__init__` also creates a `ChatGoogleGenerativeAI` model directly. This file also imports `langchain_core.messages.HumanMessage` and `SystemMessage`.

**After:**
```python
# __init__: replace ChatGoogleGenerativeAI with google.genai.Client
from google import genai
from google.genai import types

self._genai_client = genai.Client(
    api_key=settings.AI_GEMINI_API_KEY,
)
self._genai_config = types.GenerateContentConfig(
    temperature=0.3,
    max_output_tokens=2000,
)
# self.model kept for any isinstance checks (set to self._genai_client)

# _generate_ai_summary: replace ainvoke with generate_content
# Combine system prompt + user prompt into a single contents string
# (google-genai supports system_instruction in config, or concatenate into prompt)
# Use system_instruction field:
config_with_system = types.GenerateContentConfig(
    temperature=0.3,
    max_output_tokens=2000,
    system_instruction=PATIENT_SUMMARY_SYSTEM_PROMPT,
)
response = await asyncio.wait_for(
    self._genai_client.aio.models.generate_content(
        model=settings.AI_GEMINI_MODEL,
        contents=formatted_prompt,
        config=config_with_system,
    ),
    timeout=settings.AI_GEMINI_TIMEOUT_SECONDS
)
content_text = response.text or ""
# Token usage: response.usage_metadata.total_token_count
token_usage = 0
if response.usage_metadata:
    token_usage = response.usage_metadata.total_token_count or 0
```

**Note on system_instruction:** `GenerateContentConfig` has a `system_instruction` field (verified from field list). This replaces the `SystemMessage` + `HumanMessage` pattern.

### Pattern 3: PIISafeAgent.run_sync_safe() — Celery Bridge

**What:** pydantic-ai's `Agent.run_sync()` calls `_utils.get_event_loop()` which calls `asyncio.get_event_loop()`. In Celery workers, if the event loop was previously closed (e.g., after worker process shutdown/init cycles), this returns a **closed** loop, causing `RuntimeError: Event loop is closed`.

**Root cause verified:** `pydantic_ai._utils.get_event_loop()` does NOT check `loop.is_closed()`. It catches `RuntimeError` (missing loop) but not a closed loop.

**Fix:** Add `_safe_run_sync()` method to `PIISafeAgent` that ensures a fresh open loop before delegating to `self._agent.run_sync()`:

```python
# app/ai/agents/base.py
def _safe_run_sync(self, prompt: str, deps: AIDeps, *, operation: str) -> Any:
    """Celery-safe synchronous runner. Ensures event loop is open before run_sync."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Now safe to call pydantic-ai's run_sync (which calls get_event_loop internally)
    safe_prompt = sanitize_prompt_text_for_external_ai(prompt)
    model = GoogleModel(deps.model_name, provider=GoogleProvider(api_key=deps.gemini_api_key))
    result = self._agent.run_sync(safe_prompt, model=model, deps=deps)
    return result.output
```

**Celery task usage pattern:**
```python
# In a Celery task (sync context):
agent = HumanizeAgent()
result = agent._safe_run_sync(prompt, deps, operation="humanize")
```

**Scope clarification:** The broader `async_to_sync` pattern used across 40+ existing Celery tasks is NOT being changed. Only Celery tasks that **call pydantic-ai agents directly** need this bridge. Currently, no Celery task imports agents directly — they call services which call `GeminiDomainClient.humanize_flow_message()` etc., which in turn call the agents. The `_use_pydantic_agents()` check in GeminiDomainClient (guarded by `AI_FRAMEWORK`) will be removed along with the setting; the pydantic-ai path becomes the only path.

### Pattern 4: AI_FRAMEWORK Setting Removal

**What:** `AI_FRAMEWORK` setting in `integrations.py` and `AI_FLOW_FRAMEWORK` setting are used to toggle between legacy and pydantic-ai paths in `GeminiDomainClient._use_pydantic_agents()`. With the hard-switch, this method is deleted, and all domain client methods call pydantic-ai agents directly.

**Files to update:**
- `app/config/settings/integrations.py` — delete `AI_FRAMEWORK` field
- `app/ai/client_domain.py` — delete `_use_pydantic_agents()` method and all if/else branches; keep only the pydantic-ai agent call path
- `backend-hormonia/.env.example` — remove `AI_FRAMEWORK=legacy` line

### Anti-Patterns to Avoid

- **Do not** keep the LangChain import path as a fallback (hard-switch decision, no toggle)
- **Do not** use `asyncio.run()` from Celery tasks (can fail if there's a running loop in some contexts)
- **Do not** call `self._agent.run_sync()` without first ensuring the loop is open
- **Do not** confuse `google-generativeai` (old SDK) with `google-genai` (new SDK) — they have different module paths
- **Do not** try to extract `finish_reason` from `response.response_metadata` (LangChain concept) — use `response.candidates[0].finish_reason` with the enum's `.name` property

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Event loop safety in Celery | Custom thread-local loop management | Thin wrapper checking `loop.is_closed()` before `run_sync()` | The codebase already has `run_async_in_celery()` and `async_to_sync` for other tasks; only the agent calls need the run_sync bridge |
| System prompt in google-genai | Concatenate system + user prompt manually | `GenerateContentConfig(system_instruction=...)` | The SDK has a first-class `system_instruction` field |
| Token usage extraction | Parse response metadata dict | `response.usage_metadata.total_token_count` | Typed field on the response model |

**Key insight:** The google-genai SDK provides a much simpler interface than LangChain — no message wrapping objects needed, direct string as `contents`, typed response with `.text` property and `.candidates[0].finish_reason` enum.

---

## Common Pitfalls

### Pitfall 1: response.text Can Be None

**What goes wrong:** `response.text` returns `Optional[str]`. If the response has no candidates or no text parts, it returns `None`. Current code does `str(response.content).strip()` which converts None to "None".

**Why it happens:** Safety filter blocks, MAX_TOKENS truncation with no text, or empty model response.

**How to avoid:** Always use `(response.text or "").strip()` and check for empty string before proceeding.

**Warning signs:** Silent empty content in production responses, empty string passed through guardrails.

### Pitfall 2: Event Loop Already Closed in Celery Worker

**What goes wrong:** After a Celery worker processes tasks and the cleanup runs `cleanup_all_event_loops()`, the thread-local event loop is closed and set as the current loop. The next task invocation calling `asyncio.get_event_loop()` gets the closed loop. `run_sync()` then fails with `RuntimeError: Event loop is closed`.

**Why it happens:** pydantic-ai's `_utils.get_event_loop()` catches `RuntimeError` for missing loops but returns a closed loop without error. The closed loop then fails at `loop.run_until_complete()`.

**How to avoid:** Add the `is_closed()` check before `run_sync()` (Pattern 3 above). The existing `celery_app.py` `worker_process_init` already creates a fresh loop and calls `asyncio.set_event_loop(loop)`, so this issue only occurs if the loop gets closed mid-session, e.g., by the `cleanup_all_event_loops()` call in `worker_process_shutdown`.

**Warning signs:** `RuntimeError: Event loop is closed` in Celery logs after first batch of tasks completes.

### Pitfall 3: finish_reason Type Change

**What goes wrong:** Current code extracts `finish_reason` from `response.response_metadata` (a dict with string keys like `"finish_reason"` or `"finishReason"`). The google-genai SDK returns a `FinishReason` enum on `response.candidates[0].finish_reason`.

**Why it happens:** LangChain wraps the response and provides metadata dicts; google-genai provides typed objects.

**How to avoid:** Access `response.candidates[0].finish_reason.name` to get the enum name as a string (e.g., `"STOP"`). Update the "complete" status set to `{"STOP", "FINISH_REASON_UNSPECIFIED"}` (removing `"STOPPED"`, `"COMPLETE"`, `"COMPLETED"`, `"SUCCESS"` which were LangChain interpretations).

**Warning signs:** All responses flagged as "incomplete" in retry loop — finish_reason is None or unrecognized string.

### Pitfall 4: Undeclared Transitive Dependencies

**What goes wrong:** `langchain-google-genai` and `langchain-core` are NOT in `requirements.txt` — they were already absent. They exist only as transitive dependencies. After removing import sites, running `pip check` may show they are still installed. That is expected — they just won't be imported.

**Why it happens:** pip doesn't remove packages that other packages depend on.

**How to avoid:** The success criterion is zero Python `import` statements in production code importing from `langchain*`. Run `grep -r "langchain" app/ tests/ requirements.txt` — all must return zero matches in `.py` files.

### Pitfall 5: GeminiClient._model_loop_id Loop Tracking

**What goes wrong:** The current code tracks `_model_loop_id` to detect event loop changes and reinitialize the ChatGoogleGenerativeAI model. The google-genai `Client` is not event-loop-bound — it uses httpx internally which is loop-agnostic.

**Why it happens:** LangChain's ChatGoogleGenerativeAI maintained internal async state tied to the event loop.

**How to avoid:** Remove the `_model_loop_id` tracking and `_ensure_model_for_loop()` logic. The google-genai `Client` can be initialized once and reused across loops. Simplify `_initialize_model()` to just create the `genai.Client` once.

### Pitfall 6: LangChainOrchestrator Name in Codebase

**What goes wrong:** `app/integrations/gemini_orchestrator.py` exports `get_langchain_orchestrator()` and `LangChainOrchestrator` class. These names don't use LangChain but are named after it. They are used in `response_processor/extractors.py` and `webhook/handlers/message_handler.py`.

**Why it happens:** Name was set when LangChain was the backing implementation.

**How to avoid:** These classes do NOT use LangChain imports — they delegate to `GeminiClient`. They only need the comment/name updated. No functional change required.

---

## Code Examples

### Minimal google-genai Client Usage

```python
# Source: google-genai 1.64.0, verified via inspect and pip show
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

# Async (for FastAPI/GeminiClient path):
response = await client.aio.models.generate_content(
    model="gemini-2.0-flash",
    contents="Your prompt here",
    config=types.GenerateContentConfig(
        temperature=0.7,
        max_output_tokens=1000,
        top_p=0.9,
        top_k=40,
    ),
)
text = (response.text or "").strip()

# With system instruction:
response = await client.aio.models.generate_content(
    model="gemini-2.0-flash",
    contents="User prompt here",
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful medical assistant.",
        temperature=0.3,
        max_output_tokens=2000,
    ),
)

# Sync (for scripts/health checks):
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="test",
)
```

### Finish Reason Check (updated for google-genai)

```python
from google.genai import types

# Complete statuses in google-genai SDK
_COMPLETE_FINISH_REASONS = {"STOP", "FINISH_REASON_UNSPECIFIED"}

finish_reason = None
if response.candidates:
    fr = response.candidates[0].finish_reason
    finish_reason = fr.name if fr is not None else None

incomplete = (
    finish_reason is not None
    and finish_reason not in _COMPLETE_FINISH_REASONS
)
```

### Token Usage Extraction

```python
token_usage = 0
if response.usage_metadata:
    token_usage = response.usage_metadata.total_token_count or 0
```

### PIISafeAgent Celery-Safe run_sync

```python
# app/ai/agents/base.py — new method on PIISafeAgent
def _safe_run_sync(self, prompt: str, deps: AIDeps, *, operation: str) -> Any:
    """Celery-safe synchronous runner for pydantic-ai agents."""
    import asyncio
    # pydantic-ai's run_sync uses get_event_loop() which may return a closed loop.
    # Celery workers can have a closed loop from prior cleanup cycles.
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    safe_prompt = sanitize_prompt_text_for_external_ai(prompt)
    model = GoogleModel(
        deps.model_name,
        provider=GoogleProvider(api_key=deps.gemini_api_key),
    )
    result = self._agent.run_sync(safe_prompt, model=model, deps=deps)
    self._warn_on_output_pii(str(result.output), operation=operation)
    return result.output
```

### Permanent CI Assertion (no-langchain test)

```python
# tests/test_no_langchain_imports.py
import ast
import pathlib
import pytest

_BANNED = {"langchain", "langchain_core", "langchain_google_genai", "langchain_google"}

@pytest.mark.parametrize("py_file", list(pathlib.Path("app").rglob("*.py")))
def test_no_langchain_imports(py_file: pathlib.Path):
    """Permanent gate: zero LangChain imports anywhere in production code."""
    try:
        tree = ast.parse(py_file.read_bytes())
    except SyntaxError:
        return  # Skip unparseable files
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = getattr(node, "module", "") or ""
            names = [alias.name for alias in getattr(node, "names", [])]
            all_names = mod + " " + " ".join(names)
            for banned in _BANNED:
                if banned in all_names:
                    pytest.fail(
                        f"{py_file}: LangChain import detected: {mod or names}"
                    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| google-generativeai (old) | google-genai (new, unified) | 2024 | Different module path; new SDK is maintained, old is deprecated |
| ChatGoogleGenerativeAI (langchain) | google.genai.Client | Phase 13 | Direct SDK; removes LangChain layer |
| HumanMessage wrapping | Plain string contents | Phase 13 | Simpler API |
| response.response_metadata dict | response.candidates[0].finish_reason enum | Phase 13 | Typed, no dict parsing |
| model.ainvoke(messages) | client.aio.models.generate_content(model=, contents=, config=) | Phase 13 | Direct async method |

**Deprecated/outdated after Phase 13:**
- `langchain_core.messages.HumanMessage` / `SystemMessage`: removed from client.py and patient_summary_service.py
- `langchain_google_genai.ChatGoogleGenerativeAI`: removed from client.py and patient_summary_service.py
- `GeminiClient._model_loop_id` and `_ensure_model_for_loop()`: loop-rebinding not needed with google-genai Client
- `GeminiClient._model_loop_id` attribute: google.genai.Client is loop-agnostic
- `AI_FRAMEWORK` setting: deleted (not tombstoned)
- `GeminiDomainClient._use_pydantic_agents()` method: deleted, pydantic-ai is now unconditional

---

## Scope Map: All Langchain Import Sites

**Codebase audit result (confirmed by grep):**

| File | Langchain Imports | Migration Action |
|------|-------------------|-----------------|
| `app/ai/client.py` | `langchain_core.messages.HumanMessage`, `langchain_google_genai.ChatGoogleGenerativeAI` (x2) | Replace with google-genai SDK calls |
| `app/services/ai/patient_summary_service.py` | `langchain_core.messages.HumanMessage, SystemMessage`, `langchain_google_genai.ChatGoogleGenerativeAI` | Replace with google-genai SDK calls |
| `app/main.py` | `"langchain_core"`, `"langchain_google_genai"` (in LANGGRAPH_AUDIT set) | Update audit set to remove these entries (they're no longer importable) |
| `tests/unit/test_gemini_client_pii_redaction.py` | `pytest.importorskip("langchain_google_genai")` at top | Remove the importorskip guard; update test stub for google-genai response shape |
| `tests/validation/detailed_import_analysis.py` | `langchain_core`, `langchain_google_genai` in known-packages dict | Remove entries |
| `tests/validation/import_analysis_report.json` | Same entries in JSON | Remove entries |

**Not requiring changes (no LangChain imports):**
- `app/integrations/gemini_orchestrator.py` — named `LangChainOrchestrator` but has zero LangChain imports; delegates to GeminiClient only — name can stay or be renamed (cosmetic)
- `app/integrations/__init__.py` — exports `get_langchain_orchestrator`; functional code is fine
- All Celery task files — use `async_to_sync` / `run_async_in_celery`, not langchain directly

---

## Open Questions

1. **Does patient_summary_service.py need a full GeminiClient refactor or standalone genai.Client?**
   - What we know: It creates its own `ChatGoogleGenerativeAI` instance directly, not via `GeminiClient`
   - What's unclear: Whether to route it through `GeminiClient.generate_content()` (with system_instruction injected into the prompt) or keep a standalone `genai.Client` instance in the service
   - Recommendation: Route through the existing `GeminiClient.generate_content()` — the service can prepend the system prompt to the user prompt, or pass it as a profile. This removes the duplicate model initialization and avoids maintaining two SDK clients.

2. **Which Celery tasks actually call AI agents (requiring run_sync bridge)?**
   - What we know: No Celery task file directly imports `HumanizeAgent`, `SentimentAgent`, etc. They call services (e.g., `enhanced_flow_engine`, `follow_up_system`) which call `GeminiDomainClient` methods, which delegate to pydantic-ai agents when `AI_FRAMEWORK=pydantic-ai`. After removing the AI_FRAMEWORK toggle, all calls go through pydantic-ai.
   - What's unclear: The exact call stack path from each Celery task to an agent invocation
   - Recommendation: After removing `_use_pydantic_agents()`, all `GeminiDomainClient` methods call pydantic-ai agents. Since these methods are async and called via `async_to_sync()` or `run_async_in_celery()`, the `await self._safe_run(...)` inside `PIISafeAgent` runs inside an event loop already. **run_sync() is NOT needed for the existing task path** — the existing `async_to_sync()` wrappers handle it. The `run_sync()` decision from CONTEXT.md applies specifically to NEW direct agent calls from sync Celery tasks. The existing path (async_to_sync → service → GeminiDomainClient → agent.run()) already works.

3. **Does removing AI_FRAMEWORK break any monitoring/admin endpoint?**
   - What we know: `AI_FRAMEWORK` is only referenced in `integrations.py` (Field definition) and `client_domain.py` (_use_pydantic_agents)
   - What's unclear: Whether any health check endpoint reads `settings.AI_FRAMEWORK`
   - Recommendation: Quick grep for `AI_FRAMEWORK` in routers/endpoints before deletion

---

## Validation Architecture

*Nyquist validation not enabled in config — section skipped.*

---

## Sources

### Primary (HIGH confidence)

- google-genai 1.64.0 — installed locally; `google.genai.Client`, `aio.models.generate_content`, `GenerateContentConfig`, `FinishReason` enum, `GenerateContentResponse.text` verified via Python inspect
- pydantic-ai-slim 1.63.0 — `Agent.run_sync()` and `_utils.get_event_loop()` source verified via Python inspect; closed loop behavior confirmed by test
- `backend-hormonia/app/ai/client.py` — full source read; all langchain import sites catalogued
- `backend-hormonia/app/services/ai/patient_summary_service.py` — full source read; migration pattern defined
- `backend-hormonia/app/ai/agents/base.py` — PIISafeAgent structure verified; _safe_run_sync placement point confirmed
- `backend-hormonia/requirements.txt` — langchain-google-genai and langchain-core confirmed absent from declared dependencies

### Secondary (MEDIUM confidence)

- Codebase grep of all `langchain` references — complete list of 6 files with imports catalogued
- `backend-hormonia/app/celery_app.py` — Celery async bridge patterns reviewed; worker_process_init/shutdown confirmed

### Tertiary (LOW confidence)

- None — all critical findings verified against actual installed packages and source code

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — google-genai 1.64.0 verified installed; API signatures inspected directly
- Architecture: HIGH — migration patterns derived from actual installed SDK, not documentation alone
- Pitfalls: HIGH — root cause of Event loop is closed confirmed by running pydantic-ai source inspection and asyncio behavior test
- Scope: HIGH — all langchain import sites catalogued via grep on actual codebase

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (30 days; google-genai SDK is stable)
