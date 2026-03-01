# Deferred Items - Phase 29

## 2026-02-28

- Out-of-scope pre-existing failure during full orchestration suite verification:
  - `tests/unit/orchestration/test_saga_orchestrator_split_contract.py::test_orchestrator_under_500_lines`
  - Failure: `app/orchestration/saga_orchestrator/orchestrator.py` is 546 lines, contract asserts `< 500`
  - Reason deferred: not caused by plan 29-02 task changes (`types.py`, `query_helpers.py`, new audit tests)

- Out-of-scope contract failure during plan 29-01 verification:
  - `tests/unit/orchestration/test_saga_orchestrator_split_contract.py::test_orchestrator_under_500_lines`
  - Failure: `app/orchestration/saga_orchestrator/orchestrator.py` is 615 lines, contract asserts `< 500`
  - Reason deferred: this plan is correctness-focused (async DB safety + Pydantic v2 audit), while module size reduction requires architectural refactor beyond 29-01 scope
