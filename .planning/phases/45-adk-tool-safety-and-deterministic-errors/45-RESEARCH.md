# Phase 45: ADK Tool Safety and Deterministic Errors - Research

**Researched:** 2026-03-05
**Domain:** ADK tool guardrails, deterministic failure taxonomy, and safe fallback boundaries
**Confidence:** HIGH for the implementation direction; MEDIUM for any undocumented raw ADK exception names, which should not be used as the source of truth

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADK-11 | Block unsafe tool calls through `before_tool_callback` before any side effect | Confirmed: ADK supports `before_tool_callback`, and returning a dict short-circuits tool execution before the tool runs |
| ADK-12 | Classify ADK failures deterministically as `timeout`, `policy_block`, `tool_error`, or `upstream_error` | Confirmed: ADK exposes callback and plugin hooks, but the public docs do not provide a stable operator-facing exception taxonomy, so the application must own the final classification boundary |

</phase_requirements>

## Summary

Phase 45 should stay narrow and deterministic. The correct design is to add an app-owned `before_tool_callback` to the single-tool ADK `Agent` created in `backend-hormonia/app/ai/adk/runtime.py`, and make that callback return the same normalized payload shape the runtime already understands: `{"status": "policy_block", "result": {...}}`. That satisfies the requirement that unsafe tool requests are blocked before tool execution and keeps the route contract stable because `_normalize_result()` already preserves payloads that contain both `status` and `result`.

The deterministic error taxonomy must live at the application runtime boundary, not inside undocumented ADK internals. Public ADK docs show `before_tool_callback` and plugin `on_tool_error_callback`, but they do not define a stable operator taxonomy that matches this project’s four required classes. The safest direction is therefore to keep `timeout` from the existing `asyncio.wait_for(...)` boundary, add `policy_block` from the callback return path, classify exceptions raised by the registered tool handlers and `GeminiDomainClient` as `tool_error`, and classify ADK runner/model/bootstrap failures that happen outside the tool handler as `upstream_error`.

The most important codebase finding is the current broad `except Exception: pass` inside `_execute_request()`. Today, any ADK runner exception silently falls through to the direct handler path. In Phase 45 that behavior becomes incorrect: it can bypass a policy block, double-execute a tool after a runner/tool failure, and make the same scenario return different classes depending on whether ADK failed early or late. Fallback must remain, but only when the ADK runtime is unavailable before execution starts, not after runner execution has begun.

## Current Codebase Findings

### Canonical route and response surface

- `backend-hormonia/app/api/v2/routers/adk.py`
  - `/api/v2/adk/run` is already the canonical thin entrypoint.
  - The route already forwards `runtime`, `session`, and `invocation` metadata into wrapper context.
  - The route already trusts the runtime `status` field, so Phase 45 can expose `policy_block`, `tool_error`, and `upstream_error` without inventing a second response envelope.

### Wrapper seam

- `backend-hormonia/app/ai/adk/wrapper.py`
  - `PIISafeADKWrapper.safe_run()` remains the mandatory boundary and must stay that way.
  - The wrapper currently sanitizes prompts and delegates into `run_adk_tool()`, but it has no concept of tool policy blocks or deterministic error classes yet.
  - The wrapper/request seam is the right place to pass policy metadata into the runtime context, but not the right place to own the final error taxonomy. That taxonomy must stay closer to the execution branch so ADK and direct-handler outcomes are normalized identically.

### Runtime execution risk

- `backend-hormonia/app/ai/adk/runtime.py`
  - `_execute_request()` currently tries the ADK runner path and silently falls back to the direct handler on any exception.
  - `run_adk_tool()` already has the right outer control points for timeout handling, invocation metadata, and normalized result building.
  - `_normalize_result()` is already a useful choke point because it preserves structured `{"status", "result"}` payloads.
  - There is no `before_tool_callback` today, no typed classifier, and no distinction between tool exceptions and upstream runner/bootstrap exceptions.

### Tool-layer implications

- `backend-hormonia/app/ai/adk/tools.py`
  - Tool handlers are deterministic and single-purpose, which is good for classification.
  - Tool handlers currently return success payloads but let exceptions bubble.
  - Those exceptions should not be classified by string-matching their messages. They need a small typed wrapper or explicit source metadata so the same failure is always `tool_error`.

### Phase 44 carry-over constraints

- `backend-hormonia/app/ai/adk/session_store.py`
  - Phase 44 already established deterministic statuses for `cancelled`, `limit_exceeded`, `timeout`, and lifecycle states such as `closed`.
  - Phase 45 should not collapse or rename those statuses. The new taxonomy should apply to ADK execution failures that previously surfaced as generic `error` / `runtime_error`.

