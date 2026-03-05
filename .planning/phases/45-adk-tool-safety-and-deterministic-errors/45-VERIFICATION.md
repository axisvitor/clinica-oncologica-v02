---
phase: 45
slug: adk-tool-safety-and-deterministic-errors
status: gaps_found
verified_on: 2026-03-05
requirements:
  - ADK-11
  - ADK-12
verifier: Codex
---

# Phase 45 Verification

## Verdict

Phase 45 is **not verified**.

The local automated suite for the phase is green, but the runner path still allows model-supplied tool arguments to overwrite operator-supplied policy context before `before_tool_callback` makes its decision. That means ADK-11 is not actually satisfied in the runner branch, because a blocked call can still reach tool execution and produce side effects.

## Must-Have Checks

| Check | Requirement | Result | Evidence |
|---|---|---|---|
| Direct-handler path blocks unsafe tool calls before handler/domain execution | ADK-11 | Pass | `backend-hormonia/app/ai/adk/runtime.py:545-555`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:567-619` |
| Runner path blocks unsafe tool calls before handler/domain execution | ADK-11 | **Fail** | `backend-hormonia/app/ai/adk/runtime.py:898-959`; `backend-hormonia/app/ai/adk/tools.py:168-196`; manual reproduction below |
| Failures classify deterministically as `policy_block`, `tool_error`, or `upstream_error` instead of ambiguous fallback | ADK-12 | Pass in local evidence | `backend-hormonia/app/ai/adk/tools.py:128-145`; `backend-hormonia/app/ai/adk/runtime.py:605-630`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:725-922`; `backend-hormonia/tests/api/v2/test_adk.py:163-222` |
| Repeated identical scenarios keep the same classification | ADK-12 | Pass in local evidence | `backend-hormonia/tests/unit/test_adk_tools_runtime.py:585-922`; `backend-hormonia/tests/api/v2/test_adk.py:163-222` |
| Existing Phase 44 timeout/cancel/budget/session outcomes remain intact | Phase 44 regression guard | Pass in local evidence | `backend-hormonia/tests/unit/test_adk_tools_runtime.py:297-563`; `backend-hormonia/tests/api/v2/test_adk.py:362-480` |
| Real `google-adk` runner path executed locally | ADK-11, ADK-12 | Not run | `backend-hormonia/tests/unit/test_adk_runner_integration.py:58-134` was skipped because `google-adk` is not installed locally |

## Requirement Coverage

| Requirement | Status | Notes |
|---|---|---|
| ADK-11 | **Gap found** | The direct path is safe, but the runner path is bypassable because callback evaluation uses a merged context that lets tool-call args overwrite request policy and required-context inputs. |
| ADK-12 | Pass in local evidence, human follow-up still needed | Local tests cover deterministic `policy_block`, `tool_error`, and `upstream_error`, plus repeated scenarios and no post-start fallback. Real `google-adk` integration coverage was skipped locally and still needs rerun in an environment with the package installed. |

## Evidence

### 1. Automated phase suite

Command run:

```bash
cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_runner_integration.py -q -r a
```

Observed result:

- Exit code `0`
- The API/unit/wrapper suite passed
- 3 runner integration tests in `tests/unit/test_adk_runner_integration.py` were skipped because `google-adk` is not installed locally

This confirms the currently committed regression suite is green, but it does **not** prove the real runner branch is safe.

### 2. Deterministic classification evidence

- Tool-side exceptions are wrapped into `ADKToolExecutionError` in `backend-hormonia/app/ai/adk/tools.py:128-145`.
- Runtime classification maps `ADKToolExecutionError` to `tool_error` and all other post-start execution failures to `upstream_error` in `backend-hormonia/app/ai/adk/runtime.py:605-630`.
- Repeated direct and fake-runner regressions assert stable `policy_block`, `tool_error`, and `upstream_error` classifications in `backend-hormonia/tests/unit/test_adk_tools_runtime.py:567-922`.
- Route-level tests assert the canonical `/api/v2/adk/run` envelope remains stable for repeated deterministic statuses in `backend-hormonia/tests/api/v2/test_adk.py:118-222`.

### 3. Concrete safety gap in runner callback context handling

Relevant source:

- `backend-hormonia/app/ai/adk/runtime.py:898-920` builds `before_tool_callback()` and evaluates policy on callback-derived `tool_name`, `prompt`, and `context`.
- `backend-hormonia/app/ai/adk/runtime.py:945-959` merges `tool_args["context_json"]` and `tool_args["context"]` **over** `request_context`.
- `backend-hormonia/app/ai/adk/tools.py:168-196` applies the same merge pattern for actual tool execution.

Impact:

- A model-generated tool call can overwrite `tool_policy` from the original request by sending `context_json={"tool_policy": {}}`.
- A model-generated tool call can also fabricate values for `required_context_keys`, because callback evaluation and actual tool execution both trust merged tool-call context.

Manual reproduction run on 2026-03-05:

- I executed a no-file-change `/usr/bin/python3` script that loaded the app test environment, patched a fake runner, and sent a request-level blocked prompt policy.
- The fake runner then supplied `context_json={"tool_policy": {}, "patient_context": {"clinical_summary": "invented"}}`.
- Observed outcome:
  - `callback_result = None`
  - tool execution returned success
  - domain client call count became `1`
  - final runtime result was `status: "success"`

That is a direct violation of the phase goal: the blocked runner call was **not** stopped before tool execution.

### 4. Why the current tests missed it

- The runner policy regression in `backend-hormonia/tests/unit/test_adk_tools_runtime.py:623-721` only proves the happy path where `context_json` preserves the block.
- I did not find a regression that asserts model/tool-call args cannot override request-level `tool_policy` or satisfy missing required context.

## Remaining Manual Validation Items

These manual checks still matter, but they should happen **after** the ADK-11 runner-path gap is fixed:

1. Re-run the Phase 45 full suite and add a negative regression proving tool-call `context_json` / `context` cannot override request policy or fabricate required context.
2. Re-run `backend-hormonia/tests/unit/test_adk_runner_integration.py` in an environment with `google-adk` installed.
3. Execute the staging-only checks already documented in `45-VALIDATION.md`:
   - unsafe real-ADK tool call returns `policy_block` twice with no side effect
   - runner/bootstrap failure returns `upstream_error` with no fallback dispatch

## Final Assessment

The deterministic error taxonomy added by Phase 45 is locally well covered, but the core safety promise is not achieved yet. Because the runner callback trusts model-supplied tool-call context over operator-supplied policy context, Phase 45 should remain **unverified** until that bypass is removed and covered by regression tests.
