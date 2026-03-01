# Feature Research

**Domain:** AI framework migration — LangGraph to Pydantic AI agents + Google ADK orchestration for oncology WhatsApp backend
**Researched:** 2026-02-23
**Confidence:** HIGH (Pydantic AI v1 official docs + ADK official docs verified) / MEDIUM (Gemini-specific structured output patterns — active issues in pydantic-ai repo)

---

## Context: Migration Milestone Framing

This is a **framework replacement**, not a new feature. The 4 core AI operations already exist and work. The goal is to remove LangGraph and its associated infrastructure (graphs, runtime, checkpointing, state) and re-implement the same operations using:

- **Pydantic AI agents** for each of the 4 operations (typed, dependency-injected, validated output)
- **Google ADK** (SequentialAgent / ParallelAgent) for orchestrating multi-step AI flows

Existing infrastructure that must be preserved and wired in:
- Redis semantic cache (in `GeminiClient._get_cached_response` / `_cache_response`)
- Circuit breaker (`AIServiceCircuitBreaker` via `get_ai_circuit_breaker()`)
- Rate limiter (`check_ai_rate_limit` in `utils/rate_limiter.py`)
- PII redaction (`sanitize_prompt_text_for_external_ai` in `ai/pii_redaction.py`)
- Output guardrails (`GuardrailViolation`, `validate_ai_output`, `OutputProfile` in `services/ai/`)
- Audit event types (`AI_QUERY`, `AI_HUMANIZATION` etc. in `AuditEventType`)

---

## Feature Landscape

### Table Stakes (Required for a Correct Migration)

These are the features that must exist for the migration to be complete and correct. Missing any = the migration is broken or regresses existing behavior.

| Feature | Why Required | Complexity | Infrastructure Dependency |
|---------|--------------|------------|--------------------------|
| **HumanizeAgent: typed output** | Humanization is the core product value — must produce a valid, non-empty, punctuation-terminated Brazilian Portuguese message or raise `FeatureNotAvailableError`; silent degradation = robotic messages to cancer patients | MEDIUM | `MESSAGE_HUMANIZED` OutputProfile; Redis cache; circuit breaker; PII redaction |
| **SentimentAgent: structured JSON output** | Sentiment drives clinical escalation decisions; JSON must have all 7 required keys (`sentiment`, `confidence`, `emotional_indicators`, `medical_concerns`, `requires_attention`, `key_themes`, `suggested_follow_up`); a missing key downstream causes `KeyError` in alert logic | MEDIUM | `JSON_SENTIMENT` OutputProfile; `AIResponseValidation.validate_sentiment()`; circuit breaker |
| **VariationAgent: anti-repetition logic preserved** | 88% word-overlap threshold must survive migration; the `_is_too_similar_to_recent()` fallback to wrapper phrases must remain; agents seeing the same question every visit disengage | MEDIUM | `MESSAGE_STANDARD` OutputProfile; `_is_too_similar_to_recent()` logic in `nodes_ai.py` (can migrate to agent tool or post-run hook) |
| **EmpathyAgent: conditional question suppression** | `allow_questions=False` and `day_complete` flags control whether the AI may ask a follow-up question — this is a clinical decision, not a style preference; losing this produces prompts that confuse patients | MEDIUM | `MESSAGE_HUMANIZED` OutputProfile; prompt flag injection via system prompt or `deps` |
| **Pydantic AI `deps_type` pattern for infra injection** | Redis client, circuit breaker, and rate limiter must be injected as typed dependencies — not accessed as module-level globals inside agents — to enable test overrides and avoid singleton coupling during migration | MEDIUM | `dataclasses.dataclass` deps; `RunContext[Deps]` typed tools |
| **PII redaction as pre-run hook or tool** | `sanitize_prompt_text_for_external_ai()` must fire before ANY text reaches Gemini; this is a LGPD hard requirement; the existing `GeminiClient._redact_prompt_for_external_ai()` call must not be lost in the migration | LOW | `app/ai/pii_redaction.py` — no migration needed, just must be called |
| **`FeatureNotAvailableError` on circuit-open** | All callers of the 4 AI operations already catch `FeatureNotAvailableError` to degrade gracefully (send template message instead of humanized); the exception contract must be preserved | LOW | `app/core/exceptions.FeatureNotAvailableError`; circuit breaker state |
| **Output guardrail enforcement post-agent-run** | `validate_ai_output()` must run after agent output is produced, before the result is returned to the caller; moving validation into the Pydantic model field validators is acceptable but the semantics (prompt leak detection, placeholder detection, JSON key checks) must match the existing `GuardrailViolation` behavior | MEDIUM | `app/services/ai/guardrails.py`; `app/services/ai/output_profiles.py` |
| **Redis cache hit/miss preserved** | Cache lookup (SHA-256 of PII-redacted prompt + profile_hint) and write must survive migration; cache TTL 3600s must remain; cache misses that fail guardrails must regenerate, not return stale output | MEDIUM | `GeminiClient._generate_cache_key()`, `_get_cached_response()`, `_cache_response()` |
| **`GeminiDomainClient` methods replaced, not deprecated** | The 4 methods (`humanize_flow_message`, `generate_varied_question`, `analyze_response_sentiment`, `create_empathetic_follow_up`) are called directly by `flow_core.py`, `flow_service.py`, `enhanced_flow_engine.py` — they must remain importable during transition; use shim pattern until all callers migrated | LOW | Shim pattern in `app/ai/client_domain.py` |
| **LangGraph removal: no orphan imports** | After migration, `langgraph`, `langgraph.graph`, `StateGraph`, `END` must not appear in any non-tombstoned import; `graphs.py`, `runtime.py`, `state.py`, `nodes.py`, `_invoke.py` must be tombstoned or deleted | LOW | Tombstone pattern from `MEMORY.md` |
| **Consensus system deletion** | `app/ai/langgraph/consensus.py` and `app/agents/patient/flow_coordinator/consensus_manager.py` are dead code; deleting them is part of this milestone per PROJECT.md | LOW | No callers; full deletion (not tombstone) |