## Standard Stack

### Core

| Component | Use | Why |
|-----------|-----|-----|
| Agent-level `before_tool_callback` | Block unsafe tool calls before side effects | Official ADK callback surface directly supports pre-tool interception |
| Existing FastAPI route + Pydantic schemas | Keep `/api/v2/adk/run` canonical | Route already forwards normalized status and metadata |
| App-owned failure classifier in `runtime.py` | Produce deterministic `policy_block` / `tool_error` / `upstream_error` statuses | Public ADK docs do not define the exact operator taxonomy this project needs |
| Existing `asyncio.wait_for(...)` timeout boundary | Preserve `timeout` deterministically | Already shipped in Phase 44 and already covered by tests |
| Existing `ADKSessionStore` invocation metadata | Keep `invocation_id`, `session_id`, and lifecycle outcomes stable | Determinism requires the same metadata surface across all failure types |

### Supporting

| Component | Use | When |
|-----------|-----|------|
| Small policy helper module or callback factory | Centralize “is this tool call allowed?” logic | Use when the callback starts needing structured allow/block rules |
| Small typed exception layer for tool failures | Mark tool-origin exceptions without parsing message strings | Use when direct tool exceptions and runner exceptions currently look identical |
| Existing direct-handler fallback | Preserve host compatibility when ADK is absent | Use only before execution begins or when ADK capability is unavailable |

### Do Not Introduce

| Avoid | Reason |
|------|--------|
| New policy-as-code framework | Out of scope for this phase; the requirement is a minimal deterministic guardrail |
| Plugin-only error handling as the canonical taxonomy | Direct-handler fallback must stay aligned with ADK runner behavior |
| String parsing over raw exception messages | Not deterministic enough for `ADK-12` |
| New endpoint or parallel execution path | Violates the locked Phase 44 decision that `/api/v2/adk/run` stays canonical |
| LLM-mediated failure classification | The model should not decide operator-facing error classes |

## Architecture Patterns

### Pattern 1: Add the guardrail at the ADK tool boundary, not inside the tool handler

Use `before_tool_callback` on the single-tool `Agent` created in `_execute_request()`. The callback should inspect:

- requested tool name,
- tool arguments,
- merged operator context already being passed through `context_json`,
- any project-owned policy metadata added by the wrapper or route.

If the request is unsafe, the callback must return a normalized block payload immediately instead of allowing the tool handler to run.

Recommended return shape:

```python
{
    "status": "policy_block",
    "result": {
        "type": "policy_block",
        "message": "Tool call blocked by policy",
        "tool_name": tool_name,
        "invocation_id": invocation_id,
        "reason": "missing_required_context",
    },
}
```

Why this shape:

- it short-circuits execution before any side effect,
- `_normalize_result()` already preserves it,
- the route already surfaces `status` unchanged,
- tests can assert exact class equality without parsing generated text.

### Pattern 2: Keep one classifier for all non-timeout failures

Introduce a small classifier helper at the runtime boundary, for example:

- `classify_adk_failure(exc, *, source, tool_name, invocation_id) -> dict[str, Any]`

The classifier should return a normalized payload and use explicit source information, not raw message text:

- `timeout`
  - already produced by the Phase 44 timeout boundary.
- `policy_block`
  - returned directly from `before_tool_callback`.
- `tool_error`
  - raised inside the registered tool function or domain client call.
- `upstream_error`
  - raised while preparing or running the ADK runner/model path outside the tool function.

The important point is that the classifier must run in both:

- ADK runner path, and
- direct-handler fallback path.

That is the only way to keep repeated scenarios deterministic across environments.

### Pattern 3: Distinguish “ADK unavailable” from “ADK execution failed”

Retain fallback only for capability absence, not runtime failure.

Allowed fallback examples:

- `HAS_ADK_RUNTIME` is `False`
- `Agent` / `Runner` / `FunctionTool` cannot be imported
- no ADK function tool is available for the selected tool before execution starts

Do not fall back after:

- `before_tool_callback` ran,
- the runner started streaming events,
- the tool function raised,
- the runner/model path raised during execution.

Once execution starts, any failure must classify and return deterministically. Silent fallback after execution begins breaks both safety and repeatability.

### Pattern 4: Preserve shipped Phase 44 statuses as-is

Do not re-map these existing terminal states into the new taxonomy:

- `cancelled`
- `limit_exceeded`
- `closed`
- existing session errors such as `session_closed`

Phase 45 should only replace the current ambiguous `error` / `runtime_error` bucket for ADK execution failures.

