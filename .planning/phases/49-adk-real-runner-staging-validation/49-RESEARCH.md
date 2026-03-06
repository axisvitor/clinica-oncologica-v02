# Phase 49: ADK Real Runner & Staging Validation - Research

**Researched:** 2026-03-06
**Domain:** google-adk real runner validation, staging environment testing, verification artifact updates
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADK-11 | Operador pode bloquear chamadas de tool inseguras via validacao `before_tool_callback` antes de efeitos colaterais. | Phase 45 implemented the full `before_tool_callback` chain with immutable operator policy keys (`_PROTECTED_POLICY_KEYS`). Local tests pass with mocked runner. The remaining gap is exercising the real `google.adk.agents.Agent` constructor with `before_tool_callback` and confirming that the callback's dict return actually short-circuits tool execution in the real ADK runner. |
| ADK-12 | Operador pode classificar falhas ADK em classes deterministicas (`timeout`, `policy_block`, `tool_error`, `upstream_error`). | Phase 45 implemented deterministic classification at the `_classify_execution_failure` boundary. Local tests prove the classification with fake runner/agent stubs. The remaining gap is forcing a real ADK `Runner.run_async()` bootstrap/execution failure and confirming the result is `upstream_error` with no fallback to direct-handler execution. |
</phase_requirements>

## Summary

Phase 49 is the final gap-closure phase for milestone v1.8. It exists because Phase 45 verification (`45-VERIFICATION.md`) concluded with `human_needed` status: all local evidence passes, but the real `google-adk` runner path was never exercised because the package is not installed in the local development environment. Additionally, the Phase 44 validation document lists a manual multi-instance cancel check that requires a staging-like topology to prove.

The core challenge is NOT writing new production code. The `before_tool_callback`, deterministic error classification, and multi-instance cancel infrastructure already exist and are tested with mocked runners. Phase 49 must instead:

1. Create automated integration tests that can run with the real `google-adk` package installed (these tests are already partially scaffolded in `test_adk_runner_integration.py` with `@pytest.mark.skipif(not HAS_ADK, ...)`).
2. Define a reproducible staging validation procedure that can be run in the CI `smoke-adk` job (which already installs `google-adk` via `requirements.txt`) or in a Docker container matching the staging Dockerfile.
3. Update `45-VERIFICATION.md` from `human_needed` to `passed` once the evidence is captured.

The key insight is that the CI `smoke-adk` job already installs `google-adk` from `requirements.txt` (line 44: `google-adk>=1.26.0,<2.0.0`) and the staging Dockerfile (`python:3.13-slim` + `pip install -r requirements.txt`) also installs it. The gap is not infrastructure -- it is that the existing `test_adk_runner_integration.py` tests are skipped locally and no CI job currently targets them with the `google-adk` package present.

**Primary recommendation:** Write additional integration tests exercising the three success criteria (policy_block with real runner, upstream_error with real runner, multi-instance cancel), mark them with a new or existing pytest marker, and ensure they run in the CI `smoke-adk` job where `google-adk` is installed. Then capture the evidence and update verification artifacts.

## Standard Stack

### Core

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| google-adk | >=1.26.0,<2.0.0 | Real ADK Runner, Agent, InMemorySessionService, FunctionTool | Already in requirements.txt; the staging and CI environments install it |
| pytest | >=8.1.0 | Test framework for integration tests | Already configured in pyproject.toml |
| pytest-asyncio | >=0.23.0 | Async test support | Already configured with `asyncio_mode = "auto"` |
| python:3.13-slim | Docker base | Staging environment matching production | Already in Dockerfile |

### Supporting

| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| fakeredis | >=2.20.0 | In-memory Redis for session store in integration tests | When tests need ADKSessionStore without a real Redis instance |
| monkeypatch | pytest built-in | Inject fake GeminiDomainClient so tests do not hit real Gemini API | Every integration test must avoid real LLM calls |

### Alternatives Considered

None -- this phase operates entirely within established infrastructure.

## Architecture Patterns

### Pattern 1: Conditional Integration Tests with Real ADK

**What:** Tests guarded by `@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")` that exercise the real `Agent`, `Runner`, `InMemorySessionService`, and `FunctionTool` classes.

