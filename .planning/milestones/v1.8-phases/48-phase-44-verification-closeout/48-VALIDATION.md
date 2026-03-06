---
phase: 48
slug: phase-44-verification-closeout
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-03-06
---

# Phase 48 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `backend-hormonia/pyproject.toml` |
| **Quick run command** | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py -q` |
| **Full suite command** | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick suite
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 48-01-01 | 01 | 1 | ADK-09 | unit | `pytest tests/unit/test_adk_tools_runtime.py -q -k "timeout"` | ✅ | ⬜ pending |
| 48-01-02 | 01 | 1 | ADK-09 | unit | `pytest tests/unit/test_adk_tools_runtime.py -q -k "limit"` | ✅ | ⬜ pending |
| 48-01-03 | 01 | 1 | ADK-09 | unit | `pytest tests/unit/test_adk_tools_runtime.py -q -k "cancel"` | ✅ | ⬜ pending |
| 48-01-04 | 01 | 1 | ADK-09 | API | `pytest tests/api/v2/test_adk.py -q -k "cancel"` | ✅ | ⬜ pending |
| 48-01-05 | 01 | 1 | ADK-10 | unit | `pytest tests/unit/test_adk_tools_runtime.py -q -k "auto_creates_session"` | ✅ | ⬜ pending |
| 48-01-06 | 01 | 1 | ADK-10 | unit | `pytest tests/unit/test_adk_tools_runtime.py -q -k "close_session"` | ✅ | ⬜ pending |
| 48-01-07 | 01 | 1 | ADK-10 | unit | `pytest tests/unit/test_adk_tools_runtime.py -q -k "rejects_closed"` | ✅ | ⬜ pending |
| 48-01-08 | 01 | 1 | ADK-10 | unit | `pytest tests/unit/test_adk_tools_runtime.py -q -k "prune"` | ✅ | ⬜ pending |
| 48-01-09 | 01 | 1 | ADK-10 | unit | `pytest tests/unit/test_adk_tools_runtime.py -q -k "oversized"` | ✅ | ⬜ pending |
| 48-01-10 | 01 | 1 | ADK-10 | API | `pytest tests/api/v2/test_adk.py -q -k "close"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Multi-instance cancel confirmation | ADK-09 | Requires staging with 2+ Cloud Run instances | Deferred to Phase 49 (ADK Real Runner & Staging Validation) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
