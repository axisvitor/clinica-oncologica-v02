---
phase: 40-otel-removal-adk-foundation
plan: 01
subsystem: infra
tags: [adk, sentry, tracing, dependencies, python-3.13]
requires:
  - phase: 39-wuzapi-migration
    provides: WuzAPI hard-cut baseline and active backend runtime
provides:
  - ADK compatibility evidence in clean Python 3.13
  - Manual OTel instrumentation removal from backend requirements
  - Tracing tombstone with explicit ImportError migration path
  - FastAPI->Celery Sentry correlation baseline/post verification artifacts
affects: [41-adk-agent-integration, observability, ci]
tech-stack:
  added: [google-adk]
  patterns: [tombstone-module, sentry-correlation-probe, dependency-gate-first]
key-files:
  created:
    - .planning/phases/40-otel-removal-adk-foundation/40-ADK-COMPATIBILITY.md
    - backend-hormonia/scripts/sentry_correlation_probe.py
    - .planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-BASELINE.json
    - .planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-POST.json
    - .planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-VERIFICATION.md
  modified:
    - backend-hormonia/requirements.txt
    - backend-hormonia/app/integrations/whatsapp/services/message_service.py
    - backend-hormonia/app/services/unified_whatsapp_service.py
    - backend-hormonia/app/core/tracing.py
    - backend-hormonia/app/core/setup/sentry.py
key-decisions:
  - "Used python:3.13-slim container for the dependency gate because host python3.13 was unavailable."
  - "Kept protobuf pin and updated rationale to retained Google/ADK dependency compatibility."
  - "Added CeleryIntegration explicitly in setup_sentry() to preserve worker transaction correlation after tracing cleanup."
patterns-established:
  - "Dependency gate first: prove installability before editing runtime requirements"
  - "Correlation probe artifacts: baseline and post JSON plus explicit PASS/FAIL verification document"
requirements-completed: [ADK-01, ADK-02, ADK-03]
duration: 12 min
completed: 2026-03-03
---

# Phase 40 Plan 01: OTel Removal and ADK Foundation Summary

**Validated google-adk compatibility on Python 3.13, removed manual OpenTelemetry instrumentation, and preserved FastAPI-to-Celery Sentry correlation with explicit post-change evidence.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-03T19:43:49Z
- **Completed:** 2026-03-03T19:56:34Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Proved `google-adk` and `pydantic-ai-slim[google,retries]` co-install cleanly with `pip check` in isolated Python 3.13.
- Removed all 9 `opentelemetry-` requirements entries, added bounded `google-adk` dependency, and retained protobuf compatibility guardrails.
- Cleared both locked tracing callers, tombstoned `app/core/tracing.py`, and wired `CeleryIntegration(monitor_beat_tasks=True)` in Sentry setup.
- Added deterministic Sentry correlation probe and baseline/post artifacts showing `trace_linked=true` with non-regressed depth.

## Task Commits

Each task was committed atomically:

1. **Task 1: Run dependency gate in clean Python 3.13 venv and record evidence** - `7d1da7b9` (feat)
2. **Task 2: Remove OTel instrumentation, tombstone tracing, and wire CeleryIntegration** - `4675170a` (feat)

## Files Created/Modified
- `.planning/phases/40-otel-removal-adk-foundation/40-ADK-COMPATIBILITY.md` - Python 3.13 dry-run/install/pip-check evidence.
- `backend-hormonia/scripts/sentry_correlation_probe.py` - deterministic correlation probe with in-memory Sentry transport.
- `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-BASELINE.json` - baseline correlation metrics.
- `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-POST.json` - post-removal correlation metrics.
- `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-VERIFICATION.md` - baseline vs post verdict.
- `backend-hormonia/requirements.txt` - OTel instrumentation removal + ADK addition.
- `backend-hormonia/app/integrations/whatsapp/services/message_service.py` - tracing import/decorator removal.
- `backend-hormonia/app/services/unified_whatsapp_service.py` - tracing import/state removal.
- `backend-hormonia/app/core/tracing.py` - tombstone ImportError module.
- `backend-hormonia/app/core/setup/sentry.py` - CeleryIntegration inclusion.

## Decisions Made
- Ran the compatibility gate in a Python 3.13 Docker container (`python:3.13-slim`) as a Rule 3 blocking-issue fix for missing local `python3.13`.
- Updated protobuf comment rationale to retained Google/ADK dependencies after OTel instrumentation removal.
- Used a required-env override (`WHATSAPP_WUZAPI_TOKEN=dummy`) for import-time verification of Sentry setup in this non-production execution context.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python 3.13 runtime unavailable on host**
- **Found during:** Task 1
- **Issue:** `python3.13` command was not installed locally.
- **Fix:** Executed the dependency gate inside `python:3.13-slim` container with isolated venv.
- **Files modified:** `.planning/phases/40-otel-removal-adk-foundation/40-ADK-COMPATIBILITY.md`
- **Verification:** Successful install and `No broken requirements found.` in container output.
- **Committed in:** `7d1da7b9`

**2. [Rule 3 - Blocking] Sentry probe transport integration error**
- **Found during:** Task 2
- **Issue:** Initial in-memory transport shape caused Sentry SDK runtime errors during probe execution.
- **Fix:** Replaced probe transport with a `Transport` subclass that captures envelope transaction events.
- **Files modified:** `backend-hormonia/scripts/sentry_correlation_probe.py`
- **Verification:** Probe emits JSON metrics with `captured_event_count: 1` and verification command passes.
- **Committed in:** `4675170a`

**3. [Rule 3 - Blocking] settings import required WHATSAPP_WUZAPI_TOKEN during verification**
- **Found during:** Task 2
- **Issue:** `app.config.settings` validation blocked `setup_sentry` import test in local execution.
- **Fix:** Re-ran verification with scoped env override `WHATSAPP_WUZAPI_TOKEN=dummy`.
- **Files modified:** None (verification-only adaptation)
- **Verification:** `from app.core.setup.sentry import setup_sentry` succeeds under scoped env.
- **Committed in:** `4675170a`

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All deviations were execution blockers; no scope creep and all required outputs were produced.

## Issues Encountered
- Local runtime import checks for `setup_sentry` require strict settings env validation. This was handled with a scoped command-level env override only for verification.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ADK foundation gate is complete with reproducible evidence and tracing cleanup locked.
- Ready for `40-02-PLAN.md` (PIISafeADKWrapper scaffold and synthetic PHI behavior tests).

---
*Phase: 40-otel-removal-adk-foundation*
*Completed: 2026-03-03*

## Self-Check: PASSED

- Verified summary and key artifact files exist on disk.
- Verified task commit hashes `7d1da7b9` and `4675170a` exist in git history.
