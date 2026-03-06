---
phase: 49
slug: adk-real-runner-staging-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 49 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `backend-hormonia/pyproject.toml` |
| **Quick run command** | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q` |
| **Full suite command** | `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py tests/api/v2/test_adk.py tests/unit/test_adk_tools_runtime.py tests/unit/test_pii_safe_adk_wrapper.py -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token pytest tests/unit/test_adk_runner_integration.py -q`
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 49-01-01 | 01 | 1 | ADK-11 | integration | `pytest tests/unit/test_adk_runner_integration.py -q -k "policy_block"` | ❌ W0 | ⬜ pending |
| 49-01-02 | 01 | 1 | ADK-11 | integration | `pytest tests/unit/test_adk_runner_integration.py -q -k "policy_block and no_side_effect"` | ❌ W0 | ⬜ pending |
| 49-01-03 | 01 | 1 | ADK-11 | integration | `pytest tests/unit/test_adk_runner_integration.py -q -k "policy_block and repeated"` | ❌ W0 | ⬜ pending |
| 49-01-04 | 01 | 1 | ADK-12 | integration | `pytest tests/unit/test_adk_runner_integration.py -q -k "upstream_error and no_fallback"` | ❌ W0 | ⬜ pending |
| 49-01-05 | 01 | 1 | ADK-09 | integration | `pytest tests/unit/test_adk_runner_integration.py -q -k "cancel"` | ❌ W0 | ⬜ pending |
| 49-02-01 | 02 | 2 | ADK-11, ADK-12 | doc | manual review of 45-VERIFICATION.md update | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_adk_runner_integration.py` — add policy_block test with real runner (ADK-11)
- [ ] `tests/unit/test_adk_runner_integration.py` — add repeated policy_block determinism test (ADK-11)
- [ ] `tests/unit/test_adk_runner_integration.py` — add no-fallback-dispatch assertion for upstream_error (ADK-12)
- [ ] `tests/unit/test_adk_runner_integration.py` — add cancel-with-real-runner test (ADK-09)
- [ ] No new framework install needed — google-adk is already in requirements.txt

*Existing infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Multi-instance cancel across Cloud Run instances | ADK-09 | Requires multiple Cloud Run instances sharing Redis | Single-process async cancel with real runner proves mechanics; cross-instance routing proven by existing session store tests. Document reasoning in verification artifact. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
