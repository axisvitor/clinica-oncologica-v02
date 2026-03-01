# Stack Research

**Domain:** Healthcare WhatsApp backend — AI framework migration (LangGraph → Pydantic AI + Google ADK)
**Researched:** 2026-02-23
**Confidence:** HIGH (pydantic-ai versions and DI patterns), MEDIUM (google-adk dependency conflicts), HIGH (removal decisions)

---

## Executive Verdict: What to Add, Remove, or Change

| Component | Status | Action | Rationale |
|-----------|--------|--------|-----------|
| `langgraph>=1.0.7` | REMOVE | Full removal after migration | Entire orchestration layer being replaced |
| `langchain-core>=1.2.7` | REMOVE | After removing LangGraph | LangGraph's sole use of langchain-core |
| `langchain-google-genai>=2.1.12` | REMOVE | After Pydantic AI migration | `ChatGoogleGenerativeAI` replaced by `google-genai` via pydantic-ai |
| `google-ai-generativelanguage>=0.7.0` | REMOVE | Transitively with langchain-google-genai | Legacy SDK superseded by `google-genai` |
| `pydantic-ai-slim[google,retries]` | ADD | Core of migration | Typed agents, structured output, Gemini via `google-genai` |
| `google-genai>=1.56.0` | ADD (transitive) | Pulled in by pydantic-ai-slim[google] | New unified Google Gen AI SDK |
| `google-adk` | DO NOT ADD (yet) | Decision below | Critical dependency conflicts with existing stack |

---

## Recommended Stack

### New Packages to Add

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pydantic-ai-slim[google] | >=1.63.0,<2.0.0 | Typed Pydantic AI agents with Gemini support | Use slim variant to avoid pulling all model providers; `[google]` extra installs `google-genai>=1.56.0` |
| pydantic-ai-slim[retries] | Same version | Tenacity-backed retry transport for httpx | Replaces existing `ChatGoogleGenerativeAI` retry handling; integrates with existing `tenacity` |
| google-genai | >=1.56.0,<2.0.0 | Google Gen AI SDK (transitive via pydantic-ai) | New unified SDK replacing `google-ai-generativelanguage`; direct async API |

### Packages to Remove

| Package | Safe to Remove After | Why |
|---------|---------------------|-----|
| `langgraph>=1.0.7` | Migration of `graphs.py`, `runtime.py`, `nodes.py` | All graph orchestration replaced by Pydantic AI agents + programmatic Python |
| `langchain-core>=1.2.7` | After langgraph removal | Used exclusively by langgraph; `HumanMessage` in `client.py` replaced by `google-genai` types |
| `langchain-google-genai>=2.1.12` | After pydantic-ai migration | `ChatGoogleGenerativeAI` replaced by `pydantic_ai.models.google.GoogleModel` |
| `google-ai-generativelanguage>=0.7.0` | With langchain-google-genai | Legacy gRPC-based SDK; `google-genai` is the modern replacement |

### What Does NOT Change

| Package | Version | Keep Because |
|---------|---------|-------------|
| pydantic | >=2.12.5 | pydantic-ai-slim requires pydantic>=2.12; already met |
| httpx | >=0.28.1 | pydantic-ai-slim requires httpx>=0.27; already met |
| tenacity | >=8.2.3 | pydantic-ai retries extra uses tenacity under the hood |
| google-auth | >=2.47.0 | Still needed for Firebase Admin + other Google APIs |
| google-api-core | >=2.29.0 | Still needed for Firebase Admin; no conflict |
| aiobreaker | >=1.2.0 | Circuit breaker pattern stays; wraps pydantic-ai agent calls |

---

## The Google ADK Decision: DO NOT ADD in v1.2

**Recommendation: Skip google-adk for this milestone. Use Pydantic AI alone for agent structure and programmatic Python for orchestration.**

### Why google-adk Is Not Ready for This Stack

