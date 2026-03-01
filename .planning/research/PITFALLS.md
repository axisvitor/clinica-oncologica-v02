# Pitfalls Research

**Domain:** AI Framework Migration — LangGraph to Pydantic AI + Google ADK in Healthcare WhatsApp Backend
**Researched:** 2026-02-23
**Confidence:** HIGH (all critical pitfalls grounded in codebase evidence and verified external sources)

---

## Critical Pitfalls

### Pitfall 1: google-adk Pulls google-genai, Which Conflicts with langchain-google-genai 4.x

**What goes wrong:**
The project currently uses `langchain-google-genai>=2.1.12,<4.0.0` to access Gemini via `ChatGoogleGenerativeAI`. The `google-adk` package requires `google-genai>=1.56.0,<2.0.0` as a direct dependency. Meanwhile, `langchain-google-genai 4.0.0` completed a migration from `google-ai-generativelanguage` to the new `google-genai` SDK.

The critical problem: `google-adk` brings in `google-genai` with specific version constraints. If `langchain-google-genai` is still pinned to `<4.0.0` (which uses the legacy `google-ai-generativelanguage` SDK), pip may resolve to an incompatible transitive dependency tree where `google-adk`'s `google-genai` requirement conflicts with `langchain-google-genai`'s `google-ai-generativelanguage` requirement.

The failure mode is silent in many cases: `pip install` succeeds with a warning, but the Google Gemini API responses return errors at runtime because the underlying SDK's authentication or transport code has incompatible versions loaded in the same process.

Additionally, `google-adk` pulls in a large dependency tree including `google-cloud-aiplatform`, `google-cloud-bigquery`, `google-cloud-storage`, and other GCP packages. These add 200-400MB to the Docker image and extend cold start time on Cloud Run workers.

