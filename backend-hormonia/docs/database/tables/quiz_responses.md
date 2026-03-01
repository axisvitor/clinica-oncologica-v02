# Table: `quiz_responses`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **quiz_template_id** | `UUID` | ❌ | - |  | ➡️ [quiz_templates]( quiz_templates.md ).id |
| **quiz_session_id** | `UUID` | ✅ | - |  | ➡️ [quiz_sessions]( quiz_sessions.md ).id |
| **question_id** | `VARCHAR(100)` | ❌ | - |  |  |
| **question_text** | `TEXT` | ❌ | - |  |  |
| **response_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **response_value_text_backup** | `TEXT` | ❌ | - |  |  |
| **response_metadata** | `JSONB` | ✅ | - |  |  |
| **responded_at** | `TIMESTAMP` | ❌ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **other_text** | `TEXT` | ✅ | - |  |  |
| **response_value** | `JSONB` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_quiz_response_analytics_covering_index | ❌ | `quiz_template_id, question_id, response_value, responded_at` |
| idx_quiz_response_patient_template_index | ❌ | `patient_id, quiz_template_id, responded_at` |
| idx_quiz_response_session_id | ❌ | `quiz_session_id` |
| idx_quiz_responses_patient_id | ❌ | `patient_id` |
| idx_quiz_responses_quiz_template_id | ❌ | `quiz_template_id` |
| idx_quiz_responses_responded_at | ❌ | `responded_at` |
| uq_quiz_response_per_question_session | ✅ | `quiz_session_id, question_id` |
