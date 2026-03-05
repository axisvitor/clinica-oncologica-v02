---
phase: 45
slug: adk-tool-safety-and-deterministic-errors
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-05
---

# Phase 45 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `backend-hormonia/pyproject.toml` |
| **Quick run command** | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py -q` |
| **Full suite command** | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q` |
| **Estimated runtime** | ~40 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py -q`
- **After every plan wave:** Run `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 40 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 45-01-01 | 01 | 1 | ADK-11 | unit | `cd backend-hormonia && pytest tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py -q -k "policy or sanitize"` | ✅ | ✅ green |
| 45-01-02 | 01 | 1 | ADK-11, ADK-12 | API + unit | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py -q -k "policy_block or tool_policy"` | ✅ | ✅ green |
| 45-02-01 | 02 | 2 | ADK-12 | unit | `cd backend-hormonia && pytest tests/unit/test_adk_tools_runtime.py -q -k "tool_error or upstream_error"` | ✅ | ✅ green |
| 45-02-02 | 02 | 2 | ADK-12 | API + unit | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q -k "tool_error or upstream_error"` | ✅ | ✅ green |
| 45-03-01 | 03 | 3 | ADK-11, ADK-12 | regression + conditional integration | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q` | ✅ | ✅ green |
| 45-03-02 | 03 | 3 | ADK-11, ADK-12 | docs + audit | `rg -n "45-01-01|45-02-01|45-03-01|policy_block|tool_error|upstream_error" .planning/phases/45-adk-tool-safety-and-deterministic-errors/45-VALIDATION.md` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing pytest infrastructure in `backend-hormonia/pyproject.toml`
- [x] Existing ADK route/runtime/wrapper/runner test files are already present
- [x] Conditional `google-adk` coverage remains behind skip logic in `tests/unit/test_adk_runner_integration.py`

*Repeated `policy_block` determinism is locked in the API/unit/wrapper suite today; repeated real-ADK `tool_error` / `upstream_error` coverage activates automatically when `google-adk` is installed, without expanding Phase 45 into CI smoke gating.*

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real ADK deployment blocks an unsafe tool call before any external side effect | ADK-11 | Local pytest proves the direct path and fake-runner callback path, but a staging-like ADK environment is still the only place to confirm the packaged `before_tool_callback` chain around real deployment wiring | In staging, send the same blocked payload twice and confirm the API returns `policy_block` both times, the tool handler is never executed, and no downstream side effect is observed |
| Runner bootstrap/import failure in a staging-like environment does not fall through to direct tool execution | ADK-12 | Local pytest and conditional integration tests prove the deterministic classification contract, but cannot fully prove deployment packaging/import drift across production-like ADK environments | In staging, force the ADK runner/bootstrap path to fail before tool execution begins and confirm the API returns `upstream_error`, the tool handler does not execute, and no side effect is observed |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or existing infrastructure coverage
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 40s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** passed on 2026-03-05
