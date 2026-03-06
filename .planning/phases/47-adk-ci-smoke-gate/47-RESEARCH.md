# Phase 47: ADK CI Smoke Gate - Research

**Researched:** 2026-03-06
**Domain:** CI/CD pipeline integration, pytest marker-based test selection, GitHub Actions workflow gating
**Confidence:** HIGH

## Summary

Phase 47 must wire a dedicated ADK smoke test suite into the existing CI pipeline so that regressions in critical oncology ADK trajectories block deploy automatically. The codebase already has a comprehensive ADK test suite across five files (`test_adk.py`, `test_adk_tools_runtime.py`, `test_adk_metrics.py`, `test_adk_runner_integration.py`, `test_adk_run_guard_regression.py`) that exercises all four domain tools (sentiment, humanize, variation, empathy), all terminal statuses (success, timeout, policy_block, tool_error, upstream_error, cancelled, limit_exceeded), and the session lifecycle. The gap is that these tests are not tagged as smoke, not collected as a distinct CI job, and the deploy pipeline has no dependency on them.

The primary CI workflow (`ci.yml`) runs all backend tests as a monolithic `pytest tests/` invocation. The deploy workflows (`cd-staging.yml`, `railway-deploy.yml`, `cd-production.yml`) depend on test-backend jobs but do not isolate ADK smoke scenarios. The approach is: (1) define a `pytest.mark.adk_smoke` marker, (2) write a dedicated smoke test module that covers the critical oncology domain trajectories through the runtime boundary, (3) add a new GitHub Actions job `smoke-adk` to `ci.yml` that runs only `pytest -m adk_smoke`, (4) wire that job as a required dependency of the build/deploy jobs and the `ci-status` check.

**Primary recommendation:** Use a new `adk_smoke` pytest marker and a dedicated `tests/smoke/test_adk_smoke.py` module to define scenario-per-tool coverage for the four oncology tools, then add a standalone `smoke-adk` job to `ci.yml` that blocks deploy on failure.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADK-13 | Time pode bloquear deploy quando trajetorias smoke ADK de fluxos oncologicos criticos regressam no CI. | Pytest marker for `adk_smoke`, dedicated CI job in `ci.yml`, wired as dependency of `ci-status` and `build-backend` jobs |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=7.0 | Test framework, marker-based selection | Already project standard in `pyproject.toml` |
| pytest-asyncio | auto mode | Async test execution for ADK runtime | Already configured in `pyproject.toml` |
| GitHub Actions | v4 actions | CI orchestration and deploy gating | Already project CI platform |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-mock | any | Monkeypatching for domain client isolation | Already used in existing ADK tests |
| prometheus_client | any | Metric verification in smoke tests | Already imported in ADK test suite |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pytest markers | Separate test directory filtering | Markers are more flexible and compose with existing `pytest` config; directory-only selection is brittle if tests move |
| Dedicated workflow file | Job in existing `ci.yml` | A new workflow adds management overhead; a job in `ci.yml` reuses existing Python/env setup and is simpler to wire as dependency |

**Installation:**
```bash
# No new packages needed - all dependencies already present
```

## Architecture Patterns

### Recommended Project Structure
```
backend-hormonia/
├── tests/
│   ├── smoke/
│   │   ├── __init__.py
│   │   └── test_adk_smoke.py      # NEW: marked @pytest.mark.adk_smoke
│   ├── unit/
│   │   ├── test_adk_tools_runtime.py  # EXISTING: no changes
│   │   ├── test_adk_metrics.py        # EXISTING: no changes
│   │   └── ...
│   ├── api/v2/
│   │   └── test_adk.py               # EXISTING: no changes
│   └── conftest.py
├── pyproject.toml                     # ADD: adk_smoke marker registration
└── .github/workflows/
    └── ci.yml                         # ADD: smoke-adk job, wire as dependency
```

### Pattern 1: Pytest Marker for Smoke Selection
**What:** Register `adk_smoke` in `pyproject.toml` markers, apply to critical scenario tests, run with `pytest -m adk_smoke`.
**When to use:** Any time we need a tagged subset of tests runnable independently.
**Example:**
```python
# pyproject.toml
markers = [
    # ... existing markers ...
    "adk_smoke: ADK smoke tests for critical oncology trajectories",
]

# tests/smoke/test_adk_smoke.py
import pytest

@pytest.mark.adk_smoke
@pytest.mark.asyncio
async def test_sentiment_trajectory_success(monkeypatch):
    """Smoke: sentiment tool returns success for standard oncology input."""
    ...
```

