# Project Research Summary

**Project:** Clinica Oncologica v1.2 — AI Framework Migration (LangGraph to Pydantic AI)
**Domain:** Healthcare WhatsApp backend — AI framework replacement milestone
**Researched:** 2026-02-23
**Confidence:** HIGH (Pydantic AI stack and pitfalls), MEDIUM (ADK integration patterns — blocked by dependency conflicts), HIGH (feature requirements and clinical guardrails)

---

## Executive Summary

This is a framework replacement milestone, not a new product or a greenfield build. The oncology backend already delivers 4 working AI operations (message humanization, sentiment analysis, question variation, empathetic follow-up) through a LangGraph graph layer wrapping `GeminiClient`. The goal is to remove LangGraph entirely and replace its two responsibilities: (1) the 4 AI operations, migrated to typed `pydantic-ai` agents; and (2) the 2 flow routing graphs (2-node, conditional), replaced with direct async Python functions. The existing `GeminiClient` (757 LOC, production-hardened with Redis cache, circuit breaker, rate limiter, PII redaction, and output guardrails) is preserved as the execution backend throughout the migration. Nothing changes for callers in `flow_core.py`, `flow_service.py`, and `enhanced_flow_engine.py` — they interact through the same `GeminiDomainClient` interface, which becomes a routing shim during transition.