**Conflict 1: OpenTelemetry version range incompatibility.**
google-adk 1.25.1 requires `opentelemetry-sdk>=1.36.0,<1.39.0`. The existing requirements pin `opentelemetry-sdk>=1.28.0,<2.0.0`. These ranges overlap on the paper but google-adk's upper bound `<1.39.0` conflicts with future upgrades and the existing project may be on versions above 1.36.0.

**Conflict 2: google-adk bundles FastAPI internally (known design issue).**
google-adk pulls in its own FastAPI + Starlette as required dependencies for its web UI and development server. This caused documented version conflicts at v1.12 (starlette range mismatch), v1.16 (Pydantic 2.11+ schema generation failures with non-serializable httpx types). As of v1.25.1 there is no `google-adk-core` or `[minimal]` extra — the full web stack always installs. Issue #3615 requesting a lightweight install is open with no resolution timeline.

**Conflict 3: Heavy dependency footprint for embedded use.**
google-adk installs: FastAPI, Uvicorn, MCP, google-cloud-aiplatform, google-cloud-spanner, google-cloud-bigtable, google-cloud-pubsub, aiosqlite, and full OpenTelemetry stack. This is a framework designed to BE a server, not to be embedded in one. The oncology backend is already a FastAPI server.

**Conflict 4: OpenTelemetry context management issues with async code.**
ADK manages its own OpenTelemetry tracer and does not expose a public API to disable, configure, or extend it. With async generators and multiprocessing, there are persistent context detachment errors ("was created in a different Context"). The existing backend uses async generators in WebSocket and Celery contexts.

**What to use instead of SequentialAgent/ParallelAgent:**
The two remaining LangGraph graphs (`flow_message_graph`, `flow_response_graph`) have only 2 nodes each with simple conditional routing. Replace the graph execution with straightforward async Python:

```python
# Instead of LangGraph StateGraph or ADK SequentialAgent
async def execute_flow_message(state: FlowMessageState, handler: Any) -> dict:
    # Node 1: load_flow_context
    state = await load_flow_context(state, config={"configurable": {"handler": handler}})
    if state.get("result"):
        return state["result"]
    # Conditional: route to dispatch_send_mode
    state = await dispatch_send_mode(state, config={"configurable": {"handler": handler}})
    return state.get("result", {})
```

This replaces ~30 lines of graph builder code with ~10 lines of readable Python. No ADK dependency needed.

**Revisit google-adk in v1.3** if: (a) issue #3615 is resolved with a `[core]` extra, (b) the OTel range conflict is loosened, and (c) there is a concrete multi-agent orchestration need that programmatic Python cannot cleanly express.

---

## Detailed Package Analysis: pydantic-ai-slim

### Version and Python Compatibility

| Attribute | Value |
|-----------|-------|
| Latest stable version | 1.63.0 (released 2026-02-23) |
| Python support | 3.10, 3.11, 3.12, 3.13, 3.14 |
| Python 3.13 status | CONFIRMED SUPPORTED |
| Production stability | "5 - Production/Stable" on PyPI (V1 released September 2025) |
| API stability commitment | V2 planned April 2026 earliest; V1 receives security fixes for 6 months after V2 |
| License | MIT |

### Core Dependencies of pydantic-ai-slim (directly relevant)

| Dependency | Version Required | Status in Existing Stack |
|------------|-----------------|-------------------------|
| pydantic | >2.12 | ALREADY MET (>=2.12.5 in requirements) |
| httpx | >0.27 | ALREADY MET (>=0.28.1 in requirements) |
| griffe | >2.0 | NEW — small dependency for docstring introspection |
| google-genai | >1.56.0 (via [google] extra) | NEW — replaces google-ai-generativelanguage |

### The `google-genai` SDK Transition

The existing stack uses `langchain-google-genai` which wraps the legacy `google-ai-generativelanguage` gRPC-based SDK. Pydantic AI uses `google-genai` (the new unified SDK) directly.

