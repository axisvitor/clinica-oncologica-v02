# Deferred Items

- Out-of-scope pre-existing pause read still in `backend-hormonia/app/services/flow_monitoring.py:695` (`PatientFlowState.step_data["paused"]`). Not touched by Plan 14-01 scope.
- Out-of-scope pre-existing test environment/schema issue: `python3 -m pytest tests/ -x --ignore=tests/integration -q` fails in `tests/api/critical/test_patient_security_fixes.py::test_idempotency_rbac_denies_other_doctor` due to missing DB column `patients.messaging_stopped_at`.