**When to use:** Always for Phase 49 tests. These tests skip harmlessly in local environments without google-adk and activate automatically in CI/staging.

**Current implementation pattern** (from `test_adk_runner_integration.py`):
```python
try:
    import google.adk  # noqa: F401
    HAS_ADK = True
except ModuleNotFoundError:
    HAS_ADK = False

@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_exercises_runner_path_with_domain_client(monkeypatch):
    # monkeypatch GeminiDomainClient to avoid real LLM calls
    # exercise run_adk_tool() which creates real Agent + Runner
    ...
```

**Critical:** Tests MUST monkeypatch `GeminiDomainClient` to avoid real Gemini API calls. The ADK `Agent` will still call real `Runner.run_async()`, which will invoke the real `before_tool_callback` and attempt to call the real `FunctionTool`. The monkeypatched domain client intercepts at the tool handler level.

### Pattern 2: Policy Block Through Real Runner Callback Chain

**What:** Send a request with `tool_policy={"blocked_tools": {"sentiment": "blocked_for_test"}}` through `run_adk_tool()` when `HAS_ADK_RUNTIME` is True. The real `Agent(before_tool_callback=...)` must invoke the callback, which returns a dict (the policy block payload), and the real `Runner` must short-circuit tool execution.

**When to use:** ADK-11 validation.

**Why this works:** The ADK documentation confirms that when `before_tool_callback` returns a non-None dict, the framework "skips the execution of the actual tool function" and uses the returned dict as the tool result. The existing `_build_before_tool_callback(request)` in `runtime.py` returns a structured `{"status": "policy_block", ...}` dict when the policy check triggers. The real Runner should honor this return value.

**Risk:** The ADK Runner may wrap or transform the callback return value before surfacing it in events. The `_extract_runner_output` function handles various event shapes (dict with "result", Content with parts, etc.). If the policy block dict is wrapped unexpectedly, the test will reveal this.

### Pattern 3: Upstream Error Through Real Runner Failure

**What:** Force the real Runner to fail after instantiation (e.g., by monkeypatching `Runner.run_async` to raise, or by providing an invalid model name that causes a bootstrap failure). The `_execute_with_adk_runner` function catches non-`ADKToolExecutionError` exceptions and wraps them as `ADKUpstreamExecutionError`, which `_classify_execution_failure` maps to `upstream_error`.

**When to use:** ADK-12 validation.

**Key insight:** The `_execute_with_adk_runner` function already has a `try/except` that distinguishes `ADKToolExecutionError` (re-raised as-is, classified as `tool_error`) from other exceptions (wrapped as `ADKUpstreamExecutionError`, classified as `upstream_error`). A real Runner failure that occurs during `run_async()` will be a non-tool exception and should map to `upstream_error`.

### Pattern 4: Multi-Instance Cancel Confirmation

**What:** Start a long-running invocation, then issue a cancel request. Confirm the invocation terminates with `cancelled` status and no late output.

**Why this is staging-relevant:** In production, two separate API requests (start and cancel) may hit different Cloud Run instances. The cancel must reach the correct invocation via the shared ADKSessionStore (Redis-backed). In a single-process test, this is simulated by running the invocation as an asyncio task and issuing the cancel from the test coroutine.

**Local test limitation:** A single-process test can prove the cancellation mechanics (and Phase 44 already did this) but cannot prove cross-instance routing. For Phase 49, the goal is to capture evidence that the cancel path works with the real ADK runner active (not just the direct-handler fallback).

### Anti-Patterns to Avoid

- **Do NOT make real Gemini API calls in tests.** Always monkeypatch `GeminiDomainClient`. The tests validate the ADK framework plumbing, not the LLM.
- **Do NOT write new production code.** Phase 49 is a validation phase. If tests reveal a bug, document it as a finding -- do not fix it in this phase without explicit scope expansion.
- **Do NOT remove the `skipif(not HAS_ADK)` guards.** These must remain so local development without google-adk continues to work.
- **Do NOT change existing test behavior.** Phase 49 tests are additive.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ADK agent/runner instantiation | Custom agent framework | `google.adk.agents.Agent` + `google.adk.runners.Runner` | The goal is to validate the real ADK classes, not replacements |
| Session service for runner tests | Custom session backend | `google.adk.sessions.InMemorySessionService` | Real ADK InMemorySessionService exercises the exact code path that staging uses |
| Redis for session store in tests | Real Redis connection | `fakeredis` or memory fallback (already built into ADKSessionStore) | ADKSessionStore falls back to process-local memory when Redis is unavailable |
| Verification artifact format | New template | Copy structure from `45-VERIFICATION.md` | Established project format |

