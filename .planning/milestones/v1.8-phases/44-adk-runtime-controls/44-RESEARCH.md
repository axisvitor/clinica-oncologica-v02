# Phase 44: ADK Runtime Controls - Research

**Researched:** 2026-03-05
**Domain:** Canonical ADK runtime controls, session lifecycle, explicit cancellation, and bounded session state
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Session lifecycle
- New session is auto-created when `session_id` is omitted; the response returns the generated session id.
- Resume is valid only within the same `tool_name`; sessions do not cross tool contexts.
- Sessions can be closed explicitly and also expire after inactivity to prevent uncontrolled accumulation.
- Closed sessions are terminal; reusing a closed `session_id` is rejected instead of reopening or silently replacing it.

#### Invocation limits
- `/api/v2/adk/run` exposes runtime controls as optional per-request overrides on top of safe server defaults.
- `max_llm_calls` uses a conservative default when the operator does not provide one.
- Hitting the LLM call budget stops execution immediately and returns an explicit limit-hit failure.
- Timeout also has a safe default with optional override; exceeding it returns an explicit timeout failure.

#### Cancellation behavior
- Cancellation is an explicit operator action, not an implicit side effect of client disconnect alone.
- The operator receives explicit confirmation that the execution was cancelled and will not continue processing.
- If a result arrives after cancellation is requested, cancellation wins and the late result is discarded.
- Cancelling a turn does not close the session; the session remains valid for retry/resume without partial output from the cancelled turn.

#### State growth policy
- Resumable session state keeps recent relevant turns plus structured clinical context, not unbounded raw history.
- When state nears the configured limit, the oldest low-priority context is pruned first.
- Structured clinical context and the most recent successful turn have highest retention priority.
- If resume would still exceed the configured limit after pruning, resume is blocked and the operator must start a fresh session.

### Claude's Discretion
- Exact field names and payload shape for runtime/session controls, as long as `/api/v2/adk/run` remains the canonical thin entrypoint.
- Exact default numeric values for `max_llm_calls`, timeout, inactivity expiry, and state-size budget.
- Internal strategy for measuring state growth (count, tokens, serialized payload size, or equivalent).
- Internal cancellation handle/confirmation mechanism, as long as cancellation stays explicit and deterministic for operators.

### Deferred Ideas (OUT OF SCOPE)
- Deterministic ADK error taxonomy beyond explicit timeout handling belongs to Phase 45.
- `before_tool_callback` blocking policy belongs to Phase 45.
- Persistent DB-backed ADK session service belongs to deferred requirement `ADK-ADV-01`.
- Observability and CI smoke gates belong to Phases 46 and 47.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADK-09 | Operator can apply per-invocation ADK limits (`max_llm_calls`, timeout, cancellation) on `/api/v2/adk/run` | Confirmed: current route/schema expose none of these controls, so Phase 44 must extend request contract, runtime execution path, and tests in one slice |
| ADK-10 | Operator can execute ADK session lifecycle (create/resume/close) with controlled state growth | Confirmed: current runtime creates a fresh `InMemorySessionService()` per call, so there is no persisted lifecycle or bounded session state today |
</phase_requirements>

## Summary

Phase 44 is a backend runtime-control phase, not a new AI capability phase. The code already has the correct ADK safety boundary and a canonical route, but the runtime path is still essentially stateless and ungoverned. `backend-hormonia/app/api/v2/routers/adk.py` is a thin route that validates `prompt`, `tool_name`, `user_id`, `session_id`, and `context`, then calls `PIISafeADKWrapper.safe_run()` and normalizes the result. `backend-hormonia/app/ai/adk/wrapper.py` correctly sanitizes prompt input before calling the runtime and scans output for PII leakage. `backend-hormonia/app/ai/adk/runtime.py` already builds a deterministic single-tool `Runner` invocation, but it instantiates `InMemorySessionService()` inside each call and does not expose timeout, call-budget, cancellation, or lifecycle controls.