### Pattern 2: Oncology Domain Trajectory Test
**What:** Each smoke test exercises a complete oncology domain trajectory through `run_adk_tool()` with monkeypatched domain client, asserting the status and response structure.
**When to use:** The four tools (sentiment, humanize, variation, empathy) each get at least one success trajectory and one failure trajectory.
**Example:**
```python
@pytest.mark.adk_smoke
@pytest.mark.asyncio
async def test_sentiment_success_trajectory(adk_runtime_store, monkeypatch):
    """Oncology critical: patient sentiment analysis returns success."""
    class FakeClient:
        async def analyze_response_sentiment(self, *, response, patient_context):
            return {"sentiment": "negative", "confidence": 0.92}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient)

    result = await run_adk_tool(ADKToolRunRequest(
        prompt="Paciente relata nausea persistente apos quimioterapia",
        tool_name="sentiment",
        deps=AIDeps(gemini_api_key="test", model_name="gemini-2.0-flash"),
        user_id="smoke-user",
        session=ADKSessionControls(action="create"),
        context={"patient_context": {"tumor_type": "mama", "treatment_cycle": "Q3"}},
    ))

    assert result["status"] == "success"
    assert "result" in result
```

### Pattern 3: CI Job as Deploy Gate
**What:** A new `smoke-adk` job in `ci.yml` runs `pytest -m adk_smoke` and is added to the `needs` list of `build-backend` and `ci-status`.
**When to use:** When deploy must be blocked on smoke failure.
**Example:**
```yaml
smoke-adk:
  name: ADK Smoke Tests
  runs-on: ubuntu-latest
  timeout-minutes: 5
  needs: [lint-backend]
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.13'
    - name: Install dependencies
      working-directory: backend-hormonia
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-mock
    - name: Run ADK smoke tests
      working-directory: backend-hormonia
      env:
        TESTING: "true"
        ENVIRONMENT: test
      run: |
        pytest -m adk_smoke --tb=short -v --junitxml=adk-smoke-report.xml
    - uses: actions/upload-artifact@v4
      if: always()
      with:
        name: adk-smoke-results
        path: backend-hormonia/adk-smoke-report.xml
        retention-days: 7
```

### Anti-Patterns to Avoid
- **Running smoke tests inside the monolithic test-backend job:** This defeats the purpose of a fast, isolated gate. The smoke suite must be a separate job so its pass/fail verdict is independently visible and can independently block deploy.
- **Requiring real google-adk for smoke tests:** The project documents that `google-adk` is conditionally available. Smoke tests must work with monkeypatched domain clients so they run on any CI runner without API keys. The `HAS_ADK` guard pattern already exists in `test_adk_runner_integration.py`.
- **Making smoke tests slow:** Smoke tests should complete in under 30 seconds total. No real LLM calls, no database, no Redis. Only runtime boundary verification with fakes.
- **Duplicating existing test logic:** Smoke tests should exercise the `run_adk_tool()` boundary (or the API endpoint via `TestClient`), not re-implement the unit-level assertions already in `test_adk_tools_runtime.py`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test selection for CI subset | Custom test runner script | `pytest -m adk_smoke` with registered marker | Pytest markers are the standard mechanism; custom scripts are fragile and don't integrate with pytest plugins |
| CI job dependency gating | Custom status-check script | GitHub Actions `needs:` directive | Built-in, atomic, shows status clearly in PR checks UI |
| JUnit report for CI visibility | Custom report format | `pytest --junitxml` | Standard format, works with GitHub Actions upload-artifact and status annotations |

**Key insight:** The CI gate is pure infrastructure wiring. The test logic already exists in the runtime boundary tests. Smoke tests just need to be a curated subset with a marker.

## Common Pitfalls

### Pitfall 1: Smoke tests that depend on google-adk being installed
**What goes wrong:** CI runners may not have google-adk installed or it may conflict with other dependencies. Tests fail with ImportError before exercising any logic.
**Why it happens:** The existing `test_adk_runner_integration.py` uses `@pytest.mark.skipif(not HAS_ADK, ...)` which means those tests are skipped in most environments.
**How to avoid:** Smoke tests must exercise the `run_adk_tool()` direct-handler fallback path (which works without google-adk) or use monkeypatched domain clients. Never skipif in smoke tests -- they must always run.
**Warning signs:** `0 tests ran` in the smoke job output.

