# Code Quality Report

## mypy (strict)
Command:
```
python -m mypy app/orchestration/saga_orchestrator/ app/core/distributed_lock.py app/models/patient_onboarding_saga.py --strict --show-error-codes --pretty
```
Result: Interrupted (long run). First errors observed:
- `app/services/analytics/data_extraction/patterns.py`: missing return type annotation (`[no-untyped-def]`).
- `app/utils/key_validation/distribution.py`: missing type parameters for `dict` (`[type-arg]`).

## ruff
Result: All checks passed.

## radon
Result:
- `SagaOrchestrator._resume_saga_internal` complexity C.
- All other scanned functions B or A.
Average complexity: A (2.86).

## bandit
Result: 0 findings (JSON report in `backend-hormonia/bandit_report.json`).