---

### Differentiators (Migration-Specific Competitive Advantages)

Features that the migration uniquely enables, beyond parity with current behavior.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Typed output models for all 4 operations** | `SentimentResult(BaseModel)` with `sentiment: Literal["positive", "neutral", "negative"]`, `confidence: float = Field(ge=0.0, le=1.0)`, etc. replaces manual `json.loads()` + `AIResponseValidation.validate_sentiment()` — type errors caught at schema level, not at runtime | MEDIUM | Pydantic AI's `output_type=SentimentResult` converts BaseModel to JSON schema sent to Gemini; validation is automatic before result is returned; eliminates the current `_parse_sentiment_analysis()` + `AIResponseValidation` dual-validation pattern |
| **PromptedOutput for Gemini JSON operations** | Gemini cannot use tool calling AND structured outputs simultaneously (confirmed limitation); for `SentimentAgent`, use `PromptedOutput(SentimentResult)` which injects JSON schema into the system prompt rather than using function calling — avoids the Gemini tool-calling-vs-structured-output conflict | MEDIUM | `pydantic_ai.PromptedOutput` wrapper; MEDIUM confidence — this is the documented workaround per Pydantic AI docs; validate with `gemini-2.5-flash` before committing |
| **Google ADK SequentialAgent for flow_message_graph replacement** | Current `build_flow_message_graph()` is `load_flow_context → dispatch_send_mode`; ADK SequentialAgent with two sub-agents replaces this with no StateGraph overhead, no checkpoint store, no graph compilation at startup | MEDIUM | ADK `SequentialAgent(sub_agents=[LoadContextAgent, HumanizeAgent])`; `output_key` pattern for passing context between steps |
| **Google ADK ParallelAgent for sentiment + follow-up** | When a patient responds, sentiment analysis and follow-up generation are independent operations on the same input; ParallelAgent runs them concurrently, halving wall-clock latency for the response flow | HIGH | ADK `ParallelAgent(sub_agents=[SentimentAgent, EmpathyAgent])`; each agent writes to separate `output_key`; results merged by downstream agent or caller |
| **`deps_type` enables test isolation per agent** | Each Pydantic AI agent can be tested with `agent.override(deps=TestDeps(redis=FakeRedis(), circuit_breaker=AlwaysOpenBreaker()))` — no more module-level singleton patching with `mock.patch` during testing | LOW | `pydantic_ai.Agent.override()` test pattern; enables proper unit tests for each of the 4 agents independently |
| **`GoogleModelSettings` for safety thresholds** | Current `ChatGoogleGenerativeAI` initialization has `temperature`, `max_output_tokens`, `top_p`, `top_k` — these map directly to `GoogleModelSettings` in Pydantic AI; adds explicit `google_safety_settings` per operation type | LOW | `pydantic_ai.models.google.GoogleModelSettings`; sentiment agent may want different thresholds than humanization |
| **`UsageLimits` per agent run** | Pydantic AI supports `UsageLimits(request_tokens_limit=N, response_tokens_limit=N)` at the per-run level, complementing the existing distributed rate limiter | LOW | Replaces the manual `max_output_tokens` config in `ChatGoogleGenerativeAI` with per-operation limits |

