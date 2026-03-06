# Phase 44: ADK Runtime Controls - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Allow operators to control ADK execution at `/api/v2/adk/run` with per-invocation runtime limits (`max_llm_calls`, timeout, cancellation) and explicit ADK session lifecycle (`create/resume/close`) with bounded state growth. Tool safety, broader error taxonomy, observability, and CI smoke gates remain in later phases.

</domain>

<decisions>
## Implementation Decisions

### Session lifecycle
- New session is auto-created when `session_id` is omitted; the response returns the generated session id.
- Resume is valid only within the same `tool_name`; sessions do not cross tool contexts.
- Sessions can be closed explicitly and also expire after inactivity to prevent uncontrolled accumulation.
- Closed sessions are terminal; reusing a closed `session_id` is rejected instead of reopening or silently replacing it.

### Invocation limits
- `/api/v2/adk/run` exposes runtime controls as optional per-request overrides on top of safe server defaults.
- `max_llm_calls` uses a conservative default when the operator does not provide one.
- Hitting the LLM call budget stops execution immediately and returns an explicit limit-hit failure.
- Timeout also has a safe default with optional override; exceeding it returns an explicit timeout failure.

### Cancellation behavior
- Cancellation is an explicit operator action, not an implicit side effect of client disconnect alone.
- The operator receives explicit confirmation that the execution was cancelled and will not continue processing.
- If a result arrives after cancellation is requested, cancellation wins and the late result is discarded.
- Cancelling a turn does not close the session; the session remains valid for retry/resume without partial output from the cancelled turn.

### State growth policy
- Resumable session state keeps recent relevant turns plus structured clinical context, not unbounded raw history.
- When state nears the configured limit, the oldest low-priority context is pruned first.
- Structured clinical context and the most recent successful turn have highest retention priority.
- If resume would still exceed the configured limit after pruning, resume is blocked and the operator must start a fresh session.

### Claude's Discretion
- Exact field names and payload shape for runtime/session controls, as long as `/api/v2/adk/run` remains the canonical thin entrypoint.
- Exact default numeric values for `max_llm_calls`, timeout, inactivity expiry, and state-size budget.
- Internal strategy for measuring state growth (count, tokens, serialized payload size, or equivalent).
- Internal cancellation handle/confirmation mechanism, as long as cancellation stays explicit and deterministic for operators.

</decisions>

<specifics>
## Specific Ideas

- Keep `/api/v2/adk/run` as the canonical runtime entrypoint; do not introduce a parallel execution path for the same capability.
- Session semantics should stay predictable: one tool per session lineage, no silent reopen, and no silent new session when a closed or oversized session is reused.
- Operator-facing failures in this phase should be legible and distinct: limit hit, timeout, and cancellation confirmed.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend-hormonia/app/api/v2/routers/adk.py`: canonical thin route already building request context, `AIDeps`, and normalized response.
- `backend-hormonia/app/schemas/v2/adk.py`: current request/response schema surface where runtime and session controls will be added.
- `backend-hormonia/app/ai/adk/wrapper.py`: mandatory `PIISafeADKWrapper.safe_run()` boundary for all ADK invocations.
- `backend-hormonia/app/ai/adk/runtime.py`: `ADKToolRunRequest`, `run_adk_tool()`, `Runner.run_async()` path, and current per-call `InMemorySessionService()` instantiation.
- `backend-hormonia/app/ai/adk/tools.py`: deterministic single-tool registry and `ContextVar`-backed tool context for ADK `FunctionTool` compatibility.
- `backend-hormonia/tests/api/v2/test_adk.py`, `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py`, `backend-hormonia/tests/unit/test_adk_tools_runtime.py`, `backend-hormonia/tests/unit/test_adk_runner_integration.py`: regression test base for route, wrapper, runtime, and runner behavior.
- `backend-hormonia/app/api/v2/routers/tasks/endpoints/operations.py` and `backend-hormonia/app/api/v2/routers/flows.py`: nearby backend patterns for explicit cancel/revoke semantics and `asyncio.wait_for` timeout wrapping.

### Established Patterns
- `/api/v2/adk/run` must stay thin and delegate execution through `PIISafeADKWrapper.safe_run()`.
- ADK results are normalized to stable `{status, result}` internally and `{status, tool_name, session_id, output}` externally.
- Runtime currently executes one tool per request via deterministic `FunctionTool` selection.
- Direct-handler fallback must remain when the ADK runtime is unavailable.

### Integration Points
- Route and schema contract: `backend-hormonia/app/api/v2/routers/adk.py` and `backend-hormonia/app/schemas/v2/adk.py`
- Safety boundary: `backend-hormonia/app/ai/adk/wrapper.py`
- Runtime and session controls: `backend-hormonia/app/ai/adk/runtime.py`
- Tool-context propagation: `backend-hormonia/app/ai/adk/tools.py`
- Regression coverage to extend: route, wrapper, runtime, and runner integration suites under `backend-hormonia/tests/`

</code_context>

<deferred>
## Deferred Ideas

- Deterministic ADK error taxonomy beyond explicit timeout handling (`policy_block`, `tool_error`, `upstream_error`) belongs to Phase 45.
- `before_tool_callback` blocking policy belongs to Phase 45.
- ADK observability baseline and production metrics belong to Phase 46.
- CI smoke gating for critical oncology trajectories belongs to Phase 47.

</deferred>

---

*Phase: 44-adk-runtime-controls*
*Context gathered: 2026-03-05*