The design constraint from the user context is strong and useful: do not create a second runtime entrypoint. The safest planning direction is therefore to keep `/api/v2/adk/run` as the single operator endpoint and extend its contract so operators can:

1. Run with safe defaults or request-specific overrides.
2. Create/resume/close sessions without leaving the canonical route surface.
3. Cancel a specific in-flight invocation explicitly and receive a deterministic cancellation confirmation.

The biggest implementation risk is not the route or schema; it is lifecycle coordination across requests. The current code has no ADK session persistence, and the current shell environment does not have `google.adk` importable, so planning must separate:
- local/fallback coverage that proves route + wrapper + runtime contracts, and
- conditional runtime-real coverage that only runs where ADK is installed.

## Current Codebase Findings

### Canonical route and contract
- `backend-hormonia/app/api/v2/routers/adk.py`
  - already the canonical `/api/v2/adk/run` handler.
  - already constructs the execution context and `AIDeps`.
  - already normalizes external response shape to `{status, tool_name, session_id, output}`.
- `backend-hormonia/app/schemas/v2/adk.py`
  - currently has only `prompt`, `tool_name`, `user_id`, `session_id`, and `context`.
  - Phase 44 needs to extend this file first, because every other change hangs off the request contract.

### Safety boundary
- `backend-hormonia/app/ai/adk/wrapper.py`
  - already enforces prompt sanitization before runtime execution.
  - already logs/flags output PII leakage.
  - should remain the only place allowed to call the runtime.

### Runtime and tool wiring
- `backend-hormonia/app/ai/adk/runtime.py`
  - `ADKToolRunRequest` is the current execution contract between wrapper and runtime.
  - `run_adk_tool()` already handles deterministic tool selection and direct-handler fallback when ADK runtime is unavailable.
  - current `Runner` path uses `InMemorySessionService()` created inside the call, which means no lifecycle continuity.
- `backend-hormonia/app/ai/adk/tools.py`
  - registry is already deterministic and constrained to four supported tools.
  - `ContextVar`-based tool context is the right place to preserve structured context for a bounded session.

### Existing reusable patterns
- `backend-hormonia/app/core/redis_manager/session_cache.py`
  - proven TTL and max-age session handling in Redis.
  - useful as the reference pattern for ADK session inactivity expiration and metadata refresh.
- `backend-hormonia/app/api/v2/routers/tasks/endpoints/operations.py`
  - established API pattern for explicit cancellation, cancellation reason, and status transition tracking.
- `backend-hormonia/app/api/v2/routers/flows.py`
  - established `asyncio.wait_for(...)` timeout wrapping pattern.
- `backend-hormonia/app/services/redis_pubsub_manager.py`
  - existing Redis pub/sub infrastructure for cross-instance signaling if cancellation needs owner-instance coordination.

### Existing tests to extend
- `backend-hormonia/tests/api/v2/test_adk.py`
  - baseline route tests.