### Pattern 5: Use deterministic markers, not inferred text, for policy and tool failures

For policy blocks, return a normalized payload directly from the callback.

For tool failures, prefer a small explicit marker such as:

- wrapping tool-handler exceptions in a local `ADKToolExecutionError`, or
- attaching `source="tool"` metadata before re-raising from the tool-dispatch seam.

This is safer than trying to decide after the fact whether an exception came from:

- ADK runner bootstrap,
- Gemini upstream/model invocation,
- tool dispatch,
- application policy code.

### Pattern 6: Keep broader security reuse optional

Official ADK docs recommend plugins for reusable security guardrails across agent hierarchies. That is directionally correct, but this phase should stay minimal and explicit:

- implement the required `before_tool_callback` first,
- keep its logic app-owned and small,
- only extract it into a plugin later if multiple agents start sharing the same rule set.

That keeps Phase 45 aligned with the roadmap’s “minimal guardrail first” scope.

## Don't Hand-Roll

| Problem | Don’t build | Use instead | Why |
|---------|-------------|-------------|-----|
| Unsafe tool blocking | Custom validation deep inside each tool handler | One `before_tool_callback` guardrail | Ensures the tool never executes when blocked |
| Deterministic failure mapping | Regex over exception strings | Small typed classifier with source-aware metadata | Same scenario must map to the same class every time |
| Cross-path normalization | Separate ADK and fallback error taxonomies | One runtime-level normalized payload builder | Route/tests stay stable across environments |
| Broad security framework | Policy engine or generic DSL | Narrow app-owned rules for the supported four tools | Scope is too small to justify a framework |
| Post-hoc model interpretation | Let the LLM explain why the tool was blocked | Return structured payloads directly | Operator-facing status must not depend on model output |

## Common Pitfalls

### Pitfall 1: Keeping the current broad catch-and-fallback logic

The current `except Exception: pass` in `_execute_request()` is the biggest risk in this phase. If it stays in place, a blocked or failed ADK execution can quietly reroute into the direct handler and execute anyway. That defeats `ADK-11`.

### Pitfall 2: Returning plain text from the callback

If `before_tool_callback` returns plain text instead of a normalized `{"status", "result"}` payload, the runner may surface it as a successful text output, which makes `policy_block` ambiguous at the API boundary.

### Pitfall 3: Making plugin hooks the only source of deterministic classification

Plugin `on_tool_error_callback` is useful, but direct-handler fallback still exists in this project. If canonical classification lives only in the ADK plugin path, the same failure can classify differently in non-ADK environments.

### Pitfall 4: Treating all exceptions as upstream failures

Tool exceptions and upstream runner/model failures are not the same operational problem. If everything becomes `upstream_error`, operators lose the distinction between:

- “the tool logic/domain call failed” and
- “the ADK runner/model orchestration failed before or around the tool”

### Pitfall 5: Reclassifying Phase 44 control outcomes

`timeout`, `cancelled`, and `limit_exceeded` are already explicit runtime outcomes. Phase 45 should extend deterministic failure handling, not destabilize the statuses that Phase 44 already locked with tests.

### Pitfall 6: Ignoring tool args/context in the guardrail

The block decision should not inspect only the prompt string. The current ADK tool flow already passes structured context through `context_json`; unsafe conditions can live there too. Tests should cover both prompt-driven and context-driven policy blocks.

### Pitfall 7: Verifying only one execution path

The direct-handler compatibility path and the ADK runner path must both be covered. Determinism means “same scenario, same class” regardless of which runtime branch is active.

## Code Examples

### Example 1: Minimal pre-tool guardrail

```python
def build_before_tool_callback(*, invocation_id: str):
    async def before_tool_callback(tool, args, tool_context):
        tool_name = getattr(tool, "name", None) or "unknown"
        reason = evaluate_tool_policy(
            tool_name=tool_name,
            args=args or {},
            context=getattr(tool_context, "state", {}) or {},
        )
        if reason is None:
            return None
        return {
            "status": "policy_block",
            "result": {
                "type": "policy_block",
                "tool_name": tool_name,
                "invocation_id": invocation_id,
                "message": "Tool call blocked by policy",
                "reason": reason,
            },
        }

    return before_tool_callback
```

### Example 2: Runtime-owned classifier

```python
def build_failure_result(
    *,
    status: str,
    exc: Exception | None,
    invocation_id: str,
    tool_name: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "result": {
            "type": status,
            "tool_name": tool_name,
            "invocation_id": invocation_id,
            "message": str(exc) if exc else status,
        },
    }


def classify_adk_failure(exc: Exception, *, source: str) -> str:
    if source == "tool":
        return "tool_error"
    return "upstream_error"
```

