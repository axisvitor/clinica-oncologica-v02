# Table: `quiz_templates`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **name** | `VARCHAR(255)` | ❌ | - |  |  |
| **version** | `VARCHAR(50)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **questions** | `JSONB` | ❌ | - |  |  |
| **is_active** | `BOOLEAN` | ❌ | `true` |  |  |
| **category** | `VARCHAR(100)` | ✅ | - |  |  |
| **tags** | `ARRAY` | ✅ | - |  |  |
| **passing_score** | `INTEGER` | ✅ | - |  |  |
| **time_limit_minutes** | `INTEGER` | ✅ | - |  |  |
| **randomize_questions** | `BOOLEAN` | ✅ | `false` |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_quiz_templates_category | ❌ | `category` |
| idx_quiz_templates_is_active | ❌ | `is_active` |
