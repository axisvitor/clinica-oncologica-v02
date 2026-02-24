# Phase 11: Agent Implementation - Research

**Researched:** 2026-02-24
**Domain:** pydantic-ai agent construction, PII guardrails, feature-flag shim
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Guardrail strictness:**
- Hard fail (raise exception) when any guardrail check fails -- no silent fallbacks, no swallowed errors
- Each agent declares its own `@output_validator` decorators (not shared in base class) -- allows agent-specific thresholds (e.g., sentiment needs shorter output than humanize)
- SentimentResult: core fields (sentiment, confidence) are required; optional fields (key_themes, suggested_follow_up, etc.) fill with Pydantic defaults if Gemini omits them
- Downstream alert logic never encounters a KeyError because Pydantic model guarantees all 7 fields are populated

**Feature flag transition:**
- One global `AI_FRAMEWORK` environment variable toggles all 4 operations at once
- Lives in .env / Cloud Run env config -- standard pattern for this codebase
- When AI_FRAMEWORK is off (legacy path), log at INFO level that legacy path is active
- `GeminiDomainClient` shim reads the flag and delegates to either new agents or old direct calls

**PII redaction boundaries:**
- Use existing `sanitize_prompt_text_for_external_ai()` from `app/ai/pii_redaction.py` as-is -- no modifications
- `PIISafeAgent` enforces sanitization automatically on every call -- mandatory, no opt-out, no skip_pii flag
- Also scan Gemini OUTPUT for leaked PII before returning to caller (belt-and-suspenders for LGPD)
- If sanitization itself fails/errors, block the agent call entirely -- do NOT call Gemini with unsanitized data

**Agent failure handling:**
- Gemini timeout/unavailable: retry once with backoff, then raise exception to caller
- Gemini returns bad output (unparseable, wrong structure): use pydantic-ai's built-in validation retry (re-sends with "your output was invalid" hint), one retry, then fail
- 30-second timeout per agent call
- Structured logging on every agent call: operation name, input hash, latency, success/failure, retry count, error type

### Claude's Discretion
- Which specific old guardrails to keep, adjust, or drop -- based on codebase analysis of existing GeminiClient checks
- How long both paths coexist before old direct calls are removed -- based on complexity and maintenance burden assessment
- Exact retry backoff strategy and timing
- Structured log format (JSON, Python logging dict, etc.)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGENT-01 | SentimentAgent analyzes patient responses returning typed SentimentResult (7 fields) via PromptedOutput | `PromptedOutput(SentimentResult)` pattern confirmed; existing `SentimentAnalysisResult` schema in `app/schemas/ai_schemas.py` can be adapted |
| AGENT-02 | HumanizeAgent transforms flow templates into natural messages preserving question count and placeholders | `PromptedOutput(str)` or direct `output_type=str`; existing prompt in `build_humanization_prompt()` reused as system prompt |
| AGENT-03 | VariationAgent generates question variations avoiding 88% word overlap with recent interactions | Same message output type; existing `_is_too_similar_to_recent()` logic (88% threshold in `nodes_ai.py`) maps to post-validator check |
| AGENT-04 | EmpathyAgent generates empathetic follow-up messages based on sentiment analysis | Same message output type; existing `build_empathetic_prompt()` reused |
| AGENT-05 | All 4 agents enforce PII/PHI redaction before every Gemini call via PIISafeAgent wrapper (LGPD Art. 46) | `sanitize_prompt_text_for_external_ai()` is a pure function -- PIISafeAgent wraps `agent.run()` to call it before invoking Gemini |
| AGENT-06 | All 4 agents validate output via `@output_validator` decorators reconnecting existing guardrails (banned patterns, prompt leak detection, length validation) | `Agent.output_validator` confirmed in pydantic-ai 1.63.0; existing `_BANNED_PATTERNS`, `_PROMPT_LEAK_MARKERS`, `validate_ai_output()` in `app/services/ai/guardrails.py` are the source of truth |
| AGENT-07 | GeminiDomainClient methods delegate to new pydantic-ai agents via shim pattern (zero breaking changes to callers) | Shim pattern established in codebase; `AI_FRAMEWORK` env var not yet in settings -- must be added to `integrations.py` |
| AGENT-08 | 50-scenario output regression test suite passes comparing old GeminiClient vs new agent outputs | pytest with `asyncio_mode=auto` already configured; no existing agent tests -- Wave 0 gap |
</phase_requirements>

