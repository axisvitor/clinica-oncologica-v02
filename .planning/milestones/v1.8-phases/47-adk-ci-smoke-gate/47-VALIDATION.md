---
phase: 47
slug: adk-ci-smoke-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.0 with pytest-asyncio (auto mode) |
| **Config file** | `backend-hormonia/pyproject.toml` |
| **Quick run command** | `cd backend-hormonia && pytest -m adk_smoke -x -q` |
| **Full suite command** | `cd backend-hormonia && pytest -m adk_smoke -v --tb=short --junitxml=adk-smoke-report.xml` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend-hormonia && pytest -m adk_smoke -x -q`
- **After every plan wave:** Run `cd backend-hormonia && pytest -m adk_smoke -v --tb=short --junitxml=adk-smoke-report.xml`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | ADK-13 | config | `pytest -m adk_smoke --collect-only` | No — W0 | pending |
| 47-01-02 | 01 | 1 | ADK-13 | smoke | `pytest -m adk_smoke -x -q` | No — W0 | pending |
| 47-01-03 | 01 | 1 | ADK-13 | CI | Manual: verify `needs` chain in `ci.yml` | No — W0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/smoke/__init__.py` — empty init for test discovery
- [ ] `tests/smoke/test_adk_smoke.py` — smoke test module with `@pytest.mark.adk_smoke`
- [ ] `pyproject.toml` — register `adk_smoke` marker
- [ ] `.github/workflows/ci.yml` — add `smoke-adk` job and wire into dependency chain

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI job blocks deploy on smoke failure | ADK-13b | Requires actual GitHub Actions run | Push branch, verify `smoke-adk` job appears in checks, verify `build-backend` waits for it |
| CI passes without manual bypass | ADK-13c | Requires actual GitHub Actions run | Push branch with all smoke tests passing, verify pipeline completes to deploy stage |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
