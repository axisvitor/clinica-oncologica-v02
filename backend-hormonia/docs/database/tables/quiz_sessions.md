# Table: `quiz_sessions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **quiz_template_id** | `UUID` | ❌ | - |  | ➡️ [quiz_templates]( quiz_templates.md ).id |
| **status** | `VARCHAR(50)` | ❌ | `'started'::character varying` |  |  |
| **current_question** | `INTEGER` | ✅ | `0` |  |  |
| **total_questions** | `INTEGER` | ✅ | - |  |  |
| **answered_questions** | `INTEGER` | ✅ | `0` |  |  |
| **score** | `NUMERIC(5, 2)` | ✅ | - |  |  |
| **max_score** | `NUMERIC(5, 2)` | ✅ | - |  |  |
| **passed** | `BOOLEAN` | ✅ | - |  |  |
| **started_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **time_spent_seconds** | `INTEGER` | ✅ | - |  |  |
| **session_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **expiration_date** | `TIMESTAMP` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_quiz_session_cursor_pagination | ❌ | `created_at, id` |
| idx_quiz_session_unique_active | ✅ | `patient_id, quiz_template_id` |
| idx_quiz_sessions_completed_at_v2 | ❌ | `completed_at` |
| idx_quiz_sessions_created_at | ❌ | `created_at` |
| idx_quiz_sessions_created_at_v2 | ❌ | `created_at` |
| idx_quiz_sessions_patient_created | ❌ | `patient_id, created_at` |
| idx_quiz_sessions_patient_id | ❌ | `patient_id` |
| idx_quiz_sessions_patient_id_v2 | ❌ | `patient_id` |
| idx_quiz_sessions_patient_started_desc | ❌ | `patient_id, started_at` |
| idx_quiz_sessions_patient_status | ❌ | `patient_id, status` |
| idx_quiz_sessions_patient_status_v2 | ❌ | `patient_id, status` |
| idx_quiz_sessions_patient_template_v2 | ❌ | `patient_id, quiz_template_id, started_at` |
| idx_quiz_sessions_quiz_template_id_v2 | ❌ | `quiz_template_id` |
| idx_quiz_sessions_started_at | ❌ | `started_at` |
| idx_quiz_sessions_status_v2 | ❌ | `status` |
| idx_quiz_sessions_template_status_v2 | ❌ | `quiz_template_id, status` |
