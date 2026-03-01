# Test Execution Status

## Integration
- `tests/integration/test_patient_saga.py -v -s`:
  - Failed at fixture setup: DATABASE_URL did not contain "test" (from .env override).
- `tests/integration/test_saga_compensation.py::TestSagaFullRollback::test_saga_compensation_idempotency -v`:
  - Failed at fixture setup: User model rejects `username` kwarg (test out of sync).
- `tests/integration/test_saga_concurrency.py -v`:
  - All scenarios failed: fixture `saga_orchestrator` not found.

## Orchestration
- `tests/orchestration/test_saga_orchestrator.py -k retry -v`:
  - 4 tests collected, 0 selected (no retry tests).
- `tests/orchestration/test_saga_orchestrator.py -k error -v`:
  - 4 tests collected, 0 selected (no error tests).
