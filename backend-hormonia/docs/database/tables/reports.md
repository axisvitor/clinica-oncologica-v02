# Table: `reports`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **type** | `VARCHAR(15)` | ❌ | - |  |  |
| **title** | `VARCHAR` | ❌ | - |  |  |
| **content** | `JSONB` | ✅ | - |  |  |
| **pdf_data** | `BYTEA` | ✅ | - |  |  |
| **status** | `VARCHAR(10)` | ✅ | - |  |  |
| **generated_at** | `TIMESTAMP` | ✅ | - |  |  |
| **metadata** | `JSONB` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_reports_id | ❌ | `id` |
| ix_reports_patient_id | ❌ | `patient_id` |