### Pitfall 2: Smoke job not wired into deploy gate
**What goes wrong:** The smoke-adk job runs but deploy proceeds regardless of its outcome because it is not in the `needs` chain.
**Why it happens:** Forgetting to add `smoke-adk` to the `needs` list of `build-backend` and `ci-status` jobs.
**How to avoid:** Explicitly add `smoke-adk` to the dependency chain. The `ci-status` job already checks all upstream results; adding the new job there gates the final status check.
**Warning signs:** Smoke-adk job is yellow/red but the overall CI badge is green.

### Pitfall 3: Flaky smoke tests from shared state
**What goes wrong:** In-memory session store or Prometheus registry state from other tests leaks into smoke tests.
**Why it happens:** The `adk_runtime_store` fixture clears `_MEMORY_SESSIONS` and `_MEMORY_INVOCATIONS` but global Prometheus metrics are cumulative.
**How to avoid:** Smoke tests should assert on response structure and status, not on exact metric counter values. Use the existing `adk_runtime_store` fixture for session isolation.
**Warning signs:** Tests pass individually but fail in suite.

### Pitfall 4: Not requiring all four oncology tools in smoke
**What goes wrong:** Only sentiment tool is smoke-tested; a regression in humanize/variation/empathy reaches production undetected.
**Why it happens:** Sentiment is the most commonly tested tool in the existing suite; other tools are less prominent.
**How to avoid:** The ADK-13 requirement specifies "trajetorias oncologicas criticas" which covers all four domain tools. Smoke suite must cover: sentiment (patient response analysis), humanize (message humanization), variation (question variation), empathy (empathetic follow-up).
**Warning signs:** Smoke test count is less than 8 (at minimum: 4 tools x success + 4 tools x policy_block).

### Pitfall 5: Forgetting the policy_block trajectory
**What goes wrong:** Smoke only tests happy paths; a regression in policy enforcement (which is the safety boundary from Phase 45) reaches production.
**Why it happens:** Focusing on "does the tool work" rather than "does the safety gate work."
**How to avoid:** Include at least one policy_block scenario per tool to verify the `before_tool_callback` safety mechanism from ADK-11 continues to function.
**Warning signs:** All smoke tests are success-only.

## Code Examples

Verified patterns from the existing codebase:

### Existing Runtime Boundary Test Pattern (from test_adk_tools_runtime.py)
```python
# Source: backend-hormonia/tests/unit/test_adk_tools_runtime.py:59-99
# This pattern monkeypatches the Runner and domain client to exercise
# run_adk_tool() without google-adk or real API calls.
def _install_runner_override_harness(monkeypatch, *, tool_args_factory):
    from app.ai.adk import runtime
    calls = {"runner": 0, "domain": 0}
    # ... fake classes that simulate ADK runtime behavior
```

### Existing API Endpoint Test Pattern (from test_adk.py)
```python
# Source: backend-hormonia/tests/api/v2/test_adk.py:24-52
# This pattern monkeypatches PIISafeADKWrapper.safe_run and exercises
# the /api/v2/adk/run endpoint through FastAPI TestClient.
def test_adk_run_accepts_payload_and_returns_normalized_response(
    client: TestClient, monkeypatch
):
    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        return {"status": "success", "result": {"text": f"processed:{prompt}"}}
    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run, raising=False,
    )
    response = client.post("/api/v2/adk/run", json={...})
    assert response.status_code == 200
```

### Existing Marker Registration Pattern (from pyproject.toml)
```toml
# Source: backend-hormonia/pyproject.toml:40-61
markers = [
    "api: API integration tests",
    "unit: Unit tests",
    "slow: Slow running tests",
    # ... more markers
]
```

