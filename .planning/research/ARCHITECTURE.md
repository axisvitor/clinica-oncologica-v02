# Architecture Research

**Domain:** AI Framework Migration — LangGraph to Pydantic AI + Google ADK (oncology WhatsApp backend)
**Researched:** 2026-02-23
**Confidence:** MEDIUM-HIGH (Pydantic AI API: HIGH via official docs; Google ADK integration patterns: MEDIUM via community sources and GitHub discussions; migration coexistence strategy: HIGH via codebase analysis)

---

## Migration Goal

Replace LangGraph and its associated infrastructure (graphs, runtime, checkpointing, state, consensus) with Pydantic AI agents for the 4 AI operations (humanize, sentiment, question variation, empathetic follow-up) and Google ADK workflow agents for the 2 flow orchestration operations (send_day_messages, handle_response_and_continue). The resulting system must be simpler, fully type-safe, and preserve all existing protections (PII redaction, rate limiting, circuit breaker, output guardrails, LGPD compliance).

---

## Current State: What Exists

### LangGraph Components to Remove

```
backend-hormonia/app/ai/langgraph/
├── __init__.py          — imports to delete
├── _invoke.py           — invoke_langgraph_graph() wrapper — replace with direct agent calls
├── ai_state.py          — AIState TypedDict — replace with Pydantic models
├── consensus.py         — DEAD CODE — delete outright (no production callers)
├── graphs.py            — build_flow_message_graph(), build_flow_response_graph() — replace with ADK
├── nodes.py             — load_flow_context(), dispatch_send_mode(), etc — logic moves to ADK agents
├── nodes_ai.py          — prompt building helpers — KEEP (move to prompts package)
├── prompts.py           — build_humanization_prompt(), build_sentiment_prompt(), etc — KEEP as-is
├── runtime.py           — compile_graph(), instrument_node(), RedisCheckpointer — DELETE
└── state.py             — FlowMessageState TypedDict — REPLACE with Pydantic model
```

### Components to Keep (Unchanged)

```
backend-hormonia/app/ai/
├── client.py            — GeminiClient (rate limiting, circuit breaker, Redis cache, PII redaction) — KEEP, adapt
├── client_domain.py     — GeminiDomainClient (4 domain methods) — REWORK as Pydantic AI agents
├── context_compactor.py — compact_patient_context() — KEEP as-is
├── models.py            — PatientContext, ConcernLevel Pydantic models — KEEP as-is
├── pii_redaction.py     — sanitize_prompt_text_for_external_ai() — KEEP, called from agents

backend-hormonia/app/services/ai/
├── guardrails.py        — normalize_ai_output(), validate_ai_output() — KEEP as-is
├── output_profiles.py   — OutputProfile, MESSAGE_HUMANIZED, JSON_SENTIMENT, etc — KEEP as-is
├── ai_service.py        — AIService wrapper — KEEP, update imports
└── ...                  — other files — KEEP as-is

backend-hormonia/app/services/flow/
├── sequential_message_handler.py — REWORK (remove graph invocations, call ADK runner)
└── ...                            — other files — KEEP as-is
```

### The 4 AI Operations (Currently GeminiDomainClient methods)

| Method | What It Does | Output Type |
|--------|-------------|-------------|
| `humanize_flow_message()` | Transform template into natural message | `str` (MESSAGE_HUMANIZED profile) |
| `generate_varied_question()` | Generate non-repetitive question variant | `str` (MESSAGE_STANDARD profile) |
| `analyze_response_sentiment()` | Analyze patient response sentiment | `Dict[str,Any]` (JSON_SENTIMENT profile) |
| `create_empathetic_follow_up()` | Generate empathetic follow-up after patient response | `str` (MESSAGE_HUMANIZED profile) |

### The 2 Flow Orchestration Operations (Currently LangGraph graphs)

| Graph | Entry | Nodes | What It Does |
|-------|-------|-------|-------------|
| `flow_message_graph` | `load_flow_context` -> `dispatch_send_mode` | 2 nodes + conditional edge | Send day messages to patient |
| `flow_response_graph` | `load_response_context` -> `dispatch_response_continuation` | 2 nodes + conditional edge | Handle patient response and continue flow |

---

## Target State: New Architecture

### System Overview

