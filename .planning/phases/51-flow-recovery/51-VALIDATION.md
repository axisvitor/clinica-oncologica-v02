---
phase: 51
slug: flow-recovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 51 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio (asyncio_mode=auto) |
| **Config file** | `backend-hormonia/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend-hormonia && python -m pytest tests/unit/tasks/test_stuck_detection.py tests/unit/services/flow/test_flow_recovery.py tests/unit/api/test_admin_flow_ops.py -x -q` |
| **Full suite command** | `cd backend-hormonia && python -m pytest tests/unit/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend-hormonia && python -m pytest tests/unit/tasks/test_stuck_detection.py tests/unit/services/flow/test_flow_recovery.py tests/unit/api/test_admin_flow_ops.py -x -q`
- **After every plan wave:** Run `cd backend-hormonia && python -m pytest tests/unit/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 51-01-01 | 01 | 1 | RECV-01 | unit | `pytest tests/unit/tasks/test_stuck_detection.py -x` | W0 | pending |
| 51-02-01 | 02 | 1 | RECV-02 | unit | `pytest tests/unit/services/flow/test_flow_recovery.py -x` | W0 | pending |
| 51-02-02 | 02 | 1 | RECV-03 | unit | `pytest tests/unit/api/test_admin_flow_ops.py -x` | W0 | pending |
| 51-03-01 | 03 | 2 | RECV-04 | unit | `pytest tests/unit/api/test_admin_flow_ops.py::test_list_failed_ops -x` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/tasks/test_stuck_detection.py` — stubs for RECV-01 (detector finds stuck flows, respects threshold, handles empty results)
- [ ] `tests/unit/services/flow/test_flow_recovery.py` — stubs for RECV-02 (resend vs advance decision, recovery attempt tracking, max recovery limit)
- [ ] `tests/unit/api/test_admin_flow_ops.py` — stubs for RECV-03, RECV-04 (unstick, advance, reset endpoints; failed ops query)

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
