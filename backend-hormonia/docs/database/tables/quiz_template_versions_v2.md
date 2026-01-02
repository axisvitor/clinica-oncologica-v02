# Table: `quiz_template_versions_v2`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **template_id** | `UUID` | ❌ | - |  | ➡️ [quiz_templates]( quiz_templates.md ).id |
| **version_number** | `INTEGER` | ❌ | - |  |  |
| **questions** | `JSONB` | ❌ | - |  |  |
| **scoring_rules** | `JSONB` | ✅ | - |  |  |
| **is_active** | `BOOLEAN` | ✅ | `false` |  |  |
| **is_draft** | `BOOLEAN` | ✅ | `true` |  |  |
| **published_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_by** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **change_notes** | `TEXT` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_quiz_template_versions_v2_active | ❌ | `template_id, is_active` |
| idx_quiz_template_versions_v2_template | ❌ | `template_id` |
| unique_template_version | ✅ | `template_id, version_number` |