```
+-------------------------------------------------------------------------+
|                         FastAPI Request Layer                           |
|  Webhook Handler  |  Flow Router  |  Quiz Handler  |  Celery Tasks      |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
|                    SequentialMessageHandler (REWORKED)                  |
|  send_day_messages()  |  handle_response_and_continue()                 |
|  -- previously called LangGraph graph.ainvoke()                         |
|  -- now calls ADK Runner.run_async()                                    |
+------------------------+-----------------------------------------------+
                         |
          +--------------v--------------+
          |     Google ADK Layer         |
          |  (NEW: app/ai/adk/)          |
          |                             |
          |  FlowMessageAgent           |
          |  (SequentialAgent)          |
          |  +----------------------+   |
          |  | LoadFlowContextAgent |   |
          |  | (custom BaseAgent)   |   |
          |  +----------------------+   |
          |  | DispatchSendMode     |   |
          |  | Agent (custom)       |   |
          |  +----------------------+   |
          |                             |
          |  FlowResponseAgent          |
          |  (SequentialAgent)          |
          |  +----------------------+   |
          |  | LoadResponseContext  |   |
          |  | Agent (custom)       |   |
          |  +----------------------+   |
          |  | DispatchResponse     |   |
          |  | ContinuationAgent    |   |
          |  +----------------------+   |
          +--------------+--------------+
                         |
          +--------------v--------------+
          |    Pydantic AI Agent Layer   |
          |  (NEW: app/ai/agents/)       |
          |                             |
          |  HumanizeAgent              |
          |  SentimentAgent             |
          |  QuestionVariationAgent     |
          |  EmpathyAgent               |
          +--------------+--------------+
                         |
          +--------------v--------------+
          |      GeminiClient (KEPT)     |
          |   Rate limit | Circuit breaker|
          |   Cache      | PII redaction  |
          |   Guardrails | Output profiles|
          +-----------------------------+
```

---

## Component Architecture

### Component Responsibilities

| Component | Location | Responsibility | Status |
|-----------|----------|---------------|--------|
| `HumanizeAgent` | `app/ai/agents/humanize.py` | Pydantic AI agent: wrap `humanize_flow_message` with typed input/output | NEW |
| `SentimentAgent` | `app/ai/agents/sentiment.py` | Pydantic AI agent: wrap `analyze_response_sentiment` with `SentimentResult` output | NEW |
| `QuestionVariationAgent` | `app/ai/agents/question_variation.py` | Pydantic AI agent: wrap `generate_varied_question` with typed input/output | NEW |
| `EmpathyAgent` | `app/ai/agents/empathy.py` | Pydantic AI agent: wrap `create_empathetic_follow_up` with typed input/output | NEW |
| `FlowMessageAgent` | `app/ai/adk/flow_message/agent.py` | ADK SequentialAgent: orchestrate load+dispatch for sending day messages | NEW |
| `FlowResponseAgent` | `app/ai/adk/flow_response/agent.py` | ADK SequentialAgent: orchestrate load+dispatch for response continuation | NEW |
| `ADKRunner` | `app/ai/adk/runner.py` | Singleton InMemorySessionService + Runners, shared across requests | NEW |
| `GeminiClient` | `app/ai/client.py` | Core Gemini HTTP client with all protections — continues as underlying model for Pydantic AI | KEEP |
| `GeminiDomainClient` | `app/ai/client_domain.py` | Thin shim re-exporting from agents (backward compat) then tombstoned after migration | REWORK |
| `SequentialMessageHandler` | `app/services/flow/sequential_message_handler.py` | Remove LangGraph invocations, call ADK Runner instead | REWORK |
| `app/ai/langgraph/` | entire directory | All files deleted or tombstoned after migration complete | DELETE |

---

## Pydantic AI Agent Pattern

### How Pydantic AI Agents Work

Pydantic AI `Agent` is a generic class parameterized by `(DepsType, OutputType)`:

```python
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

agent: Agent[HumanizeDeps, str] = Agent(
    model=GoogleModel(
        settings.AI_GEMINI_MODEL,
        provider=GoogleProvider(api_key=settings.AI_GEMINI_API_KEY)
    ),
    deps_type=HumanizeDeps,
    output_type=str,
    system_prompt="You are a healthcare message humanizer...",
)
```

Agents are run with `await agent.run(user_prompt, deps=deps_instance)` which returns an `AgentRunResult[str]` where `result.output` is the validated typed output.

### Dependency Injection Pattern

The `deps_type` pattern is Pydantic AI's way to inject runtime context (database sessions, services, config) into system prompts and tools without global state:

```python
from dataclasses import dataclass
from pydantic_ai import RunContext

@dataclass
class HumanizeDeps:
    gemini_client: GeminiClient  # existing client with all protections
    template: str
    patient_name: str
    patient_context: dict
    conversation_history: list[str]
    recent_interactions: list[dict] | None = None
    ai_instructions: str | None = None

@agent.system_prompt
async def build_system_prompt(ctx: RunContext[HumanizeDeps]) -> str:
    return build_humanization_prompt(
        template=ctx.deps.template,
        ai_instructions=ctx.deps.ai_instructions,
        recent_interactions=ctx.deps.recent_interactions,
    )
```

This replaces the LangGraph `config["configurable"]["handler"]` pattern which was brittle and untyped.

### Structured Output for Sentiment

The 3 string-output agents use `output_type=str` with guardrail post-processing. The sentiment agent uses a Pydantic model for structured output, replacing the JSON dict return:

```python
from pydantic import BaseModel
from typing import Literal

class SentimentResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative", "concerning"]
    confidence: float
    emotional_indicators: list[str]
    medical_concerns: list[str]
    requires_attention: bool
    key_themes: list[str]
    suggested_follow_up: str

sentiment_agent: Agent[SentimentDeps, SentimentResult] = Agent(
    model=...,
    output_type=SentimentResult,
)
```

Pydantic AI uses the model's tool-calling capability to enforce this schema — the Gemini model receives a JSON schema tool definition and must return valid JSON matching `SentimentResult`. This replaces the fragile JSON parsing in `_parse_sentiment_analysis()`.

### How Google Gemini is Configured in Pydantic AI

```python
# Pydantic AI uses google-genai SDK (not langchain-google-genai)
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

provider = GoogleProvider(api_key=settings.AI_GEMINI_API_KEY)
model = GoogleModel(settings.AI_GEMINI_MODEL, provider=provider)
```

**Important dependency change:** Pydantic AI uses `google-genai` (the official Google SDK) not `langchain-google-genai`. This means `langchain-google-genai` and `langchain-core` can eventually be removed from `requirements.txt`. The `langchain_core.messages.HumanMessage` import in `client.py` line 25 will need updating when GeminiClient is migrated to the official SDK.

Confidence: HIGH — verified against official Pydantic AI Google model documentation.

---

## Google ADK Orchestration Pattern

### How ADK SequentialAgent Replaces LangGraph Multi-Node Graphs

The current LangGraph graphs follow this pattern:

```
START -> load_flow_context -> (conditional) -> dispatch_send_mode -> END
```

The conditional edge checks `state.get("result")` — if a result was already set (error, skip, waiting), it exits early via the END edge.

ADK SequentialAgent maps directly to this pattern:

```python
from google.adk.agents import SequentialAgent
from google.adk.agents.base_agent import BaseAgent

# Sub-agent 1: load context (equivalent to load_flow_context node)
load_context_agent = LoadFlowContextAgent(name="LoadFlowContext")

# Sub-agent 2: dispatch send (equivalent to dispatch_send_mode node)
dispatch_agent = DispatchSendModeAgent(name="DispatchSendMode")

# Orchestrator (equivalent to the compiled StateGraph)
flow_message_agent = SequentialAgent(
    name="FlowMessageAgent",
    sub_agents=[load_context_agent, dispatch_agent],
    description="Orchestrates sending day messages to a patient",
)
```

**State passing between ADK agents:** ADK uses `context.session.state` (a dict on `InvocationContext`) as the shared state between sub-agents. Sub-agents write to `context.session.state["key"]` and subsequent agents read from it. This is functionally equivalent to LangGraph's `FlowMessageState` TypedDict, but simpler — it is a plain dict with no schema enforcement at the graph level (enforce with Pydantic models inside each agent if needed).

**Conditional routing:** The conditional edge (`_route_after_load` in LangGraph) was a function returning `"end"` or `"dispatch_send_mode"` based on `state.get("result")`. In ADK, this becomes a check at the start of `DispatchSendModeAgent._run_async_impl()` — if `context.session.state.get("result")` is already set, the agent returns immediately. This is explicit Python control flow rather than graph edge routing.

### ADK Runner Integration with FastAPI

The ADK `Runner` is the execution engine. It is stateless, safe for concurrent use, and should be created once and reused:

```python
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

class ADKRunner:
    """Singleton ADK runner for flow message orchestration."""

    def __init__(self):
        self._session_service = InMemorySessionService()
        self._flow_message_runner = Runner(
            agent=flow_message_agent,
            app_name="clinica-flow-message",
            session_service=self._session_service,
        )
        self._flow_response_runner = Runner(
            agent=flow_response_agent,
            app_name="clinica-flow-response",
            session_service=self._session_service,
        )

    async def run_flow_message(
        self,
        session_id: str,
        patient_id: UUID,
        day_number: int,
        flow_kind: str,
        handler: Any,
    ) -> dict:
        session = await self._session_service.create_session(
            app_name="clinica-flow-message",
            user_id=str(patient_id),
            session_id=session_id,
            state={
                "patient_id": patient_id,
                "day_number": day_number,
                "flow_kind": flow_kind,
                "handler": handler,
            },
        )
        async for event in self._flow_message_runner.run_async(
            user_id=str(patient_id),
            session_id=session_id,
            new_message=Content(parts=[Part(text="run")]),
        ):
            pass  # events consumed; result is written to session state
        final_session = await self._session_service.get_session(
            app_name="clinica-flow-message",
            user_id=str(patient_id),
            session_id=session_id,
        )
        return final_session.state.get("result", {})
```