## Common Pitfalls

### Pitfall 1: Real Runner Wraps Callback Return in Unexpected Event Shape

**What goes wrong:** The `before_tool_callback` returns `{"status": "policy_block", "result": {...}}` but the real Runner wraps this in a `Content` object or nested event structure that `_extract_runner_output` does not recognize.
**Why it happens:** The ADK documentation says returning a dict skips tool execution, but does not specify the exact event shape that surfaces in `Runner.run_async()` output.
**How to avoid:** The integration test must assert the FINAL `run_adk_tool()` output (not intermediate events) has `status == "policy_block"`. If the Runner wraps the callback return, `_execute_with_adk_runner` will process it through `_extract_runner_output` and `_normalize_result`. The test should check the normalized output.
**Warning signs:** Test returns `upstream_error` instead of `policy_block` -- this means the callback return was lost or misinterpreted.

### Pitfall 2: ADK Runner Requires Real Gemini API Key

**What goes wrong:** The real `Runner.run_async()` attempts to call the Gemini API even though the tool is blocked by the callback.
**Why it happens:** The ADK Runner may validate the model connection before invoking tools.
**How to avoid:** Provide a fake but structurally valid API key (e.g., `"fake-key-for-integration-test"`). If the Runner validates the key before reaching the callback, monkeypatch the model initialization. The existing tests in `test_adk_runner_integration.py` already use `gemini_api_key="fake-key"` -- check if this works with the real ADK.
**Warning signs:** Test fails with an authentication error before any tool callback fires.

### Pitfall 3: ADK Version Mismatch Between CI and Staging

**What goes wrong:** The CI `smoke-adk` job and the staging Dockerfile resolve different google-adk versions, leading to different behavior.
**Why it happens:** The version pin `>=1.26.0,<2.0.0` allows a wide range. pip resolution can select different versions depending on the resolver state.
**How to avoid:** Log the installed google-adk version in the test output (`google.adk.__version__` or `pip show google-adk`). If validation passes in CI, check the staging version matches.
**Warning signs:** Tests pass in CI but staging behavior differs.

### Pitfall 4: Updating 45-VERIFICATION.md Prematurely

**What goes wrong:** The verification artifact is updated to `passed` before all evidence is captured and validated.
**Why it happens:** Eagerness to close the phase.
**How to avoid:** Write tests first, capture evidence, THEN update 45-VERIFICATION.md with the evidence referenced. The update should include specific test names, pytest output, and file:line references.
**Warning signs:** 45-VERIFICATION.md says `passed` but references no new evidence.

### Pitfall 5: WHATSAPP_WUZAPI_TOKEN Not Set in Test Environment

**What goes wrong:** Backend settings bootstrap fails because `WHATSAPP_WUZAPI_TOKEN` is unset.
**Why it happens:** The test environment does not set all required env vars.
**How to avoid:** Set `WHATSAPP_WUZAPI_TOKEN=test-token` in the test command, as already done in the CI `smoke-adk` job (line 260 of `ci.yml`).

## Code Examples

### Existing Real-Runner Integration Test Pattern

Source: `backend-hormonia/tests/unit/test_adk_runner_integration.py:29-55`
```python
@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_exercises_runner_path_with_domain_client(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls.append((response, patient_context))
            return {"sentiment": "neutral"}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="paciente relata melhora",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="fake-key", model_name="gemini-2.0-flash"),
            user_id="integration-user",
            session_id="integration-session",
            session=ADKSessionControls(action="create", session_id="integration-session"),
            context={"patient_context": {"cycle": "Q1"}},
        )
    )

    assert result["status"] == "success"
    assert "result" in result
    assert calls, "Domain client was not called through ADK runtime path"
```

### ADK before_tool_callback Signature