**Why it happens:**
The migration is fundamentally a package ecosystem transition: the LangChain world used the old `google-ai-generativelanguage` SDK while the new world (ADK + Pydantic AI's `GoogleModel`) both use the new `google-genai` SDK. The two SDKs cannot cleanly coexist because they claim different API clients for the same Google AI endpoints.

**How to avoid:**
Do not attempt to run both `langchain-google-genai` (LangChain era) and `google-adk` simultaneously during migration. Instead:
1. Migrate `GeminiClient` to use `pydantic-ai` with `GoogleModel` (which uses `google-genai`) before installing `google-adk`.
2. Remove `langchain-google-genai`, `langchain-core`, and `langgraph` from `requirements.txt` in the same commit that adds `pydantic-ai` and `google-adk`.
3. Pin exact versions: `google-adk==1.25.1` and `pydantic-ai>=0.0.13,<1.0.0` together, tested against each other.
4. Run `pip install --dry-run` and check the resolution before committing to `requirements.txt`.

During the transition phase (if running old and new code simultaneously), isolate them into separate Docker images/services — not the same `requirements.txt`.

**Warning signs:**
- `pip install google-adk langchain-google-genai` produces version conflict warnings
- `ImportError: cannot import name 'GenerativeModel' from 'google.generativeai'` at runtime
- Two different versions of `google-protobuf` or `googleapis-common-protos` loaded (visible via `pip list | grep google`)
- Docker build time increases by more than 5 minutes (ADK bringing in cloud SDK packages)

**Phase to address:** Phase 1 (Dependency Migration) — must be resolved in isolation before writing any migration code

---

### Pitfall 2: PII Redaction Layer Not Applied to Pydantic AI System Prompts

**What goes wrong:**
The existing `GeminiClient.generate_content()` applies `sanitize_prompt_text_for_external_ai()` at line 559 of `client.py` before every Gemini API call. This is the LGPD PHI guardrail. When migrating to Pydantic AI `Agent`, the system prompt is often defined at agent construction time via `system_prompt=` or `instructions=`, not at call time. If a developer creates a `HumanizationAgent` with a static system prompt and passes the patient context directly to `agent.run(prompt)`, the PII redaction that existed in `GeminiClient._redact_prompt_for_external_ai()` is bypassed entirely.

Concretely: `app/ai/pii_redaction.py:sanitize_prompt_text_for_external_ai()` strips patient names, CPF numbers, phone numbers, and emails from free-text prompts. If the patient's name appears in the dynamic portion of the prompt passed to a Pydantic AI agent — and the developer forgets to call `sanitize_prompt_text_for_external_ai()` before `agent.run()` — the patient name reaches Google's servers, violating LGPD Art. 46 and potentially Art. 11 (processing of sensitive health data).

The Pydantic AI `output_type` validation catches structural problems with AI outputs, but it provides no input sanitization. It is purely an output concern.

**Why it happens:**
In the current architecture, PII redaction is hidden inside `GeminiClient` and enforced automatically. After migration, developers new to the codebase may call `agent.run(prompt)` directly and not realize PII redaction is a separate concern that must be applied manually before every agent invocation.

**How to avoid:**
Create a `PIISafeAgent` wrapper class in `app/ai/agents/base.py` that:
1. Wraps any `pydantic_ai.Agent` instance
2. Calls `sanitize_prompt_text_for_external_ai(prompt)` and `redact_patient_context(deps)` before every `run()` call
3. Raises `PiiRedactionError` if any bypass is attempted

Make this wrapper the only sanctioned way to call Pydantic AI agents. Do not allow direct `Agent.run()` calls outside this wrapper. Add a `grep`-based CI check that fails if any file in `app/ai/agents/` calls `.run()` or `.run_sync()` directly without going through the wrapper.

Also verify: the `deps` (RunContext dependencies) passed to agents do not contain raw patient objects with PII fields. Pass a pre-redacted `PatientAIContext` dataclass instead.

**Warning signs:**
- Any Pydantic AI agent that receives `patient.name`, `patient.phone`, or `patient.cpf` as direct input
- A test that calls `agent.run(f"Patient {patient.name}...")` without sanitization
- Sentry traces showing the raw patient name in an LLM API request body

**Phase to address:** Phase 2 (Agent Implementation) — must be a mandatory part of every agent's Definition of Done; a CI lint rule is required before any agent ships

---

### Pitfall 3: Pydantic AI GoogleModel Event Loop Conflict with async_to_sync

**What goes wrong:**
The codebase uses `asgiref.sync.async_to_sync()` as the canonical bridge for calling async code from Celery workers (established pattern in `tasks/flows/base.py:10-11`). Pydantic AI's `GoogleModel` uses `httpx` with `google-genai`'s async HTTP client under the hood. The `google-genai` client manages its own connection pool and event loop references.

When `async_to_sync()` (which creates/reuses a thread's event loop via `asyncio.get_event_loop()`) wraps a Pydantic AI `agent.run()` call, the `httpx` async client's connection cleanup runs after the async frame returns. If `async_to_sync()` has already shut down the thread's loop by the time connection cleanup fires, the error is:

```
RuntimeError: Event loop is closed
```

This is the exact same class of bug documented in pydantic-ai GitHub issue #3762 and issue #748. It does not occur reliably in development (where one event loop exists throughout), but occurs in Celery workers that process many tasks sequentially (where `async_to_sync` creates and tears down loops more aggressively).

**Why it happens:**
`httpx` async clients hold open connections across requests for efficiency. When the event loop the client was bound to closes, the cleanup coroutine that drains the connection pool runs into a closed loop. The `google-genai` SDK does not eagerly close connections at the end of each request.

**How to avoid:**
Use `agent.run_sync()` for Celery workers instead of wrapping `agent.run()` with `async_to_sync()`. Pydantic AI's `run_sync()` uses its own event loop management internally and handles cleanup correctly. Verify this works with the specific version of `google-genai` in use before committing to this pattern.

If `run_sync()` is insufficient (for example, if agents need to call async DB utilities during their run), use `anyio.from_thread.run_sync()` with a persistent event loop that lives for the Celery worker process lifetime (created in `@worker_process_init.connect`), rather than letting `async_to_sync()` create a new loop per invocation.

Do NOT use `nest_asyncio.apply()` in Celery workers as a fix — it allows nested event loops, which masks the resource leak rather than preventing it.

**Warning signs:**
- `RuntimeError: Event loop is closed` in Celery worker logs after 10-50 task invocations
- Worker memory growing steadily until OOM kill (connection pool resources leaking)
- Errors appearing only under load, not in unit tests

**Phase to address:** Phase 2 (Celery Integration) — must be verified with a load test simulating 100 Celery task invocations before declaring the migration complete

---

### Pitfall 4: LangGraph Redis Checkpoint Data Is Not Cleaned Up

**What goes wrong:**
The existing `RedisCheckpointer` in `app/ai/langgraph/runtime.py` stores data in Redis Dragonfly DB 0 under these key patterns:
- `langgraph:checkpoint:{graph_name}:ckpt:{thread_id}:{checkpoint_ns}:{checkpoint_id}`
- `langgraph:checkpoint:{graph_name}:latest:{thread_id}:{checkpoint_ns}`
- `langgraph:checkpoint:{graph_name}:index:{thread_id}:{checkpoint_ns}`
- `langgraph:checkpoint:{graph_name}:writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}`

After removing LangGraph, this data remains in Redis indefinitely. The TTL is configurable via `LANGGRAPH_CHECKPOINT_TTL_SECONDS` (default: 3600 seconds). However, the index keys (`index:`) use `sadd` which does not auto-expire set members — only the set itself expires. Set members pointing to expired checkpoint data accumulate as garbage, and if the index key TTL is renewed before set cleanup, the set can grow unbounded.

After migration, none of these keys serve any purpose. They consume memory in Dragonfly and, more importantly, obscure future debugging (a future developer might assume these keys represent active state and investigate them during an incident).

**Why it happens:**
Migrations typically add new infrastructure but defer cleanup of old infrastructure. The old data is "harmless" initially, so cleanup is deprioritized. But in Redis (a memory-bound datastore), accumulated garbage keys from a previous system become a capacity problem over time, especially for a healthcare system that processes daily patient messages.

**How to avoid:**
Write a one-time migration script (or a Celery task run once at deployment) that:
1. Uses `scan_iter(match="langgraph:checkpoint:*", count=100)` (never `keys()`) to find all checkpoint keys
2. Deletes them in batches of 500 with `pipeline().delete(*batch).execute()`
3. Logs the count of deleted keys for audit purposes
4. Is idempotent (safe to run multiple times)

Schedule this cleanup for the same deployment that removes LangGraph from `requirements.txt`. Do not leave it as a follow-up task — once LangGraph is gone, there is no mechanism to re-examine what those keys meant.

Additionally, verify that `LANGGRAPH_CHECKPOINT_TTL_SECONDS` is present in the environment configuration and set to a value shorter than 3600 during the transition, so natural expiry accelerates cleanup before the migration script runs.

**Warning signs:**
- `langgraph:checkpoint:*` keys visible in Dragonfly SCAN output after migration is complete
- Dragonfly memory usage not decreasing after LangGraph removal
- A future developer opening a debugging session and wondering what `langgraph:checkpoint:flow_message_graph:index:*` means

**Phase to address:** Phase 1 (Dependency Removal) — cleanup script must be written in the same story that removes LangGraph, executed at deployment

---

### Pitfall 5: Existing Output Guardrails Must Be Manually Re-Connected to Every New Agent

**What goes wrong:**
The `GeminiClient.generate_content()` in `client.py` applies a full guardrail pipeline automatically to every AI call:
- `normalize_ai_output()` or `normalize_json_output()` (strip wrapping quotes, code fences)
- `validate_ai_output()` (check min/max length, banned patterns, prompt leak markers, placeholder detection)
- Guardrail-aware retry loop with `guardrail_retries` attempts
- `_repair_ending_punctuation()` for MESSAGE outputs

Pydantic AI's `output_type` validation enforces Pydantic schema structure (field types, required fields), but it does NOT enforce:
- Healthcare-specific banned patterns (e.g., "as an AI language model")
- Prompt leak detection (e.g., "MENSAGEM HUMANIZADA", "NOVA PERGUNTA" appearing in output)
- Minimum/maximum character length constraints
- Brazilian Portuguese ending punctuation requirements

If these guardrails are not re-implemented as Pydantic AI output validators or `@result_validator` decorators on every agent, the migration silently removes protection that exists in the current system. The output quality regression may not be visible in unit tests — it only surfaces when the model occasionally produces out-of-character responses under load.

**Why it happens:**
Developers migrating to Pydantic AI see `output_type=HumanizedMessage` with Pydantic validation and assume the existing quality controls are replicated. They are not — Pydantic validates structure, not content semantics. The banned pattern checks and prompt leak detection are application-specific business logic that has no equivalent in the Pydantic AI framework.

**How to avoid:**
Create a `HealthcareOutputValidator` class (or a set of `@result_validator` decorators) that wraps the exact logic from `app/services/ai/guardrails.py`. Apply these validators to every Pydantic AI agent. Run side-by-side output comparison tests: given identical prompts, compare the full validation pipeline output from `GeminiClient.generate_content()` with the new agent's output for at least 50 sample patient contexts.

Also preserve the guardrail retry mechanism: Pydantic AI supports `max_retries` on agents, which triggers when output validators fail via `ModelRetry`. Wire this to replace the existing `guardrail_retries` loop in `GeminiClient`.

Do not remove `app/services/ai/guardrails.py` during migration — it contains the canonical guardrail logic. Import and reuse it in the new agents.

**Warning signs:**
- A new agent returning output that passes Pydantic schema validation but contains "as an AI language model"
- Outputs containing template leak markers like "MENSAGEM HUMANIZADA" in WhatsApp messages
- Outputs shorter than 20 characters or longer than 1600 characters being accepted
- A test suite that passes but does not include banned-pattern assertions on agent outputs

**Phase to address:** Phase 2 (Agent Implementation) — output quality regression tests must pass before any agent replaces GeminiClient in production

---

### Pitfall 6: The 5 Existing "Agent" Classes Are Not Real Agents — They Must Not Be Migrated as Pydantic AI Agents

**What goes wrong:**
The `app/agents/` directory contains 5 classes with agent names: `AlertAnalyzer`, `PatientMonitor`, `MessageComposer`, `ResponseProcessor`, `FlowCoordinator`. These are service wrappers — Python classes with async methods that orchestrate business logic. They do NOT:
- Call an LLM
- Use `pydantic_ai.Agent`
- Have tools, system prompts, or output types

If a developer assumes these are "agents to migrate to Pydantic AI," they will attempt to refactor them into `pydantic_ai.Agent` instances, adding unnecessary LLM calls and complexity to what are currently efficient service classes.

The only LLM calls in the system are in `GeminiClient.generate_content()` (via `app/ai/client.py` and `app/ai/client_domain.py`) and in the 2 remaining LangGraph graphs (`flow_message_graph`, `flow_response_graph`). The 5 "agent" classes are the service layer that calls `GeminiClient` — they are NOT candidates for Pydantic AI migration.

**Why it happens:**
The naming is misleading. "Agent" in the codebase means a DDD service component (following the Hive-Mind/Swarm architecture pattern). "Agent" in Pydantic AI means an LLM-backed reasoning entity. The same word means different things.

**How to avoid:**
Before beginning migration work, explicitly document which components are LLM-backed vs. service wrappers:
- `app/ai/client.py` (`GeminiClient`) — LLM caller, migrate to Pydantic AI agents
- `app/ai/langgraph/graphs.py` (flow_message_graph, flow_response_graph) — LangGraph graphs with LLM nodes, replace with Pydantic AI + ADK orchestration
- `app/agents/*` classes — service wrappers with no LLM calls, rename to `*Service` or leave as-is, do NOT add `pydantic_ai.Agent`

Add a one-line comment at the top of each `app/agents/` file: `# Service component. Not an LLM agent. Do not migrate to pydantic_ai.Agent.`

**Warning signs:**
- A PR that adds `pydantic_ai.Agent` to `AlertAnalyzer`, `PatientMonitor`, or `FlowCoordinator`
- Story scope including "migrate 5 agents to Pydantic AI" (should be "4 AI operations to Pydantic AI agents")
- A PR that significantly increases response latency in alert processing (previously synchronous, now making LLM calls)

**Phase to address:** Phase 1 (Scope Definition) — must be clarified before any migration stories are created

---

### Pitfall 7: Google ADK Session State Collides with LangGraph Thread State Concepts

**What goes wrong:**
LangGraph uses `thread_id` in `config['configurable']['thread_id']` to isolate conversation state per patient. The `RedisCheckpointer` in `runtime.py` stores state keyed by `thread_id`. When migrating to Google ADK, the equivalent is `Session` objects with `session_id`. These concepts are structurally similar but semantically different:

- LangGraph `thread_id`: identifies a conversation thread; state persists across invocations
- Google ADK `session_id`: identifies a user session; can include multi-turn conversation history, tool results, and agent state
- Google ADK has its own `InMemorySessionService` and `DatabaseSessionService` that conflict with the existing Redis-based state management

If the migration assumes 1:1 equivalence and maps `patient_id → session_id`, the ADK session service may persist state in a second datastore (SQLite by default for `DatabaseSessionService`), creating a dual-state problem: patient conversation state in Redis (from the old system) and patient conversation state in ADK sessions (from the new system), with no reconciliation.

**Why it happens:**
Google ADK is designed for standalone agent applications, not for embedding into existing stateful services. Its session management assumes it owns the session lifecycle. Embedding it into a system that already has Redis-based state management requires explicitly choosing which layer owns state.

**How to avoid:**
Do not use ADK's built-in session services. Use ADK's `SequentialAgent` and `ParallelAgent` for orchestration only (pure computation), with no session persistence in ADK. Manage all patient conversation state in the existing Redis/PostgreSQL layer. Pass context to ADK agents as stateless inputs per invocation.

Concretely: use `InMemorySessionService` for ADK (zero persistence, treated as ephemeral per-invocation context), and explicitly construct the full context from Redis/DB at the start of each invocation. This matches how `GeminiClient` works today (stateless, context passed per call).

**Warning signs:**
- A PR that imports `DatabaseSessionService` or `VertexAiSessionService` from `google.adk.sessions`
- ADK creating SQLite files in the working directory (`agent_data.db`)
- Patient conversation history being read from two different sources (Redis + ADK session) with no merge logic

**Phase to address:** Phase 2 (Architecture) — must be documented in the agent architecture design before implementation begins

---

### Pitfall 8: LangChain Dependency Removal Breaks Callers Outside the AI Module

**What goes wrong:**
`langchain-core`, `langchain-google-genai`, and `langgraph` are imported in at least 15 non-AI files (confirmed by codebase grep). After removing these packages, startup fails with `ModuleNotFoundError` at import time for any file that imports:
- `from langchain_core.messages import HumanMessage` (used in `client.py`, flows)
- `from langgraph.graph import StateGraph` (used in `graphs.py`)
- `from langgraph.checkpoint.memory import MemorySaver` (used in `runtime.py`)

The `try/except ImportError: X = None` guards in `langgraph/` module prevent startup failures from LangGraph itself, but any OTHER file that imports from LangChain without such a guard will hard-crash.

Beyond imports, the consensus system in `app/ai/langgraph/consensus.py` and `app/agents/patient/flow_coordinator/consensus_manager.py` have LangGraph dependencies that are described as "dead code" but have not been tombstoned. If they are imported anywhere in the import tree, removal of LangGraph breaks the import.

**Why it happens:**
LangChain packages spread through a codebase via transitive imports. A module uses `HumanMessage` because it seemed like a good type at the time. Removal requires a complete import graph audit, not just searching for `import langgraph`.

**How to avoid:**
Before removing LangChain packages, run:
```bash
grep -r "from langchain\|import langchain\|from langgraph\|import langgraph" app/ --include="*.py" -l
```
This gives the full list of files to update. Tombstone or delete the consensus system in the same phase as the LangGraph removal. Use `python -c "import app.main"` as a smoke test after removal — if it succeeds, all import-time dependencies are resolved.

Also check `requirements.txt` for packages that have `langchain-core` as a transitive dependency (some packages like `langchain-text-splitters` pull in LangChain implicitly).

**Warning signs:**
- `ModuleNotFoundError: No module named 'langchain_core'` in production after deployment
- Startup health check failing with import error (not a Gemini API error)
- Any import in `app/` that is not inside a `try/except ImportError` block but uses a LangChain class

**Phase to address:** Phase 1 (Dependency Removal) — complete import graph audit must be the first task, before any code changes

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Running pydantic-ai and langchain-google-genai in the same requirements.txt during migration | Allows incremental feature-by-feature migration | Dependency conflict between google-genai and google-ai-generativelanguage SDKs; unpredictable runtime behavior | Only if tested and verified compatible; prefer clean cutover |
| Using `nest_asyncio.apply()` to fix event loop conflicts in Celery workers | Quick fix for the closed event loop error | Masks resource leaks; makes debugging harder; not compatible with all async libraries | Never in production Celery workers |
| Migrating agents one-by-one while keeping GeminiClient as the fallback | Low risk per story | Two code paths to maintain; PII redaction guardrails must be in both; test coverage complexity doubles | Only if migration is phased across multiple milestones, with a clear sunset date |
| Skipping output regression tests ("we'll compare manually") | Faster migration | Silent quality degradation in patient messages; banned pattern violations only discovered in production | Never — output regression tests are mandatory before cutover |
| Reusing ADK session state across invocations for "conversational memory" | Simpler per-invocation code | Dual state with Redis/PostgreSQL; no reconciliation; stale context if DB updates between sessions | Never — use stateless ADK invocations with context rebuilt from canonical store |
| Keeping `app/agents/` class names as-is after migration | No renaming effort | Future developers will continue trying to "migrate" these service classes to pydantic-ai | Acceptable only if a comment is added clearly stating these are service components, not LLM agents |

---

## Integration Gotchas

Common mistakes when connecting the new AI framework to existing system components.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Pydantic AI + Redis Cache | Assuming `output_type` validation output can be cached with the same cache key as the old hash-based `GeminiClient` key | The cache key in `GeminiClient._generate_cache_key()` is a SHA-256 of `profile_hint:prompt`. Pydantic AI agents have different call signatures. Rebuild the cache key generation from scratch for each agent type, and flush old gemini_cache:* keys at migration time. |
| Pydantic AI + Circuit Breaker | Using the existing `get_ai_circuit_breaker()` which wraps `_generate_content_internal()` — a method that no longer exists | Re-wrap the new Pydantic AI `agent.run()` calls inside a circuit breaker. The `FeatureNotAvailableError` exception contract must be preserved so all 15+ callers that catch it continue to work. |
| Pydantic AI + Rate Limiter | Calling `check_ai_rate_limit()` before `agent.run()` (currently in `GeminiClient._generate_content_internal()`) | Extract rate limiting into a decorator or shared utility that wraps any Pydantic AI agent invocation. It must not be an internal detail of GeminiClient. |
| Google ADK + Celery | Calling `adk_agent._run_async_impl()` directly with `asyncio.run()` | Use `agent.run_sync()` or a persistent event loop via `@worker_process_init.connect`. ADK's async impl uses httpx which has the same closed-loop cleanup problem as pydantic-ai. |
| Pydantic AI + Audit Trail | Calling `pydantic_ai.Agent.run()` with no audit wrapping | All AI operations must emit `AuditEventType.AI_QUERY` before and `AuditEventType.AI_RECOMMENDATION` after, the same as existing `GeminiClient` calls. This is an LGPD requirement. Wrap every agent call site in an audit context manager. |
| Pydantic AI GoogleModel + Async Redis | `GoogleModel` creating its own `httpx.AsyncClient` that conflicts with existing async Redis client in the same async context | Verify that both use compatible asyncio event loop state. Run integration tests that call both a Pydantic AI agent and a Redis operation in the same async function. |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Google ADK ParallelAgent for all 4 AI operations by default | Higher Gemini API costs, quota exhaustion, inconsistent output order | Use ParallelAgent only when operations are truly independent and order-invariant. Humanization must precede sentiment analysis. | At high patient message volume (50+ concurrent flows) |
| Pydantic AI `max_retries` set to match old `guardrail_retries=2` without timeout | Retry storms when the model consistently produces invalid output (e.g., network issue causing empty responses) | Set both `max_retries` AND a `total_timeout` on `agent.run()`. The existing circuit breaker must also wrap the retry loop to prevent retry amplification during Gemini API outages. | During any Gemini API degradation event |
| `google-adk` full install in production Docker image | 300-400MB image size increase; 15-30s Cloud Run cold start increase | Install only the ADK components needed. Check if `google-adk` has a slim install or if only specific submodules are required for SequentialAgent/ParallelAgent without the full GCP service SDK. | Immediately on first deployment |
| Rebuilding full patient context from DB/Redis on every Pydantic AI agent invocation | 100-200ms DB overhead per AI operation | Cache the compiled `PatientAIContext` in Redis with a 60s TTL per patient. This was implicitly handled by the LangGraph thread_id state cache. The new agents are stateless, so the cache must be rebuilt explicitly. | At >20 concurrent patient message flows |
| Pydantic AI agents created per request | New `Agent` object instantiation overhead; Google API client re-initialization | Create agents as module-level singletons (like `get_gemini_client()` pattern), not per-request. The `GoogleModel` initialization is expensive. | At >10 req/s |

---

## Security Mistakes

Domain-specific security issues specific to this migration.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Patient data in Pydantic AI `RunContext.deps` without redaction | PHI (name, phone, CPF) reaches Google Gemini API, violating LGPD Art. 46 | Create a `PatientAIContext` dataclass with only pre-redacted fields; validate in CI that no Patient ORM object is passed to `agent.run()` |
| System prompt containing patient name placeholder injected at construction time | System prompt logged in plaintext; patient name cached in `Agent` object memory | System prompts must be static and patient-agnostic; all patient context passes through the user prompt which is sanitized by `sanitize_prompt_text_for_external_ai()` |
| LangGraph checkpoint data in Redis not cleaned up after migration | Old checkpoint data may contain conversation history with patient identifiers that was stored pre-redaction (before PII redaction was applied to state objects) | Audit what the old `FlowMessageState` stored; if it contained patient names, the Redis cleanup script must be treated as a PHI purge and logged as a LGPD data deletion event |
| Pydantic AI `output_type` schema exposed in error logs | Validation errors include the full schema definition; if patient data is embedded in the schema via dynamic enum values, it appears in logs | Output type schemas must be static; never generate `Enum` values from patient data |
| Google ADK tool invocations not audited | Agent tool calls (e.g., database lookups) bypass the existing audit trail | Every tool registered with an ADK agent must emit an audit event for `AuditEventType.AI_QUERY`; tool results must be sanitized before logging |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces in this specific migration.

- [ ] **LangGraph removed**: `requirements.txt` no longer has `langgraph`, `langchain-core`, `langchain-google-genai` — but verify that all 15+ files that imported from these packages have been updated and that `python -c "import app.main"` succeeds
- [ ] **Redis checkpoint cleanup**: LangGraph package removed — but verify that `langgraph:checkpoint:*` keys are absent from the Dragonfly instance (run the cleanup script and confirm)
- [ ] **PII redaction preserved**: New Pydantic AI agents invoke Gemini — but verify that `sanitize_prompt_text_for_external_ai()` is called before EVERY `agent.run()` invocation, not just in one wrapper class
- [ ] **Output guardrails preserved**: Agents return structured output — but verify that banned pattern detection, prompt leak markers check, length validation, and ending punctuation check are applied as `@result_validator` decorators or equivalent
- [ ] **Circuit breaker preserved**: Agents can call Gemini — but verify that `FeatureNotAvailableError` is raised when the circuit is open and that existing catch blocks in `enhanced_flow_engine.py`, `sequential_message_handler.py`, and other callers still work
- [ ] **Rate limiter preserved**: Agents have API access — but verify that `check_ai_rate_limit()` is called before each invocation and the in-process fallback limiter still works when Redis is unavailable
- [ ] **Celery async bridge correct**: Agents are callable from Celery tasks — but verify with 100 sequential task invocations that no `RuntimeError: Event loop is closed` occurs and worker memory is stable
- [ ] **Audit trail complete**: AI operations happen — but verify that `AuditEventType.AI_QUERY` and `AuditEventType.AI_RECOMMENDATION` events are emitted for every agent invocation that processes patient data
- [ ] **Output regression tests pass**: New agents produce output — but verify that 50 canonical patient scenarios produce output that passes ALL existing guardrail checks (not just Pydantic schema validation)
- [ ] **Service classes not converted**: 5 `app/agents/` classes exist — but verify none of them were converted to `pydantic_ai.Agent` instances (they should remain as service classes)

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Dependency conflict discovered after deployment | MEDIUM | Roll back to previous Docker image immediately; resolve conflict in a dedicated branch with `pip install --dry-run` testing; redeploy |
| PII data sent to Google API via unredacted agent call | HIGH | Report to ANPD within 72 hours (LGPD Art. 48); collect evidence of which patients and what data; apply the `PIISafeAgent` wrapper immediately; audit all agent call sites |
| Redis checkpoint data confirmed to contain PHI | HIGH | Execute cleanup script immediately as LGPD data purge; log purge as LGPD deletion event; ANPD notification if data was present for >72 hours without redaction |
| Output guardrail regression discovered in production | MEDIUM | Roll back to GeminiClient temporarily; add missing guardrail validators to agents; run full regression test suite; redeploy |
| Event loop memory leak in Celery workers | MEDIUM | Restart workers immediately (clears memory); switch to `agent.run_sync()` pattern; verify fix with 100-task load test |
| LangGraph import errors after removal | LOW | Roll back to previous image; audit all LangGraph imports with grep; fix import graph; redeploy |
| ADK session state conflict with Redis state | HIGH | Disable ADK session persistence (switch to `InMemorySessionService`); reconcile patient state from canonical PostgreSQL source; purge ADK session data |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| google-adk vs langchain-google-genai dependency conflict | Phase 1: Dependency Migration | `pip install --dry-run` resolves cleanly; Docker build succeeds; `python -c "import app.main"` passes |
| PII redaction bypass in Pydantic AI agents | Phase 2: Agent Implementation | CI lint check for direct `.run()` calls; integration test sends patient context and verifies no PII in Gemini API request body |
| async_to_sync + GoogleModel event loop conflict | Phase 2: Celery Integration | 100-task Celery load test with no RuntimeError and stable memory |
| LangGraph Redis checkpoint data not cleaned | Phase 1: Dependency Migration | Post-deployment scan shows zero `langgraph:checkpoint:*` keys in Dragonfly |
| Output guardrails not re-applied to new agents | Phase 2: Agent Implementation | Output regression test suite covering 50 patient scenarios passes all guardrail assertions |
| Service classes misidentified as LLM agents | Phase 1: Scope Definition | Architecture document explicitly lists 4 AI operations (not 5 agents); no `pydantic_ai.Agent` in `app/agents/` |
| ADK session state conflict with Redis | Phase 2: Architecture | ADK integration uses `InMemorySessionService` only; no SQLite files or ADK session tables in DB |
| LangChain import graph not fully cleaned | Phase 1: Dependency Migration | `grep -r "from langchain\|from langgraph" app/` returns zero results after migration |
| Missing circuit breaker on new agents | Phase 2: Agent Implementation | Circuit breaker test: simulate Gemini API error → verify `FeatureNotAvailableError` raised → verify all 15+ callers handle it |
| Missing audit trail for new AI operations | Phase 2: Agent Implementation | Integration test verifies `AI_QUERY` + `AI_RECOMMENDATION` audit events emitted for each new agent invocation |

---

## Sources

- Codebase analysis: `/backend-hormonia/app/ai/client.py` — GeminiClient with PII redaction, guardrails, circuit breaker, rate limiter (confirmed integration points that must be preserved)
- Codebase analysis: `/backend-hormonia/app/ai/langgraph/runtime.py` — Redis checkpoint key patterns (`langgraph:checkpoint:{graph_name}:*`)
- Codebase analysis: `/backend-hormonia/app/ai/pii_redaction.py` — `sanitize_prompt_text_for_external_ai()` and `redact_patient_context()` (mandatory LGPD guardrails)
- Codebase analysis: `/backend-hormonia/app/services/ai/guardrails.py` — banned pattern detection, prompt leak markers, placeholder detection, length validation
- Codebase analysis: `/backend-hormonia/app/agents/` — 5 service classes named "agents" that have zero LLM calls
- Codebase analysis: `/backend-hormonia/requirements.txt` — current dependency pinning and LangChain ecosystem packages
- [google-adk PyPI: Dependencies include google-genai>=1.56.0](https://pypi.org/project/google-adk/) — confirmed ADK uses google-genai (not langchain-google-genai)
- [pydantic-ai Issue #1887: instructions/system_prompt not working for GoogleModel](https://github.com/pydantic/pydantic-ai/issues/1887) — system prompt passing via constructor is broken with some google-genai versions; fixed in PR #1922
- [pydantic-ai Issue #3762: RuntimeError: Event loop is closed when using GoogleModel with asyncio.run()](https://github.com/pydantic/pydantic-ai/issues/3762) — httpx connection cleanup after loop close
- [pydantic-ai Issue #748: Gemini causes 'Event loop is closed' when running inside an async context](https://github.com/pydantic/pydantic-ai/issues/748) — same class of loop management bug
- [langchain-google-genai 4.0.0 Release Discussion: Migration to google-genai SDK](https://github.com/langchain-ai/langchain-google/discussions/1422) — breaking change: gRPC removed; now uses google-genai directly; 50-250% latency increase reported for some users after migration
- [google-adk Installation DeepWiki](https://deepwiki.com/google/adk-python/2.1-installation) — ADK requires google-genai>=1.56.0; full GCP dependency tree
- [Google ADK Sequential and Parallel Agents Documentation](https://google.github.io/adk-docs/agents/workflow-agents/sequential-agents/) — confirmed ADK uses InvocationContext sharing between SequentialAgent sub-agents
- [Google ADK Safety and Security Documentation](https://google.github.io/adk-docs/safety/) — Gemini as a Judge, in-tool guardrails, callback-based screening
- [Pydantic AI Output Documentation](https://ai.pydantic.dev/output/) — `output_type` validation scope (structure only, not content semantics)
- [Pydantic AI Evaluations Framework](https://deepwiki.com/pydantic/pydantic-ai/5.1-evaluation-framework) — regression testing approach for LLM output quality
- [Comparing Agent Frameworks: PydanticAI, LangChain 1.0 and Google ADK](https://levelup.gitconnected.com/comparing-agent-frameworks-pydanticai-langchain-1-0-and-google-adk-4d2d46d927f0) — framework differences and integration considerations
- [LangGraph Redis Checkpoint Migration Guide](https://github.com/redis-developer/langgraph-redis/blob/main/MIGRATION_0.2.0.md) — Redis key patterns and cleanup requirements

---
*Pitfalls research for: AI Framework Migration — LangGraph to Pydantic AI + Google ADK, Healthcare Oncology WhatsApp Backend*
*Researched: 2026-02-23*
