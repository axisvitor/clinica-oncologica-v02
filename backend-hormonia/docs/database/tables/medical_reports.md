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
| **insights** | `JSONB` | ✅ | - |  |  |
| **charts_data** | `JSONB` | ✅ | - |  |  |
| **alerts** | `JSONB` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_medical_reports_generated_by | ❌ | `generated_by` |
| ix_medical_reports_id | ❌ | `id` |
| ix_medical_reports_patient_id | ❌ | `patient_id` |