`langchain-google-genai` 4.2.1 (latest) also migrated to `google-genai` under the hood as of v4.0.0. This means both pydantic-ai-slim[google] and langchain-google-genai 4.x reference the same underlying SDK — **they can coexist during migration** without version conflict. The old `google-ai-generativelanguage` package becomes removable once `langchain-google-genai` is removed.

Confidence: MEDIUM — the specific version constraint pydantic-ai-slim places on google-genai (>1.56.0) matches what google-adk also requires (>=1.56.0 minimum). No conflict found between these two packages on the google-genai version.

---

## Pydantic AI Integration with Existing FastAPI DI Patterns

### How pydantic-ai Dependency Injection Works

pydantic-ai uses typed dataclass dependencies passed at `agent.run()` time, accessed via `RunContext[DepsType]`. This is the analog of FastAPI's `Depends()` — not the same mechanism but composable with it:

```python
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass
class FlowDeps:
    db: AsyncSession
    redis_manager: Any  # existing RedisManager singleton
    patient_id: str

humanization_agent = Agent(
    "google-gla:gemini-2.0-flash",  # google-genai model identifier
    deps_type=FlowDeps,
    output_type=str,  # or a Pydantic BaseModel for structured output
    system_prompt="You humanize medical questionnaire messages for oncology patients.",
)

@humanization_agent.system_prompt
async def get_dynamic_prompt(ctx: RunContext[FlowDeps]) -> str:
    # Can access ctx.deps.db, ctx.deps.patient_id
    return f"Patient ID: {ctx.deps.patient_id}. Be empathetic."
```

In FastAPI route handlers:
```python
@router.post("/flow/message")
async def send_flow_message(
    payload: FlowMessageRequest,
    db: AsyncSession = Depends(get_async_db_session),
):
    deps = FlowDeps(db=db, redis_manager=redis_manager, patient_id=str(payload.patient_id))
    result = await humanization_agent.run(payload.template_text, deps=deps)
    return result.output
```

The FastAPI `Depends()` system provides the `AsyncSession`; pydantic-ai's `deps_type` receives it. No framework collision. This is the recommended pattern.

### PII Redaction Integration

The existing `app/ai/pii_redaction.py` with `sanitize_prompt_text_for_external_ai()` integrates into pydantic-ai at two points:

1. **System prompt function:** Apply PII redaction to dynamic system prompt content before passing to Gemini.
2. **Before `agent.run()`:** Redact the user-provided message before it reaches the agent.

```python
# Pattern: redact before run
sanitized_message = sanitize_prompt_text_for_external_ai(template_text)
result = await humanization_agent.run(sanitized_message, deps=deps)
```

The existing `AIResponseValidation.validate_sentiment()` in `nodes_ai.py` maps directly to pydantic-ai's `output_type=SentimentResult` (a Pydantic BaseModel), which replaces manual JSON parsing.

### Circuit Breaker Integration

The existing `aiobreaker`-based circuit breaker (`get_ai_circuit_breaker()`) wraps agent calls at the service layer — not inside pydantic-ai:

```python
async def humanize_message(template: str, patient_id: str, db: AsyncSession) -> str:
    cb = get_ai_circuit_breaker()
    async with cb:  # raises FeatureNotAvailableError when circuit is open
        deps = FlowDeps(db=db, patient_id=patient_id)
        result = await humanization_agent.run(
            sanitize_prompt_text_for_external_ai(template), deps=deps
        )
        return result.output
```

This preserves the existing circuit breaker pattern without pydantic-ai changes.

---

## Coexistence Strategy During Migration

The migration can proceed module by module without a big-bang cutover:

