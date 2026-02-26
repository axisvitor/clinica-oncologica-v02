# Deferred Items - Phase 19

## 2026-02-26

- Out-of-scope pre-existing regression in `tests/orchestration/test_saga_orchestrator.py::test_execute_patient_onboarding_saga_success`: fixture uses `MagicMock` DB while `SagaStepExecutor` now awaits async DB methods (`flush`, `execute`), causing `TypeError: object MagicMock can't be used in 'await' expression`.
- Out-of-scope pre-existing regression in `tests/services/test_saga_compensation.py::TestSagaCompensateMessage::test_compensate_message_marks_as_cancelled`: compensation path awaits `self.db.execute(...)` but test fixture injects sync `MagicMock`, causing the same async/sync mismatch.
