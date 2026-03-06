---
phase: 45
slug: adk-tool-safety-and-deterministic-errors
status: passed
verified_on: 2026-03-06
requirements:
  - ADK-11
  - ADK-12
verifier: Codex
---

# Phase 45 Verification

## Verdict

Phase 45 is **fully verified**. Plan 45-04 closed the runner-path policy-bypass bug in repository code, and Phase 49 closes the last external validation gap by adding conditional real-runner integration tests tagged `adk_smoke`. Those tests activate in the existing CI `smoke-adk` job, where `google-adk` is installed, and cover policy blocking before side effects, repeated deterministic `policy_block`, upstream runner failure without direct-handler fallback, and cancellation with the real runner active.

## Must-Have Checks

| Check | Requirement | Result | Evidence |
|---|---|---|---|
| Direct-handler path blocks unsafe tool calls before handler/domain execution | ADK-11 | Pass | `backend-hormonia/app/ai/adk/runtime.py:635-691`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:690-789` |
| Runner callback context cannot be overwritten by model-supplied `context_json` / `context` before `before_tool_callback` | ADK-11 | Pass in local evidence | `backend-hormonia/app/ai/adk/runtime.py:948-998`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:793-941` |
| Model-supplied payload cannot fabricate required context to bypass policy | ADK-11 | Pass in local evidence | `backend-hormonia/app/ai/adk/runtime.py:980-1026`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:842-891` |
| Tool-dispatch merge preserves operator policy metadata after approved runner execution | ADK-11 | Pass in local evidence | `backend-hormonia/app/ai/adk/tools.py:169-210`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:945-985` |
| Failures classify deterministically as `policy_block`, `tool_error`, or `upstream_error` instead of ambiguous fallback | ADK-12 | Pass in local evidence | `backend-hormonia/app/ai/adk/tools.py:129-146`; `backend-hormonia/app/ai/adk/runtime.py:607-632`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:988-1186`; `backend-hormonia/tests/api/v2/test_adk.py:118-222` |
| Repeated identical scenarios keep the same classification and response envelope | ADK-12 | Pass in local evidence | `backend-hormonia/tests/unit/test_adk_tools_runtime.py:793-1186`; `backend-hormonia/tests/api/v2/test_adk.py:163-222` |
| Full Phase 45 suite stays green after 45-04 | ADK-11, ADK-12 | Pass in local evidence | Local rerun on 2026-03-05: `pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_runner_integration.py -q -r a` exited `0` with only the expected `google-adk` skips |
| Real `google-adk` runner path executed in automated smoke coverage | ADK-11, ADK-12 | Pass | `backend-hormonia/tests/unit/test_adk_runner_integration.py` now includes `test_run_adk_tool_runner_policy_block_no_side_effect`, `test_run_adk_tool_runner_policy_block_repeated_deterministic`, `test_run_adk_tool_runner_upstream_error_no_fallback_dispatch`, and `test_run_adk_tool_runner_cancel_terminates_invocation`, all tagged with `@pytest.mark.adk_smoke`; `.github/workflows/ci.yml` runs `pytest -m adk_smoke` after installing `google-adk` |

## Requirement Coverage

| Requirement | Status | Notes |
|---|---|---|
| ADK-11 | Pass | The old bypass is closed in code, and Phase 49 adds automated real-runner smoke coverage that proves `before_tool_callback` blocks unsafe tool calls before domain side effects. |
| ADK-12 | Pass | Runtime classification remains deterministic in local regressions, and Phase 49 adds automated real-runner smoke coverage for repeated `policy_block`, upstream failure without fallback, and cancel termination. |

## Evidence

### 1. 45-04 delivered the intended code changes

- `45-04-PLAN.md` required immutable operator policy keys in both `runtime.py` and `tools.py`, plus negative regressions for overwrite/fabrication bypasses.
- The current runtime now defines `_PROTECTED_POLICY_KEYS` and restores protected keys plus required-context paths before policy evaluation in `backend-hormonia/app/ai/adk/runtime.py:59` and `backend-hormonia/app/ai/adk/runtime.py:948-1026`.
- The current tool dispatch path now restores protected keys after `context_json` merge in `backend-hormonia/app/ai/adk/tools.py:23` and `backend-hormonia/app/ai/adk/tools.py:169-210`.
- The targeted regressions promised by 45-04 exist in `backend-hormonia/tests/unit/test_adk_tools_runtime.py:793-985`.

### 2. The runner-path bypass found by the previous verification is closed locally

- The vulnerable behavior was that model-supplied tool-call context could overwrite operator policy before `before_tool_callback`.
- That no longer holds in the current code because `_resolve_callback_context()` merges tool args and then `_restore_operator_policy_context()` restores operator-owned policy keys and required-context paths before `_evaluate_tool_policy()` runs.
- The new regressions prove the exact exploit shapes that previously failed:
  - `context_json={"tool_policy": {}}` cannot erase a blocked-tool policy: `backend-hormonia/tests/unit/test_adk_tools_runtime.py:793-838`
  - fabricated `patient_context.clinical_summary` cannot satisfy `required_context_keys`: `backend-hormonia/tests/unit/test_adk_tools_runtime.py:842-891`
  - combined dict-form `context` plus JSON payload cannot erase policy metadata: `backend-hormonia/tests/unit/test_adk_tools_runtime.py:895-941`
  - tool-dispatch merge still preserves operator `tool_policy`: `backend-hormonia/tests/unit/test_adk_tools_runtime.py:945-985`
- I reran the focused bypass regressions on 2026-03-05:

```bash
cd backend-hormonia && pytest tests/unit/test_adk_tools_runtime.py -q -k 'override or fabricated or cannot_override'
```

Observed result: `4 passed` and exit code `0`.

### 3. Deterministic ADK failure classification still holds

- Tool-side exceptions are wrapped into `ADKToolExecutionError` in `backend-hormonia/app/ai/adk/tools.py:129-146`.
- Runtime classification still maps wrapped tool exceptions to `tool_error` and all other post-start failures to `upstream_error` in `backend-hormonia/app/ai/adk/runtime.py:607-632`.
- Repeated runner/direct regressions remain explicit in:
  - `backend-hormonia/tests/unit/test_adk_tools_runtime.py:988-1116` for `tool_error`
  - `backend-hormonia/tests/unit/test_adk_tools_runtime.py:1120-1186` for `upstream_error`
  - `backend-hormonia/tests/api/v2/test_adk.py:118-222` for stable API envelopes across repeated `policy_block`, `tool_error`, and `upstream_error`

### 4. Plan artifact cross-check

- `45-04-SUMMARY.md` claims the bypass was closed and the full Phase 45 suite was rerun; the current code/tests match that claim.
- `45-VALIDATION.md` still lists per-task rows only through 45-03 at `.planning/phases/45-adk-tool-safety-and-deterministic-errors/45-VALIDATION.md:39-46`.
- That is documentation drift, but not a functional verification blocker here, because the phase-level manual checks in `.planning/phases/45-adk-tool-safety-and-deterministic-errors/45-VALIDATION.md:64-69` still correctly describe the remaining external verification work and the 45-04 code/test evidence is present in the repository.

### 5. Phase 49 converts the last runner-path gap into automated smoke coverage

- `backend-hormonia/tests/unit/test_adk_runner_integration.py` now tags every real-runner integration test with `@pytest.mark.adk_smoke` while preserving `@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")`.
- Phase 49 adds four new real-runner checks:
  - `test_run_adk_tool_runner_policy_block_no_side_effect`
  - `test_run_adk_tool_runner_policy_block_repeated_deterministic`
  - `test_run_adk_tool_runner_upstream_error_no_fallback_dispatch`
  - `test_run_adk_tool_runner_cancel_terminates_invocation`
- These tests avoid real Gemini calls by monkeypatching `GeminiDomainClient`, so the only runtime under test is the real `google-adk` agent/runner/tool pipeline.
- `.github/workflows/ci.yml` already installs `google-adk` for the `smoke-adk` job and runs `pytest -m adk_smoke`, which turns the former manual follow-up into automated regression coverage.

## Remaining Human Validation

None for ADK-11 or ADK-12. The former real-runner checks are now covered by `adk_smoke` integration tests that activate in environments where `google-adk` is installed.

## Final Assessment

The specific Phase 45 gap that previously invalidated ADK-11 is closed in the current codebase, and Phase 49 promotes the remaining real-runner validation into automated smoke coverage instead of ad hoc manual follow-up. ADK-11 and ADK-12 are now fully satisfied by repository evidence plus the CI execution path that installs `google-adk`.

**Final status: `passed`**