### Example 3: Safe fallback boundary

```python
if not HAS_ADK_RUNTIME or Agent is None or Runner is None:
    return await invoke_direct_handler(...)

try:
    return await run_with_adk(...)
except ADKToolExecutionError as exc:
    return build_failure_result(
        status="tool_error",
        exc=exc,
        invocation_id=invocation_id,
        tool_name=request.tool_name,
    )
except Exception as exc:
    return build_failure_result(
        status="upstream_error",
        exc=exc,
        invocation_id=invocation_id,
        tool_name=request.tool_name,
    )
```

## Verification Targets

The phase plan should lock at least these scenarios:

1. Blocked tool call through `before_tool_callback`
   - requested tool never executes
   - status is exactly `policy_block`
   - repeated same payload returns `policy_block` again

2. Tool handler failure
   - domain client or registered handler raises
   - status is exactly `tool_error`
   - no generic `runtime_error` remains

3. ADK runner/bootstrap/model failure outside tool execution
   - status is exactly `upstream_error`
   - no fallback tool execution happens afterward

4. Existing timeout path
   - status remains `timeout`
   - new taxonomy does not override the Phase 44 timeout behavior

5. ADK-available and ADK-unavailable parity
   - same tool-side failure classifies as `tool_error` in both branches when applicable

## Validation Architecture

Phase 45 can reuse the existing backend pytest infrastructure. No new framework or harness is needed before planning; the work is to extend the current ADK route/runtime/wrapper tests so they lock the new deterministic classes without weakening the Phase 44 controls.

### Test infrastructure

| Property | Value |
|----------|-------|
| Framework | `pytest` |
| Config file | `backend-hormonia/pyproject.toml` |
| Quick run command | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py -q` |
| Full suite command | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_runner_integration.py -q` |
| Expected feedback latency | ~30-40 seconds locally |

### Coverage shape the plans should preserve

1. `tests/api/v2/test_adk.py`
   - route-level normalization for `policy_block`, `tool_error`, and `upstream_error`
   - route still calls `PIISafeADKWrapper.safe_run()` exactly once
   - API payload stays on the existing `{status, tool_name, session_id, output}` contract

2. `tests/unit/test_adk_tools_runtime.py`
   - blocked tool request proves no handler/domain client side effect occurs
   - tool exception classifies as `tool_error`
   - runner/bootstrap failure classifies as `upstream_error`
   - timeout / cancel / limit-exceeded regressions stay intact
   - same scenario returns the same class in repeated runs

3. `tests/unit/test_pii_safe_adk_wrapper.py`
   - prompt sanitization remains mandatory
   - new policy metadata does not create an execution path that bypasses the wrapper boundary

4. `tests/unit/test_adk_runner_integration.py`
   - conditional real-ADK path remains compatible when `google-adk` is installed
   - at least one deterministic failure-class scenario is exercised against the runner-enabled branch without making local feedback depend on ADK availability

### Sampling strategy

- After every task commit: run the quick command.
- After every plan wave: run the full suite command.
- Before phase verification: full suite must be green and no generic `runtime_error` assertions should remain for scenarios now covered by `policy_block`, `tool_error`, or `upstream_error`.

### Wave 0 assessment

Existing infrastructure already covers this phase:

- test files already exist for route, runtime, wrapper, and conditional runner coverage
- pytest config already supports async tests and strict markers
- no new external test dependency is required

The only Wave 0 expectation is to add/adjust test cases inside the existing files above. Plans do not need a separate infrastructure setup step unless implementation introduces a new helper module that requires dedicated fixtures.

## Sources

### Official ADK docs

- https://google.github.io/adk-docs/agents/callbacks/
- https://google.github.io/adk-docs/agents/plugins/
- https://google.github.io/adk-docs/tutorials/agent-team/

### Local code references

- `backend-hormonia/app/api/v2/routers/adk.py`
- `backend-hormonia/app/ai/adk/wrapper.py`
- `backend-hormonia/app/ai/adk/runtime.py`
- `backend-hormonia/app/ai/adk/tools.py`
- `backend-hormonia/app/ai/adk/session_store.py`
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py`
- `.planning/phases/44-adk-runtime-controls/44-CONTEXT.md`
- `.planning/phases/44-adk-runtime-controls/44-RESEARCH.md`
- `.planning/phases/44-adk-runtime-controls/44-03-SUMMARY.md`

---
*Phase: 45-adk-tool-safety-and-deterministic-errors*
*Research completed: 2026-03-05*
