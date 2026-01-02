# Table: `quiz_questions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **quiz_template_id** | `UUID` | ❌ | - |  | ➡️ [quiz_templates]( quiz_templates.md ).id |
| **question_text** | `VARCHAR` | ❌ | - |  |  |
| **question_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **question_order** | `INTEGER` | ❌ | - |  |  |
| **options** | `JSONB` | ✅ | - |  |  |
| **correct_answer** | `VARCHAR` | ✅ | - |  |  |
| **points** | `INTEGER` | ✅ | - |  |  |
| **is_required** | `BOOLEAN` | ✅ | - |  |  |
| **metadata** | `JSONB` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_quiz_questions_id | ❌ | `id` |
| ix_quiz_questions_quiz_template_id | ❌ | `quiz_template_id` |