## Summary

Phase 11 replaces four direct GeminiClient calls with typed pydantic-ai agents. The codebase already has all the building blocks: pydantic-ai-slim 1.63.0 is installed and confirmed working, the `sanitize_prompt_text_for_external_ai()` PII function is complete, guardrail logic lives in `app/services/ai/guardrails.py`, prompt builders are in `app/ai/langgraph/prompts.py`, and existing Pydantic schemas (`SentimentAnalysisResult`) can be adapted as the typed output model.

The pydantic-ai 1.63.0 API confirmed by live inspection: `Agent` accepts `output_type=PromptedOutput(SentimentResult)`, `output_retries=1` for built-in "re-ask" behavior, `model_settings=ModelSettings(timeout=30.0)`, and `defer_model_check=True` to allow runtime model injection. The `output_validator` decorator on an `Agent` instance accepts a `ModelRetry` raise to trigger a structured re-prompt. `AgentRunResult.output` is the accessor for the typed result.

The `GeminiDomainClient` shim is the critical backward-compatibility layer. It must remain a subclass of `GeminiClient` (no changes to class hierarchy), add a new `AI_FRAMEWORK` boolean setting to `integrations.py`, and delegate each of the 4 methods to the corresponding pydantic-ai agent when the flag is on. The flag is not yet in the codebase -- it must be added in Plan 11-04.

**Primary recommendation:** Implement in the prescribed order (11-01 scaffold, 11-02 SentimentAgent, 11-03 remaining 3 agents, 11-04 shim + regression tests). Each plan is independently committable because the shim is added last and both paths coexist until the flag is toggled.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-ai-slim[google,retries] | 1.63.0 (pinned <2.0.0) | Typed agent framework with Gemini backend | Already installed, tested, pinned in requirements.txt; breaking V2 planned April 2026 |
| pydantic-ai providers.google.GoogleProvider | bundled with pydantic-ai | Runtime API key injection per call | Avoids global env var; allows per-request key in AIDeps |
| pydantic-ai models.google.GoogleModel | bundled | Model binding with provider | Pairs with GoogleProvider for clean per-call setup |
| pydantic (v2) | existing | Typed output schemas (SentimentResult, etc.) | Already the codebase standard; pydantic-ai is built on pydantic |
| asyncio | stdlib | async agent invocation | `Agent.run()` is a coroutine |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib | stdlib | Input prompt hash for structured logs | Log correlation without logging raw PHI |
| time / asyncio | stdlib | Latency measurement per agent call | Required by locked decision on structured logging |
| dataclasses | stdlib | AIDeps dataclass | Idiomatic pydantic-ai pattern for dependency injection |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `PromptedOutput(SentimentResult)` | `NativeOutput(SentimentResult)` | `NativeOutput` requires Gemini native structured output (tool-calling mode) which conflicts with Gemini API for this model -- decision from STATE.md |
| Per-agent `@output_validator` | Shared base class validator | Base class validator cannot access agent-specific thresholds; locked decision requires per-agent |
| `ModelRetry` in output_validator | Raising `ValueError` | `ValueError` causes hard failure; `ModelRetry` triggers pydantic-ai's "re-ask" loop respecting `output_retries` |

**Installation:** Already in `requirements.txt`. No new packages needed.

## Architecture Patterns

### Recommended Project Structure