- `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py`
  - baseline wrapper safety tests.
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py`
  - runtime/tool fallback and runner-path tests.
- `backend-hormonia/tests/unit/test_adk_runner_integration.py`
  - conditional real-runtime integration when `google-adk` is installed.

## Standard Stack

### Core
| Component | Use | Why |
|-----------|-----|-----|
| FastAPI route + Pydantic schemas | Operator-facing runtime/session contract | Already canonical in `app/api/v2/routers/adk.py` and `app/schemas/v2/adk.py` |
| `PIISafeADKWrapper` | Mandatory safety boundary | Already required by earlier phases and must remain intact |
| `run_adk_tool()` + deterministic tool registry | ADK runner execution | Already the runtime seam for Phase 44 |
| Redis-backed metadata/session storage | Session lifecycle and bounded state growth | Existing project already relies on Redis for session semantics and cache-backed coordination |
| `asyncio.wait_for` and task cancellation primitives | Timeout and explicit cancellation enforcement | Existing backend pattern; no new async framework needed |

### Supporting
| Component | Use | When |
|-----------|-----|------|
| `SessionCache` TTL / max-age semantics | Inactivity expiry and terminal close metadata | Reuse the pattern, not necessarily the class itself |
| `RedisPubSubManager` pattern | Cross-instance cancellation signaling if needed | Use only if same-process cancellation registry is insufficient |
| Existing `AIDeps` dataclass | Model and API key propagation | Keep current dependency surface small |

### Do Not Introduce
| Avoid | Reason |
|------|--------|
| New permanent DB-backed session subsystem | Deferred by `ADK-ADV-01`; too large for Phase 44 |
| Second runtime endpoint for the same operator action | Violates the locked decision that `/api/v2/adk/run` remains canonical |
| New external workflow/orchestration library | Current FastAPI/asyncio/Redis stack is enough for this phase |

## Recommended Architecture Patterns

### Pattern 1: Extend the canonical request contract instead of adding another execution route

Recommended direction: keep `/api/v2/adk/run` and extend `ADKRunRequest` with explicit runtime and session-control payloads. The exact field names are discretionary, but the contract should separate three concerns cleanly:

- execution input (`prompt`, `tool_name`, clinical context),
- runtime overrides (`max_llm_calls`, `timeout_seconds`),
- lifecycle intent (`auto` / `create` / `resume` / `close` / `cancel` or equivalent).

This keeps the route thin while avoiding overloaded ad hoc behavior hidden inside `context`.

**Planning implication:** first implementation slice should update `app/schemas/v2/adk.py`, `app/api/v2/routers/adk.py`, and `app/ai/adk/runtime.py` together so route, schema, and runtime request object stay aligned.

### Pattern 2: Use Redis-backed ADK session metadata, not process-local session state

`InMemorySessionService()` per request is fine as an execution helper, but it cannot be the source of truth for Phase 44 because it dies at the end of the request. Phase 44 needs cross-request lifecycle, inactivity expiry, and bounded state. The closest existing production-safe pattern is Redis-backed session metadata.

Recommended shape:
- store session envelope under a dedicated namespace such as `adk:session:{session_id}`;
- include `tool_name`, `status` (`open`, `closed`, `expired`), `created_at`, `last_activity`, `closed_at`, and bounded serialized state;
- keep explicit `state_size` or equivalent measurement inside the envelope so growth checks are deterministic;
- refresh inactivity TTL on resume/run, not on close.

This matches the locked decision set and avoids dragging Phase 44 into persistent DB design.

### Pattern 3: Treat bounded state as an application envelope, not as opaque ADK internals

The requirement is controlled state growth, not “perfect ADK-native long memory.” That means the plan should persist a normalized, app-owned envelope:
- recent turn summaries or sanitized turn payloads,
- structured clinical context,
- most recent successful turn output,
- size metadata used for pruning decisions.

This is safer than relying entirely on opaque ADK internals, especially because `google.adk` is not importable in the current shell, so the exact session-service API cannot be treated as known from local inspection.

**Planning implication:** the plan should include a dedicated task that defines what is retained, how it is serialized, and how pruning happens before any real runtime wiring.

### Pattern 4: Model cancellation as invocation lifecycle plus owner-local task registry

Session lifecycle and invocation lifecycle are not the same thing. A session remains open across turns; an invocation is one in-flight run that may complete, time out, fail, or be cancelled.

Recommended direction:
- generate or accept an `invocation_id` per run;
- track invocation status separately from session status;
- keep a local in-process task registry so the running `asyncio.Task` can be cancelled explicitly;
- persist invocation metadata in Redis so a cancel request can confirm final state and avoid returning stale/late results.

If deployment topology requires cross-instance cancellation, reuse Redis pub/sub patterns already present in the app to signal the owner instance. That is a planning risk, not a reason to open a new subsystem.

### Pattern 5: Enforce timeout outside the ADK library boundary

The current runtime has no wrapper around `Runner.run_async()` or `_extract_runner_output()`. The safest pattern for Phase 44 is the same one already used in other backend routes: wrap the invocation boundary with `asyncio.wait_for(...)` and classify the result as an explicit timeout at the runtime boundary. This keeps the route thin and lets tests assert the timeout behavior without requiring the real ADK runtime.

### Pattern 6: Keep direct-handler fallback behavior intact

Earlier phases intentionally preserved host compatibility by keeping direct-handler fallback when ADK runtime is unavailable. Phase 44 must not remove that compatibility path. Runtime controls should therefore be enforced above the branch point where possible, so both:
- real ADK runner path, and
- direct-handler fallback path

obey the same timeout, cancellation, session, and normalized result contracts.

## Recommended Implementation Slices

### Slice A: Contract and lifecycle foundation
Build the API/runtime contract first.

Scope:
- extend `ADKRunRequest` / `ADKRunResponse`;
- extend `ADKToolRunRequest` with runtime and lifecycle fields;
- add a dedicated ADK session/invocation store module using Redis-backed envelopes;
- keep route thin while making lifecycle intent explicit.

Why first:
- everything else depends on stable request semantics;
- tests can lock the contract before any complex runtime behavior is introduced.

### Slice B: Runtime enforcement
Wire limits and explicit cancellation into wrapper/runtime.

Scope:
- enforce `max_llm_calls`;
- enforce timeout with `asyncio.wait_for`;
- introduce invocation registry and cancellation flow;
- guarantee cancelled/late results do not leak through;
- preserve direct-handler fallback.

Why second:
- relies on Slice A identifiers and store contract;
- this is where most race conditions live.

### Slice C: Bounded resume/close semantics and regression coverage
Finish session-state policy and lock it with tests.

Scope:
- state pruning and limit accounting;
- close semantics and rejection of closed sessions;
- resume rejection when state remains oversized after pruning;
- route, unit, and conditional runtime-real tests for all critical flows.

Why third:
- bounded-state behavior depends on both lifecycle contract and runtime wiring being in place;
- verification value is highest when all external behavior is already implemented.

## Don’t Hand-Roll

| Problem | Don’t build | Use instead | Why |
|---------|-------------|-------------|-----|
| Session TTL / inactivity semantics | New expiration model from scratch | Reuse the `SessionCache` pattern | Already proven in production |
| Timeout handling | Custom polling loop | `asyncio.wait_for(...)` at runtime boundary | Existing backend convention and easy to test |
| Cancellation metadata | Hidden flags inside `context` only | Explicit invocation/session metadata object | Easier to verify and less error-prone |
| Bounded-state accounting | Implicit “recent enough” heuristics | Store explicit serialized-size or equivalent budget metadata | Deterministic pruning and testability |
| ADK-only test reliance | Assume `google.adk` always exists locally | Keep route/unit tests runtime-agnostic and gate real-runtime test conditionally | Current shell lacks `google.adk` import support |

## Common Pitfalls

### Pitfall 1: Solving session persistence with process-local memory
**What goes wrong:** create/resume/close appear to work in one request path but disappear across requests or instances.
**Why it happens:** `InMemorySessionService()` is instantiated inside `run_adk_tool()` and dies at the end of the call.
**How to avoid:** make Redis-backed session metadata the source of truth and treat in-memory ADK session helpers as request-local execution details.

### Pitfall 2: Mixing session and invocation state
**What goes wrong:** cancelling a single run accidentally closes the whole session, or a closed session still appears runnable because only invocation state changed.
**Why it happens:** no explicit separation between “session open/closed” and “invocation running/cancelled/completed.”
**How to avoid:** store and test them separately.

### Pitfall 3: Late result leakage after cancellation
**What goes wrong:** operator receives “cancelled” and then still gets a completed result or mutated session state.
**Why it happens:** runtime completes after cancellation request but there is no final-state guard.
**How to avoid:** mark invocation terminal state centrally and reject any late completion write-back if status is already `cancelled`.

### Pitfall 4: Over-scoping into Phase 45
**What goes wrong:** implementation starts introducing generalized error taxonomy or `before_tool_callback` safety policy.
**Why it happens:** timeout/cancel work touches adjacent error handling paths.
**How to avoid:** in Phase 44, only timeout/limit/cancel/session semantics should become explicit. Broader deterministic classes wait for Phase 45.

### Pitfall 5: Planning only for the real ADK runtime
**What goes wrong:** local tests become impossible on machines without `google.adk`, or runtime controls exist only on the ADK branch and not on fallback.
**Why it happens:** current host environment does not have `google.adk` importable.
**How to avoid:** enforce contracts above the runtime branch and keep the real ADK integration test conditional.

## Test Strategy

### Route tests
Extend `backend-hormonia/tests/api/v2/test_adk.py` to cover:
- request validation for runtime/session-control payloads;
- auto-create session response path;
- close action path;
- cancel action path;
- rejection of closed session reuse;
- normalized timeout/cancel/limit result shapes.

### Runtime unit tests
Extend `backend-hormonia/tests/unit/test_adk_tools_runtime.py` to cover:
- timeout enforcement around runner/direct path;
- `max_llm_calls` exhaustion behavior;
- invocation status transitions (`running` -> `cancelled`, `running` -> `timeout`, `running` -> `completed`);
- late-result discard after cancellation;
- state pruning and oversized-resume rejection.

### Wrapper tests
Keep `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py` focused on safety boundary, but add targeted coverage that new runtime-control fields still pass through the wrapper without bypassing sanitization.

### Conditional runtime-real test
Keep or extend `backend-hormonia/tests/unit/test_adk_runner_integration.py` as conditional-only coverage for the real `google-adk` branch. Do not make phase verification depend solely on this test, because the current shell environment does not have the module installed.

## Validation Architecture

### Framework
- **Framework:** pytest
- **Config:** `backend-hormonia/pytest.ini` if present, otherwise repository pytest defaults
- **Quick feedback command:** `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py -q`
- **Full phase command:** `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q`

### Sampling strategy
- Run the quick command after each runtime/schema task group.
- Run the full phase command after each plan wave.
- Keep the integration test conditional so missing `google.adk` does not invalidate local feedback.

### Minimum verification map for planning
- **ADK-09**
  - route contract accepts runtime overrides;
  - timeout returns explicit timeout failure;
  - `max_llm_calls` hit returns explicit limit failure;
  - cancellation marks invocation cancelled and discards late result.
- **ADK-10**
  - omitted `session_id` creates session;
  - same-tool resume succeeds within bounded state;
  - explicit close makes session terminal;
  - oversize resume after pruning still blocks.

### Expected wave-0 gaps
- No new test framework is needed.
- If runtime-real ADK validation is required in CI, the environment must install `google-adk`; local shell currently does not import it.
- If cancellation requires cross-instance signaling, plan verification should include a mocked Redis/pubsub path rather than waiting for full production observability.

## Planning Risks

1. **ADK library not importable in current shell** — route/unit coverage must remain runtime-agnostic, and any real-runner validation must stay conditional or run in the phase-specific container/venv.
2. **Cross-instance cancellation semantics** — if cancel requests can land on a different API instance, the implementation will need either owner-instance routing or Redis-based signaling in addition to local task cancellation.
3. **Unknown ADK session-service rehydration surface** — plan should avoid depending on undocumented ADK-native persistence semantics and instead own the bounded session envelope at the application layer.

## Recommendation

Plan Phase 44 as three sequential execution plans:

1. **Contract + session/invocation store foundation**
2. **Runtime limit + timeout + cancel enforcement**
3. **Bounded-state finalize + regression coverage**

That sequence matches the phase risks: first define stable external semantics, then wire the hard async control paths, then lock the phase with tests.
