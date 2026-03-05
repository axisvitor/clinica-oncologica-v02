---
phase: 45
slug: adk-tool-safety-and-deterministic-errors
status: draft
nyquist_compliant: false
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
| **Quick run command** | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py -q` |
| **Full suite command** | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_runner_integration.py -q` |
| **Estimated runtime** | ~40 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py -q`
- **After every plan wave:** Run `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_runner_integration.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 40 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 45-01-01 | 01 | 1 | ADK-11 | unit | `cd backend-hormonia && pytest tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py -q` | ✅ | ⬜ pending |
| 45-01-02 | 01 | 1 | ADK-11, ADK-12 | API + unit | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py -q` | ✅ | ⬜ pending |
| 45-02-01 | 02 | 2 | ADK-12 | unit | `cd backend-hormonia && pytest tests/unit/test_adk_tools_runtime.py -q` | ✅ | ⬜ pending |
| 45-02-02 | 02 | 2 | ADK-12 | API + unit | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q` | ✅ | ⬜ pending |
| 45-03-01 | 03 | 3 | ADK-11, ADK-12 | regression | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_runner_integration.py -q` | ✅ | ⬜ pending |
| 45-03-02 | 03 | 3 | ADK-11, ADK-12 | docs + audit | `rg -n "45-01-01|45-02-01|45-03-01|policy_block|tool_error|upstream_error" .planning/phases/45-adk-tool-safety-and-deterministic-errors/45-VALIDATION.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing pytest infrastructure in `backend-hormonia/pyproject.toml`
- [x] Existing ADK route/runtime/wrapper/runner test files are already present
- [x] Conditional `google-adk` coverage remains behind skip logic in `tests/unit/test_adk_runner_integration.py`

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Runner bootstrap/import failure in a staging-like environment does not fall through to direct tool execution | ADK-12 | Local pytest can simulate the classification path, but cannot fully prove deployment packaging/import drift across production-like ADK environments | In staging, force the ADK runner/bootstrap path to fail before tool execution begins and confirm the API returns `upstream_error`, the tool handler does not execute, and no side effect is observed |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or existing infrastructure coverage
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