Source: [google/adk-python LlmAgent](https://github.com/google/adk-python/blob/main/src/google/adk/agents/llm_agent.py)
```python
# Callback type alias:
_SingleBeforeToolCallback = Callable[
    [BaseTool, dict[str, Any], ToolContext],
    Union[Awaitable[Optional[dict]], Optional[dict]],
]

# Agent constructor:
Agent(
    name="...",
    model="...",
    tools=[function_tool],
    instruction="...",
    before_tool_callback=my_callback,  # receives (tool, args, tool_context)
)
```

Return `None` to proceed with tool execution. Return a `dict` to skip tool execution and use the dict as the tool result.

### Existing Runner Path in runtime.py

Source: `backend-hormonia/app/ai/adk/runtime.py:1183-1234`
```python
async def _execute_with_adk_runner(*, request, function_tool):
    context_token = set_adk_tool_context(deps=request.deps, context=request.context)
    try:
        agent = Agent(
            name=f"hormonia-adk-{request.tool_name}",
            model=request.deps.model_name or "gemini-2.0-flash",
            tools=[function_tool],
            instruction="Use the available tool to process the prompt and return the result.",
            before_tool_callback=_build_before_tool_callback(request),
        )
        executor = Runner(app_name="hormonia-adk", agent=agent, session_service=InMemorySessionService())
        # ... run_async and extract output ...
    except ADKToolExecutionError:
        raise
    except Exception as exc:
        raise ADKUpstreamExecutionError(str(exc) or "ADK runner execution failed") from exc
    finally:
        reset_adk_tool_context(context_token)
```

### Deterministic Error Classification

Source: `backend-hormonia/app/ai/adk/runtime.py:649-674`
```python
def _classify_execution_failure(exc, *, tool_name, invocation_id):
    if isinstance(exc, ADKToolExecutionError):
        status = "tool_error"
        message = str(exc) or f"{tool_name} tool execution failed"
    else:
        status = "upstream_error"
        message = str(exc) or "ADK upstream execution failed"
    # ... build result payload ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Runner tests skipped locally due to missing google-adk | Phase 49 validates in CI/staging where google-adk IS installed | Phase 49 | Closes `human_needed` gap |
| Multi-instance cancel tested only in single-process | Phase 49 validates cancel mechanics with real runner active | Phase 49 | Proves cancel works through real ADK execution path |
| 45-VERIFICATION.md stuck at `human_needed` | Phase 49 updates to `passed` with evidence | Phase 49 | Closes final v1.8 audit gap |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `backend-hormonia/pyproject.toml` |
| Quick run command | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q` |
| Full suite command | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADK-11 | Real runner blocks unsafe tool call via before_tool_callback and returns policy_block | integration (conditional) | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q -k "policy_block"` | Wave 0 |
| ADK-11 | Real runner policy_block produces no side effect (domain client never called) | integration (conditional) | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q -k "policy_block and no_side_effect"` | Wave 0 |
| ADK-11 | Repeated policy_block returns identical status | integration (conditional) | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q -k "policy_block and repeated"` | Wave 0 |
| ADK-12 | Real runner bootstrap/execution failure returns upstream_error | integration (conditional) | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q -k "upstream_error"` | Partial (existing test covers Runner failure) |
| ADK-12 | Real runner upstream_error has no fallback dispatch | integration (conditional) | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q -k "upstream_error and no_fallback"` | Wave 0 |
| ADK-09 | Cancel with real runner active terminates invocation | integration (conditional) | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q -k "cancel"` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q`
- **Per wave merge:** Full ADK suite (all 4 test files)
- **Phase gate:** Full suite green before verification update

### Wave 0 Gaps

- [ ] `tests/unit/test_adk_runner_integration.py` -- add policy_block test with real runner (ADK-11)
- [ ] `tests/unit/test_adk_runner_integration.py` -- add repeated policy_block determinism test (ADK-11)
- [ ] `tests/unit/test_adk_runner_integration.py` -- add no-fallback-dispatch assertion for upstream_error (ADK-12)
- [ ] `tests/unit/test_adk_runner_integration.py` -- add cancel-with-real-runner test (ADK-09)
- [ ] No new framework install needed -- google-adk is already in requirements.txt

## Open Questions

1. **Will the real ADK Runner honor before_tool_callback return dict without calling Gemini API?**
   - What we know: ADK docs say returning a dict skips tool execution. The existing success-path test (`test_run_adk_tool_exercises_runner_path_with_domain_client`) works with `fake-key`. The Runner DOES create a model reference but the callback fires before tool dispatch.
   - What's unclear: Whether the Runner validates the API key or makes a model call BEFORE reaching the tool callback (e.g., to generate the initial tool-call decision).
   - Recommendation: If the real Runner requires a valid API key before reaching the callback, monkeypatch the model initialization at the ADK level (e.g., `google.genai.Client` or similar). Document the finding.

2. **Does the CI `smoke-adk` job exercise `test_adk_runner_integration.py` tests?**
   - What we know: The `smoke-adk` job runs `pytest -m adk_smoke`. The integration tests in `test_adk_runner_integration.py` are NOT currently marked with `@pytest.mark.adk_smoke`.
   - What's unclear: Whether to add `adk_smoke` marker to integration tests or create a separate CI step.
   - Recommendation: Add the `adk_smoke` marker to the new Phase 49 integration tests so they run in the existing `smoke-adk` CI job. This avoids creating a new CI job and leverages the existing infrastructure where `google-adk` is already installed.

3. **How to prove multi-instance cancel in a single-process test?**
   - What we know: Phase 44 already tests cancel mechanics in single-process. The staging topology has multiple Cloud Run instances sharing Redis.
   - What's unclear: Whether single-process async cancel with real runner is sufficient evidence for the staging validation gap.
   - Recommendation: The single-process test with real ADK runner proves the cancel mechanics work through the real runner path. The cross-instance routing is a deployment infrastructure concern (Redis-backed session store), which is already proven by the existing session store tests. Document this reasoning in the verification artifact.

## Sources

### Primary (HIGH confidence)

- `backend-hormonia/app/ai/adk/runtime.py` -- Real runner path implementation (lines 570-600, 1183-1234)
- `backend-hormonia/app/ai/adk/tools.py` -- Tool handler and context merge implementation
- `backend-hormonia/app/ai/adk/wrapper.py` -- PIISafeADKWrapper boundary
- `backend-hormonia/tests/unit/test_adk_runner_integration.py` -- Existing conditional integration tests (3 tests)
- `.planning/phases/45-adk-tool-safety-and-deterministic-errors/45-VERIFICATION.md` -- `human_needed` status with specific remaining checks
- `.planning/phases/45-adk-tool-safety-and-deterministic-errors/45-VALIDATION.md` -- Manual verification instructions
- `.planning/phases/44-adk-runtime-controls/44-VALIDATION.md` -- Multi-instance cancel manual check
- `.planning/v1.8-MILESTONE-AUDIT.md` -- Gap analysis that created Phase 49
- `.github/workflows/ci.yml` (lines 220-268) -- `smoke-adk` CI job installs google-adk
- `backend-hormonia/requirements.txt` (line 44) -- `google-adk>=1.26.0,<2.0.0`
- `backend-hormonia/Dockerfile` -- Staging image installs full requirements.txt

### Secondary (MEDIUM confidence)

- [google/adk-python LlmAgent source](https://github.com/google/adk-python/blob/main/src/google/adk/agents/llm_agent.py) -- `before_tool_callback` signature: `Callable[[BaseTool, dict[str, Any], ToolContext], Union[Awaitable[Optional[dict]], Optional[dict]]]`
- [ADK Callbacks documentation](https://google.github.io/adk-docs/callbacks/) -- Returning a dict from before_tool_callback skips tool execution
- [PyPI google-adk](https://pypi.org/project/google-adk/) -- Version 1.26.0, Python 3.10-3.14 support

### Tertiary (LOW confidence)

None -- all findings derived from project artifacts and official ADK documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies; google-adk already in requirements.txt and CI
- Architecture: HIGH - Extends existing test patterns with no new production code
- Pitfalls: MEDIUM - The real Runner's behavior with callback returns is documented but not yet validated in this codebase; this is exactly what Phase 49 must prove
- Verification format: HIGH - Established project format used across multiple phases

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable -- google-adk pin prevents breaking changes)
