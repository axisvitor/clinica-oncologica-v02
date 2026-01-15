# Findings - Saga Orchestrator Deep Review

## Existing Findings (Validation)

### Finding #1: Transaction Locks Longos (P1)
- Status: Partially mitigated. Step 3 now schedules Celery task instead of direct WhatsApp call.
- Evidence:
  - `backend-hormonia/app/orchestration/saga_orchestrator/steps.py:134` uses async task scheduling.
- Blocker: No runtime duration metrics captured (test DB unavailable).
- Recommendation: Run integration profiling with test DB and confirm P95 < 2s.

### Finding #2: Compensation Silenciosa (P1)
- Status: ✅ RESOLVED - Alert integration exists in `saga_retry.py`.
- Evidence:
  - `backend-hormonia/app/tasks/saga_retry.py:394` - `_alert_admin_max_retries_exceeded()` sends:
    - Sentry alert (capture_message)
    - Database Alert record (Alert model)
    - Admin email (if configured)
  - Line 86: Calls `run_async(_alert_admin_max_retries_exceeded(saga, db))`
- No further action needed.

## New Findings

### Finding #3: Saga Retry Scheduling Not Implemented
- Priority: ✅ RESOLVED
- Status: Full retry scheduling exists in `saga_retry.py`.
- Evidence:
  - `retry_patient_onboarding_saga` task with exponential backoff (lines 36-155)
  - `scan_and_retry_failed_sagas` periodic task (lines 158-236)
  - `_calculate_exponential_backoff` helper (lines 378-391): base_delay * 2^retry_count
  - Backoff: 60s, 120s, 240s (capped at 600s)
- No further action needed.

### Finding #4: Compensation Backoff and TTL Mismatch with Spec
- Priority: ✅ RESOLVED
- Category: Compensation
- Description: Spec expects 1/2/4s backoff and 30-day TTL for failure tracking.
- Fix Applied:
  - `compensation.py:201` - Changed base delay from 0.5s to 1.0s (now 1/2/4s)
  - `compensation.py:398` - Changed TTL from 7 days to 30 days
- No further action needed.


### Finding #5: Missing Saga Observability Metrics
- Priority: P2 - Future
- Category: Observability
- Description: No Prometheus counters/histograms for saga executions, compensations, or durations.
- Impact: Limited operational visibility; hard to detect regressions.
- Evidence:
  - No metrics usage in `backend-hormonia/app/orchestration/saga_orchestrator/`.
- Recommendation: Add Prometheus counters/histograms (executions, compensations, duration, active count).
- Estimate: 4-6h

### Finding #6: Integration Tests Out of Sync with Current Code
- Priority: P2 - Future
- Category: Tests
- Description: Integration tests fail due to outdated fixtures and model changes.
- Impact: Integration coverage blocked; concurrency/idempotency not validated.
- Evidence:
  - `backend-hormonia/tests/integration/test_saga_concurrency.py` uses missing fixture `saga_orchestrator`.
  - `backend-hormonia/tests/integration/test_saga_compensation.py` uses `User(username=...)` which is not a model field.
- Recommendation: Update fixtures and test data to align with current models and orchestrator API.
- Estimate: 6-8h

### Finding #7: No Automated Tests for Saga Retry/Error Handling
- Priority: P2 - Future
- Category: Tests
- Description: No tests selected for `-k retry` or `-k error` in orchestration tests.
- Impact: Retry and error handling paths are unvalidated.
- Evidence:
  - `pytest tests/orchestration/test_saga_orchestrator.py -k retry -v` returns 0 selected.
  - `pytest tests/orchestration/test_saga_orchestrator.py -k error -v` returns 0 selected.
- Recommendation: Add unit tests for retry scheduling and error propagation paths.
- Estimate: 4-6h
