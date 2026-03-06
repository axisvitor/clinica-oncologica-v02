---
phase: 47
slug: adk-ci-smoke-gate
status: human_needed
verified_on: 2026-03-05
requirements:
  - ADK-13
verifier: Codex
---

# Phase 47 Verification

## Verdict

Phase 47 is **verified in repository and local test evidence**, but it still needs **human verification** before final closeout because ADK-13 requires a real GitHub Actions run to prove the new `smoke-adk` job actually blocks and then releases the deploy path.

## Must-Have Checks

| Check | Requirement | Result | Evidence |
|---|---|---|---|
| Smoke suite covers sentiment, humanize, variation, and empathy success trajectories | ADK-13 | Pass in local evidence | `backend-hormonia/tests/smoke/test_adk_smoke.py:18-81`; `backend-hormonia/tests/smoke/test_adk_smoke.py:155-177` |
| Each critical tool has a policy-block smoke trajectory that prevents domain execution | ADK-13 | Pass in local evidence | `backend-hormonia/tests/smoke/test_adk_smoke.py:135-152`; `backend-hormonia/tests/smoke/test_adk_smoke.py:180-214` |
| Unsupported tool invocations are surfaced explicitly instead of as generic runtime errors | ADK-13 | Pass in local evidence | `backend-hormonia/app/ai/adk/runtime.py:127-147`; `backend-hormonia/tests/smoke/test_adk_smoke.py:217-234` |
| CI pipeline has an independent `smoke-adk` job that runs only `pytest -m adk_smoke` and uploads a JUnit artifact | ADK-13 | Pass in repository evidence | `.github/workflows/ci.yml:220-270` |
| `build-backend` and `ci-status` are blocked when `smoke-adk` fails | ADK-13 | Pass in repository evidence | `.github/workflows/ci.yml:383-387`; `.github/workflows/ci.yml:443-466` |
| Pipeline reaches the deploy path when all smoke scenarios pass with no manual bypass | ADK-13 | Not run | `47-VALIDATION.md:41-68` marks this as a manual-only GitHub Actions verification |

## Requirement Coverage

| Requirement | Status | Notes |
|---|---|---|
| ADK-13 | Pass in local and repository evidence, human verification still needed | The repository now contains the smoke suite, explicit unsupported-tool semantics, and a CI dependency chain that should block deploy on smoke failure. The remaining gap is an actual GitHub Actions run proving the configured workflow behaves as intended end to end. |

## Evidence

### 1. Phase 47 delivered the planned smoke coverage

- The roadmap still defines Phase 47 as the ADK CI smoke gate and requires ADK-13 at `.planning/ROADMAP.md:86-98`.
- The smoke suite now exists at `backend-hormonia/tests/smoke/test_adk_smoke.py:1-234` and uses the `adk_smoke` marker registered in `backend-hormonia/pyproject.toml`.
- Success coverage is parameterized across the four oncology tools in `backend-hormonia/tests/smoke/test_adk_smoke.py:18-81` and `backend-hormonia/tests/smoke/test_adk_smoke.py:155-177`.
- Policy-block coverage is parameterized across the same four tools in `backend-hormonia/tests/smoke/test_adk_smoke.py:135-152` and `backend-hormonia/tests/smoke/test_adk_smoke.py:180-214`.
- Unsupported-tool coverage is explicit in `backend-hormonia/tests/smoke/test_adk_smoke.py:217-234`.

### 2. Runtime semantics now match the smoke contract

- Missing tool names now emit `status="unsupported_tool"` and record the same status in metrics at `backend-hormonia/app/ai/adk/runtime.py:127-147`.
- That matters because ADK-13 needs smoke failures to be diagnosable as configuration/runtime contract regressions rather than a generic error bucket.
- The matching runtime regression was updated in `backend-hormonia/tests/unit/test_adk_tools_runtime.py:1300-1321`.

### 3. Local validation commands are green

- Local collect-only verification on 2026-03-05:

```bash
cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/smoke/test_adk_smoke.py --collect-only -q
```

Observed result: `tests/smoke/test_adk_smoke.py: 9`

- Local smoke execution on 2026-03-05:

```bash
cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/smoke/test_adk_smoke.py -q -x
```

Observed result: `9 passed`

- Existing ADK regression suite rerun on 2026-03-05:

```bash
cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/unit/test_adk_tools_runtime.py tests/api/v2/test_adk.py -q -x
```

Observed result: exit code `0`

### 4. CI gating is wired correctly in the repository

- The dedicated `smoke-adk` job is defined at `.github/workflows/ci.yml:220-270`, depends only on `lint-backend`, and runs `pytest -m adk_smoke --tb=short -v --junitxml=adk-smoke-report.xml`.
- The job exports `WHATSAPP_WUZAPI_TOKEN=smoke-ci-token`, `TESTING=true`, and `ENVIRONMENT=test`, which matches the local bootstrap requirement found during verification.
- `build-backend` waits on `smoke-adk` via `.github/workflows/ci.yml:383-387`.
- `ci-status` depends on `smoke-adk` and fails if `needs.smoke-adk.result != "success"` via `.github/workflows/ci.yml:443-466`.
- `REQUIREMENTS.md` now traces ADK-13 to Phase 47 as complete at `.planning/REQUIREMENTS.md:56-68`.

## Remaining Human Validation

These are the only remaining blockers to marking the whole phase as fully passed:

1. Push the current branch and confirm the GitHub Actions run shows a standalone `smoke-adk` check before `build-backend`.
2. Force one smoke scenario to fail in a temporary branch or commit, then confirm `smoke-adk` fails and `build-backend` plus `ci-status` are blocked automatically.
3. Restore the passing smoke suite and confirm the same workflow proceeds through `smoke-adk` to `build-backend` with no manual bypass.

## Final Assessment

Phase 47 satisfies ADK-13 in code and local regression evidence: the repository has the required oncology smoke suite and the CI dependency chain needed to block deploy when those critical trajectories regress. The only missing evidence is a real GitHub Actions execution proving the configured gate behaves that way in the hosted CI environment.

**Final status: `human_needed`**
