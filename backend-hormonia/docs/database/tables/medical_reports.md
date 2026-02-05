# Table: `medical_reports`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **generated_by** | `UUID` | ❌ | - |  | ➡️ [users]( users.md ).id |
| **period_start** | `DATE` | ❌ | - |  |  |
| **period_end** | `DATE` | ❌ | - |  |  |
| **summary** | `TEXT` | ✅ | - |  |  |
| **insights** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **charts_data** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **alerts** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **report_type** | `VARCHAR(50)` | ✅ | - |  |  |
| **report_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_medical_reports_generated_by | ❌ | `generated_by` |
| idx_medical_reports_patient_id | ❌ | `patient_id` |
| idx_medical_reports_patient_period | ❌ | `patient_id, period_start, period_end` |
| idx_medical_reports_period | ❌ | `period_start, period_end` |
