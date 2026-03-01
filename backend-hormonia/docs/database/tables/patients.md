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
| **treatment_phase** | `VARCHAR(100)` | ✅ | - |  |  |
| **diagnosis** | `TEXT` | ✅ | - |  |  |
| **flow_state** | `ENUM(flow_state)` | ❌ | - |  |  |
| **current_day** | `INTEGER` | ❌ | - |  |  |
| **doctor_notes** | `TEXT` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **metadata** | `JSONB` | ✅ | - |  |  |
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
| ix_patients_cpf_hash | ❌ | `cpf_hash` |
| ix_patients_cpf_hash_doctor | ❌ | `cpf_hash, doctor_id` |
| ix_patients_created_at | ❌ | `created_at` |
| ix_patients_deleted_at | ❌ | `deleted_at` |
| ix_patients_diagnosis | ❌ | `diagnosis` |
| ix_patients_doctor_id | ❌ | `doctor_id` |
| ix_patients_email_hash | ❌ | `email_hash` |
| ix_patients_email_hash_doctor | ✅ | `email_hash, doctor_id` |
| ix_patients_id | ❌ | `id` |
| ix_patients_idempotency_key | ✅ | `idempotency_key` |
| ix_patients_phone_hash | ❌ | `phone_hash` |
| ix_patients_phone_hash_doctor | ✅ | `phone_hash, doctor_id` |
| ix_patients_treatment_phase | ❌ | `treatment_phase` |
| ix_patients_treatment_start_date | ❌ | `treatment_start_date` |
| ix_patients_treatment_type | ❌ | `treatment_type` |
| uq_patient_cpf_hash_doctor | ✅ | `cpf_hash, doctor_id` |
