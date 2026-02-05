# Performance Analysis

Instrumentation:
- Added transaction duration logging in `backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py`.
- Added per-step duration logging in `backend-hormonia/app/orchestration/saga_orchestrator/steps.py`.

Execution:
- 100-saga profiling not run (test DB unavailable; integration tests blocked by .env override).

SQL logging:
- `SQLALCHEMY_ECHO=False` reverted to production-safe value in `backend-hormonia/.env`.

Next steps:
- Configure DATABASE_URL for a test database and rerun saga profiling to collect P50/P95/P99.
