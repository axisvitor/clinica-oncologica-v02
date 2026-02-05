# Onboarding Process - Deep Review Report

**Epic:** 2476b16c-c6a7-4898-b766-97a1afddde2d
**Spec:** Revisao Profunda - Componente 5: Onboarding Process
**Date:** 2026-01-10
**Reviewer:** Codex

---

## Executive Summary

The onboarding saga is **production-ready** with strong orchestration, compensation, and logging. The current implementation is a **3-step saga** (Create Patient -> Initialize Flow -> Schedule Welcome Message), while the spec still references 4 steps (Step 2 deprecated Firebase integration). Key gaps are **lock TTL risk**, **idempotency key propagation**, **missing circuit breaker at the messaging boundary**, **test gaps around compensation**, and **missing metrics**.

**Component Status:** APPROVED WITH RESERVATIONS

---

## Phase 1 - Saga Logic Validation

### 1.1 Step Validation (3-step implementation)

**Step 1: Create Patient** (`app/orchestration/saga_orchestrator/steps.py`)
- Validates payload through `PatientCreate` schema (v2 -> v1 conversion happens upstream).
- Uses `PatientRepository.create(..., auto_commit=False)` for idempotent creation.
- Supports `idempotency_key` on patient creation.
- Records saga progress (`current_step=1`, `SagaStatus.STEP_1_PATIENT_CREATED`).

**Step 2 (Deprecated):** Firebase user creation was removed; numbering skips from 1 -> 3.

**Step 3: Initialize Flow** (`step_initialize_flow`)
- Calls `PatientFlowService.initialize_default_flow()` and `activate_patient()`.
- Records `current_step=3`, status `STEP_3_FLOW_INITIALIZED`.

**Step 4: Send Welcome Message (Async)** (`step_send_welcome_message`)
- Resolves template from `MessageTemplate` or falls back to `DEFAULT_WELCOME_MESSAGE`.
- Schedules message through `MessageService.schedule_message()` and Celery task.
- Non-fatal: saga completes even if scheduling fails.
- Records `current_step=4`, status `STEP_4_MESSAGE_SENT`.

**Step numbering discrepancy:** implementation uses 1, 3, 4; spec still expects 1-4.

### 1.2 Compensation Validation

**Compensator** (`app/orchestration/saga_orchestrator/compensation.py`)
- `_compensate_message`: marks messages as `CANCELLED` with audit metadata.
- `_compensate_flow`: hard deletes `PatientFlowState` rows.
- `_compensate_patient`: hard deletes patient (LGPD-safe for incomplete onboarding).
- `_compensate_step_with_retry`: exponential backoff (1s, 2s, 4s), max 3 retries.
- Idempotency: `step_data.compensated_steps` prevents repeated compensation.
- `_track_compensation_failure`: Redis tracking + alert creation + patient quarantine.

### 1.3 Idempotency & Duplicate Prevention

- Distributed lock uses normalized phone hash + doctor_id, TTL=60s, timeout=5s.
- `step_create_patient` uses repository-level duplicate checks.
- Resume logic includes checks for existing flow and welcome message before re-running steps.
- **Gap:** idempotency key only used for patient creation, not for flow/message steps.

---

## Phase 2 - Error Handling & Performance

### Error Handling

- Validation errors handled in `OnboardingCoordinator` and raised as `ValidationError`.
- Saga failures rollback, record a failed saga, then trigger compensation.
- Welcome message sending is best-effort; failures do not fail the saga.

### Performance & Timeouts

- `execute_patient_onboarding_saga` measures and logs transaction duration.
- Celery async message send reduces transaction time (<2s target).
- Lock TTL: 60s (risk if transaction exceeds TTL in extreme scenarios).

---

## Phase 3 - Tests & Coverage

### Tests Executed

- `pytest tests/services/patient/test_onboarding_saga_integration.py -v`
  - OK 3 passed
- `pytest tests/services/patient/test_onboarding_happy_path.py -v`
  - OK 2 passed
- `pytest tests/services/patient/test_onboarding_validation_errors.py -v`
  - OK 3 passed

### Coverage Attempt

- `pytest tests/services/patient/ -v --cov=app.orchestration.saga_orchestrator --cov=app.services.patient.onboarding_factory --cov-report=html`
- FAILED: Aborted: `passlib` builtin bcrypt backend initialization hangs during app config import.
- **Action:** Run coverage in a dedicated test config that avoids full security init or injects a lighter bcrypt backend for tests.

### Known Coverage Gaps

- Compensation scenarios (step-by-step, failure/retry paths)
- Concurrent saga execution / lock contention tests
- Resume saga idempotency edge cases
- Lock acquisition failure scenarios

---

## Phase 4 - Observability

### Logging

- Structured logs include `saga_id`, `step`, `status`, and durations.
- Compensation logs include per-step results and errors.

### Alerts

- Compensation failures generate alert records and quarantine patients.
- Sentry notifications emitted for compensation failures.

### Metrics Gaps

- No Prometheus counters/histograms for saga duration, failure rate, lock acquisition time.
- Recommendation: add metrics in orchestrator and compensator.

---

## Findings Summary

**Total:** 8 findings (0 P0, 3 P1, 3 P2, 2 P3)

- P1: Lock TTL vs transaction duration (ticket exists).
- P1: Missing circuit breaker at messaging boundary.
- P1: Idempotency key not propagated to flow/message steps.
- P2: Compensation tests missing.
- P2: Missing saga metrics.
- P2: Resume-step idempotency edge cases.
- P3: Deprecated enum value for Firebase step.
- P3: Step numbering mismatch in spec/docs.

---

## Artifacts

- Profiling output: `backend-hormonia/docs/reports/performance/onboarding.prof` (captured during debug script run; execution aborted due to invalid test phone).
- Debug script: `scripts/debug/debug_full_onboarding.py` fails due to invalid test phone format (`uuid4().hex` includes letters).

---

## Recommendations

1. Extend or refresh lock TTL during saga execution (P1).
2. Add messaging circuit breaker at task boundary (P1).
3. Persist idempotency key on saga and apply to flow/message steps (P1).
4. Add compensation unit tests and resume edge-case tests (P2).
5. Add Prometheus metrics for saga duration, failures by step, and lock acquisition time (P2).
6. Update documentation to reflect 3-step process and deprecated Step 2 (P3).
