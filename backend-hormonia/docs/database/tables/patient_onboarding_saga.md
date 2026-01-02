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
