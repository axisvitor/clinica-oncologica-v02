# Table: `patients`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **doctor_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **name** | `VARCHAR(255)` | ❌ | - |  |  |
| **birth_date** | `DATE` | ✅ | - |  |  |
| **treatment_type** | `VARCHAR(100)` | ✅ | - |  |  |
| **treatment_start_date** | `DATE` | ✅ | - |  |  |
| **treatment_phase** | `VARCHAR(50)` | ✅ | - |  |  |
| **diagnosis** | `TEXT` | ✅ | - |  |  |
| **flow_state** | `VARCHAR(10)` | ❌ | `'onboarding'::flow_state` |  |  |
| **current_day** | `INTEGER` | ❌ | `0` |  |  |
| **doctor_notes** | `TEXT` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **deleted_at** | `TIMESTAMP` | ✅ | - |  |  |
| **cpf_encrypted** | `TEXT` | ✅ | - |  |  |
| **cpf_hash** | `VARCHAR(64)` | ✅ | - |  |  |
| **idempotency_key** | `VARCHAR(64)` | ✅ | - |  |  |
| **email_encrypted** | `BYTEA` | ✅ | - |  |  |
| **email_hash** | `VARCHAR(64)` | ✅ | - |  |  |
| **phone_encrypted** | `BYTEA` | ✅ | - |  |  |
| **phone_hash** | `VARCHAR(64)` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_patient_cursor_pagination | ❌ | `created_at, id` |
| idx_patient_metadata_consent_gin | ❌ | `<expr>` |
| idx_patient_metadata_gin | ❌ | `metadata` |
| idx_patient_metadata_preferences_gin | ❌ | `<expr>` |
| idx_patients_active | ❌ | `deleted_at` |
| idx_patients_cpf_hash | ❌ | `cpf_hash` |
| idx_patients_created_at | ❌ | `created_at` |
| idx_patients_deleted | ❌ | `deleted_at` |
| idx_patients_doctor_created | ❌ | `doctor_id, created_at` |
| idx_patients_doctor_id | ❌ | `doctor_id` |
| idx_patients_doctor_id_opt | ❌ | `doctor_id` |
| idx_patients_doctor_status_date | ❌ | `doctor_id, flow_state, created_at, id` |
| idx_patients_email_hash | ❌ | `email_hash` |
| idx_patients_flow_state | ❌ | `flow_state` |
| idx_patients_listing_optimized | ❌ | `doctor_id, deleted_at, created_at` |
| idx_patients_metadata_gin | ❌ | `metadata` |
| idx_patients_name_trgm | ❌ | `name` |
| idx_patients_pagination | ❌ | `created_at, id` |
| idx_patients_phone_hash | ❌ | `phone_hash` |
| idx_patients_status_filtering | ❌ | `doctor_id, flow_state, deleted_at, created_at` |
| idx_patients_treatment_phase | ❌ | `treatment_phase` |
| idx_patients_treatment_start_date | ❌ | `treatment_start_date` |
| idx_patients_treatment_type | ❌ | `treatment_type` |
| ix_patients_cpf_hash | ❌ | `cpf_hash` |
| ix_patients_cpf_hash_doctor | ❌ | `cpf_hash, doctor_id` |
| ix_patients_cursor_pagination | ❌ | `created_at, id` |
| ix_patients_email_hash | ❌ | `email_hash` |
| ix_patients_email_hash_doctor | ✅ | `email_hash, doctor_id` |
| ix_patients_idempotency_key | ✅ | `idempotency_key` |
| ix_patients_phone_hash | ❌ | `phone_hash` |
| ix_patients_phone_hash_doctor | ✅ | `phone_hash, doctor_id` |
| uq_patient_cpf_hash_doctor | ✅ | `cpf_hash, doctor_id` |
