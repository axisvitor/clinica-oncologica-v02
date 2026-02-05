# Table: `patient_summaries`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **generated_by** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **start_date** | `DATE` | ❌ | - |  |  |
| **end_date** | `DATE` | ❌ | - |  |  |
| **content** | `JSONB` | ❌ | `'{}'::jsonb` |  |  |
| **pdf_data** | `BYTEA` | ✅ | - |  |  |
| **token_usage** | `INTEGER` | ✅ | - |  |  |
| **model_used** | `VARCHAR(100)` | ✅ | `'gemini-2.5-flash-latest'::character varying` |  |  |
| **generation_time_ms** | `INTEGER` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_patient_summaries_created_at | ❌ | `created_at` |
| idx_patient_summaries_patient_id | ❌ | `patient_id` |
| idx_patient_summaries_patient_period | ❌ | `patient_id, start_date, end_date` |
