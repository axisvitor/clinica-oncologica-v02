# Table: `patient_onboarding_saga`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ✅ | - |  | ➡️ [patients]( patients.md ).id |
| **doctor_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **status** | `VARCHAR(28)` | ❌ | `'STARTED'::saga_status` |  |  |
| **current_step** | `INTEGER` | ❌ | `0` |  |  |
| **retry_count** | `INTEGER` | ❌ | `0` |  |  |
| **max_retries** | `INTEGER` | ❌ | `3` |  |  |
| **patient_data** | `JSONB` | ❌ | - |  |  |
| **execution_log** | `JSONB` | ❌ | `'[]'::jsonb` |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **error_type** | `VARCHAR(255)` | ✅ | - |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **started_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **failed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **last_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **step_data** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_patient_onboarding_saga_doctor_id | ❌ | `doctor_id` |
| idx_patient_onboarding_saga_last_retry | ❌ | `last_retry_at` |
| idx_patient_onboarding_saga_patient_id | ❌ | `patient_id` |
| idx_patient_onboarding_saga_retry | ❌ | `status, next_retry_at` |
| idx_patient_onboarding_saga_status | ❌ | `status` |
| idx_patient_onboarding_saga_execution_log_gin | ❌ | `execution_log` (GIN) |
| idx_patient_onboarding_saga_step_data_gin | ❌ | `step_data` (GIN) |
| idx_patient_onboarding_saga_patient_data_gin | ❌ | `patient_data` (GIN) |

## JSONB Structures

### `patient_data`

Stores the inbound `PatientCreate` payload (v2 -> v1 normalized) used by the saga.

Example:
```json
{
  "name": "Joao Silva",
  "phone": "+5511999887766",
  "email": "joao.silva@example.com",
  "birth_date": "1980-05-15",
  "cpf": null,
  "treatment_type": "quimioterapia",
  "treatment_phase": "initial",
  "diagnosis": "Cancer de mama",
  "metadata": {
    "source": "api_v2",
    "campaign": "onboarding"
  }
}
```

### `execution_log`

Append-only list of step execution events.

Example:
```json
[
  {
    "step": 1,
    "action": "create_patient",
    "status": "success",
    "timestamp": "2026-01-10T01:12:30.000Z"
  },
  {
    "step": 3,
    "action": "initialize_flow",
    "status": "success",
    "timestamp": "2026-01-10T01:12:31.100Z"
  },
  {
    "step": 4,
    "action": "send_message",
    "status": "scheduled_async",
    "timestamp": "2026-01-10T01:12:31.400Z"
  }
]
```

### `step_data`

Tracks compensation idempotency and per-step metadata.

Example:
```json
{
  "compensated_steps": ["message", "flow", "patient"],
  "idempotency_key": "qw-004-uuid"
}
```

## Notes

- `status` values are defined in `app/models/enums.py` (`SagaStatus`).
- `current_step` uses saga step numbering (1=patient created, 3=flow initialized, 4=welcome scheduled); step 2 is deprecated.
- `step_data.idempotency_key` is populated when the onboarding request includes an idempotency key.
