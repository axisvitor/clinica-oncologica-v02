---
phase: 04-ai-reliability
verified: 2026-02-22T21:30:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Deploy to staging with LangGraph intentionally removed from requirements.txt"
    expected: "Application fails at startup with RuntimeError mentioning LangGraph is not available in staging environment"
    why_human: "Cannot simulate real startup environment; grep confirms the check exists and is correctly placed, but actual startup sequence in production/staging requires real deployment to confirm RuntimeError propagates before traffic is accepted"
  - test: "Trigger a LangGraph graph to return None/empty during a real patient message flow"
    expected: "Sentry dashboard shows a FeatureNotAvailableError event with graph_name and operation context; patient receives unhumanized template message (not blank, not robotic error string)"
    why_human: "Cannot trigger real Sentry capture programmatically; the call path and try/except blocks are correctly wired but real Sentry event reception requires a running app"
---

# Phase 4: AI Reliability Verification Report

**Phase Goal:** Falhas de LangGraph e Gemini sao visiveis, explicitas e capturadas pelo Sentry — nenhuma falha silenciosa entrega mensagens roboticas a pacientes
**Verified:** 2026-02-22T21:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | If LangGraph is unavailable at startup, the application fails with a clear error instead of accepting traffic and producing non-humanized messages | VERIFIED | `_check_langgraph_available()` at `lifespan.py:214` raises `RuntimeError` in `("production", "prod", "staging")` environments; called at line 90, before `asyncio.gather()` at line 112 |
| 2 | When a LangGraph call returns `None`, the system raises explicit `FeatureNotAvailableError` captured by Sentry — no silent degradation delivering non-humanized templates | VERIFIED | `invoke_langgraph_graph()` in `_invoke.py` raises `FeatureNotAvailableError` on None/empty; both call sites in `enhanced_flow_engine.py` wrap it with `except FeatureNotAvailableError as exc: sentry_sdk.capture_exception(exc)` before fallback |
| 3 | `FeatureNotAvailableError` exists in the exception hierarchy as a subclass of `AIServiceError` | VERIFIED | `exceptions.py:730` — `class FeatureNotAvailableError(AIServiceError)` with `graph_name`, `operation`, `error_code="FEATURE_NOT_AVAILABLE"`, `is_recoverable=True` |
| 4 | The silent `{"sentiment": "neutral", "confidence": 0.5}` fallback is eliminated | VERIFIED | Zero occurrences of `confidence.*0.5` in `enhanced_flow_engine.py`; fallback now uses `confidence: 0.0` at line 549, signaling fallback (not real analysis) to downstream threshold checks |
| 5 | The humanization fallback raises `FeatureNotAvailableError` caught by caller with unhumanized message as final patient-visible fallback | VERIFIED | `enhanced_flow_engine.py:426-433` — `except FeatureNotAvailableError`: Sentry capture, then `personalized_message = message_template.base_content` (unhumanized but complete template) |

**Score:** 5/5 truths verified

### Required Artifacts (Plan 04-01)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend-hormonia/app/core/exceptions.py` | `FeatureNotAvailableError` exception class | VERIFIED | Class exists at line 730; subclass of `AIServiceError`; `graph_name` and `operation` instance attributes confirmed |
| `backend-hormonia/app/core/lifespan.py` | LangGraph startup health check | VERIFIED | `_check_langgraph_available()` function at line 214; called at line 90 before `asyncio.gather()` at line 112 |

### Required Artifacts (Plan 04-02)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend-hormonia/app/ai/langgraph/_invoke.py` | Centralized LangGraph invocation wrapper | VERIFIED | 63-line file; `invoke_langgraph_graph()` with `expect_dict` flag; raises `FeatureNotAvailableError` on bad output; deferred import of exception avoids circular imports |
| `backend-hormonia/app/ai/client_domain.py` | Uses wrapper instead of bare `ainvoke` | VERIFIED | 5 occurrences of `invoke_langgraph_graph` (1 import + 4 call sites); 0 remaining bare `graph.ainvoke()` calls at these sites |
| `backend-hormonia/app/services/enhanced_flow_engine.py` | Explicit `FeatureNotAvailableError` handling replacing silent fallbacks | VERIFIED | 3 occurrences of `invoke_langgraph_graph` (1 import + 2 calls); 2 `sentry_sdk.capture_exception` calls; imports `sentry_sdk`, `invoke_langgraph_graph`, `FeatureNotAvailableError` at module level |

### Key Link Verification

#### Plan 04-01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `lifespan.py` | `langgraph/graphs.py` | `from app.ai.langgraph.graphs import _LANGGRAPH_IMPORT_ERROR` | WIRED | Line 229 of `lifespan.py`; `_LANGGRAPH_IMPORT_ERROR` defined at module level in `graphs.py:11` as `Exception | None = None` (set to the ImportError if `langgraph` is not installed) |
| `lifespan.py` | `lifespan.py` (`_startup()`) | `_check_langgraph_available()` called before `asyncio.gather()` | WIRED | Called at line 90; `asyncio.gather()` first appears at line 112 — ordering confirmed |

