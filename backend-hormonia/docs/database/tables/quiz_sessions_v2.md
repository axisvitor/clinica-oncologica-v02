# Table: `quiz_sessions_v2`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **template_version_id** | `UUID` | ❌ | - |  | ➡️ [quiz_template_versions_v2]( quiz_template_versions_v2.md ).id |
| **status** | `VARCHAR(50)` | ✅ | `'started'::character varying` |  |  |
| **started_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **session_data** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_quiz_sessions_v2_patient | ❌ | `patient_id` |
| idx_quiz_sessions_v2_template_version | ❌ | `template_version_id` |
