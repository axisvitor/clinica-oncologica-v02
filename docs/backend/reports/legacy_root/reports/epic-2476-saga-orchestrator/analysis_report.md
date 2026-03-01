# Saga Orchestrator Deep Review - Analysis Report

Spec: d1332ecb-75e9-44fa-befe-84f61fd01514
Branch: review/saga-orchestrator-deep-dive

## 1. Transaction Management
- No explicit `async with db.begin()`; transactions are managed via explicit `commit()`/`rollback()` in `SagaOrchestrator`.
- Transaction duration logging added in `backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py`.
- Step duration logging added in `backend-hormonia/app/orchestration/saga_orchestrator/steps.py`.
- External calls inside transaction: see `docs/reports/epic-2476-saga-orchestrator/data/external_calls.json`.
- Isolation level: `app/core/database.py` does not set isolation; `app/thread_safe_database.py` sets READ_COMMITTED.
- Ticket P1 (transaction locks): WhatsApp call replaced with async task scheduling; duration not measured due to test DB constraints.

## 2. Compensation Logic
- Compensation order is reverse (4 -> 3 -> 1).
- Idempotency is enforced via `compensated_steps` guards.
- Retry backoff aligns with spec (1/2/4s).
- Failure tracking TTL aligns with spec (30 days).
- Alert integration exists in `backend-hormonia/app/tasks/saga_retry.py` via `_alert_admin_max_retries_exceeded()` (Sentry, DB alert, email).

## 3. Distributed Locks
- Lock key: `saga:onboarding:{doctor_id}:{phone_hash}`, TTL=60s, timeout=5s.
- Release uses Lua script with ownership check.
- Concurrency tests failed due to missing fixture; see `data/concurrency_report.md`.
- Redis failure handling is fail-fast; test added to document this behavior (see `data/redis_failure.md`).
- Metrics snapshot captured with mocked Redis (see `data/lock_metrics.json`).

## 4. Retry Logic
- Retry scheduling is implemented in `backend-hormonia/app/tasks/saga_retry.py` (`scan_and_retry_failed_sagas` + `retry_patient_onboarding_saga`).
- Exponential backoff is 60s, 120s, 240s (capped at 600s).
- `resume_saga` re-fetches after lock acquisition (TOCTOU fix present).
- No retry tests exist (`-k retry` deselected all tests).

## 5. Error Handling
- Global catch-all in `execute_patient_onboarding_saga` creates failure record and triggers compensation; returns `None` on error.
- Coordinator wraps errors into `ValidationError` for API responses.
- See `data/error_handling_map.md` for details.

## 6. Observability
- 45 logger statements found in saga orchestrator modules.
- No Prometheus metrics for saga execution/compensation.
- Alerting hooks exist for max-retry failures in `backend-hormonia/app/tasks/saga_retry.py`.
- No tracing in saga orchestrator modules.
- See `data/observability_status.md`.

## 7. Tests & Coverage
- Integration tests blocked by fixture issues and environment constraints.
- Coverage run aborted (see `data/coverage_status.md`).
- Test execution summary: `data/tests_status.md`.

## 8. Code Quality
- mypy strict: errors observed (see `data/quality_report.md`).
- ruff: clean.
- radon: one method at complexity C (`_resume_saga_internal`).
- bandit: 0 findings (report in `backend-hormonia/bandit_report.json`).

## 9. Performance
- Instrumentation added; no runtime metrics collected due to test DB constraints.
- SQL echo reverted to production-safe value in `.env`.
- See `data/performance_report.md`.