#### Plan 04-02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_invoke.py` | `app/core/exceptions.py` | `from app.core.exceptions import FeatureNotAvailableError` | WIRED | Deferred import inside function body (line 42) — avoids circular import risk at module load time |
| `client_domain.py` | `langgraph/_invoke.py` | `from app.ai.langgraph._invoke import invoke_langgraph_graph` | WIRED | Line 11 of `client_domain.py`; 4 call sites confirmed (lines 71, 129, 166, 216) |
| `enhanced_flow_engine.py` | `langgraph/_invoke.py` | `from app.ai.langgraph._invoke import invoke_langgraph_graph` | WIRED | Line 36 of `enhanced_flow_engine.py`; 2 call sites at lines 419 and 534 |
| `enhanced_flow_engine.py` | `sentry_sdk` | `sentry_sdk.capture_exception` on `FeatureNotAvailableError` | WIRED | `import sentry_sdk` at line 34; `sentry_sdk.capture_exception(exc)` at lines 427 and 543 — before each fallback branch |

Additional verified: `langgraph/__init__.py` re-exports `invoke_langgraph_graph` via `from ._invoke import invoke_langgraph_graph  # noqa: F401`.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AI-01 | 04-01-PLAN.md | LangGraph startup health check que verifica disponibilidade na inicializacao da aplicacao | SATISFIED | `_check_langgraph_available()` in `lifespan.py` inspects `_LANGGRAPH_IMPORT_ERROR` sentinel; raises `RuntimeError` in production/staging; logs CRITICAL in dev/test; placed before `asyncio.gather()` so exception is not swallowed by `return_exceptions=True` |
| AI-02 | 04-02-PLAN.md | Converter fallbacks `None` de LangGraph para `FeatureNotAvailableError` explicito (sem silent degradation) | SATISFIED | `invoke_langgraph_graph()` wrapper centralizes None validation; all 6 call sites (4 in `client_domain.py`, 2 in `enhanced_flow_engine.py`) use it; silent `confidence: 0.5` fallback eliminated; Sentry captures both failure paths |

No orphaned requirements found. Both AI-01 and AI-02 are the only requirements mapped to Phase 4 in REQUIREMENTS.md (lines 26-27, 102-103).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `lifespan.py` | 596 | `"Evolution API key placeholder detected"` | Info | Pre-existing string in `_initialize_evolution_api()` detecting placeholder config values — not introduced by Phase 4, not related to AI reliability |

No blockers or warnings introduced by Phase 4 changes. The single Info-level finding is pre-existing and unrelated.

### Scope Check: Remaining `ainvoke` Call

One `ainvoke` call remains at `backend-hormonia/app/ai/client.py:400`: `self.model.ainvoke(messages)`. This is `LangChain's ChatGoogleGenerativeAI.ainvoke()` (the Gemini model client, not a LangGraph compiled graph). It is outside the scope of AI-02, which targets LangGraph graph calls. This call is the LLM invocation layer that LangGraph nodes themselves use internally.

### Human Verification Required

#### 1. LangGraph Startup Fail-Fast in Real Staging Environment

**Test:** Deploy to staging with `langgraph` removed from `requirements.txt`
**Expected:** Application fails at startup with `RuntimeError: LangGraph is not available in staging environment` before any HTTP request is served
**Why human:** The startup check (`_check_langgraph_available()` at `lifespan.py:90`) and its placement before `asyncio.gather()` are confirmed in code, but the actual propagation of `RuntimeError` through the FastAPI/uvicorn startup sequence requires a real deployment to confirm no outer handler silently absorbs it

#### 2. Sentry Event Reception on Real LangGraph Failure

**Test:** Trigger a graph invocation that returns `None` (e.g., mock the graph or disable LangGraph mid-run in a staging patient flow)
**Expected:** Sentry dashboard shows `FeatureNotAvailableError` with `graph_name` and `operation` context; patient receives the unhumanized `base_content` template (not blank, not an error string)
**Why human:** The `sentry_sdk.capture_exception()` call path is confirmed wired in code, but actual Sentry event ingestion requires a running app with a valid Sentry DSN and a real error trigger

### Gaps Summary

No gaps. All 5 observable truths verified, all 5 artifacts pass all three levels (exists, substantive, wired), all 4 key links in Plan 04-01 and Plan 04-02 are confirmed wired. Both AI-01 and AI-02 requirements are satisfied with evidence directly in the codebase.

The two human verification items are operational confirmation of correct code behavior — the code structure fully supports both outcomes.

---

_Verified: 2026-02-22T21:30:00Z_
_Verifier: Claude (gsd-verifier)_