| Phase | LangGraph | pydantic-ai | Notes |
|-------|-----------|-------------|-------|
| Start | Active (graphs.py) | Not yet installed | v1.1 state |
| Install | Active | Installed, no agents yet | Add to requirements.txt; install creates no conflicts |
| Migrate AI ops | Active | Agents for 4 AI operations | consensus.py removed first (dead code) |
| Migrate flows | Removed | Async Python for flow routing | graphs.py, runtime.py deleted |
| Cleanup | Removed | Active | Remove langchain-core, langchain-google-genai |

**Key insight:** pydantic-ai-slim[google] and langchain-google-genai can coexist in the same virtualenv because both now use `google-genai` as the underlying SDK. There is no import conflict. The migration can safely install pydantic-ai before removing LangGraph.

**Order of removal matters:**
1. Remove consensus system (dead code, zero callers)
2. Replace 4 AI operations with pydantic-ai agents
3. Replace flow graph execution with direct async Python functions
4. Remove langgraph, langchain-core, langchain-google-genai, google-ai-generativelanguage

---

## The 4 AI Operations: Migration Targets

Based on codebase analysis, the 4 AI operations that move to pydantic-ai agents are:

| Operation | Current Implementation | New Implementation | Output Type |
|-----------|----------------------|-------------------|-------------|
| Message Humanization | `GeminiClient.generate_content()` via `ChatGoogleGenerativeAI` | `humanization_agent.run(template)` | `str` |
| Sentiment Analysis | `_parse_sentiment_analysis()` with manual JSON parsing | `sentiment_agent.run(response)` | `SentimentResult(BaseModel)` |
| Question Variation | Direct Gemini call in `nodes_ai.py` | `variation_agent.run(question)` | `str` |
| Empathetic Follow-up | Direct Gemini call | `followup_agent.run(context)` | `str` |

The `flow_message_graph` and `flow_response_graph` graphs are NOT AI operations — they are routing logic. Replace with direct async Python (not pydantic-ai agents).

---

## Structured Output: Pydantic AI + Gemini Compatibility Note

Pydantic AI supports two modes for structured output with Gemini:

1. **Tool-calling mode (default):** Agent uses Gemini's function-calling API to return structured JSON. Works with most Pydantic models.
2. **NativeOutput mode:** Uses Gemini's native JSON schema response format. Required for deeply nested models. **Limitation:** Cannot use tools simultaneously when NativeOutput is active with Gemini.

For this project's use case (sentiment analysis returning a flat model like `SentimentScore`, `sentiment: str`, `confidence: float`), tool-calling mode is sufficient and the NativeOutput limitation does not apply.

Confidence: MEDIUM — verified via pydantic-ai docs and GitHub issue #3483 about nested models with Gemini.

---

## Version Compatibility Matrix

| Package | Our Version | pydantic-ai-slim Requires | Compatible? |
|---------|------------|--------------------------|-------------|
| pydantic | >=2.12.5 | >2.12 | YES |
| httpx | >=0.28.1 | >0.27 | YES |
| tenacity | >=8.2.3 | (used internally by [retries] extra) | YES |
| google-auth | >=2.47.0 | No direct constraint | YES (no conflict) |
| google-api-core | >=2.29.0 | No direct constraint | YES (no conflict) |
| protobuf | >=5.0,<7.0.0 | Inherited via google-genai | YES (google-genai requires protobuf; same range) |
| opentelemetry-sdk | >=1.28.0,<2.0.0 | No constraint | YES |

| Package | Our Version | google-adk 1.25.1 Requires | Compatible? |
|---------|------------|---------------------------|-------------|
| opentelemetry-sdk | >=1.28.0,<2.0.0 | >=1.36.0,<1.39.0 | CONFLICT (upper bound) |
| fastapi | >=0.128.0,<0.200.0 | >=0.124.1,<1.0.0 | Overlaps but starlette sub-dep causes issues |
| google-cloud-aiplatform | Not pinned | >=1.132.0,<2.0.0 | Would force new heavy dependency |

---

## Installation

