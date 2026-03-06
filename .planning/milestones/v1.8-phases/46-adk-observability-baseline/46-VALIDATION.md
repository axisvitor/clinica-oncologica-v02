---
phase: 46
slug: adk-observability-baseline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 46 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 |
| **Config file** | `backend-hormonia/pyproject.toml` |
| **Quick run command** | `cd backend-hormonia && pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py -q` |
| **Full suite command** | `cd backend-hormonia && pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend-hormonia && pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py -q`
- **After every plan wave:** Run `cd backend-hormonia && pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 46-01-01 | 01 | 0 | OBS-02-a | unit | `pytest tests/unit/test_adk_metrics.py::test_histogram_records_duration -x` | ❌ W0 | ⬜ pending |
| 46-01-02 | 01 | 0 | OBS-02-b | unit | `pytest tests/unit/test_adk_metrics.py::test_counter_increments -x` | ❌ W0 | ⬜ pending |
| 46-01-03 | 01 | 0 | OBS-02-c | unit | `pytest tests/unit/test_adk_metrics.py::test_in_flight_gauge -x` | ❌ W0 | ⬜ pending |
| 46-01-04 | 01 | 0 | OBS-02-d | unit | `pytest tests/unit/test_adk_metrics.py::test_structured_log_emitted -x` | ❌ W0 | ⬜ pending |
| 46-01-05 | 01 | 1 | OBS-02-e | unit | `pytest tests/unit/test_adk_tools_runtime.py -k "metrics" -x` | ❌ W0 | ⬜ pending |
| 46-01-06 | 01 | 1 | OBS-02-f | unit | `pytest tests/unit/test_adk_tools_runtime.py -x` | ✅ | ⬜ pending |
| 46-01-07 | 01 | 1 | OBS-02-g | integration | `pytest tests/api/v2/test_adk.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_adk_metrics.py` — stubs for OBS-02-a/b/c/d (new file)
- [ ] `app/ai/adk/metrics.py` — Prometheus instruments + record helper (new file)
- [ ] Metrics integration tests inside `tests/unit/test_adk_tools_runtime.py` — verify run_adk_tool records metrics for success/error/timeout/policy_block statuses

*Existing infrastructure covers framework and config; only ADK-specific test/metric files are missing.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prometheus scrape works in Cloud Run | OBS-02 | Depends on production scraper config | Deploy to staging, hit `/metrics`, verify `adk_*` series appear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