```
backend-hormonia/app/ai/
├── agents/                     # NEW -- Phase 11 creates this
│   ├── __init__.py             # exports PIISafeAgent, AIDeps, all 4 agents
│   ├── deps.py                 # AIDeps dataclass
│   ├── base.py                 # PIISafeAgent base class + run() wrapper
│   ├── sentiment_agent.py      # SentimentAgent + SentimentResult
│   ├── humanize_agent.py       # HumanizeAgent
│   ├── variation_agent.py      # VariationAgent
│   └── empathy_agent.py        # EmpathyAgent
├── client.py                   # UNCHANGED -- GeminiClient
├── client_domain.py            # MODIFIED in 11-04 -- add AI_FRAMEWORK shim
├── pii_redaction.py            # UNCHANGED -- used by PIISafeAgent
├── langgraph/                  # UNCHANGED -- still used by legacy path
└── models.py                   # UNCHANGED
```

### Pattern 1: AIDeps dataclass

**What:** A dataclass that carries the Gemini API key and model name into every agent invocation via pydantic-ai's dependency injection.
**When to use:** All 4 agents inherit from PIISafeAgent which requires AIDeps.
**Example:**
```python
# backend-hormonia/app/ai/agents/deps.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class AIDeps:
    gemini_api_key: str
    model_name: str = "gemini-2.0-flash"
```

### Pattern 2: PIISafeAgent base class

**What:** Wraps `Agent.run()` to enforce PII redaction on input (mandatory) and scan output for leaked PII (LGPD belt-and-suspenders). Raises if sanitization itself errors -- never calls Gemini with unsanitized data.
**When to use:** All 4 domain agents inherit from this class and call `await self._safe_run(prompt, deps)` instead of `await self.agent.run(prompt, ...)`.
**Example:**
```python
# backend-hormonia/app/ai/agents/base.py
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, TypeVar

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.google import GoogleModel

from app.ai.pii_redaction import sanitize_prompt_text_for_external_ai, sanitize_for_logging

logger = logging.getLogger(__name__)
OutputT = TypeVar("OutputT")


class PIISafeAgent:
    """
    LGPD-compliant agent wrapper.

    All 4 AI operations MUST inherit from this class.
    Direct agent.run() calls outside this wrapper are blocked by CI lint rule.
    """

    _agent: Agent  # set by subclass

    async def _safe_run(
        self,
        prompt: str,
        deps: Any,
        *,
        operation: str,
    ) -> Any:
        # 1. PII redaction - hard block if it fails
        try:
            safe_prompt = sanitize_prompt_text_for_external_ai(prompt)
        except Exception as exc:
            raise RuntimeError(
                f"PII sanitization failed for {operation} -- blocking Gemini call"
            ) from exc

        # 2. Build model at runtime from deps
        model = GoogleModel(
            deps.model_name,
            provider=GoogleProvider(api_key=deps.gemini_api_key),
        )

        # 3. Run with structured logging
        input_hash = hashlib.sha256(safe_prompt.encode()).hexdigest()[:12]
        start = time.monotonic()
        logger.info(
            "Agent call started",
            extra={
                "operation": operation,
                "input_hash": input_hash,
                "retry_count": 0,
            },
        )
        try:
            result = await self._agent.run(safe_prompt, model=model, deps=deps)
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "Agent call failed",
                extra={
                    "operation": operation,
                    "input_hash": input_hash,
                    "latency_ms": round(elapsed * 1000),
                    "error_type": type(exc).__name__,
                },
            )
            raise

        elapsed = time.monotonic() - start
        logger.info(
            "Agent call completed",
            extra={
                "operation": operation,
                "input_hash": input_hash,
                "latency_ms": round(elapsed * 1000),
                "success": True,
            },
        )
        return result.output
```

### Pattern 3: SentimentAgent with PromptedOutput

