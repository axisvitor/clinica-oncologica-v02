# Table: `patient_onboarding_saga`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | - | 🔑 |  |
| **patient_id** | `UUID` | ✅ | - |  | ➡️ [patients]( patients.md ).id |
| **doctor_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **status** | `ENUM(saga_status)` | ❌ | - |  |  |
| **current_step** | `INTEGER` | ❌ | - |  |  |
| **retry_count** | `INTEGER` | ❌ | - |  |  |
| **max_retries** | `INTEGER` | ❌ | - |  |  |
| **patient_data** | `JSONB` | ❌ | - |  |  |
| **execution_log** | `JSONB` | ❌ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **error_type** | `VARCHAR(255)` | ✅ | - |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **started_at** | `TIMESTAMP` | ❌ | - |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **failed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **last_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **step_data** | `JSONB` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_patient_onboarding_saga_doctor_id | ❌ | `doctor_id` |
| idx_patient_onboarding_saga_patient_id | ❌ | `patient_id` |
| idx_patient_onboarding_saga_retry | ❌ | `status, next_retry_at` |
| idx_patient_onboarding_saga_status | ❌ | `status` |
| ix_patient_onboarding_saga_doctor_id | ❌ | `doctor_id` |
| ix_patient_onboarding_saga_patient_id | ❌ | `patient_id` |
| ix_patient_onboarding_saga_status | ❌ | `status` |
