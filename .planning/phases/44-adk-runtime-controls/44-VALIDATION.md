---
phase: 44
slug: adk-runtime-controls
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-05
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `backend-hormonia/pyproject.toml` |
| **Quick run command** | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py -q` |
| **Full suite command** | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py -q`
- **After every plan wave:** Run `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 1 | ADK-09, ADK-10 | API contract | `cd backend-hormonia && pytest tests/api/v2/test_adk.py -q` | ✅ | ✅ green |
| 44-01-02 | 01 | 1 | ADK-10 | unit | `cd backend-hormonia && pytest tests/unit/test_adk_tools_runtime.py -q -k "session or lifecycle"` | ✅ | ✅ green |
| 44-02-01 | 02 | 2 | ADK-09 | unit | `cd backend-hormonia && pytest tests/unit/test_adk_tools_runtime.py -q -k "timeout or limit"` | ✅ | ✅ green |
| 44-02-02 | 02 | 2 | ADK-09 | API + unit | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py -q -k "cancel or invocation"` | ✅ | ✅ green |
| 44-03-01 | 03 | 3 | ADK-10 | unit | `cd backend-hormonia && pytest tests/unit/test_adk_tools_runtime.py -q -k "prune or close or resume"` | ✅ | ✅ green |
| 44-03-02 | 03 | 3 | ADK-09, ADK-10 | regression | `cd backend-hormonia && pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing pytest infrastructure in `backend-hormonia/pyproject.toml`
- [x] Existing route/runtime/wrapper tests to extend
- [x] ADK runtime-real environment remains conditional in local execution; `google-adk` coverage is preserved behind skip logic

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-instance cancel confirmation under real multi-instance topology | ADK-09 | Local pytest can mock state transitions but cannot fully prove production load-balancer routing behavior alone | In a staging-like multi-instance environment, start a long-running invocation, issue explicit cancel from a second request, confirm final status is `cancelled` and no late output is returned |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or existing infrastructure coverage
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 30s for quick checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** passed on 2026-03-05