**What:** Typed agent that returns a fully-populated SentimentResult Pydantic model using PromptedOutput (JSON schema injected into system prompt -- avoids Gemini tool-calling conflict).
**When to use:** Plan 11-02.
**Example:**
```python
# backend-hormonia/app/ai/agents/sentiment_agent.py
from __future__ import annotations

from typing import List
from pydantic import BaseModel, field_validator
from pydantic_ai import Agent, RunContext, ModelRetry, PromptedOutput, ModelSettings

from app.ai.agents.base import PIISafeAgent
from app.ai.agents.deps import AIDeps
from app.services.ai.guardrails import _BANNED_PATTERNS, _PROMPT_LEAK_MARKERS

import re


class SentimentResult(BaseModel):
    sentiment: str = "neutral"
    confidence: float = 0.5
    emotional_indicators: List[str] = []
    medical_concerns: List[str] = []
    requires_attention: bool = False
    key_themes: List[str] = []
    suggested_follow_up: str = "standard"

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment_value(cls, v: str) -> str:
        allowed = {"positive", "negative", "neutral", "concerning"}
        v = v.strip().lower() if isinstance(v, str) else "neutral"
        return v if v in allowed else "neutral"

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v) if v is not None else 0.5))


_sentiment_agent = Agent(
    model=None,
    output_type=PromptedOutput(SentimentResult),
    deps_type=AIDeps,
    retries=1,
    output_retries=1,
    model_settings=ModelSettings(timeout=30.0),
    defer_model_check=True,
)


@_sentiment_agent.output_validator
def validate_sentiment_output(
    ctx: RunContext[AIDeps], result: SentimentResult
) -> SentimentResult:
    # Guardrail: banned patterns cannot appear in suggested_follow_up or key_themes
    for pattern in _BANNED_PATTERNS:
        for field_val in [result.suggested_follow_up] + result.key_themes:
            if re.search(pattern, str(field_val)):
                raise ModelRetry("Output contains banned pattern -- regenerate")
    # Guardrail: prompt leak markers
    for marker in _PROMPT_LEAK_MARKERS:
        if marker in result.suggested_follow_up:
            raise ModelRetry("Prompt echo detected in sentiment output")
    return result


class SentimentAgent(PIISafeAgent):
    _agent = _sentiment_agent

    async def analyze(self, response: str, context_snapshot: dict, deps: AIDeps) -> SentimentResult:
        from app.ai.langgraph.prompts import build_sentiment_prompt
        prompt = build_sentiment_prompt(response=response, context_snapshot=context_snapshot)
        return await self._safe_run(prompt, deps, operation="sentiment")
```

### Pattern 4: Message agents (HumanizeAgent, VariationAgent, EmpathyAgent)

**What:** Text-output agents using `output_type=str` with `@output_validator` decorators that reuse existing `_BANNED_PATTERNS`, `_PROMPT_LEAK_MARKERS`, and length bounds from `guardrails.py`.
**When to use:** Plan 11-03.
**Example (HumanizeAgent snippet):**
```python
_humanize_agent = Agent(
    model=None,
    output_type=str,
    deps_type=AIDeps,
    retries=1,
    output_retries=1,
    model_settings=ModelSettings(timeout=30.0),
    defer_model_check=True,
)

@_humanize_agent.output_validator
def validate_humanize_output(ctx: RunContext[AIDeps], result: str) -> str:
    text = (result or "").strip()
    # Length bounds (MESSAGE_HUMANIZED profile: min=6, max=1800)
    if len(text) < 6:
        raise ModelRetry("Output too short -- regenerate")
    if len(text) > 1800:
        raise ModelRetry("Output too long -- regenerate")
    # Banned patterns
    for pattern in _BANNED_PATTERNS:
        if re.search(pattern, text):
            raise ModelRetry("Banned pattern in output -- regenerate")
    # Prompt leak markers
    for marker in _PROMPT_LEAK_MARKERS:
        if marker in text:
            raise ModelRetry("Prompt echo detected -- regenerate")
    # Brazilian Portuguese ending punctuation
    if not re.search(r"[.!?…][\"')\]]*$", text.rstrip()):
        # Attempt self-repair before retry
        text = text.rstrip() + "."
    return text
```

### Pattern 5: GeminiDomainClient shim (Plan 11-04)