**Session isolation:** Each flow invocation gets a unique `session_id` (equivalent to the current `thread_id` in LangGraph's `config["configurable"]["thread_id"]`). The `InMemorySessionService` isolates state per session. For the current production use case (stateless invocations, no cross-request state persistence needed), in-memory session is correct — no checkpointing is used in the current LangGraph implementation either.

**Known ADK limitation:** ADK's `run_live()` does not work with `SequentialAgent`/`ParallelAgent` because they lack a `.tools` attribute (GitHub issue #819, May 2025). This is not relevant here — the codebase uses `runner.run_async()` for event-driven batch processing, not live streaming.

Confidence: MEDIUM — ADK FastAPI patterns verified via GitHub discussions and community articles; exact API surface for custom BaseAgent subclasses needs validation during Phase 1 implementation spike.

---

## Proposed Directory Layout

```
backend-hormonia/app/ai/
├── __init__.py
├── client.py                    — GeminiClient (KEEP — used by Pydantic AI agents)
├── context_compactor.py         — compact_patient_context() (KEEP)
├── models.py                    — PatientContext, ConcernLevel (KEEP)
├── pii_redaction.py             — sanitize_prompt_text_for_external_ai() (KEEP)
|
├── agents/                      — NEW: Pydantic AI agent layer
|   ├── __init__.py
|   ├── base.py                  — Shared GeminiDeps dataclass, model factory
|   ├── humanize.py              — HumanizeAgent + HumanizeDeps
|   ├── sentiment.py             — SentimentAgent + SentimentDeps + SentimentResult
|   ├── question_variation.py    — QuestionVariationAgent + QuestionVariationDeps
|   └── empathy.py               — EmpathyAgent + EmpathyDeps
|
├── adk/                         — NEW: Google ADK orchestration layer
|   ├── __init__.py
|   ├── runner.py                — ADKRunner singleton (InMemorySessionService + Runners)
|   ├── flow_message/            — FlowMessageAgent (SequentialAgent)
|   |   ├── __init__.py
|   |   ├── agent.py             — SequentialAgent definition
|   |   ├── load_context.py      — LoadFlowContext sub-agent (custom BaseAgent)
|   |   └── dispatch_send.py     — DispatchSendMode sub-agent (custom BaseAgent)
|   └── flow_response/           — FlowResponseAgent (SequentialAgent)
|       ├── __init__.py
|       ├── agent.py             — SequentialAgent definition
|       ├── load_response.py     — LoadResponseContext sub-agent
|       └── dispatch_response.py — DispatchResponseContinuation sub-agent
|
├── prompts/                     — MOVED from langgraph/prompts.py (no content changes)
|   ├── __init__.py
|   ├── humanize.py              — build_humanization_prompt()
|   ├── sentiment.py             — build_sentiment_prompt()
|   ├── question.py              — build_question_variation_prompt()
|   └── empathy.py               — build_empathetic_prompt()
|
└── langgraph/                   — TOMBSTONED after migration complete
    ├── __init__.py              — raises ImportError with migration message
    └── [all files]              — tombstoned; kept only as import error guards
```

**Note on `client_domain.py`:** After agents are implemented, `GeminiDomainClient` becomes a thin shim that delegates to the Pydantic AI agents via feature flag. It is kept temporarily for backward-compatibility, then tombstoned after full migration. Primary callers are: `sequential_message_handler.py`, `nodes_ai.py` (via prompts), `gemini_orchestrator.py`.

---

## Data Flow: Before vs After

### Before (LangGraph)

```
SequentialMessageHandler.send_day_messages()
  |
  +-- get_flow_message_graph()          # lru_cache compiled StateGraph
  |   # graphs.py -> runtime.py -> nodes.py
  |
  +-- graph.ainvoke(state, config)      # config carries thread_id + handler
       |
       +-- load_flow_context(state, config)
       |   +-- _require_handler(config)         # extracts handler from untyped dict
       |   +-- asyncio.to_thread(db.query(...)) # sync Session in thread pool
       |   +-- handler._get_day_config(...)     # Redis cache + DB query
       |   +-- handler._get_or_create_flow_state(...)
       |
       +-- dispatch_send_mode(state, config)
           +-- asyncio.to_thread(db.query(...))
           +-- handler._send_message_at_index(...)
                +-- GeminiDomainClient.humanize_flow_message(...)
                    +-- GeminiClient.generate_content(prompt, profile=MESSAGE_HUMANIZED)
```

### After (Pydantic AI + ADK)

```
SequentialMessageHandler.send_day_messages()
  |
  +-- adk_runner.run_flow_message(      # replaces graph.ainvoke()
  |       session_id=thread_id,
  |       patient_id=...,
  |       day_number=...,
  |       flow_kind=...,
  |       handler=self,
  |   )
  |   |
  |   +-- FlowMessageAgent (SequentialAgent)
  |       |
  |       +-- LoadFlowContextAgent._run_async_impl(context)
  |       |   +-- handler._get_day_config(...)    # unchanged -- direct call
  |       |   +-- await db.execute(select(...))   # AsyncSession (existing hot-path pattern)
  |       |   +-- context.session.state["result"] = {...}   # replaces LangGraph state dict
  |       |
  |       +-- DispatchSendModeAgent._run_async_impl(context)
  |           +-- if context.session.state.get("result"): return  # early exit (was conditional edge)
  |           +-- handler._send_message_at_index(...)
  |               +-- humanize_agent.run(prompt, deps=deps)
  |                   +-- build_humanization_prompt(deps)  # typed deps, not untyped config
  |                   +-- GeminiClient.generate_content(...)  # same client, all protections kept
  |
  +-- result = final_session.state["result"]
```

**Key difference:** The ADK session state replaces LangGraph's `FlowMessageState` TypedDict. The handler injection changes from `config["configurable"]["handler"]` (stringly-typed dict lookup) to `context.session.state["handler"]` (explicit pre-populated state). No change to the GeminiClient layer below.

---

## Integration Points

### External Services

| Service | Current Integration | Status After Migration |
|---------|-------------------|----------------------|
| Google Gemini API | `langchain-google-genai.ChatGoogleGenerativeAI` in GeminiClient | Pydantic AI uses `google-genai` SDK for agent model calls; GeminiClient itself needs to migrate from `langchain-google-genai` to `google-genai` direct SDK |
| Dragonfly/Redis | Response cache in GeminiClient via `redis_manager` | No change — GeminiClient cache layer is preserved entirely |
| PostgreSQL | `AsyncSession` for DB queries in flow nodes | No change — existing async queries in hot paths are preserved |

### Internal Boundaries

| Boundary | Before | After |
|----------|--------|-------|
| `SequentialMessageHandler` -> AI layer | `from app.ai.langgraph.graphs import get_flow_message_graph` | `from app.ai.adk.runner import get_adk_runner` |
| `GeminiDomainClient` -> AI operations | Direct method calls | Shim delegating to Pydantic AI agents via feature flag |
| Flow nodes -> DB | `asyncio.to_thread(db.query(...))` (sync Session in thread) | `await db.execute(select(...))` (AsyncSession — already the pattern in hot paths) |
| `nodes_ai.py` helpers | Used by LangGraph nodes | Moved to `app/ai/prompts/` — used by Pydantic AI agent `system_prompt` builders |
| `_invoke.py` wrapper | `invoke_langgraph_graph()` wrapper function | Deleted — replaced by `agent.run()` which raises `FeatureNotAvailableError` on empty output |

### GeminiClient Preservation Strategy

The `GeminiClient` (757 LOC) must be preserved entirely through the migration. It contains:
- Redis-backed semantic caching (`_generate_cache_key`, `_get_cached_response`, `_cache_response`)
- Rate limiting with Redis sliding window + in-process fallback
- Circuit breaker via `get_ai_circuit_breaker()`
- PII redaction via `_redact_prompt_for_external_ai()`
- Output guardrails via `validate_ai_output()` + `normalize_ai_output()`
- Retry logic with exponential backoff
- Loop-safe model reinitialization (`_ensure_model_for_loop`)

**The Pydantic AI agents do NOT replace the GeminiClient directly.** Instead, the Pydantic AI agent's `system_prompt` function assembles the typed prompt via `deps`, and the agent's execution still calls `GeminiClient.generate_content()`. This preserves all protections without reimplementing them.

Recommended implementation approach for the 3 string-output agents (humanize, question_variation, empathy):

```python
class HumanizeAgent:
    """Typed wrapper around GeminiClient.generate_content for humanization."""

    async def run(self, deps: HumanizeDeps) -> str:
        # Type-safe prompt assembly (was untyped in nodes_ai.py)
        prompt = build_humanization_prompt(
            template=deps.template,
            ai_instructions=deps.ai_instructions,
            recent_interactions=deps.recent_interactions,
        )
        # GeminiClient handles: PII redaction, rate limit, circuit breaker, cache, guardrails
        result = await deps.gemini_client.generate_content(prompt, profile=MESSAGE_HUMANIZED)
        if not result:
            raise FeatureNotAvailableError(
                "humanization returned no output", "humanization", "humanize"
            )
        return result
```

For `SentimentAgent`, the `output_type=SentimentResult` Pydantic model can be applied either via:
1. Full Pydantic AI `Agent` with `output_type=SentimentResult` (using google-genai SDK directly via Pydantic AI) — replaces the brittle JSON parsing
2. Calling `GeminiClient.generate_content(prompt, profile=JSON_SENTIMENT)` then validating the JSON output against `SentimentResult.model_validate(json.loads(result))` — keeps GeminiClient guardrails

Option 2 is lower risk for the initial migration. Option 1 is the architectural ideal.

---

## Coexistence Strategy During Migration

### Strategy: Feature-Flag Routing with Parallel Paths

The migration uses env-var feature flags to route each operation independently. This allows per-operation migration, instant rollback without code deployment, and integration testing with real traffic before full cutover.

```python
# settings.py additions
AI_FRAMEWORK: str = "langgraph"  # "langgraph" | "pydantic_ai"
AI_FLOW_FRAMEWORK: str = "langgraph"  # "langgraph" | "adk"
```

### Coexistence in SequentialMessageHandler

```python
async def send_day_messages(self, patient_id, day_number, flow_kind):
    if settings.AI_FLOW_FRAMEWORK == "adk":
        return await self._send_via_adk(patient_id, day_number, flow_kind)
    return await self._send_via_langgraph(patient_id, day_number, flow_kind)

async def _send_via_langgraph(self, ...):
    # Existing code unchanged
    graph = get_flow_message_graph()
    state = await graph.ainvoke(...)
    ...

async def _send_via_adk(self, ...):
    # New ADK path
    runner = get_adk_runner()
    return await runner.run_flow_message(...)
```

### Coexistence in GeminiDomainClient

```python
async def humanize_flow_message(self, template, patient_name, ...):
    if settings.AI_FRAMEWORK == "pydantic_ai":
        from app.ai.agents.humanize import HumanizeAgent, HumanizeDeps
        deps = HumanizeDeps(gemini_client=self, template=template, ...)
        return await HumanizeAgent().run(deps)
    # Original implementation preserved exactly below
    ...
```

### Migration Order

Recommended migration sequence ordered by risk and dependency:

**Step 1 — Pydantic AI agents for 4 AI operations** (Low risk)
- Start with `SentimentAgent` (most benefit from structured output; replaces fragile `_parse_sentiment_analysis()` JSON parsing)
- Then `HumanizeAgent`, `QuestionVariationAgent`, `EmpathyAgent` (same pattern, same GeminiClient integration)
- GeminiDomainClient becomes a shim with feature flag; no callers change

**Step 2 — ADK FlowMessageAgent** (Medium risk)
- Most complex step: requires ADK session plumbing, porting `load_flow_context` (200+ LOC node)
- Must be tested with shadow traffic before full cutover via `AI_FLOW_FRAMEWORK` flag
- `consensus.py` is already dead code — delete immediately as part of step 2 setup

**Step 3 — ADK FlowResponseAgent** (Medium risk, same as Step 2)
- Build after FlowMessageAgent is stable

**Step 4 — Delete LangGraph infrastructure** (Do last)
- Tombstone `langgraph/` directory
- Remove `langgraph`, `langchain-core`, `langchain-google-genai` from `requirements.txt`
- Add `pydantic-ai[google]`, `google-adk`, `google-genai` to `requirements.txt`
- Update GeminiClient to use `google-genai` SDK directly (removes last LangChain dependency)

### What Can Run in Parallel

Steps 1 and 2 can begin simultaneously (different files, no conflicts). However, within a single patient request, the feature flag routes entirely to LangGraph OR entirely to ADK — never mixed. This avoids state divergence between LangGraph checkpoints and ADK session state.

---

## Architectural Patterns

### Pattern 1: GeminiClient as Execution Backend (Preserved)

**What:** Pydantic AI agents assemble typed prompts using deps, but execute through `GeminiClient.generate_content()`, not the raw Pydantic AI model invocation path.
**When to use:** When the existing client has production-hardened protections that would be expensive to replicate in Pydantic AI model settings.
**Trade-offs:** Loses Pydantic AI's model-level retry and streaming. Gains zero migration risk to cache/rate-limit/circuit-breaker layer. Accepted tradeoff for this migration.

### Pattern 2: ADK Custom BaseAgent for Deterministic Logic

**What:** Use ADK `BaseAgent` subclass (not `LlmAgent`) for sub-agents that execute deterministic Python logic without LLM calls.
**When to use:** Flow context loading and send-mode dispatching are pure Python logic (DB queries, cache lookups, WhatsApp sends). They do not need an LLM.
**Trade-offs:** Requires implementing `_run_async_impl()` instead of providing a natural-language instruction string. ADK documentation focuses on `LlmAgent` — `BaseAgent` usage is less documented but well-supported.

```python
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from typing import AsyncGenerator
from google.adk.events import Event

class LoadFlowContextAgent(BaseAgent):
    """Pure-Python ADK agent: loads patient + flow state from DB."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        handler = ctx.session.state["handler"]
        patient_id = ctx.session.state["patient_id"]
        day_number = ctx.session.state["day_number"]
        flow_kind = ctx.session.state["flow_kind"]
        # Direct port of load_flow_context() LangGraph node logic
        result = await _load_and_validate(handler, patient_id, day_number, flow_kind)
        ctx.session.state["result"] = result
        yield Event(author=self.name, content=Content(parts=[Part(text="done")]))
```

### Pattern 3: FeatureNotAvailableError as Unified AI Failure Signal

**What:** All Pydantic AI agents and ADK agents raise `FeatureNotAvailableError` (existing exception in `app/core/exceptions.py`) when output is empty or invalid.
**When to use:** Always. This is the established contract from v1.0 — `FeatureNotAvailableError` is caught by the circuit breaker and by all callers throughout the codebase. Do not introduce new exception types.
**Trade-offs:** None — this is the existing pattern and must be continued.

### Pattern 4: InMemorySessionService for Stateless Flow Invocations

**What:** ADK `InMemorySessionService` holds state for the duration of a single flow invocation (milliseconds), then is discarded. No cross-request state persistence.
**When to use:** The current LangGraph implementation has zero state persistence across requests (no Redis checkpointer used; `@lru_cache` is on the compiled graph object, not execution state). ADK session matches this: state is per-invocation.
**Trade-offs:** If future requirements need cross-request state (e.g., resuming a flow after a crash mid-execution), this would need to change to `DatabaseSessionService`. Flag as future consideration.

---

## Anti-Patterns

### Anti-Pattern 1: Replacing GeminiClient with Pydantic AI Model Invocation

**What people do:** Use `Agent('google-gla:gemini-2.5-flash')` as the model, letting Pydantic AI handle all model calls, effectively removing GeminiClient.
**Why it's wrong:** GeminiClient contains 757 LOC of production-hardened logic: Redis semantic caching, distributed rate limiting with in-process fallback, circuit breaker, PII redaction, loop-safe reinitialization. Removing it for a clean framework migration would require reimplementing all of this in Pydantic AI model settings — a scope-expanding, high-risk rework that goes far beyond the migration goal.
**Do this instead:** Keep GeminiClient as execution backend. Use Pydantic AI agents only for typed prompt assembly and structured output validation.

### Anti-Pattern 2: Using LlmAgent for Deterministic Flow Logic

**What people do:** Define all ADK sub-agents as `LlmAgent` with natural-language instructions describing the flow logic.
**Why it's wrong:** Loading flow context from DB and dispatching messages are pure deterministic operations — they must not be delegated to an LLM. Using `LlmAgent` for these creates non-deterministic behavior, adds ~500ms per LLM call, and incurs unnecessary Gemini API cost for each patient message.
**Do this instead:** Use `BaseAgent` subclasses with `_run_async_impl()` for all sub-agents performing deterministic operations. Only use `LlmAgent` if a step genuinely requires language model reasoning.

### Anti-Pattern 3: Mixing ADK and LangGraph State Within a Single Request

**What people do:** During migration, attempt to share state between the LangGraph path and the ADK path within a single `send_day_messages()` call.
**Why it's wrong:** LangGraph state is a `TypedDict` passed through node return values. ADK state lives in `InvocationContext.session.state` (a plain dict). They have different lifecycles and serialization. Sharing state between them requires either duplication (inconsistency risk) or a complex adapter.
**Do this instead:** Use the `AI_FLOW_FRAMEWORK` feature flag to route entirely to one path per invocation. Never mix paths within a single call.

### Anti-Pattern 4: Deleting LangGraph Before Cutover Validation

**What people do:** Remove LangGraph from `requirements.txt` as soon as the ADK implementation is code-complete.
**Why it's wrong:** The feature flag coexistence strategy requires LangGraph to remain importable during validation. If the ADK path has a bug in production, reverting requires re-adding LangGraph — which requires a code deployment on Railway.
**Do this instead:** Keep LangGraph in requirements until the ADK path has been validated with real traffic for at least one week with zero errors. Only then tombstone the `langgraph/` directory and remove from `requirements.txt`.

### Anti-Pattern 5: Creating a New BaseAgent for the Existing Agent Pattern

**What people do:** Replace the existing `app/agents/base.py` (the hive-mind BaseAgent with message queues, heartbeat, consensus) with the ADK BaseAgent.
**Why it's wrong:** The existing `app/agents/` directory (with `BaseAgent`, `AlertAnalyzerAgent`, `PatientMonitor`, etc.) is a separate concern — it is the hive-mind coordination layer, not the Gemini AI layer. The ADK `BaseAgent` is for flow orchestration sub-agents only.
**Do this instead:** Keep `app/agents/` unchanged. ADK agents live exclusively under `app/ai/adk/`. The two agent systems do not interact.

---

## Scaling Considerations

| Scale | Architecture Considerations |
|-------|----------------------------|
| Current (dozens of patients) | InMemorySessionService is correct — no persistence needed, no cross-instance state sharing required |
| 500+ patients | ADK session service remains in-memory (sessions are sub-second, not persisted). Monitor Pydantic AI agent overhead per request (should be less than 5ms vs LangGraph's ~14ms). |
| 2000+ patients | Consider ADK `DatabaseSessionService` if post-execution session inspection is needed for debugging. No architectural change needed for throughput at this scale — bottleneck remains Gemini API rate limit and DB connections. |

**First bottleneck:** Gemini API rate limit (60 RPM default) — existing rate limiter in GeminiClient handles this. ADK does not change this boundary.
**Second bottleneck:** PostgreSQL connection pool — unchanged by this migration. AsyncSession in flow nodes is already established.

---

## Build Order (considering dependencies)

The dependency graph for implementation:

```
1. prompts/ module extraction        (no deps -- pure file move, no content changes)
   |
   +-- 2. SentimentAgent             (depends on: google-genai or pydantic-ai[google] installed,
   |       SentimentResult Pydantic  SentimentResult model defined, GeminiClient integration validated)
   |       model defined
   |
   +-- 3. HumanizeAgent              (depends on: prompts/ moved, step 2 pattern validated)
   +-- 4. QuestionVariationAgent     (depends on: step 2 pattern validated, parallel with 3)
   +-- 5. EmpathyAgent               (depends on: step 2 pattern validated, parallel with 3)
   |
   +-- 6. ADKRunner setup            (depends on: google-adk installed, session service API confirmed)
       |
       +-- 7. FlowMessageAgent       (depends on: ADKRunner, load_flow_context logic ported)
       |
       +-- 8. FlowResponseAgent      (depends on: FlowMessageAgent pattern validated, parallel with 7)
           |
           +-- 9. Feature flag cutover + LangGraph deletion
```

**Parallelizable:** Steps 3, 4, 5 can be built in parallel once step 2 validates the GeminiClient integration pattern. Steps 7 and 8 can be built in parallel once step 6 is validated.

**Critical path:** google-genai/pydantic-ai integration (step 2) -> ADK custom BaseAgent pattern (step 7) -> LangGraph deletion (step 9).

---

## New Dependencies

| Package | Version | Purpose | Replaces |
|---------|---------|---------|---------|
| `pydantic-ai[google]` | >=0.0.46 | Pydantic AI framework with Google provider | Nothing directly; sits above GeminiClient |
| `google-adk` | >=1.0.0 | Google Agent Development Kit for SequentialAgent | `langgraph` (flow orchestration) |
| `google-genai` | Latest stable | Official Google Gemini SDK (used by Pydantic AI) | `langchain-google-genai` (for Pydantic AI model path) |

**Packages to remove (after migration complete):**

| Package | Currently Used For | Safe to Remove When |
|---------|-------------------|---------------------|
| `langgraph` | flow_message_graph, flow_response_graph | After ADK paths validated and AI_FLOW_FRAMEWORK="adk" is default |
| `langchain-google-genai` | ChatGoogleGenerativeAI in GeminiClient | After GeminiClient updated to use `google-genai` SDK directly |
| `langchain-core` | HumanMessage import in client.py line 25 | After langchain-google-genai is removed |

**Note on `langchain-google-genai` in GeminiClient:** `client.py` imports `ChatGoogleGenerativeAI` from `langchain-google-genai` and `HumanMessage` from `langchain-core`. These are the last remaining LangChain imports after LangGraph is removed. Migrating `_initialize_model()` and `_generate_content_internal()` to use `google-genai` SDK directly completes the full LangChain removal. This is medium complexity (~50 LOC change) and is the final cleanup step.

---

## Sources

- [Pydantic AI official docs — Agent class API](https://ai.pydantic.dev/agent/) — HIGH confidence (official)
- [Pydantic AI official docs — Output types and structured validation](https://ai.pydantic.dev/output/) — HIGH confidence (official)
- [Pydantic AI official docs — Google model provider configuration](https://ai.pydantic.dev/models/google/) — HIGH confidence (official)
- [Google ADK docs — SequentialAgent](https://google.github.io/adk-docs/agents/workflow-agents/sequential-agents/) — HIGH confidence (official)
- [Google ADK docs — ParallelAgent](https://google.github.io/adk-docs/agents/workflow-agents/parallel-agents/) — HIGH confidence (official)
- [Google ADK docs — Multi-agent systems and state passing](https://google.github.io/adk-docs/agents/multi-agents/) — HIGH confidence (official)
- [ADK GitHub issue #819 — run_live() incompatibility with SequentialAgent](https://github.com/google/adk-python/issues/819) — HIGH confidence (confirmed issue; not relevant to run_async path used here)
- [ADK GitHub discussion #3924 — FastAPI + Runner concurrency safety](https://github.com/google/adk-python/discussions/3924) — MEDIUM confidence (community, confirmed: Runner is reusable and concurrency-safe)
- [ZenML blog — Pydantic AI vs LangGraph](https://www.zenml.io/blog/pydantic-ai-vs-langgraph) — MEDIUM confidence (third-party, consistent with framework documentation)
- Direct codebase analysis: `backend-hormonia/app/ai/langgraph/graphs.py`, `nodes.py`, `runtime.py`, `state.py`, `_invoke.py`
- Direct codebase analysis: `backend-hormonia/app/ai/client.py`, `client_domain.py`
- Direct codebase analysis: `backend-hormonia/app/services/flow/sequential_message_handler.py`
- Direct codebase analysis: `backend-hormonia/app/services/ai/output_profiles.py`, `guardrails.py`

---

*Architecture research for: AI Framework Migration — LangGraph to Pydantic AI + Google ADK*
*Researched: 2026-02-23*