### Existing CI Job Dependency Pattern (from ci.yml)
```yaml
# Source: .github/workflows/ci.yml:331-335
# build-backend depends on test-backend and security-scan
build-backend:
  name: Build Backend (Docker)
  needs: [test-backend, security-scan]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ADK tests embedded in monolithic test suite | No change yet (still monolithic) | Phase 47 will change this | Smoke tests will become an independently gatable CI job |
| Deploy depends only on `test-backend` | Phase 47 adds `smoke-adk` as additional gate | Phase 47 | Deploy blocks on ADK-specific regressions with per-scenario visibility |
| google-adk runner tests are skipped in CI | Remains skipped; smoke uses direct-handler path | Phase 45 established pattern | Smoke tests run regardless of google-adk availability |

**Deprecated/outdated:**
- None. All existing CI patterns are current and stable.

## Open Questions

1. **Should smoke tests also exercise the API endpoint layer (`/api/v2/adk/run`) or just `run_adk_tool()`?**
   - What we know: Both layers are already tested. `run_adk_tool()` is the runtime boundary where all status normalization happens. The API layer adds FastAPI validation and the PIISafeADKWrapper envelope.
   - What's unclear: Whether ADK-13 "trajetorias" implies end-to-end API-level or runtime-boundary-level.
   - Recommendation: Test at `run_adk_tool()` level for speed and isolation. The API layer is already well-covered in `test_adk.py`. If both are needed, include a single API-level sentinel test.

2. **Should the `smoke-adk` job require Redis/Postgres services?**
   - What we know: The existing `adk_runtime_store` fixture uses `ADKSessionStore(redis_client=None)` which falls back to in-memory. Smoke tests don't need database.
   - What's unclear: Whether the test runner's conftest auto-creates database fixtures that could fail without services.
   - Recommendation: Run smoke tests with `pytest -m adk_smoke` in isolation (no service containers). If conftest imports cause failures, use `--override-ini="norecursedirs=integration"` or ensure the smoke directory's conftest does not inherit database fixtures.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 with pytest-asyncio (auto mode) |
| Config file | `backend-hormonia/pyproject.toml` |
| Quick run command | `cd backend-hormonia && pytest -m adk_smoke -x -q` |
| Full suite command | `cd backend-hormonia && pytest -m adk_smoke -v --tb=short --junitxml=adk-smoke-report.xml` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADK-13a | Smoke tests run and produce per-scenario pass/fail | smoke | `pytest -m adk_smoke -v` | No - Wave 0 |
| ADK-13b | CI job `smoke-adk` blocks deploy on failure | CI integration | Manual: verify `needs` chain in `ci.yml` | No - Wave 0 |
| ADK-13c | CI passes without bypass when all scenarios green | CI integration | Manual: trigger CI run after implementation | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend-hormonia && pytest -m adk_smoke -x -q`
- **Per wave merge:** `cd backend-hormonia && pytest tests/ -x -q --maxfail=3`
- **Phase gate:** Full ADK suite green + smoke job green in CI

### Wave 0 Gaps
- [ ] `tests/smoke/__init__.py` -- empty init for test discovery
- [ ] `tests/smoke/test_adk_smoke.py` -- smoke test module with `@pytest.mark.adk_smoke`
- [ ] `pyproject.toml` marker registration -- add `adk_smoke` marker
- [ ] `.github/workflows/ci.yml` -- add `smoke-adk` job and wire into dependency chain

## Sources

### Primary (HIGH confidence)
- `.github/workflows/ci.yml` -- current CI pipeline structure, job dependencies, test-backend configuration
- `.github/workflows/cd-staging.yml` -- staging deploy pipeline with smoke test patterns
- `.github/workflows/cd-production.yml` -- production deploy pipeline and pre-deployment checks
- `backend-hormonia/pyproject.toml` -- pytest configuration, markers, asyncio_mode
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py` -- runtime boundary test patterns, fixture patterns
- `backend-hormonia/tests/api/v2/test_adk.py` -- API endpoint test patterns
- `backend-hormonia/tests/unit/test_adk_runner_integration.py` -- HAS_ADK guard pattern
- `backend-hormonia/app/ai/adk/runtime.py` -- run_adk_tool entry point, HAS_ADK_RUNTIME fallback
- `backend-hormonia/app/ai/adk/tools.py` -- tool registry, four domain tools

### Secondary (MEDIUM confidence)
- `.planning/phases/45-adk-tool-safety-and-deterministic-errors/45-VERIFICATION.md` -- Phase 45 deferral of CI smoke to Phase 47
- `.planning/ROADMAP.md` -- Phase 47 success criteria and dependency chain
- `.planning/STATE.md` -- accumulated decisions about ADK testing patterns

### Tertiary (LOW confidence)
- None. All findings are from primary codebase sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools already in project, no new dependencies
- Architecture: HIGH -- patterns directly derived from existing test and CI files
- Pitfalls: HIGH -- derived from observed codebase patterns and known ADK conditional-import behavior

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain; CI patterns and pytest are mature)
