# Onboarding Saga Troubleshooting Guide

**Last Updated:** 2026-01-10
**Scope:** Patient onboarding saga (`app/orchestration/saga_orchestrator/`)

---

## Quick Health Checks

1. **Saga status**
   ```sql
   SELECT id, status, current_step, retry_count, error_type, error_message
   FROM patient_onboarding_saga
   WHERE id = '<saga_id>';
   ```

2. **Execution log**
   ```sql
   SELECT execution_log
   FROM patient_onboarding_saga
   WHERE id = '<saga_id>';
   ```

3. **Compensation progress**
   ```sql
   SELECT step_data
   FROM patient_onboarding_saga
   WHERE id = '<saga_id>';
   ```

4. **Welcome message status**
   ```sql
   SELECT id, status, failure_reason, message_metadata
   FROM messages
   WHERE patient_id = '<patient_id>'
     AND message_metadata->>'saga_id' = '<saga_id>';
   ```

---

## Common Failure Scenarios

### 1) Lock acquisition failure

**Symptom:** `LockAcquisitionError` or API returns a conflict/timeout.

**Likely cause:** Another onboarding is running for the same `doctor_id + phone_hash`.

**What to do:**
- Wait for the running saga to finish.
- If this is recurrent, review lock TTL and transaction duration (see ticket `a6b3c463-3534-4232-87bb-37758c3569d4`).

### 2) Saga failed after Step 1 (patient created)

**Symptom:** `status=FAILED`, `current_step=1`.

**What to do:**
- Check for partial flow state.
- Resume saga or trigger retry task (see below).
- If compensation was executed, confirm patient deletion and flow cleanup.

### 3) Saga failed after Step 3 (flow initialized)

**Symptom:** `status=FAILED`, `current_step=3`.

**What to do:**
- Validate `PatientFlowState` exists.
- Ensure compensation removed flow states if saga is `FAILED` and retry_count is maxed.

### 4) Welcome message not sent

**Symptom:** `messages.status = PENDING` or missing message row.

**What to do:**
- Verify the Celery task `send_scheduled_message` executed.
- If missing due to race, the periodic scheduler should pick it up.
- Manually trigger the task if needed:
  ```python
  from app.tasks.messaging import send_scheduled_message
  send_scheduled_message.delay("<message_id>")
  ```

### 5) Compensation failure + patient quarantined

**Symptom:** Alert `SAGA_COMPENSATION_FAILURE`, `patient.metadata.quarantine=true`.

**What to do:**
- Inspect `step_data->'compensated_steps'` to see which steps completed.
- Resolve the underlying issue, then manually complete cleanup.
- Remove quarantine only after verification.

---

## How to Resume a Failed Saga

### Option A: Celery Retry Task (recommended)

```python
from app.tasks.saga_retry import retry_patient_onboarding_saga
retry_patient_onboarding_saga.delay("<saga_id>")
```

### Option B: Direct Resume (admin console / debug)

```python
from uuid import UUID
from app.orchestration.saga_orchestrator import SagaOrchestrator

orchestrator = SagaOrchestrator(db=session)
result = await orchestrator.resume_saga(UUID("<saga_id>"))
```

**Safety checks:**
- Ensure saga is not `COMPENSATING`.
- Ensure patient is not quarantined.

---

## Monitoring Queries

### Failed sagas in last 24 hours

```sql
SELECT id, status, current_step, retry_count, failed_at, error_type
FROM patient_onboarding_saga
WHERE status = 'FAILED'
  AND failed_at > now() - interval '24 hours'
ORDER BY failed_at DESC;
```

### Compensation failures (alerts)

```sql
SELECT id, patient_id, created_at, description
FROM alerts
WHERE alert_type = 'SAGA_COMPENSATION_FAILURE'
ORDER BY created_at DESC;
```

### Message send failures by saga

```sql
SELECT patient_id, status, failure_reason, message_metadata
FROM messages
WHERE message_metadata->>'message_type' = 'welcome'
  AND status IN ('FAILED', 'CANCELLED')
ORDER BY created_at DESC;
```

---

## Escalation Checklist

- Verify `patient_onboarding_saga` status, `execution_log`, and `step_data`.
- Confirm message row exists and status transitions are correct.
- Review alerts and patient quarantine flags.
- Check Redis keys for `saga:compensation_failure:<saga_id>`.