**What:** `GeminiDomainClient` gains an internal helper `_use_pydantic_agents()` that reads `settings.AI_FRAMEWORK` and each of the 4 public methods delegates based on the flag.
**When to use:** Plan 11-04. Zero changes to callers (flow_core.py, flow_service.py, enhanced_flow_engine.py).
**Example:**
```python
# Inside GeminiDomainClient (client_domain.py)
from app.config import settings

def _use_pydantic_agents(self) -> bool:
    ai_framework = getattr(settings, "AI_FRAMEWORK", "legacy")
    if ai_framework != "pydantic-ai":
        logger.info("AI_FRAMEWORK=legacy -- using GeminiClient.generate_content() path")
        return False
    return True

async def analyze_response_sentiment(self, response, patient_context, strict=False):
    if self._use_pydantic_agents():
        from app.ai.agents.sentiment_agent import SentimentAgent
        from app.ai.agents.deps import AIDeps
        deps = AIDeps(gemini_api_key=self.api_key, model_name=self.model_name)
        result = await SentimentAgent().analyze(response, compact_patient_context(patient_context), deps)
        return result.model_dump()
    # ... existing legacy code unchanged below ...
```

### Anti-Patterns to Avoid

- **Direct `agent.run()` outside PIISafeAgent:** Bypasses mandatory PII redaction; blocked by CI lint rule (Plan 11-01).
- **Shared `@output_validator` in base class:** Cannot accommodate per-agent length thresholds (SentimentResult has different bounds than HumanizeAgent output); locked decision requires per-agent decorators.
- **`NativeOutput(SentimentResult)` instead of `PromptedOutput`:** NativeOutput uses tool-calling mode; Gemini cannot use tool-calling and native structured output simultaneously -- documented in STATE.md.
- **Raising `ValueError` in output_validator instead of `ModelRetry`:** ValueError causes immediate hard fail; ModelRetry causes pydantic-ai to re-send with a correction hint (the built-in "validation retry" behavior from CONTEXT.md). Use `ModelRetry` for guardrail failures; only raise hard exceptions for truly unrecoverable cases.
- **Setting model at Agent construction time:** Model must be set at runtime via `model=` parameter to `agent.run()` because the API key lives in `AIDeps` (per-request injection). Use `defer_model_check=True` when constructing.
- **Checking `result.data` instead of `result.output`:** In pydantic-ai 1.63.0, `AgentRunResult.output` is the typed accessor (not `.data` or `.result`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema injection for structured output | Custom prompt formatter that serializes Pydantic schema | `PromptedOutput(SentimentResult)` | pydantic-ai auto-injects the schema into the system prompt and handles parsing/retry |
| Re-ask on bad output | Custom retry loop with message_history manipulation | `output_retries=1` on Agent + `ModelRetry` in output_validator | pydantic-ai sends the validation error message back to Gemini as a correction prompt |
| Timeout per agent call | `asyncio.wait_for()` wrapper | `model_settings=ModelSettings(timeout=30.0)` | pydantic-ai delegates timeout to the HTTP client layer; no manual wrapping needed |
| API key per-request injection | Custom model factory | `model=GoogleModel(..., provider=GoogleProvider(api_key=...))` passed to `agent.run()` | GoogleProvider accepts api_key at construction; swap model on each run |
| Output type normalization for SentimentResult | Custom dict normalizer | Pydantic field validators + `field_default` | Pydantic fills missing fields with defaults; no KeyError possible |

**Key insight:** pydantic-ai handles the hard parts (JSON schema injection, structured re-ask, timeout propagation). The only custom code needed is guardrail validators and PII wrapping.

## Common Pitfalls

### Pitfall 1: `result_validator` vs `output_validator` naming confusion

**What goes wrong:** Code uses `@agent.result_validator` (old name) -- AttributeError at registration time.
**Why it happens:** pydantic-ai renamed `result_validator` to `output_validator` in a recent version. Live inspection confirms 1.63.0 exposes `output_validator`, not `result_validator` (the `result_validator` attribute returns empty in inspection).
**How to avoid:** Always use `@agent.output_validator` in all 4 agent files.
**Warning signs:** `AttributeError: 'Agent' object has no attribute 'result_validator'` at module import.

### Pitfall 2: Missing `defer_model_check=True`

**What goes wrong:** Agent raises immediately at import time because `GOOGLE_API_KEY` is not set in the environment (agents are module-level singletons).
**Why it happens:** pydantic-ai resolves the model at `Agent()` construction time by default; without `defer_model_check=True`, it calls `GoogleProvider(api_key=None)` and errors.
**How to avoid:** All 4 agents must pass `defer_model_check=True` and `model=None` at construction; model is injected per-call via `GoogleModel(..., provider=GoogleProvider(api_key=deps.gemini_api_key))`.
**Warning signs:** `Set the GOOGLE_API_KEY environment variable` error at application startup or test collection.

### Pitfall 3: `ValueError` instead of `ModelRetry` in output_validator triggers hard failure

**What goes wrong:** A guardrail violation immediately propagates as an exception to the caller instead of triggering pydantic-ai's re-ask loop.
**Why it happens:** pydantic-ai only intercepts `ModelRetry` in `output_validator` to trigger a correction prompt. A plain `ValueError` or `GuardrailViolation` propagates up to the caller unchanged.
**How to avoid:** In `output_validator`, raise `ModelRetry("explanation")` for conditions where re-asking Gemini might fix the problem. Raise hard exceptions only for irrecoverable conditions (e.g., PII still present after redaction).
**Warning signs:** Guardrail violations causing hard failures on the first attempt despite `output_retries=1` being set.

### Pitfall 4: AI_FRAMEWORK setting missing from integrations.py

**What goes wrong:** `getattr(settings, "AI_FRAMEWORK", "legacy")` silently defaults to legacy forever -- shim never activates even when the env var is set.
**Why it happens:** Pydantic Settings only reads env vars that are declared as fields. An undeclared env var is silently ignored.
**How to avoid:** Plan 11-04 must add `AI_FRAMEWORK: str = Field(default="legacy", ...)` to `app/config/settings/integrations.py` and `AI_FRAMEWORK=legacy` to `.env.example`.
**Warning signs:** Setting `AI_FRAMEWORK=pydantic-ai` in Cloud Run env config has no effect.

### Pitfall 5: VariationAgent 88% overlap check in output_validator causes infinite ModelRetry

**What goes wrong:** The 88% overlap check (`_is_too_similar_to_recent`) rejects the output and raises `ModelRetry` -- but Gemini generates the same output again because the prompt doesn't include the "too similar" feedback.
**Why it happens:** ModelRetry sends the validation message back as a correction prompt, but if recent questions are not part of the prompt, Gemini cannot avoid them.
**How to avoid:** Build recent questions into the system prompt before calling the agent (already done in `build_question_variation_prompt()`). In the validator, fall back to `_build_non_repetitive_question()` (the deterministic wrapper from `nodes_ai.py`) instead of raising `ModelRetry` after first retry. This matches existing behavior in `generate_varied_question()`.
**Warning signs:** VariationAgent exhausting `output_retries=1` on every call when the patient has recent interaction history.

### Pitfall 6: Output PII scan (belt-and-suspenders) must not block valid responses

**What goes wrong:** Gemini legitimately echoes the word "Paciente" (the pseudonym) in the empathy response and the output PII scan flags it as a leak.
**Why it happens:** The scan treats any occurrence of name-like patterns as PII. "Paciente" is the approved pseudonym and is intentional.
**How to avoid:** Output PII scan should check for real PII patterns (CPF, phone, email, proper names) using the same `_PROMPT_EMAIL_PATTERN`, `_PROMPT_CPF_PATTERN`, `_PROMPT_PHONE_PATTERN` regexes from `pii_redaction.py` -- not the word "Paciente". Log a warning but do not block the response.

## Code Examples

Verified patterns from live API inspection (pydantic-ai 1.63.0):

### Confirmed: Agent construction with defer_model_check

```python
# Source: live .venv/lib/python3.12/site-packages/pydantic_ai/agent/__init__.py
from pydantic_ai import Agent, PromptedOutput, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

agent = Agent(
    model=None,
    output_type=PromptedOutput(SentimentResult),
    deps_type=AIDeps,
    retries=1,
    output_retries=1,
    model_settings=ModelSettings(timeout=30.0),
    defer_model_check=True,
)
```

### Confirmed: Runtime model injection pattern

```python
# Source: live API inspection
result = await agent.run(
    user_prompt,
    model=GoogleModel(deps.model_name, provider=GoogleProvider(api_key=deps.gemini_api_key)),
    deps=deps,
)
typed_output = result.output  # AgentRunResult.output is the typed accessor
```

### Confirmed: output_validator decorator

```python
# Source: live API inspection - Agent.output_validator signature confirmed
@agent.output_validator
def validate(ctx: RunContext[AIDeps], result: SentimentResult) -> SentimentResult:
    if result.confidence < 0.0:
        raise ModelRetry("confidence out of range")
    return result
```

### Confirmed: system_prompt decorator

```python
@agent.system_prompt
def build_system_prompt(ctx: RunContext[AIDeps]) -> str:
    return "Your system prompt here."
```

### Existing guardrail source to reconnect

```python
# Source: app/services/ai/guardrails.py (existing file, no modifications)
from app.services.ai.guardrails import (
    _BANNED_PATTERNS,        # list of compiled regex patterns
    _PROMPT_LEAK_MARKERS,    # list of str markers
)
# Existing length bounds per profile (from app/services/ai/output_profiles.py):
# MESSAGE_STANDARD:  min=3, max=1600
# MESSAGE_HUMANIZED: min=6, max=1800
# JSON_SENTIMENT:    min=10, max=2400
# Ending punctuation regex: r"[.!?…][\"')\]]*$"
```

### Existing prompt builders to reuse

```python
# Source: app/ai/langgraph/prompts.py (existing file, no modifications)
from app.ai.langgraph.prompts import (
    build_humanization_prompt,       # used by HumanizeAgent
    build_question_variation_prompt, # used by VariationAgent
    build_sentiment_prompt,          # used by SentimentAgent
    build_empathetic_prompt,         # used by EmpathyAgent
)
# All 4 already call sanitize_prompt_text_for_external_ai() internally
# PIISafeAgent adds a second pass for belt-and-suspenders
```

### CI lint rule for blocking direct .run() calls

```python
# Planned CI lint rule (to be added in Plan 11-01)
# Check: any .run() or .run_sync() or .run_stream() call on an Agent instance
# outside app/ai/agents/base.py is a violation
# Implementation: ruff custom rule or simple grep check in CI
# Pattern to block: re.search(r'_agent\.run\b|agent\.run\b', line)
# Exemption: app/ai/agents/base.py
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `result_validator` decorator | `output_validator` decorator | pydantic-ai ~1.x rename | Must use `output_validator` in all agent files |
| `.data` accessor on AgentRunResult | `.output` accessor | pydantic-ai 1.x | `result.output` is the typed result |
| Global `GOOGLE_API_KEY` env var | Per-call `GoogleProvider(api_key=...)` | pydantic-ai 1.x | Allows runtime key injection from AIDeps |
| `NativeOutput` for Gemini structured output | `PromptedOutput` for Gemini | Confirmed in STATE.md | Gemini cannot use tool-calling + native structured output simultaneously |

**Deprecated/outdated:**
- `Agent.result_validator`: renamed to `output_validator` in current version. The attribute still exists but returns a no-op wrapper (do not use).
- Setting model at Agent construction time: requires global API key; incompatible with per-request key injection pattern.

## Open Questions

1. **Output PII scan on empathy/humanize text outputs**
   - What we know: `sanitize_prompt_text_for_external_ai()` is designed for prompts (input), not for free-text outputs. It may over-redact legitimate content.
   - What's unclear: Whether a lighter-weight regex scan (CPF, phone, email only) is sufficient for output scanning without false positives.
   - Recommendation: Claude's discretion. Apply `_PROMPT_CPF_PATTERN`, `_PROMPT_PHONE_PATTERN`, `_PROMPT_EMAIL_PATTERN` (the three concrete PII regexes) to the output text as a warning-only log. Do not block valid empathy messages.

2. **Retry backoff strategy for Gemini timeout**
   - What we know: `retries=1` on Agent means pydantic-ai retries the model call once on transport error. `output_retries=1` means one re-ask for bad output.
   - What's unclear: Whether a 1-second fixed delay or exponential backoff is needed between the model retry.
   - Recommendation: Claude's discretion. pydantic-ai's `retries` parameter handles the retry internally; for the transport retry, pydantic-ai uses the httpx client default. The 30-second timeout from `ModelSettings(timeout=30.0)` is the primary protection.

3. **Regression test scope for 50 scenarios**
   - What we know: AGENT-08 requires comparing old GeminiClient vs new agent outputs on 50 scenarios.
   - What's unclear: Whether scenarios can use recorded fixtures (no live Gemini calls) or require live calls.
   - Recommendation: Use pytest fixtures with mocked Gemini responses captured from old GeminiClient. The comparison is structural (all 7 SentimentResult fields populated, guardrails pass) not semantic (exact text match). This avoids CI flakiness from non-deterministic Gemini outputs.

## Validation Architecture

> `workflow.nyquist_validation` is not set in `.planning/config.json` -- Validation Architecture section skipped per instructions.

## Sources

### Primary (HIGH confidence)

- Live pydantic-ai 1.63.0 inspection via `.venv/bin/python` -- `Agent.__init__` signature, `output_validator`, `PromptedOutput`, `AgentRunResult.output`, `ModelRetry`, `ModelSettings.timeout`, `GoogleProvider`, `GoogleModel` all confirmed
- `backend-hormonia/app/services/ai/guardrails.py` -- `_BANNED_PATTERNS`, `_PROMPT_LEAK_MARKERS`, `_PLACEHOLDER_PATTERNS`, `_ENDING_PUNCTUATION_PATTERN` source of truth
- `backend-hormonia/app/services/ai/output_profiles.py` -- length bounds per operation type
- `backend-hormonia/app/ai/langgraph/prompts.py` -- all 4 prompt builders confirmed to exist and call `sanitize_prompt_text_for_external_ai()` internally
- `backend-hormonia/app/ai/pii_redaction.py` -- `sanitize_prompt_text_for_external_ai()` is a pure function, no modifications needed
- `backend-hormonia/app/schemas/ai_schemas.py` -- existing `SentimentAnalysisResult` has all 7 fields with Pydantic defaults (no KeyError possible)
- `backend-hormonia/app/config/settings/integrations.py` -- `AI_FRAMEWORK` not yet present, must be added in Plan 11-04
- `backend-hormonia/pyproject.toml` -- pytest configured with `asyncio_mode=auto`, test path `tests/`
- `backend-hormonia/app/ai/langgraph/nodes_ai.py` -- `_is_too_similar_to_recent()` 88% threshold and `_build_non_repetitive_question()` fallback both present

### Secondary (MEDIUM confidence)

- `backend-hormonia/.planning/STATE.md` -- PromptedOutput rationale (Gemini tool-calling conflict), pydantic-ai pin rationale (<2.0.0)
- `backend-hormonia/tests/unit/test_gemini_client_pii_redaction.py` -- established test pattern for AI unit tests (mock model stub, monkeypatch, no live Gemini calls)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pydantic-ai 1.63.0 live-inspected; all key classes confirmed
- Architecture: HIGH -- all source files read; existing code paths confirmed; new module structure follows codebase conventions
- Pitfalls: HIGH for pitfalls 1-4 (confirmed by live inspection); MEDIUM for pitfalls 5-6 (based on code analysis of existing guard logic)

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (pydantic-ai is stable at 1.63.0; pinned <2.0.0)