---

### Anti-Features (Commonly Proposed, Explicitly Avoid in This Migration)

| Anti-Feature | Why Attractive | Why Avoid | What to Do Instead |
|--------------|----------------|-----------|-------------------|
| **Native structured output mode for Gemini** | Guarantees schema adherence at the protocol level | Gemini cannot use tools simultaneously with native structured outputs; adding tools for cache/rate-limit checks is blocked; confirmed limitation in Pydantic AI issues #582, #1237, #3483 | Use `PromptedOutput` for JSON operations (SentimentAgent); keep validation via Pydantic field validators |
| **Full streaming of agent output** | Lower time-to-first-byte for patient messages | Gemini streaming is unsupported with structured outputs (Pydantic AI issue #1237); streaming text output conflicts with JSON validation; healthcare messages must be fully validated before delivery | Retain `await agent.run()` non-streaming; validate complete output before return |
| **ADK `LlmAgent` for all 4 operations instead of Pydantic AI agents** | Single framework, no Pydantic AI dependency | ADK's `LlmAgent` has weaker Python typing, no `output_type` BaseModel validation, no `deps_type` system; Pydantic AI agents produce type-safe results that integrate naturally with existing Pydantic domain models | Use ADK SequentialAgent/ParallelAgent ONLY for orchestration; keep Pydantic AI agents for the 4 AI operations themselves |
| **Replacing `GeminiClient.generate_content()` with direct Pydantic AI agent call everywhere** | Cleaner — one fewer abstraction layer | `generate_content()` is called in at least 3 places outside the 4 domain operations; replacing all callsites simultaneously creates large migration diff; risk of breaking callers | Migrate `GeminiDomainClient` methods to Pydantic AI agents first; leave `GeminiClient.generate_content()` intact for other callers; deprecate later |
| **LangGraph checkpointing/persistence migration to ADK SessionService** | "We should preserve conversation history with ADK sessions" | ADK's `SessionService` is designed for interactive conversations, not fire-and-forget clinical flows; current flows are stateless request-response (state lives in PostgreSQL `patient_flow_state`, not in the graph checkpoint); adding ADK session persistence adds Redis/DB dependency with zero benefit | Keep flow state in PostgreSQL as-is; do not use ADK session persistence for these operations |
| **Using `ModelRetry` for automatic JSON correction** | Let the framework retry on validation failure | Gemini structured output retries within Pydantic AI already cost extra API calls; existing code has its own `guardrail_retries` counter that already handles re-prompting; two retry loops conflict | Keep existing guardrail retry counter in the wrapping infrastructure; configure `output_retries=0` on agents and handle retries at the caller level |
| **Migrating prompt strings into ADK LlmAgent `instruction` field** | "One place for everything ADK" | Current prompt builders (`build_humanization_prompt`, `build_sentiment_prompt` etc.) do PII-safe template substitution, question counting, and Portuguese-language specific formatting; ADK `instruction` field does not support dynamic prompt building with pre-processing hooks | Keep `app/ai/langgraph/prompts.py` prompt builders (rename to `app/ai/prompts.py`); call them before passing prompt to Pydantic AI agent |

---

## Feature Dependencies

```
[PII Redaction Hook]
    └──required by──> [HumanizeAgent] (LGPD hard requirement)
    └──required by──> [SentimentAgent]
    └──required by──> [VariationAgent]
    └──required by──> [EmpathyAgent]

[Pydantic AI deps_type pattern]
    └──required by──> [Redis cache integration in agents]
    └──required by──> [Circuit breaker injection in agents]
    └──enables──> [Test isolation per agent]

[PromptedOutput workaround]
    └──required by──> [SentimentAgent typed JSON output] (Gemini tool+structured limitation)
    └──does NOT apply to──> [HumanizeAgent] (text output, no conflict)
    └──does NOT apply to──> [VariationAgent] (text output, no conflict)
    └──does NOT apply to──> [EmpathyAgent] (text output, no conflict)

[SentimentResult BaseModel]
    └──replaces──> [AIResponseValidation.validate_sentiment()]
    └──required by──> [Alert escalation pipeline] (fields: requires_attention, medical_concerns)
    └──required by──> [SentimentAgent]

[GeminiDomainClient shim]
    └──required by──> [Zero-downtime migration] (existing callers in flow_core.py, flow_service.py)
    └──enables──> [Incremental replacement of 4 methods]

[ADK SequentialAgent (flow_message)]
    └──replaces──> [build_flow_message_graph() in langgraph/graphs.py]
    └──requires──> [HumanizeAgent] (sub-agent)
    └──requires──> [LoadContextAgent or equivalent]

[ADK ParallelAgent (response processing)]
    └──replaces──> [build_flow_response_graph() in langgraph/graphs.py]
    └──requires──> [SentimentAgent] (sub-agent)
    └──requires──> [EmpathyAgent] (sub-agent)

[LangGraph removal]
    └──requires──> [All 4 agents implemented]
    └──requires──> [ADK orchestration replacing graphs]
    └──requires──> [GeminiDomainClient callers migrated]
    └──enables──> [Consensus system deletion]
    └──enables──> [LangGraph package removal from requirements.txt]

[Consensus system deletion]
    └──requires──> [Zero callers verified] (consensus_manager.py, consensus.py)
    └──does NOT require──> [4 agents complete] (independent dead code removal)
```

### Dependency Notes

- **PII redaction is unconditional**: It must fire before the prompt text reaches any Pydantic AI agent. The cleanest pattern is a `@agent.system_prompt` async function in `deps` that pre-processes the input, or wrapping the agent call in the shim method. Do not rely on the agent framework to enforce this.
- **PromptedOutput applies only to SentimentAgent**: The Gemini tool-calling + structured output conflict only manifests when `output_type` is a Pydantic BaseModel AND you want to use tools simultaneously. HumanizeAgent, VariationAgent, and EmpathyAgent produce text (not JSON schemas), so standard `output_type=str` or custom type with `ToolOutput` works.
- **ADK orchestration is additive, not required for individual agents**: The 4 Pydantic AI agents can be used standalone (called directly) without ADK. ADK SequentialAgent/ParallelAgent adds value for the flow execution paths that need multi-step coordination — but is not a prerequisite for migrating the 4 agents themselves.
- **Shim pattern gates the migration deadline**: Because `flow_core.py`, `flow_service.py`, and `enhanced_flow_engine.py` call `GeminiDomainClient` methods directly, those methods must remain importable during the migration. The shim at `app/ai/client_domain.py` should delegate to the new Pydantic AI agent implementations without changing the method signatures.

---

## How Each AI Operation Maps to Pydantic AI Patterns

### Operation 1: Message Humanization

**Current**: `GeminiDomainClient.humanize_flow_message()` → `build_humanization_prompt()` → `generate_content(profile=MESSAGE_HUMANIZED)`

**Pydantic AI pattern**:
```python
from dataclasses import dataclass
from pydantic import BaseModel, field_validator
from pydantic_ai import Agent, RunContext

@dataclass
class AIDeps:
    redis_client: Any          # injected; existing async Redis client
    circuit_breaker: Any       # AIServiceCircuitBreaker from get_ai_circuit_breaker()
    pii_redactor: Callable     # sanitize_prompt_text_for_external_ai

class HumanizedMessage(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_message(cls, v: str) -> str:
        # Run existing validate_ai_output() logic here
        validate_ai_output(v, OutputKind.MESSAGE, ...)
        return v

humanize_agent = Agent(
    "google-gla:gemini-2.5-flash",
    deps_type=AIDeps,
    output_type=HumanizedMessage,
    output_retries=0,              # handled by existing guardrail loop
)

@humanize_agent.system_prompt
async def system_prompt(ctx: RunContext[AIDeps]) -> str:
    return (
        "Reescreva a mensagem mantendo o mesmo propósito. "
        "Escreva em português do Brasil. "
        "Responda apenas com a mensagem final, sem listas e sem aspas."
    )
```

**Output mode**: `ToolOutput(HumanizedMessage)` (default) — acceptable for text output; no Gemini tool conflict because we are not asking for JSON schema output simultaneously.

**Complexity**: MEDIUM — field validator wraps existing guardrail logic; deps injection replaces module-level globals.

---

### Operation 2: Sentiment Analysis

**Current**: `GeminiDomainClient.analyze_response_sentiment()` → `build_sentiment_prompt()` → `generate_content(profile=JSON_SENTIMENT)` → `_parse_sentiment_analysis()` → `AIResponseValidation.validate_sentiment()`

**Pydantic AI pattern**:
```python
from typing import Literal
from pydantic import BaseModel, Field

class SentimentResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    confidence: float = Field(ge=0.0, le=1.0)
    emotional_indicators: list[str]
    medical_concerns: list[str]
    requires_attention: bool
    key_themes: list[str]
    suggested_follow_up: str

sentiment_agent = Agent(
    "google-gla:gemini-2.5-flash",
    deps_type=AIDeps,
    output_type=PromptedOutput(SentimentResult),  # avoids Gemini tool+JSON conflict
    output_retries=2,
)
```

**Output mode**: `PromptedOutput` — injects JSON schema into system prompt; Gemini returns JSON text which Pydantic AI parses; avoids the tool-calling conflict. Replaces the entire `_parse_sentiment_analysis()` + `AIResponseValidation.validate_sentiment()` chain.

**Complexity**: MEDIUM — `PromptedOutput` is the critical choice; must be validated against `gemini-2.5-flash` before committing. Pydantic AI issues #582 and #3483 document edge cases with nested models.

---

### Operation 3: Question Variation

**Current**: `GeminiDomainClient.generate_varied_question()` → `build_question_variation_prompt()` → `generate_content(profile=MESSAGE_STANDARD)` → `_is_too_similar_to_recent()` → `_build_non_repetitive_question()` fallback

**Pydantic AI pattern**:
```python
variation_agent = Agent(
    "google-gla:gemini-2.5-flash",
    deps_type=AIDeps,
    output_type=str,
    output_retries=0,
)
```

The `_is_too_similar_to_recent()` check and wrapper fallback happen **after** the agent run — they are not agent behavior, they are post-processing. This logic stays in the shim method (migrated from `client_domain.py`), calling `agent.run()` then checking similarity.

**Output mode**: `str` output with no structured type; validate with existing guardrails after run.

**Complexity**: LOW — simpler than sentiment; post-run similarity check is pure Python logic, does not touch Gemini.

---

### Operation 4: Empathetic Follow-Up

**Current**: `GeminiDomainClient.create_empathetic_follow_up()` → `build_empathetic_prompt()` (with `allow_questions`, `day_complete` flags) → `generate_content(profile=MESSAGE_HUMANIZED)`

**Pydantic AI pattern**:
```python
@dataclass
class EmpathyDeps(AIDeps):
    allow_questions: bool = False
    day_complete: bool = False

empathy_agent = Agent(
    "google-gla:gemini-2.5-flash",
    deps_type=EmpathyDeps,
    output_type=str,
    output_retries=0,
)

@empathy_agent.system_prompt
async def empathy_system_prompt(ctx: RunContext[EmpathyDeps]) -> str:
    question_rule = (
        "Se fizer pergunta, faça no máximo uma." if ctx.deps.allow_questions
        else "Não faça perguntas."
    )
    completion = (
        "Se for apropriado, informe que as perguntas de hoje terminaram."
        if ctx.deps.day_complete else ""
    )
    return f"Crie uma resposta empática e de apoio ao paciente. {question_rule} {completion}"
```

The `allow_questions` and `day_complete` flags become `deps` fields — injected at call time, consumed by the dynamic system prompt. This preserves the clinical behavior while eliminating the prompt-building function's flag parameters.

**Output mode**: `str` with guardrail validation post-run.

**Complexity**: MEDIUM — flag injection via deps is idiomatic; the critical risk is that the system prompt must precisely replicate the existing `build_empathetic_prompt()` clinical constraints.

---

## ADK Orchestration Patterns

### Pattern A: SequentialAgent replacing `flow_message_graph`

Current LangGraph graph: `load_flow_context → conditional → dispatch_send_mode`

ADK equivalent:
```python
from google.adk.agents import SequentialAgent
# Step 1: custom BaseAgent subclass that loads context from DB, writes to session.state
# Step 2: Pydantic AI HumanizeAgent (wrapped via AgentTool or custom BaseAgent subclass)

flow_message_orchestrator = SequentialAgent(
    name="FlowMessageOrchestrator",
    sub_agents=[LoadContextAgent, HumanizeDispatchAgent],
)
```

**Key constraint**: ADK `LlmAgent` cannot directly call Pydantic AI agents. The integration pattern is wrapping the Pydantic AI agent call inside a custom `BaseAgent._run_async_impl()` method.

**Complexity**: HIGH — requires custom `BaseAgent` subclasses; ADK event model differs from LangGraph state model; must preserve the early-exit branch (`if state.get("result"): return END`).

---

### Pattern B: ParallelAgent replacing `flow_response_graph` (new capability)

ADK equivalent for response processing:
```python
from google.adk.agents import ParallelAgent

response_analysis_orchestrator = ParallelAgent(
    name="ResponseAnalysis",
    sub_agents=[SentimentAnalysisAgent, EmpathyGenerationAgent],
)
```

Both agents receive the same patient response and context from session state. `SentimentAnalysisAgent` writes to `session.state["sentiment_result"]`; `EmpathyGenerationAgent` writes to `session.state["empathy_message"]`. A downstream aggregator reads both.

**Complexity**: HIGH — parallel agents with shared session state require careful key namespacing; the existing `flow_response_graph` is sequential, not parallel; this is a new optimization beyond parity.

**Recommendation**: Implement parity (sequential) first; add parallel optimization only after sequential migration is stable.

---

## MVP Definition for Migration Milestone

### Phase 1: Agent Parity (Must Complete for Migration to be Correct)

- [ ] `HumanizedMessage` Pydantic model with field validator wrapping existing guardrail logic
- [ ] `SentimentResult` Pydantic model replacing `AIResponseValidation.validate_sentiment()`
- [ ] `humanize_agent` with `deps_type=AIDeps` (Redis, circuit breaker, PII redactor injected)
- [ ] `sentiment_agent` with `PromptedOutput(SentimentResult)` — validated against Gemini
- [ ] `variation_agent` with post-run `_is_too_similar_to_recent()` preserved
- [ ] `empathy_agent` with `allow_questions` / `day_complete` via `EmpathyDeps`
- [ ] PII redaction called before all agent prompts (in system_prompt hook or shim)
- [ ] Redis cache read/write preserved in shim wrapper around each agent
- [ ] Circuit breaker wrapping each `agent.run()` call
- [ ] `GeminiDomainClient` shim: all 4 methods delegate to new agents, same signatures
- [ ] Consensus system deleted (`consensus.py`, `consensus_manager.py`)

### Phase 2: LangGraph Removal (After Phase 1 Verified in Staging)

- [ ] `build_flow_message_graph()` replaced with ADK SequentialAgent or direct agent calls
- [ ] `build_flow_response_graph()` replaced with ADK SequentialAgent (sequential parity)
- [ ] All `langgraph.*` imports removed from non-tombstoned files
- [ ] `ai/langgraph/` directory: `graphs.py`, `runtime.py`, `state.py`, `nodes.py`, `_invoke.py` tombstoned
- [ ] `langgraph` removed from `requirements.txt`
- [ ] `langchain_core`, `langchain_google_genai` removed if no other callers

### Phase 3: ADK Optimization (After Phase 2 Stable — Optional for This Milestone)

- [ ] ParallelAgent for simultaneous sentiment + empathy during response processing
- [ ] `GoogleModelSettings` per operation type (different temperatures for message vs JSON)
- [ ] `UsageLimits` per agent run complementing distributed rate limiter

---

## Feature Prioritization Matrix

| Feature | Migration Correctness | Clinical Safety | Implementation Cost | Priority |
|---------|----------------------|-----------------|---------------------|----------|
| HumanizeAgent (parity) | HIGH | HIGH | MEDIUM | P1 |
| SentimentAgent with PromptedOutput | HIGH | HIGH | MEDIUM | P1 |
| PII redaction hook in agents | HIGH | HIGH | LOW | P1 |
| Circuit breaker wrapping agent.run() | HIGH | HIGH | LOW | P1 |
| FeatureNotAvailableError contract | HIGH | HIGH | LOW | P1 |
| VariationAgent (parity + similarity check) | HIGH | MEDIUM | LOW | P1 |
| EmpathyAgent with flag injection | HIGH | HIGH | MEDIUM | P1 |
| GeminiDomainClient shim (zero-downtime) | HIGH | MEDIUM | LOW | P1 |
| Consensus system deletion | LOW | MEDIUM | LOW | P1 |
| Redis cache preservation | MEDIUM | LOW | MEDIUM | P1 |
| LangGraph import removal | MEDIUM | LOW | MEDIUM | P2 |
| ADK SequentialAgent for flow_message | MEDIUM | LOW | HIGH | P2 |
| SentimentResult typed fields in alert pipeline | MEDIUM | HIGH | LOW | P2 |
| ADK ParallelAgent for response | LOW | LOW | HIGH | P3 |
| GoogleModelSettings per operation | LOW | LOW | LOW | P3 |
| UsageLimits per agent run | LOW | LOW | LOW | P3 |

**Priority key:**
- P1: Must complete for migration to be correct and production-safe
- P2: Should complete for full LangGraph removal
- P3: Future optimization — defer to post-migration milestone

---

## Gemini-Specific Structured Output Notes

These constraints are MEDIUM confidence (from Pydantic AI GitHub issues and official docs, as of Feb 2026):

| Scenario | Pydantic AI Output Mode | Works with Gemini? | Notes |
|----------|------------------------|--------------------|-------|
| Text message output (str) | `ToolOutput(str)` default | YES | HumanizeAgent, VariationAgent, EmpathyAgent |
| Simple JSON with flat schema | `PromptedOutput(Model)` | YES | SentimentResult — all fields are primitives or `list[str]` |
| Nested Pydantic models in JSON | `PromptedOutput(NestedModel)` | RISKY | Issues #3483: nested models may be treated as tool calls |
| JSON + simultaneous tool calls | `NativeOutput` or `ToolOutput` | NO | Gemini limitation — tool + structured output conflict |
| Streaming structured output | Any mode | NO | Gemini does not support streaming with structured output |

**Recommendation**: Keep `SentimentResult` flat (no nested Pydantic models as fields). Use `list[str]` and `str` for all fields. This avoids issue #3483.

---

## Sources

- [Pydantic AI Output Modes — official docs](https://ai.pydantic.dev/output/) — ToolOutput / NativeOutput / PromptedOutput patterns; HIGH confidence
- [Pydantic AI Google Model — official docs](https://ai.pydantic.dev/models/google/) — GoogleModel, GoogleModelSettings, API key setup; HIGH confidence
- [Pydantic AI Dependencies — official docs](https://ai.pydantic.dev/dependencies/) — deps_type, RunContext, override() test pattern; HIGH confidence
- [Pydantic AI v1 announcement](https://pydantic.dev/articles/pydantic-ai-v1) — API stability guarantees, Logfire integration; HIGH confidence
- [Google ADK Sequential Agents — official docs](https://google.github.io/adk-docs/agents/workflow-agents/sequential-agents/) — SequentialAgent, output_key, InvocationContext; HIGH confidence
- [Google ADK Parallel Agents — official docs](https://google.github.io/adk-docs/agents/workflow-agents/parallel-agents/) — ParallelAgent, concurrent execution, state isolation; HIGH confidence
- [Google ADK Multi-Agent Systems — official docs](https://google.github.io/adk-docs/agents/multi-agents/) — agent hierarchy, AgentTool, delegation patterns; HIGH confidence
- [Gemini structured output + tool calling limitation — Pydantic AI issue #582](https://github.com/pydantic/pydantic-ai/issues/582) — confirmed incompatibility; MEDIUM confidence (open issue)
- [Nested models as tool calls — Pydantic AI issue #3483](https://github.com/pydantic/pydantic-ai/issues/3483) — flat schema recommendation; MEDIUM confidence (open issue)
- [Gemini streaming structured output — Pydantic AI issue #1237](https://github.com/pydantic/pydantic-ai/issues/1237) — streaming limitation confirmed; MEDIUM confidence
- [Google ADK + FastAPI integration — DEV Community](https://dev.to/timtech4u/building-ai-agents-with-google-adk-fastapi-and-mcp-26h7) — production integration patterns; MEDIUM confidence
- [Coercing LLM agents to structured outputs — Higherpass](https://www.higherpass.com/2025/05/22/coercing-llm-agents-with-structured-responses-using-pydantic-ai/) — field validator production patterns; MEDIUM confidence
- Codebase analysis: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/ai/` — current implementation patterns verified directly; HIGH confidence

---

*Feature research for: AI framework migration — LangGraph to Pydantic AI + Google ADK (oncology WhatsApp backend v1.2)*
*Researched: 2026-02-23*
