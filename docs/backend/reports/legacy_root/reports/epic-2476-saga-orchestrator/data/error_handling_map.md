# Error Handling Map

## execute_patient_onboarding_saga
- Catches all `Exception`.
- Logs error with `exc_info=True`.
- Calls `db.rollback()`.
- Attempts to create failure saga record and commit.
- Triggers compensation in a nested try; logs if compensation fails.
- Returns `None` on failure (no exception propagation).

## resume_saga
- Catches `LockAcquisitionError` and returns `ResumeResult` with error message.

## _resume_saga_internal
- Catches all `Exception`.
- Logs error, rolls back, stores `error_message`, commits.
- Returns `ResumeResult` with status `failed`.

## API surface
- Coordinator wraps saga failure into `ValidationError` (mapped to HTTP error by API handlers).