**Critical conflict reconciliation:** The Stack and Pitfalls researchers both independently confirmed that `google-adk` has irresolvable dependency conflicts with this stack: an OpenTelemetry version upper-bound cap (`<1.39.0`) that conflicts with the existing range (`<2.0.0`), a bundled FastAPI/Starlette sub-dependency that creates documented schema failures with Pydantic 2.11+ (issue #3173, unfixed as of 2026-02-23), and a heavy GCP footprint (aiplatform, spanner, bigtable) adding 300-400 MB to the Docker image. The Architecture researcher proposed ADK `SequentialAgent`/`ParallelAgent` patterns without verifying these conflicts — those patterns are architecturally sound and are documented here for future use, but cannot be implemented with `google-adk` in v1.2. The resolution for v1.2 is to replace both 2-node LangGraph graphs with direct async Python functions (10-15 lines each). Pydantic AI alone provides all the typed agent infrastructure needed for the 4 AI operations. ADK is formally deferred to v1.3, conditional on issue #3615 (lightweight core install) being resolved.

The two primary risks in this migration are clinical safety and output quality regression. PII redaction is currently enforced automatically inside `GeminiClient` and will become an explicit manual responsibility in the new agent layer — any agent that calls Gemini without invoking `sanitize_prompt_text_for_external_ai()` first sends patient names, CPF numbers, and phone numbers to Google's servers, violating LGPD Art. 46 and Art. 11. Output quality risk arises because pydantic-ai's `output_type` schema validation enforces structure but not content semantics — the existing healthcare-specific guardrails (banned patterns, prompt leak detection, Brazilian Portuguese punctuation rules, character length bounds) must be explicitly reconnected via `@result_validator` decorators. Both risks are preventable with a `PIISafeAgent` wrapper class and a 50-scenario output regression test suite that must pass before any agent replaces the production path.

---

## Key Findings

### Recommended Stack

The stack decision is clear: add `pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0` (production-stable since September 2025, MIT license, Python 3.10-3.14 confirmed) and remove the four LangChain-era packages (`langgraph`, `langchain-core`, `langchain-google-genai`, `google-ai-generativelanguage`) after migration completes. The `[google]` extra pulls in `google-genai>=1.56.0` transitively — this new unified Google SDK is what both pydantic-ai and langchain-google-genai 4.x now use, so both can coexist during the migration transition without version conflict. The `[retries]` extra uses `tenacity` (already in requirements) for HTTP-level retry transport. All other packages (`pydantic>=2.12.5`, `httpx>=0.28.1`, `aiobreaker`, `google-auth`, `google-api-core`) are already compatible and require no changes.

`google-adk` must not be added in v1.2. The conflicts are technical, documented in open GitHub issues with no resolution timeline, and are not solvable by version pinning. The two 2-node LangGraph graphs are simple conditional routing logic that 10-15 lines of async Python replaces completely. ADK is a framework designed to be a server, not to be embedded in one — this backend is already a FastAPI server.

**Core technologies to add:**
- `pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0`: Typed agents with `deps_type` DI, `output_type` schema validation, `RunContext` typed dependency injection, `TestModel` for test isolation — replaces LangGraph graph execution for the 4 AI operations; pin to `<2.0.0` because V2 is planned for April 2026 with breaking API changes
- `google-genai>=1.56.0` (transitive via `[google]` extra): New unified Google SDK replacing `google-ai-generativelanguage`; do not pin separately unless a direct use is needed outside pydantic-ai
- `GeminiClient` (existing, unchanged): Execution backend for all pydantic-ai agents; contains Redis cache, circuit breaker, PII redaction, rate limiter, and output guardrails that must not be bypassed or replaced

**Do not add:**
- `google-adk`: OTel version cap conflict (`<1.39.0` vs existing `<2.0.0`), bundled FastAPI/Starlette schema failures with Pydantic 2.11+ (issue #3173), 300-400 MB GCP dependency footprint — defer to v1.3
- `pydantic-ai` (full): Installs all model providers and Logfire; `pydantic-ai-slim[google,retries]` is the correct variant for a Google-only deployment

**To remove after migration completes:**
- `langgraph>=1.0.7`, `langchain-core>=1.2.7`, `langchain-google-genai>=2.1.12`, `google-ai-generativelanguage>=0.7.0` — remove in the same commit in Phase 3; do not remove incrementally

### Expected Features

This migration has a clear P1/P2/P3 tiering based on correctness vs. optimization. All P1 items are required for the migration to be production-safe. Missing any P1 item means the migration is broken, regresses existing behavior, or creates LGPD violations.

**Must have — migration correctness and clinical safety (P1):**
- `HumanizeAgent`, `SentimentAgent`, `QuestionVariationAgent`, `EmpathyAgent` — 4 pydantic-ai agents replacing `GeminiDomainClient` methods; same interface, same clinical behavior
- `PromptedOutput(SentimentResult)` for SentimentAgent — Gemini cannot use tool-calling and native structured output simultaneously; `PromptedOutput` mode (injects JSON schema into system prompt) is the documented workaround; the `SentimentResult` model must preserve all 7 fields exactly (`sentiment`, `confidence`, `emotional_indicators`, `medical_concerns`, `requires_attention`, `key_themes`, `suggested_follow_up`) because downstream alert logic has implicit `KeyError` on any missing field
- `allow_questions`/`day_complete` flags in `EmpathyDeps` — these are clinical decisions controlling whether AI may ask patients follow-up questions; must be injected into the dynamic system prompt via `deps`, not hardcoded
- `_is_too_similar_to_recent()` post-run check preserved in `QuestionVariationAgent` — the 88% word-overlap anti-repetition threshold is a patient disengagement prevention feature, not a style preference
- `PIISafeAgent` wrapper class in `app/ai/agents/base.py` — the only sanctioned way to call any pydantic-ai agent; applies `sanitize_prompt_text_for_external_ai()` before every invocation; CI lint rule blocks direct `.run()` calls; mandatory before any agent goes to production
- `@result_validator` decorators reconnecting healthcare guardrails — banned patterns, prompt leak markers, character length bounds, Brazilian Portuguese ending punctuation; pydantic-ai `output_type` does not provide these; reuse `app/services/ai/guardrails.py` logic
- `GeminiDomainClient` shim with `AI_FRAMEWORK` feature flag — all 4 methods delegate to new agents via flag, same signatures for callers; enables per-operation rollout and instant rollback
- `FeatureNotAvailableError` exception contract preserved — 15+ callers throughout the codebase catch this; do not introduce new exception types
- Redis cache (SHA-256 key, 3600s TTL) preserved in shim wrapper around each agent call
- Circuit breaker wrapping each `agent.run()` call; `aiobreaker` pattern kept
- Audit events (`AuditEventType.AI_QUERY`, `AuditEventType.AI_RECOMMENDATION`) emitted for every agent invocation — LGPD accountability requirement; currently inside GeminiClient, must be explicit in new wrapper
- Consensus system deleted outright (`consensus.py`, `consensus_manager.py` — confirmed zero callers)
- 50-scenario output regression test suite — must pass all guardrail assertions before any agent replaces the production path

**Should have — full LangGraph removal (P2):**
- `build_flow_message_graph()` replaced with direct async Python function (10-15 lines, `AI_FLOW_FRAMEWORK` feature flag)
- `build_flow_response_graph()` replaced with direct async Python function (10-15 lines)
- Complete LangGraph import graph audit and cleanup (`python -c "import app.main"` succeeds with zero LangChain imports)
- LangGraph checkpoint Redis cleanup script (`scan_iter`-based, idempotent, batch-delete, treated as LGPD PHI purge event)
- `langgraph`, `langchain-core`, `langchain-google-genai`, `google-ai-generativelanguage` removed from `requirements.txt`
- `app/ai/langgraph/` directory tombstoned (all files raise `ImportError`)

**Defer to v1.3+ (P3):**
- `google-adk` integration (SequentialAgent, ParallelAgent) — blocked by dependency conflicts; revisit when issue #3615 is resolved
- Parallel sentiment + empathy processing via `asyncio.gather` or ADK ParallelAgent
- `GoogleModelSettings` per operation type (different temperatures for message vs. JSON operations)
- `UsageLimits` per agent run complementing distributed rate limiter
- `GeminiClient` migration from `ChatGoogleGenerativeAI` to direct `google-genai` SDK (last remaining LangChain import after Phase 3)

**Anti-features confirmed — do not implement in v1.2:**
- Native structured output mode for Gemini (`NativeOutput`) — blocks tool-calling simultaneously; confirmed limitation issues #582, #1237, #3483
- Full streaming of agent output — unsupported with structured outputs; healthcare messages must be fully validated before delivery
- ADK `LlmAgent` for deterministic flow logic — adds ~500ms LLM call per invocation for what is pure Python DB/cache logic
- ADK `DatabaseSessionService` or `VertexAiSessionService` — creates dual state with Redis/PostgreSQL, no reconciliation mechanism
- `ModelRetry` alongside existing `guardrail_retries` — two retry loops amplify each other during API degradation; configure `output_retries=0` and handle retries at the caller level
- `nest_asyncio.apply()` in Celery workers — masks resource leaks, not production-safe

### Architecture Approach

The migration separates into two clearly bounded layers. The Pydantic AI layer (`app/ai/agents/`) contains 4 agents that assemble typed prompts via `deps_type` and call `GeminiClient.generate_content()` as their execution backend — the GeminiClient remains completely unchanged, providing all production protections. The flow routing layer (replacing `app/ai/langgraph/graphs.py`) becomes direct async Python in `sequential_message_handler.py`, with the 2-node conditional routing expressed as simple `if/await` sequences. Feature flags (`AI_FRAMEWORK`, `AI_FLOW_FRAMEWORK` env vars in settings) route each operation independently, enabling incremental rollout and instant rollback without redeployment.

The key insight from reconciling the researcher conflict: the Architecture researcher's component design for `app/ai/agents/` is adopted in full. The proposed `app/ai/adk/` layer (ADKRunner, FlowMessageAgent, FlowResponseAgent) is architecturally correct but installation-blocked — it is documented as the target design for v1.3 ADK integration. The `SequentialAgent` pattern proposed for flow routing is replaced in v1.2 with direct async Python that produces identical runtime semantics.

**Major components:**
1. `app/ai/agents/` (NEW) — 4 pydantic-ai agents (`humanize.py`, `sentiment.py`, `question_variation.py`, `empathy.py`); `base.py` with `PIISafeAgent` wrapper and shared `AIDeps` dataclass
2. `app/ai/prompts/` (RELOCATED) — prompt builders moved from `app/ai/langgraph/prompts.py` + `nodes_ai.py` with no content changes; called by agent `system_prompt` builders via `deps`
3. `app/ai/client_domain.py` (REWORKED as shim) — all 4 `GeminiDomainClient` methods delegate to new agents via `AI_FRAMEWORK` feature flag; same signatures; tombstoned after full migration
4. `app/services/flow/sequential_message_handler.py` (REWORKED) — LangGraph `graph.ainvoke()` replaced with direct `async def execute_flow_message(state, handler)` and `async def execute_flow_response(state, handler)` functions; `AI_FLOW_FRAMEWORK` flag routes between old and new paths during validation
5. `app/ai/langgraph/` (TOMBSTONED in Phase 3) — all files raise `ImportError` after migration; `consensus.py` and `consensus_manager.py` deleted outright (not tombstoned) in Phase 1

**Critical data flow preservation:**
- PII path: `sanitize_prompt_text_for_external_ai()` must fire before every `agent.run()` — currently automatic in `GeminiClient._redact_prompt_for_external_ai()`; made explicit in `PIISafeAgent.run()` wrapper
- Audit path: `AuditEventType.AI_QUERY` before and `AuditEventType.AI_RECOMMENDATION` after every agent invocation — LGPD requirement; currently inside `GeminiClient`; must be explicit in new wrapper layer
- Exception path: `FeatureNotAvailableError` on circuit-open or empty output — 15+ callers catch this; exception contract must not change

### Critical Pitfalls

1. **PII redaction bypass in pydantic-ai agents (LGPD violation risk):** `GeminiClient` applies `sanitize_prompt_text_for_external_ai()` automatically on every call. Pydantic-ai agents do not have any input sanitization. Every agent call that skips this sends patient names, CPF numbers, and phone numbers to Google's servers, violating LGPD Art. 46 and Art. 11. Prevention: create `PIISafeAgent` wrapper class in `app/ai/agents/base.py` as the only sanctioned way to call agents; add CI lint rule blocking direct `.run()` calls; pass `PatientAIContext` dataclass with only pre-redacted fields to `deps`, never raw `Patient` ORM objects.

2. **Output guardrails silently dropped:** Pydantic-ai `output_type` validates Pydantic schema structure only. It does NOT check banned patterns ("as an AI language model"), prompt leak markers ("MENSAGEM HUMANIZADA"), Brazilian Portuguese ending punctuation, or character length bounds. These guardrails currently fire automatically in every `GeminiClient.generate_content()` call via `app/services/ai/guardrails.py`. If not reconnected via `@result_validator` decorators, the migration silently removes clinical output protection. Prevention: reconnect all guardrails as `@result_validator` decorators on each agent; require a 50-scenario output regression test suite passing all guardrail assertions before any agent goes to production.

3. **google-adk cannot be installed — irresolvable dependency conflicts:** The Architecture researcher proposed ADK as the primary flow routing replacement without verifying the dependency layer. Both Stack and Pitfalls researchers independently confirmed three blocking conflicts: OTel version cap `<1.39.0` (existing requirement allows `<2.0.0`), bundled FastAPI/Starlette schema failures with Pydantic 2.11+ (issue #3173, open and unresolved), and 300-400 MB GCP footprint from mandatory aiplatform/spanner/bigtable pull-in. Prevention: do not add `google-adk` to requirements.txt in v1.2. Replace the 2 LangGraph graphs with direct async Python. Re-evaluate at v1.3 planning time after checking issue #3615 status.

4. **async_to_sync + GoogleModel event loop conflict in Celery workers:** Pydantic-ai's `GoogleModel` uses `httpx` with `google-genai`'s async client. When `asgiref.sync.async_to_sync()` (the established Celery bridge pattern in this codebase, used in `tasks/flows/base.py`) wraps `agent.run()`, the `httpx` connection pool cleanup fires after the thread's event loop closes, producing `RuntimeError: Event loop is closed` under sequential load (confirmed pydantic-ai issues #3762, #748). Prevention: use `agent.run_sync()` for Celery task contexts instead of wrapping `agent.run()` with `async_to_sync()`; if async DB access is needed inside agents, use a persistent event loop via `@worker_process_init.connect`; validate with 100-task sequential Celery load test before declaring migration complete; never use `nest_asyncio.apply()` as a workaround.

5. **LangGraph checkpoint Redis data is a LGPD PHI purge event, not just a cleanup:** `RedisCheckpointer` in `runtime.py` stored data under `langgraph:checkpoint:*` keys in Dragonfly DB 0. Index keys using `sadd` accumulate garbage that does not auto-expire with set member TTLs. Critically, some checkpoint data may contain conversation state written before PII redaction was applied to state objects — meaning this cleanup qualifies as a LGPD PHI purge event, not just a maintenance task. Prevention: write an idempotent `scan_iter`-based cleanup script (never `keys()`), delete in batches of 500, execute at the same deployment that removes LangGraph, log the purge count as a LGPD data deletion event; if checkpoint data is confirmed to contain PHI, report the purge timeline to the LGPD compliance record.

---

## Implications for Roadmap

Based on combined research, a 4-phase structure is recommended. The dependency chain is clear and non-negotiable: scope boundary must be established before implementation begins; agent implementation must complete before LangGraph is removed; LangGraph removal completes the migration.

### Phase 1: Scope Boundary and Dependency Preparation

**Rationale:** Two scope errors would derail Phase 2 if not resolved first. First: the 5 classes in `app/agents/` (AlertAnalyzer, PatientMonitor, MessageComposer, ResponseProcessor, FlowCoordinator) are DDD service components with zero LLM calls — they are named "agents" for domain reasons, not AI reasons. Attempting to migrate them to `pydantic_ai.Agent` would add LLM calls to deterministic service logic and increase response latency by hundreds of milliseconds. Second: there are 15+ non-AI files that import from `langchain_core`, `langchain_google_genai`, or `langgraph` — a complete import graph audit is required before any package removal is attempted; missing any import creates a `ModuleNotFoundError` at startup.
**Delivers:** Architecture decision document identifying exactly 4 AI operations (not 5 "agents") as migration targets; complete LangChain import graph audit results; `pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0` added to `requirements.txt` (coexists safely with current LangChain packages during migration); `google-adk` formally deferred with documented rationale; one-line scope comments added to all `app/agents/` files clarifying they are service components; consensus system (`consensus.py`, `consensus_manager.py`) deleted immediately (zero callers, no risk); LangGraph checkpoint Redis cleanup script written and ready for Phase 3 deployment.
**Addresses features:** Consensus system deletion (P1); scope boundary for 4 AI operations (P1)
**Avoids pitfalls:** Service classes misidentified as LLM agents (Pitfall 6); LangChain import graph not audited before removal (Pitfall 8); google-adk dependency conflicts (Pitfall 3)
**Research flag:** Standard patterns — no phase research needed. All decisions are fully resolved by existing research.

### Phase 2: Pydantic AI Agent Implementation (4 Operations)

**Rationale:** This is the highest-value and highest-risk phase. The recommended build order follows the dependency graph from research: `SentimentAgent` first (most benefit from typed output — replaces the most fragile current code: manual `json.loads()` + `_parse_sentiment_analysis()` + `AIResponseValidation.validate_sentiment()` triple-parsing chain); then `HumanizeAgent`, `QuestionVariationAgent`, `EmpathyAgent` can be built in parallel (same GeminiClient integration pattern, once SentimentAgent validates it). The `GeminiDomainClient` shim with `AI_FRAMEWORK` feature flag must exist before the first agent ships — it enables per-operation rollout and instant rollback without code deployment. `PIISafeAgent` wrapper and output guardrail reconnection are P1 requirements; no agent ships to production without them.
**Delivers:** 4 pydantic-ai agents with typed output; `PIISafeAgent` wrapper enforcing PII redaction before every invocation; `@result_validator` guardrails reconnected; Redis cache preserved in shim; circuit breaker wrapping each `agent.run()`; `FeatureNotAvailableError` contract preserved; audit events emitted; Celery async bridge validated with 100-task load test; 50-scenario output regression test suite passing all guardrail assertions.
**Uses:** `pydantic-ai-slim[google,retries]>=1.63.0`; `PromptedOutput(SentimentResult)` for SentimentAgent; `output_type=str` for the 3 text agents; existing `GeminiClient` as execution backend; `app/services/ai/guardrails.py` reused in `@result_validator` decorators
**Implements:** `app/ai/agents/` layer (4 agents + base PIISafeAgent); `app/ai/prompts/` relocation from `langgraph/`; `GeminiDomainClient` shim
**Avoids pitfalls:** PII redaction bypass (Pitfall 1); output guardrails silently dropped (Pitfall 2); event loop conflict in Celery (Pitfall 4); missing circuit breaker and audit trail (integration gotchas)
**Research flag:** Phase research recommended for two areas: (a) Celery async bridge — `pydantic-ai run_sync()` behavior with `google-genai` httpx client under Celery 5.x process model needs a validation spike before stories are sized; (b) `PromptedOutput(SentimentResult)` validation against `gemini-2.5-flash` — pydantic-ai issues #582 and #3483 document edge cases with Gemini structured outputs; a 1-day validation spike should be the first Phase 2 task.

### Phase 3: LangGraph Removal

**Rationale:** Must follow Phase 2. LangGraph can only be removed after all 4 agents are validated in staging with real traffic for at least one week with zero errors. The 2 flow routing graphs are replaced with direct async Python in `sequential_message_handler.py`. LangGraph must remain importable until the new routing path is validated — a Railway redeployment to re-add LangGraph is the rollback cost if removed prematurely. The LangGraph checkpoint Redis cleanup is treated as a LGPD PHI purge event and must be logged as such.
**Delivers:** `build_flow_message_graph()` and `build_flow_response_graph()` replaced with direct async Python functions (10-15 lines each); `app/ai/langgraph/` directory fully tombstoned (all files raise `ImportError` with migration message); `langgraph`, `langchain-core`, `langchain-google-genai`, `google-ai-generativelanguage` removed from `requirements.txt` in a single commit; `python -c "import app.main"` passes with zero LangChain/LangGraph imports; LangGraph checkpoint cleanup script executed and LGPD purge logged; Dragonfly scan confirms zero `langgraph:checkpoint:*` keys.
**Avoids pitfalls:** LangGraph import graph not fully cleaned (Pitfall 8); LangGraph checkpoint PHI purge not treated as LGPD event (Pitfall 5); premature LangGraph removal before cutover validation (Architecture Anti-Pattern 4)
**Research flag:** Standard patterns — async Python replacement for 2-node conditional graphs is straightforward; patterns are fully documented in STACK.md and ARCHITECTURE.md research with code examples.

### Phase 4: Post-Migration Cleanup and ADK Readiness Assessment

**Rationale:** After Phase 3, the migration is functionally complete. `GeminiClient` still uses `ChatGoogleGenerativeAI` from `langchain-google-genai` internally (the last remaining LangChain reference in the entire backend). This phase migrates `GeminiClient._initialize_model()` and `_generate_content_internal()` to direct `google-genai` SDK, completing the full LangChain removal. It also produces a formal ADK dependency conflict re-assessment — if `google-adk` issue #3615 is resolved, a v1.3 ADK integration story can be drafted.
**Delivers:** `GeminiClient` fully migrated from `ChatGoogleGenerativeAI` to direct `google-genai` SDK; `HumanMessage` import from `langchain-core` removed from `client.py`; zero LangChain imports remaining anywhere in the backend; ADK issue #3615 status re-assessed against latest `google-adk` release; v1.3 ADK integration story drafted if conflict is resolved.
**Research flag:** Phase research recommended for `GeminiClient` SDK migration — the client is 757 LOC with retry logic, connection pool management (`_ensure_model_for_loop`), and loop-safe reinitialization; migrating from `ChatGoogleGenerativeAI` to direct `google-genai` SDK is medium complexity (~50 LOC change) but requires careful validation of all 8 execution paths (cache hit, cache miss, circuit open, rate limited, guardrail fail, retry, timeout, success).

### Phase Ordering Rationale

- Phase 1 before Phase 2: Scope errors and import graph blind spots are cheaper to fix before code is written than after 4 agents are implemented against incorrect assumptions.
- Phase 2 before Phase 3: The feature flag coexistence strategy requires LangGraph to remain importable during agent validation. Removing LangGraph before agents are validated eliminates the rollback option.
- Phase 3 after one week of validated traffic: The `AI_FLOW_FRAMEWORK` flag must gate the cutover; only remove LangGraph after the new routing path has been confirmed stable.
- Phase 4 last: `GeminiClient` SDK migration requires all other LangChain packages to be gone first (Phase 3); it is also the lowest urgency item.
- ADK deferred to v1.3: The dependency conflicts are documented, open, and have no resolution timeline. The async Python replacement delivers identical runtime behavior with zero new risk.

### Research Flags

Phases needing deeper research during planning:
- **Phase 2 (Celery bridge validation):** `pydantic-ai run_sync()` + `google-genai` httpx client under Celery 5.x process model needs a validation spike. The event loop conflict is documented but the `run_sync()` fix is MEDIUM confidence — needs a 100-task Celery load test before stories are finalized.
- **Phase 2 (PromptedOutput with Gemini):** `PromptedOutput(SentimentResult)` mode needs a 1-day validation spike against `gemini-2.5-flash` before Phase 2 story AC is finalized. Issues #582 and #3483 document edge cases that may require workarounds even for flat schemas.
- **Phase 4 (GeminiClient SDK migration):** Direct `google-genai` SDK replacement for `ChatGoogleGenerativeAI` in a 757-LOC production client warrants a dedicated research spike before implementation begins; not a straightforward find-and-replace.

Phases with standard patterns (research-phase not needed):
- **Phase 1:** Scope boundary decisions and import graph audits are deterministic, fully documented in existing research with exact file locations.
- **Phase 3:** Async Python replacement for 2-node conditional graphs is fully documented with code examples in STACK.md and ARCHITECTURE.md; no novel patterns required.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | `pydantic-ai-slim[google,retries]>=1.63.0` verified against PyPI, pyproject.toml, and official docs. google-adk conflict verified against 3 independent GitHub issues (#2657, #3173, #3615) plus pyproject.toml dependency analysis. Version compatibility matrix fully resolved for all existing packages. |
| Features | HIGH | All 4 AI operations verified against codebase (`app/ai/client_domain.py`, `app/ai/langgraph/nodes_ai.py`). `PromptedOutput` mode verified against official pydantic-ai docs. Gemini structured output limitations verified against issues #582, #1237, #3483. Clinical safety requirements (PII, guardrails, anti-repetition, flag injection) verified against `app/ai/pii_redaction.py`, `app/services/ai/guardrails.py`, and `app/ai/langgraph/nodes_ai.py`. |
| Architecture | MEDIUM | Pydantic AI agent patterns: HIGH (official docs + codebase analysis). ADK patterns: architecturally correct as designs but installation-blocked — MEDIUM because the Architecture researcher did not verify the dependency layer and initially proposed ADK as a first-class solution. The programmatic Python alternative is HIGH confidence. Custom `BaseAgent` subclass API surface for future ADK work: MEDIUM (community sources + GitHub discussions). |
| Pitfalls | HIGH | All 8 critical pitfalls grounded in codebase evidence (grep-verified import counts, Redis key patterns confirmed from `runtime.py`, event loop issues confirmed from pydantic-ai issue tracker). Recovery costs realistically assessed. LGPD violation risk scenarios verified against LGPD Art. 46, 48, and 11 text. |

**Overall confidence:** HIGH

### Gaps to Address

- **`PromptedOutput` validation against production Gemini model:** The correct output mode for `SentimentAgent` is MEDIUM confidence. A 1-day spike against `gemini-2.5-flash` should be the first task in Phase 2 before any agent implementation stories are planned. If `PromptedOutput` fails on the flat `SentimentResult` schema, the fallback is `model_validate(json.loads(result))` at the shim layer (lower elegance but same safety).
- **Celery async bridge confidence gap:** `agent.run_sync()` as the fix for the event loop conflict is documented pydantic-ai behavior but has not been validated against the specific combination of `pydantic-ai-slim==1.63.0` + `google-genai>=1.56.0` + Celery 5.x in this codebase. A 100-task load test must be a Phase 2 acceptance criterion, not a post-migration check.
- **LangGraph checkpoint PHI audit:** Before running the Redis cleanup script, the actual content of existing `langgraph:checkpoint:*` keys should be sampled to determine whether they contain patient PII that was stored before the PII redaction layer was fully hardened. If PHI is present, LGPD documentation obligations apply to the purge event.
- **ADK issue #3615 status at v1.3 planning time:** The ADK exclusion is correct for v1.2 but must be re-evaluated at the start of v1.3 planning by checking issue #3615 status and re-running the OTel version conflict check against the latest `google-adk` release at that time.
- **GeminiClient migration scope:** The exact surface of changes required to replace `ChatGoogleGenerativeAI` in `client.py` with direct `google-genai` SDK calls is not fully characterized. The `_ensure_model_for_loop` pattern (loop-safe reinitialization) has no documented equivalent in the `google-genai` SDK and may require a custom solution.

---

## Researcher Conflict Resolution Record

The Architecture researcher proposed `google-adk` (SequentialAgent, ParallelAgent, ADKRunner, InMemorySessionService, custom BaseAgent subclasses) as the primary mechanism for replacing the 2 LangGraph flow routing graphs. The Stack and Pitfalls researchers independently confirmed that `google-adk` cannot be installed in this stack due to irresolvable conflicts (OTel version cap, Pydantic 2.11+/FastAPI schema failures, mandatory GCP footprint).

**Resolution adopted in this summary:** The architectural patterns proposed by the Architecture researcher are correct design. The `app/ai/agents/` component structure, the `deps_type` injection pattern, the `PIISafeAgent` wrapper, the `InMemorySessionService` preference over persistent session services, and the `BaseAgent` subclass approach for deterministic sub-agents are all adopted for v1.2 where applicable. The `app/ai/adk/` layer (ADKRunner, FlowMessageAgent as SequentialAgent, FlowResponseAgent as SequentialAgent) is documented as the target design for v1.3 ADK integration. For v1.2, the 2-node conditional routing graphs are replaced with direct async Python functions in `sequential_message_handler.py` — equivalent behavior, zero new dependencies, lower implementation risk.

---

## Sources

### Primary (HIGH confidence)
- pydantic-ai PyPI page — version 1.63.0, Python 3.10-3.14, Production/Stable status: https://pypi.org/project/pydantic-ai/
- pydantic-ai official docs — `Agent`, `deps_type`, `RunContext`, `PromptedOutput`, `output_type`, `GoogleModel`, `TestModel`: https://ai.pydantic.dev/
- pydantic-ai pyproject.toml — core deps: `pydantic>2.12`, `httpx>0.27`, `google-genai>1.56.0` (for `[google]`): https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pyproject.toml
- google-adk pyproject.toml — confirmed OTel constraint `>=1.36.0,<1.39.0` and bundled FastAPI + full GCP dependency tree: https://github.com/google/adk-python/blob/main/pyproject.toml
- google-adk issues — #2657 (FastAPI conflict closed as "won't relax"), #3173 (Pydantic 2.11+ schema failures), #3615 (lightweight install request, open, no resolution timeline): https://github.com/google/adk-python/issues/
- Google ADK docs — SequentialAgent, ParallelAgent, BaseAgent, InMemorySessionService (documented for v1.3 reference): https://google.github.io/adk-docs/agents/
- langchain-google-genai 4.0.0 discussion — confirmed both pydantic-ai and langchain 4.x now use `google-genai`; coexistence during migration validated: https://github.com/langchain-ai/langchain-google/discussions/1422
- Codebase analysis — `app/ai/client.py` (GeminiClient 757 LOC), `app/ai/client_domain.py` (4 domain methods), `app/ai/langgraph/graphs.py` (2 graphs with 2 nodes each), `app/ai/pii_redaction.py`, `app/services/ai/guardrails.py`, `app/ai/langgraph/runtime.py` (Redis checkpoint key patterns)

### Secondary (MEDIUM confidence)
- pydantic-ai issues #582, #1237, #3483 — Gemini structured output limitations, nested model edge cases, streaming constraints: https://github.com/pydantic/pydantic-ai/issues/
- pydantic-ai issues #3762, #748 — `RuntimeError: Event loop is closed` with GoogleModel + async_to_sync: https://github.com/pydantic/pydantic-ai/issues/
- ADK GitHub discussion #3924 — Runner concurrency safety with FastAPI: https://github.com/google/adk-python/discussions/3924
- ADK GitHub issue #819 — `run_live()` incompatibility with SequentialAgent (not relevant to `run_async` path): https://github.com/google/adk-python/issues/819
- ZenML blog — pydantic-ai vs LangGraph vs ADK framework comparison: https://www.zenml.io/blog/pydantic-ai-vs-langgraph

### Tertiary (informational, not decision-critical)
- LangGraph Redis checkpoint migration guide — key patterns and cleanup requirements: https://github.com/redis-developer/langgraph-redis/blob/main/MIGRATION_0.2.0.md
- DEV Community — Google ADK + FastAPI integration production patterns (for future v1.3 reference): https://dev.to/timtech4u/building-ai-agents-with-google-adk-fastapi-and-mcp-26h7
- Google ADK Safety and Security docs — callback-based guardrail screening: https://google.github.io/adk-docs/safety/

---
*Research completed: 2026-02-23*
*Ready for roadmap: yes*