```bash
# Add to requirements.txt (production)
pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0

# google-genai installs transitively; do NOT pin separately unless needed
# google-genai>=1.56.0,<2.0.0  # only add if direct use is needed

# Remove from requirements.txt (after migration complete):
# - langgraph>=1.0.7
# - langchain-core>=1.2.7
# - langchain-google-genai>=2.1.12
# - google-ai-generativelanguage>=0.7.0
```

**Note on pinning pydantic-ai-slim:** Pin to `<2.0.0` because pydantic-ai V2 is planned for April 2026 and is expected to have breaking API changes. The V1 API (`Agent`, `RunContext`, `output_type`) is stable until V2.

---

## Alternatives Considered

| Recommended | Alternative | Why Not Alternative |
|-------------|-------------|---------------------|
| pydantic-ai-slim[google] | pydantic-ai (full) | Full variant installs all model providers (OpenAI, Anthropic, etc.) and Logfire; unnecessary bloat for a Google-only deployment |
| Programmatic Python for flow routing | google-adk SequentialAgent | ADK creates irresolvable dependency conflicts (OTel, FastAPI/Starlette) in v1.2; the routing logic is only 2-node graphs replaceable with 10 lines of Python |
| Programmatic Python for flow routing | LangGraph (keep it) | Migration goal is to remove LangGraph entirely; programmatic Python is more readable for 2-node conditional routing |
| pydantic-ai-slim[google] | Direct google-genai SDK | pydantic-ai adds typed output validation, DI system, and test mocking via `agent.override()`; the `google-genai` SDK would require rebuilding all of this manually |
| aiobreaker (keep existing) | pydantic-ai retries transport | pydantic-ai retries are for HTTP-level retries (429, 503); circuit breaker is a different concern (open/half-open/closed state machine); both are needed |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-adk` in v1.2 | Irresolvable dependency conflicts: OTel upper bound `<1.39.0`, FastAPI/Starlette sub-dep hell, heavy footprint (aiplatform, spanner, bigtable), OTel context detachment in async | Programmatic async Python for flow routing + pydantic-ai agents for AI ops |
| `pydantic-ai` (full, not slim) | Installs all model providers (OpenAI, Anthropic, Groq) and Logfire; unnecessary for Google-only deployment | `pydantic-ai-slim[google,retries]` |
| `google-generativeai` (old SDK) | Being deprecated; replaced by `google-genai`; langchain-google-genai 4.x already migrated away from it | Already transitive; remove `google-ai-generativelanguage` when removing langchain |
| Keeping `ChatGoogleGenerativeAI` after pydantic-ai migration | Two Gemini client abstractions creates confusion about which is authoritative; increases surface area for PII redaction bypass | Remove `langchain-google-genai` after migration; use `pydantic_ai.models.google.GoogleModel` |
| ADK's `SequentialAgent` for 2-node graphs | Massive dependency for a pattern solved in 10 lines of Python | Direct `async def execute_flow_sequence(*steps)` function |
| `NativeOutput` mode for simple schemas | Loses tool-calling capability; Gemini cannot use tools simultaneously | Default tool-calling mode for flat structured outputs (`SentimentResult`, etc.) |

---

## Stack Patterns for This Migration

**For AI operations that return unstructured text (humanization, question variation, empathetic follow-up):**
```python
from pydantic_ai import Agent

humanization_agent = Agent(
    "google-gla:gemini-2.0-flash",
    output_type=str,
    system_prompt="...",  # or dynamic via @agent.system_prompt
)
# PII redaction before run, circuit breaker wraps the call
result = await humanization_agent.run(sanitized_template, deps=deps)
return result.output
```

**For AI operations that return structured data (sentiment analysis):**
```python
from pydantic import BaseModel
from pydantic_ai import Agent

class SentimentResult(BaseModel):
    sentiment: str  # positive/negative/neutral
    confidence: float
    pain_indicators: list[str]

sentiment_agent = Agent(
    "google-gla:gemini-2.0-flash",
    output_type=SentimentResult,
    system_prompt="...",
)
result = await sentiment_agent.run(patient_response, deps=deps)
return result.output  # type: SentimentResult — no more manual JSON parsing
```

**For flow routing (replacing LangGraph 2-node graphs):**
```python
# Replaces build_flow_message_graph() + 30 lines of StateGraph builder
async def execute_flow_message(state: FlowMessageState, *, handler: Any) -> dict:
    state = await load_flow_context(state, handler=handler)
    if state.get("result"):
        return state["result"]
    state = await dispatch_send_mode(state, handler=handler)
    return state.get("result", {})
```

**For testing pydantic-ai agents (replaces LangGraph mock patterns):**
```python
from pydantic_ai.models.test import TestModel

async def test_humanization():
    with humanization_agent.override(model=TestModel()):
        result = await humanization_agent.run("template text", deps=test_deps)
        assert result.output  # validates without real Gemini call
```

---

## Sources

- pydantic-ai PyPI — latest 1.63.0, Python 3.10–3.14, Production/Stable: https://pypi.org/project/pydantic-ai/
- pydantic-ai install docs — slim vs full, [google] extra installs google-genai: https://ai.pydantic.dev/install/
- pydantic-ai-slim pyproject.toml — core deps: pydantic>2.12, httpx>0.27, google-genai>1.56.0 (for [google]): https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pyproject.toml
- pydantic-ai Google model docs — uses google-genai SDK, not google-generativeai: https://ai.pydantic.dev/models/google/
- pydantic-ai dependencies docs — RunContext DI pattern, dataclass deps: https://ai.pydantic.dev/dependencies/
- pydantic-ai retries docs — tenacity-based AsyncTenacityTransport: https://ai.pydantic.dev/retries/
- pydantic-ai output docs — structured output, NativeOutput mode, Gemini tool-calling limitation: https://ai.pydantic.dev/output/
- google-adk PyPI — latest 1.25.1, Python >=3.10: https://pypi.org/project/google-adk/
- google-adk pyproject.toml — deps: google-genai>=1.56.0, opentelemetry-sdk>=1.36.0,<1.39.0, fastapi>=0.124.1: https://github.com/google/adk-python/blob/main/pyproject.toml
- google-adk issue #2657 — FastAPI/starlette version conflict, closed as "won't relax": https://github.com/google/adk-python/issues/2657
- google-adk issue #3173 — Swagger docs fail in v1.16 due to Pydantic 2.11+/FastAPI schema conflict: https://github.com/google/adk-python/issues/3173
- google-adk issue #3615 — lightweight/core-only install request, OPEN, no resolution: https://github.com/google/adk-python/issues/3615
- langchain-google-genai PyPI — 4.2.1, now uses google-genai SDK (v4.0.0+ migration): https://pypi.org/project/langchain-google-genai/
- langchain-google-genai discussion #1422 — Consolidated SDK migration to google-genai in v4.0.0: https://github.com/langchain-ai/langchain-google/discussions/1422
- Codebase analysis — app/ai/client.py (ChatGoogleGenerativeAI usage), app/ai/langgraph/graphs.py (2 multi-node graphs), app/ai/langgraph/consensus.py (dead code, zero callers), app/ai/langgraph/nodes_ai.py (AI helpers, manual JSON parsing)
- ZenML blog — pydantic-ai vs LangGraph, ADK vs LangGraph comparison: https://www.zenml.io/blog/google-adk-vs-langgraph

---

*Stack research for: Healthcare WhatsApp backend — AI framework migration (LangGraph → Pydantic AI)*
*Researched: 2026-02-23*
*Confidence: HIGH for pydantic-ai choices, MEDIUM for google-adk conflict analysis (verified against GitHub issues but dependency resolution can shift with new versions)*
